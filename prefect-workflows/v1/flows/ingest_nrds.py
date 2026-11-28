"""Ingest NextGen Research DataStream (NRDS) streamflow forecasts at the gages' reaches.

One dataset per model and configuration (legacy's names: ``nrds_v22_cfenom_short_range``,
``nrds_v22_lstm0_medium_range``, ...), all sharing one series table, so one crosswalk
(``usgs_nrds22``) pairs the gages with each, as ``usgs_nwm31`` does the NWM datasets.
:mod:`teehr_core.fetch.nrds` lists and reads the t-route files from the DataStream's S3
bucket; :func:`flows.write.write_rows` writes them.

As the legacy ingest did: the reaches are the crosswalk's, for the USGS gages matching
``where``; short range and medium range member 1, with no ``member``; values at t-route's
times. Unlike legacy, a run reads from the dataset's latest cycle on (read again, in case it
was published partly), not the day before, so a missed run is caught up; and cycle 23 is read.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pyarrow as pa
from prefect import flow, get_run_logger, task
from teehr_core.fetch import nrds

from flows.catalog import catalog
from flows.ingest_nwm import latest_cycle, reaches
from flows.write import write_rows


def dataset_name(model: str, configuration: str) -> str:
    """Return legacy's dataset name for a model's configuration.

    Parameters
    ----------
    model : str
        Its directory in the bucket, e.g. ``lstm_0``.
    configuration : str
        ``short_range`` or ``medium_range``.

    Returns
    -------
    str
        The dataset name.

    Examples
    --------
    >>> dataset_name("cfe_nom", "short_range")
    'nrds_v22_cfenom_short_range'
    >>> dataset_name("lstm_0", "medium_range")
    'nrds_v22_lstm0_medium_range'
    """
    return f"nrds_v22_{model.replace('_', '')}_{configuration}"


@task(retries=2, retry_delay_seconds=60, persist_result=False,
      task_run_name="read files {first}-{last} of {total}")  # fmt: skip
def read(files: list[nrds.File], keys: list[str], workers: int,
         first: int, last: int, total: int) -> pa.Table | None:  # fmt: skip
    """Read one batch of files' rows at the reaches; retried, so a blip doesn't fail the run.

    Parameters
    ----------
    files : list[nrds.File]
        The batch, from :func:`teehr_core.fetch.nrds.files`.
    keys : list[str]
        The reaches' series keys.
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
    >>> read(found[:100], keys, 16, 1, 100, len(found))
    """
    tables = list(nrds.read_points(files, keys, workers=workers, batch_files=len(files)))
    return pa.concat_tables(tables) if tables else None


@flow(name="ingest-nrds-streamflow", log_prints=True)
def ingest_nrds_streamflow(
    model: str = "cfe_nom",
    configuration: str = "short_range",
    dataset: str | None = None,
    namespace: str = "public",
    crosswalk: str = "usgs_nrds22",
    observed: str = "usgs_inst_streamflow",
    where: str = "is_active == True and has_inst_discharge == True",
    lookback_days: int = 1,
    start: datetime | None = None,
    end: datetime | None = None,
    batch_files: int = 100,
    workers: int = 16,
    commit_rows: int = 20_000_000,
) -> dict[str, Any]:
    """Read the model's configuration's cycles from ``start`` up to ``end`` and write them.

    The reaches are ``crosswalk``'s right keys for ``observed``'s gages. New series rows get
    no ``location_key``: reaches have no location layer, and evaluations reach the gages
    through the crosswalk.

    Parameters
    ----------
    model : str, default "cfe_nom"
        Its directory in the bucket, one of :data:`teehr_core.fetch.nrds.MODELS`.
    configuration : str, default "short_range"
        ``short_range`` or ``medium_range`` (member 1).
    dataset : str, optional
        Defaults to legacy's name (:func:`dataset_name`).
    namespace : str, default "public"
    crosswalk : str, default "usgs_nrds22"
        Pairs ``observed``'s gages (left) with the reaches (right, ``nrds22-<id>``).
    observed : str, default "usgs_inst_streamflow"
        The dataset whose location layer holds the gages.
    where : str
        A row filter on the gages' layer: the reaches of the gages matching it.
    lookback_days : int, default 1
        For a dataset without rows and no ``start``: read from midnight UTC this many days
        before ``end``.
    start, end : datetime, optional
        The window of cycles. ``start`` defaults to the dataset's latest cycle, read again in
        case it was published partly; ``end`` to now.
    batch_files : int, default 100
        Files read per batch (one retried task each).
    workers : int, default 16
        Files read at once.
    commit_rows : int, default 20_000_000
        The fewest rows in each commit (a day of medium range is about 6M rows).

    Returns
    -------
    dict
        The model, configuration, dataset, reaches, files, cycles and window, and
        :func:`flows.write.write_rows`' summary.

    Examples
    --------
    The scheduled run: the cycles since the dataset's latest.

    >>> ingest_nrds_streamflow("lstm_0", "medium_range")

    A week of CFE-NOM short range.

    >>> ingest_nrds_streamflow("cfe_nom", "short_range", start=datetime(2026, 11, 1, tzinfo=UTC),
    ...                        end=datetime(2026, 11, 8, tzinfo=UTC))
    """
    log = get_run_logger()
    dataset = dataset or dataset_name(model, configuration)
    cat = catalog()
    keys = reaches(cat, namespace, crosswalk, observed, where, nrds.PREFIX)
    if not keys:
        raise ValueError(f"no {nrds.PREFIX} reaches in {namespace}.{crosswalk} for {where!r}")
    end = end or datetime.now(UTC)
    start = start or latest_cycle(cat, namespace, dataset) or (
        end - timedelta(days=lookback_days)
    ).replace(hour=0, minute=0, second=0, microsecond=0)  # fmt: skip
    found = nrds.files(model, configuration, start, end)
    cycles = len({f.reference_time for f in found})
    log.info("NRDS %s %s: %d reaches, %d files (%d cycles, %s to %s) into %s.%s", model,
             configuration, len(keys), len(found), cycles, start, end, namespace,
             dataset)  # fmt: skip

    batches = (
        read(found[i : i + batch_files], keys, workers,
             i + 1, min(i + batch_files, len(found)), len(found))
        for i in range(0, len(found), batch_files)
    )  # fmt: skip
    written = write_rows(cat, namespace, dataset, (b for b in batches if b is not None),
                         unit=nrds.UNIT, commit_rows=commit_rows)  # fmt: skip
    return {"model": model, "configuration": configuration, "dataset": dataset,
            "reaches": len(keys), "files": len(found), "cycles": cycles,
            "start": start.isoformat(), "end": end.isoformat(), **written}  # fmt: skip
