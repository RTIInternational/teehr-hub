"""Build a derived dataset (percentiles, climatology, naive scale) of an observed timeseries.

The derived dataset is registered once through the API (``teehr datasets create`` with
``type: percentiles`` and ``observed: <timeseries>``), which makes its table with its
columns, variable and unit. This flow fills it: it reads the observed dataset at one
snapshot, a batch of series at a time, builds each batch with teehr-core, and replaces the
derived table in one commit, recording the source, its snapshot, the period and the
parameters in the commit (ADR-0019 in teehr-cloud-core). Runs see the new dataset whole or
not at all; a failed build leaves the old one.
"""

from datetime import datetime
from typing import Any

from prefect import flow, get_run_logger, runtime
from pyiceberg.exceptions import NoSuchTableError
from teehr_core.warehouse.build import build_derived

from flows.catalog import catalog


@flow(name="build-derived-dataset", log_prints=True)
def build_derived_dataset(
    observed: str = "usgs_streamflow",
    kind: str = "percentiles",
    name: str | None = None,
    namespace: str = "public",
    params: dict[str, Any] | None = None,
    batch_series: int = 50,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    """Build ``name`` (default ``<observed>_<kind>``) from ``observed``, both in ``namespace``.

    ``params`` go to the builder: percentiles ``levels``, ``min_years``; climatology
    ``window_days``; naive scale ``lags``. ``batch_series`` series are read at a time (memory
    holds one batch's rows). ``start``/``end`` limit the period (default: the whole record).
    """
    log = get_run_logger()
    name = name or f"{observed}_{kind}"
    cat = catalog()
    source = cat.load_table((namespace, observed))
    try:
        target = cat.load_table((namespace, name))
    except NoSuchTableError:
        raise ValueError(
            f"{namespace}.{name} isn't registered: create it first (POST "
            f"/v1/projects/{namespace}/datasets with type: {kind}, observed: {observed})"
        ) from None
    series_table = source.properties.get("teehr.series_table")
    if not series_table:
        raise ValueError(f"{namespace}.{observed} has no series table (teehr.series_table)")
    keys = (
        cat.load_table((namespace, series_table))
        .scan(selected_fields=("series_key",))
        .to_arrow()["series_key"]
        .to_pylist()
    )
    log.info("%s %s.%s from %s.%s: %d series", kind, namespace, name, namespace, observed,
             len(keys))  # fmt: skip
    result = build_derived(
        source, target, kind, keys,
        params=params, batch_series=batch_series, start=start, end=end,
        producer=f"prefect:{runtime.flow_run.name or 'local'}",
    )  # fmt: skip
    summary = {
        "rows": result.rows,
        "series": result.series,
        "batches": result.batches,
        "snapshot_id": result.snapshot_id,
        "source_snapshot": result.source_snapshot,
        "period": [str(result.first), str(result.last)],
    }
    log.info("built %s.%s: %s", namespace, name, summary)
    return summary
