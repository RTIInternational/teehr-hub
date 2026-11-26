"""Ingest NWM operational streamflow at the gages' reaches into v1 timeseries datasets.

One dataset per configuration (legacy's names: ``nwm31_short_range``, ``nwm31_medium_range``
for ``medium_range_mem1``, ...), all sharing the version's series table, so one crosswalk
(``usgs_nwm31``) pairs the gages with each. :mod:`teehr_core.fetch.nwm` lists and reads the
files from NOAA's GCS bucket; :func:`flows.write.write_rows` writes them.

As the legacy ingest did: the reaches are the crosswalk's, for the gages in the
configuration's domain (their ``state_name``); each run reads whole UTC days, from
``lookback_days`` before now, and upserts, so cycles read again are rewritten, not repeated;
analysis keeps the latest cycle's value for each time, with no ``reference_time``.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from prefect import flow, get_run_logger, task
from pyiceberg.catalog import Catalog
from teehr_core.fetch import nwm
from teehr_core.warehouse import location_keys

from flows.catalog import catalog
from flows.write import write_rows

#: Gages outside the CONUS domain (legacy's list), by their layer's ``state_name``.
OCONUS = ("Alaska", "Hawaii", "Puerto Rico", "Guam", "American Samoa",
          "Northern Mariana Islands", "Virgin Islands")  # fmt: skip
#: The state an OCONUS configuration's name says it's for.
DOMAINS = {"alaska": "Alaska", "hawaii": "Hawaii", "puertorico": "Puerto Rico"}


def dataset_name(configuration: str, version: str = "nwm31") -> str:
    """Legacy's configuration name: ``medium_range_alaska_mem1`` -> ``nwm31_medium_range_alaska``."""
    return f"{version}_{re.sub(r'_mem[0-9]+', '', configuration)}"


def domain_filter(configuration: str) -> str:
    """The gages in the configuration's domain, as a row filter on their ``state_name``."""
    for word, state in DOMAINS.items():
        if word in configuration:
            return f"state_name == '{state}'"
    oconus = ", ".join(f"'{s}'" for s in OCONUS)
    return f"state_name is not null and state_name not in ({oconus})"


def reaches(cat: Catalog, namespace: str, crosswalk: str, observed: str, where: str,
            version: str) -> list[str]:  # fmt: skip
    """The crosswalk's ``version`` reaches for ``observed``'s gages that match ``where``."""
    gages = pa.array(location_keys(cat, namespace, observed, where), pa.string())
    links = cat.load_table((namespace, crosswalk)).scan(
        selected_fields=("left_key", "right_key")
    ).to_arrow()  # fmt: skip
    links = links.filter(pc.is_in(links["left_key"], gages))
    keys = [k for k in links["right_key"].to_pylist() if k.startswith(f"{version}-")]
    return sorted(set(keys))


@task(retries=2, retry_delay_seconds=60, persist_result=False,
      task_run_name="read files {first}-{last} of {total}")  # fmt: skip
def read(files: list[nwm.File], keys: list[str], version: str, workers: int,
         first: int, last: int, total: int) -> pa.Table | None:  # fmt: skip
    """One batch of files' rows at the reaches; retried, so a blip doesn't fail the run."""
    tables = list(nwm.read_points(files, keys, version=version, workers=workers,
                                  batch_files=len(files)))  # fmt: skip
    return pa.concat_tables(tables) if tables else None


@flow(name="ingest-nwm-streamflow", log_prints=True)
def ingest_nwm_streamflow(
    configuration: str = "short_range",
    dataset: str | None = None,
    namespace: str = "public",
    version: str = "nwm31",
    crosswalk: str = "usgs_nwm31",
    observed: str = "usgs_streamflow",
    where: str | None = None,
    lookback_days: int = 1,
    start: datetime | None = None,
    end: datetime | None = None,
    batch_files: int = 100,
    workers: int = 16,
    commit_rows: int = 2_000_000,
) -> dict[str, Any]:
    """Read the configuration's cycles from ``start`` up to ``end`` at the reaches and write them.

    The reaches are ``crosswalk``'s right keys for ``observed``'s gages. New series rows get
    no ``location_key`` (``write_rows`` without ``location_of``): reaches have no location
    layer of their own, and evaluations reach the gages through the crosswalk.

    Parameters
    ----------
    configuration : str, default "short_range"
        Its directory on GCS, one of :data:`teehr_core.fetch.nwm.CONFIGURATIONS`.
    dataset : str, optional
        Defaults to legacy's name for the configuration (:func:`dataset_name`).
    namespace : str, default "public"
    version : str, default "nwm31"
        The reaches' key prefix, and the NWM version the files are read as.
    crosswalk : str, default "usgs_nwm31"
        Pairs ``observed``'s gages (left) with the reaches (right).
    observed : str, default "usgs_streamflow"
        The dataset whose location layer holds the gages.
    where : str, optional
        A row filter on the gages' layer; defaults to the configuration's domain
        (:func:`domain_filter`).
    lookback_days : int, default 1
        Without ``start``, read from midnight UTC this many days before ``end``.
    start, end : datetime, optional
        The window of reference times; ``end`` defaults to now.
    batch_files : int, default 100
        Files read per batch (one retried task each).
    workers : int, default 16
        Files read at once.
    commit_rows : int, default 2_000_000
        The fewest rows in each commit.

    Returns
    -------
    dict
        The configuration, dataset, reaches and files counts and window, and
        :func:`flows.write.write_rows`' summary.

    Examples
    --------
    The scheduled run: yesterday and today's cycles, at the CONUS gages' reaches.

    >>> ingest_nwm_streamflow("short_range")

    A member's medium range, into legacy's ``nwm31_medium_range``, for one week.

    >>> ingest_nwm_streamflow("medium_range_mem1", start=datetime(2026, 11, 1, tzinfo=UTC),
    ...                       end=datetime(2026, 11, 8, tzinfo=UTC))

    On KinD, whose gages have no ``state_name``: every gage.

    >>> ingest_nwm_streamflow("short_range", where="True", workers=4)
    """
    log = get_run_logger()
    if configuration not in nwm.CONFIGURATIONS:
        raise ValueError(f"unknown configuration {configuration!r}: one of {nwm.CONFIGURATIONS}")
    dataset = dataset or dataset_name(configuration, version)
    cat = catalog()
    where = where or domain_filter(configuration)
    keys = reaches(cat, namespace, crosswalk, observed, where, version)
    end = end or datetime.now(UTC)
    start = start or (end - timedelta(days=lookback_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )  # fmt: skip
    found = nwm.files(configuration, start, end)
    log.info("NWM %s: %d reaches (gages: %s), %d files (cycles %s to %s) into %s.%s", configuration,
             len(keys), where, len(found), start, end, namespace, dataset)  # fmt: skip
    if not keys:
        raise ValueError(f"no {version} reaches in {namespace}.{crosswalk} for the domain's gages")

    batches = (
        read(found[i : i + batch_files], keys, version, workers,
             i + 1, min(i + batch_files, len(found)), len(found))
        for i in range(0, len(found), batch_files)
    )  # fmt: skip
    written = write_rows(cat, namespace, dataset, (b for b in batches if b is not None),
                         unit=nwm.UNIT, commit_rows=commit_rows)  # fmt: skip
    return {"configuration": configuration, "dataset": dataset, "reaches": len(keys),
            "files": len(found), "start": start.isoformat(), "end": end.isoformat(),
            **written}  # fmt: skip
