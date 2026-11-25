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
    """Write ``batches`` (values in ``unit``) into ``namespace.dataset``; a summary.

    Columns the dataset doesn't have (a source's flags) are dropped with a warning, except key
    columns: rows with a ``reference_time`` or ``member`` the dataset lacks are refused.
    Batches are joined into commits of at least ``commit_rows`` rows, each logged as it's
    written, and upserted on the dataset's key, or, with ``replace_months``, replace the whole
    months they hold.
    ``location_of`` gives a new series' location key (None: series without a location).
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
    """The batches without the non-key columns the dataset doesn't have."""
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
    """The commits, each logged (its months and rows) as it's written."""
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
