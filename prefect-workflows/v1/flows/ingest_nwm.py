"""Ingest NWM operational streamflow at the gages' reaches into v1 timeseries datasets.

One dataset per configuration (legacy's names: ``nwm31_short_range``, ``nwm31_medium_range``
for ``medium_range_mem1``, ...), all sharing the version's series table, so one crosswalk
(``usgs_nwm31``) pairs the gages with each. :mod:`teehr_core.fetch.nwm` lists and reads the
files from NOAA's GCS bucket; :func:`flows.write.write_rows` writes them.

As the legacy ingest did: the reaches are the crosswalk's, for the gages in the
configuration's domain (their ``state_name``); runs upsert, so cycles read again are
rewritten, not repeated; analysis keeps the latest cycle's value for each time, with no
``reference_time``. Unlike legacy, a run reads from the dataset's latest cycle on (read again,
in case it was published partly), not whole days: each commit rewrites the data files that
overlap its window, so the less it reads again, the less it rewrites.
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
    """Legacy's dataset name for a configuration: the version, then the name without a member.

    Parameters
    ----------
    configuration : str
        Its directory on GCS, e.g. ``medium_range_alaska_mem1``.
    version : str, default "nwm31"
        The dataset name's prefix.

    Returns
    -------
    str
        The dataset name.

    Examples
    --------
    >>> dataset_name("medium_range_alaska_mem1")
    'nwm31_medium_range_alaska'
    >>> dataset_name("analysis_assim_no_da")
    'nwm31_analysis_assim_no_da'
    """
    return f"{version}_{re.sub(r'_mem[0-9]+', '', configuration)}"


def domain_filter(configuration: str) -> str:
    """The gages in the configuration's domain, as a row filter on their ``state_name``.

    A configuration named for an OCONUS domain (:data:`DOMAINS`) is that state's gages;
    any other is CONUS: the gages with a state not in :data:`OCONUS`.

    Parameters
    ----------
    configuration : str
        Its directory on GCS.

    Returns
    -------
    str
        A row filter for :func:`teehr_core.warehouse.location_keys`.

    Examples
    --------
    >>> domain_filter("short_range_hawaii")
    "state_name == 'Hawaii'"
    >>> domain_filter("medium_range_mem1")  # doctest: +ELLIPSIS
    "state_name is not null and state_name not in ('Alaska', 'Hawaii', ...)"
    """
    for word, state in DOMAINS.items():
        if word in configuration:
            return f"state_name == '{state}'"
    oconus = ", ".join(f"'{s}'" for s in OCONUS)
    return f"state_name is not null and state_name not in ({oconus})"


def reaches(cat: Catalog, namespace: str, crosswalk: str, observed: str, where: str,
            version: str) -> list[str]:  # fmt: skip
    """The crosswalk's ``version`` reaches for ``observed``'s gages that match ``where``.

    Parameters
    ----------
    cat : Catalog
        The warehouse catalog.
    namespace : str
        Where ``crosswalk`` and ``observed`` are.
    crosswalk : str
        Pairs the gages (left) with reaches (right).
    observed : str
        The dataset whose location layer holds the gages.
    where : str
        A row filter on the gages' layer, e.g. :func:`domain_filter`'s.
    version : str
        The reaches' key prefix; links to other versions' reaches are ignored.

    Returns
    -------
    list[str]
        The reaches' keys, sorted, each once.

    Examples
    --------
    The ``nwm31`` reaches at the Alaska gages:

    >>> reaches(cat, "public", "usgs_nwm31", "usgs_streamflow",
    ...         domain_filter("short_range_alaska"), "nwm31")
    """
    gages = pa.array(location_keys(cat, namespace, observed, where), pa.string())
    links = cat.load_table((namespace, crosswalk)).scan(
        selected_fields=("left_key", "right_key")
    ).to_arrow()  # fmt: skip
    links = links.filter(pc.is_in(links["left_key"], gages))
    keys = [k for k in links["right_key"].to_pylist() if k.startswith(f"{version}-")]
    return sorted(set(keys))


def latest_cycle(cat: Catalog, namespace: str, dataset: str) -> datetime | None:
    """The dataset's latest cycle, from its files' metadata (no data is read).

    A forecast's latest ``reference_time``; analysis has none, but its latest ``value_time``
    is its latest cycle's (the file with no look-back).

    Parameters
    ----------
    cat : Catalog
        The warehouse catalog.
    namespace, dataset : str
        The timeseries dataset.

    Returns
    -------
    datetime or None
        The cycle (UTC), or None for a dataset without rows.

    Examples
    --------
    >>> latest_cycle(cat, "public", "nwm31_short_range")
    datetime.datetime(2026, 11, 27, 17, 0, tzinfo=datetime.timezone.utc)
    """
    table = cat.load_table((namespace, dataset))
    if table.current_snapshot() is None:
        return None
    names = {f.name for f in table.schema().fields}
    column = "reference_time" if "reference_time" in names else "value_time"
    metrics = table.inspect.files().column("readable_metrics").to_pylist()
    bounds = [m[column]["upper_bound"] for m in metrics if m and m.get(column)]
    latest = max((b for b in bounds if b is not None), default=None)
    if latest is None:
        return None
    return latest if latest.tzinfo else latest.replace(tzinfo=UTC)


def _check_columns(cat: Catalog, namespace: str, dataset: str, configuration: str,
                   found: list[nwm.File]) -> None:  # fmt: skip
    """Refuse, before reading any file, a dataset without the key columns the rows will have.

    Parameters
    ----------
    cat : Catalog
        The warehouse catalog.
    namespace, dataset : str
        The timeseries dataset to write.
    configuration : str
        The files' configuration, for the message.
    found : list[nwm.File]
        The files to read: a forecast's rows have a ``reference_time``, an ensemble
        member's a ``member``.

    Raises
    ------
    ValueError
        When the dataset lacks one of those columns.

    Examples
    --------
    >>> _check_columns(cat, "public", "nwm31_short_range", "medium_range_mem1",
    ...                nwm.files("medium_range_mem1", start, end))
    Traceback (most recent call last):
    ValueError: public.nwm31_short_range has no member column, which medium_range_mem1's rows ...
    """
    needed = {"reference_time" for f in found if not f.analysis} | {
        "member" for f in found if f.member is not None}  # fmt: skip
    columns = {f.name for f in cat.load_table((namespace, dataset)).schema().fields}
    missing = sorted(needed - columns)
    if missing:
        raise ValueError(f"{namespace}.{dataset} has no {' or '.join(missing)} column, which "
                         f"{configuration}'s rows have: register it with them (or pick the "
                         "dataset that has them)")  # fmt: skip


@task(retries=2, retry_delay_seconds=60, persist_result=False,
      task_run_name="read files {first}-{last} of {total}")  # fmt: skip
def read(files: list[nwm.File], keys: list[str], version: str, workers: int,
         first: int, last: int, total: int) -> pa.Table | None:  # fmt: skip
    """Read one batch of files' rows at the reaches; retried, so a blip doesn't fail the run.

    Parameters
    ----------
    files : list[nwm.File]
        The batch, from :func:`teehr_core.fetch.nwm.files`.
    keys : list[str]
        The reaches' series keys.
    version : str
        The NWM version the files are read as.
    workers : int
        Files read at once.
    first, last, total : int
        The batch's place among the run's files, for the task run's name.

    Returns
    -------
    pa.Table or None
        The rows, or None when the files hold none at the reaches.

    Examples
    --------
    >>> read(found[:100], keys, "nwm31", 16, 1, 100, len(found))
    """
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
    commit_rows: int = 20_000_000,
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
        For a dataset without rows and no ``start``: read from midnight UTC this many days
        before ``end``.
    start, end : datetime, optional
        The window of cycles. ``start`` defaults to the dataset's latest cycle
        (:func:`latest_cycle`), read again in case it was published partly; ``end`` to now.
    batch_files : int, default 100
        Files read per batch (one retried task each).
    workers : int, default 16
        Files read at once.
    commit_rows : int, default 20_000_000
        The fewest rows in each commit. Each commit rewrites the data files its window
        overlaps, so a run is best one commit: a 12-hour medium range run is about 6M rows.

    Returns
    -------
    dict
        The configuration, dataset, reaches and files counts and window, and
        :func:`flows.write.write_rows`' summary.

    Examples
    --------
    The scheduled run: the cycles since the dataset's latest, at the CONUS gages' reaches.

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
    start = start or latest_cycle(cat, namespace, dataset) or (
        end - timedelta(days=lookback_days)
    ).replace(hour=0, minute=0, second=0, microsecond=0)  # fmt: skip
    found = nwm.files(configuration, start, end)
    log.info("NWM %s: %d reaches (gages: %s), %d files (cycles %s to %s) into %s.%s", configuration,
             len(keys), where, len(found), start, end, namespace, dataset)  # fmt: skip
    if not keys:
        raise ValueError(f"no {version} reaches in {namespace}.{crosswalk} for the domain's gages")
    _check_columns(cat, namespace, dataset, configuration, found)

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
