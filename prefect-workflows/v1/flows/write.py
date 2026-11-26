"""Write a source's rows into a v1 timeseries dataset: the one write path every ingest uses.

A teehr-core source (:mod:`teehr_core.fetch`) fetches however suits it, but returns the same
thing: batches of v1 timeseries rows in its ``UNIT``. A flow picks the locations and window,
calls the source, and hands the batches to :func:`write_rows`.
"""

import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from prefect import get_run_logger, runtime
from pyiceberg.catalog import Catalog
from teehr_core.model.dataset_types import TIMESERIES_KEY
from teehr_core.warehouse import combine, write_timeseries


def write_rows(
    cat: Catalog,
    namespace: str,
    dataset: str,
    batches: Iterable[pa.Table],
    unit: str,
    location_of: Callable[[str], str] | None = None,
    commit_rows: int = 1_000_000,
    replace_months: bool = False,
) -> dict[str, Any]:
    """Write a source's batches of rows into ``namespace.dataset``.

    Columns the dataset doesn't have (a source's flags) are dropped with a warning, except key
    columns: rows with a ``reference_time`` or ``member`` the dataset lacks are refused.
    Batches are joined into commits of at least ``commit_rows`` rows, each logged as it's
    written.

    Parameters
    ----------
    cat : Catalog
        The warehouse catalog.
    namespace, dataset : str
        The timeseries dataset to write.
    batches : Iterable[pa.Table]
        v1 timeseries rows, as a :mod:`teehr_core.fetch` source returns them.
    unit : str
        The unit of the rows' values (the source's ``UNIT``), converted to the dataset's.
    location_of : Callable[[str], str | None], optional
        A new series' ``location_key`` in the dataset's location layer, from its
        ``series_key``. It's called only for series keys not yet in the dataset's series
        table, to fill their rows; existing series and the timeseries rows are unchanged.
        None (the default): new series have no location, as for NWM reaches, which are
        paired with gages through a crosswalk instead.
    commit_rows : int, default 1_000_000
        The fewest rows in each commit (but the last).
    replace_months : bool, default False
        Replace the whole months the rows hold, instead of upserting on the dataset's key.

    Returns
    -------
    dict
        ``rows``, ``commits``, ``series_added``, ``months`` (how many were written) and
        ``snapshot_id``.

    Examples
    --------
    USGS: the series key is the gage's location key.

    >>> write_rows(cat, "public", "usgs_streamflow", usgs.read_bulk(sites, start, end),
    ...            unit=usgs.UNIT, location_of=lambda key: key)

    NWM: reaches have no location layer.

    >>> write_rows(cat, "public", "nwm31_short_range", batches, unit=nwm.UNIT)

    A source whose series keys aren't location keys maps one to the other, e.g. keys per gage
    and variable (``usgs-01646500-discharge``), or a lookup the flow built.

    >>> write_rows(cat, "public", dataset, batches, unit=UNIT,
    ...            location_of=lambda key: key.rsplit("-", 1)[0])
    >>> write_rows(cat, "public", dataset, batches, unit=UNIT, location_of=site_for.get)
    """
    log = get_run_logger()
    written = write_timeseries(
        cat, namespace, dataset,
        _logged(combine(_fit(cat, namespace, dataset, batches), commit_rows)),
        producer=f"prefect:{runtime.flow_run.name or 'local'}",
        unit=unit, location_of=location_of, replace_months=replace_months,
    )  # fmt: skip
    log.info("%s.%s: wrote %d rows in %d commit(s); %d new series; months %s", namespace,
             dataset, written.rows, written.batches, written.series_added,
             ", ".join(written.months) or "-")  # fmt: skip
    return {"rows": written.rows, "commits": written.batches,
            "series_added": written.series_added, "months": len(written.months),
            "snapshot_id": written.snapshot_id}  # fmt: skip


def _fit(cat: Catalog, namespace: str, dataset: str,
         batches: Iterable[pa.Table]) -> Iterator[pa.Table]:  # fmt: skip
    """Drop the columns ``namespace.dataset`` doesn't have from each batch.

    Key columns are kept, so ``write_timeseries`` refuses rows with a ``reference_time`` or
    ``member`` the dataset lacks rather than merging them silently. Each dropped column is
    warned about once.

    Parameters
    ----------
    cat : Catalog
        The warehouse catalog.
    namespace, dataset : str
        The timeseries dataset the batches are for.
    batches : Iterable[pa.Table]
        v1 timeseries rows.

    Yields
    ------
    pa.Table
        Each batch, without the dataset's missing non-key columns.

    Examples
    --------
    USGS rows carry ``approval_status`` and ``qualifier`` flags; ``usgs_streamflow`` keeps neither.

    >>> next(_fit(cat, "public", "usgs_streamflow", [rows])).column_names
    ['series_key', 'value_time', 'value']
    """
    columns = {f.name for f in cat.load_table((namespace, dataset)).schema().fields}
    warned: set[str] = set()
    for batch in batches:
        extra = [c for c in batch.column_names if c not in columns and c not in TIMESERIES_KEY]
        if set(extra) - warned:
            get_run_logger().warning("%s.%s has no %s column(s): not kept", namespace,
                                     dataset, " or ".join(extra))  # fmt: skip
            warned |= set(extra)
        yield batch.drop_columns(extra) if extra else batch


def _logged(batches: Iterable[pa.Table]) -> Iterator[pa.Table]:
    """Log each commit (its months and rows) as it's written.

    Months are by ``reference_time`` when the rows have one, else by ``value_time``.

    Parameters
    ----------
    batches : Iterable[pa.Table]
        The commits, as :func:`teehr_core.warehouse.combine` joins them.

    Yields
    ------
    pa.Table
        Each commit, unchanged.

    Examples
    --------
    >>> write_timeseries(cat, namespace, dataset, _logged(combine(batches, 1_000_000)), ...)

    logs, per commit, e.g. ``commit 3: 2007-11..2008-02, 1004211 rows (3012655 so far, 412 s)``.
    """
    log = get_run_logger()
    began, rows = time.monotonic(), 0
    for i, batch in enumerate(batches, 1):
        column = "reference_time" if "reference_time" in batch.column_names else "value_time"
        months = [m for m in pc.unique(pc.strftime(batch[column], format="%Y-%m")).to_pylist()
                  if m]  # fmt: skip
        rows += batch.num_rows
        log.info("commit %d: %s..%s, %d rows (%d so far, %.0f s)", i, min(months, default="-"),
                 max(months, default="-"), batch.num_rows, rows,
                 time.monotonic() - began)  # fmt: skip
        yield batch
