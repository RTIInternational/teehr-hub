"""Ingest USGS streamflow observations into a v1 timeseries dataset (``public.usgs_streamflow``).

The template for v1 ingests (ADR-0019 in teehr-cloud-core): a teehr-core source
(:mod:`teehr_core.fetch.usgs`) yields rows a batch of sites at a time, and teehr-core's
writer (:func:`teehr_core.warehouse.write_timeseries`) writes them straight into the
registered dataset as the flows' service account. Each commit is upserted on the dataset's
key, so a re-run, or an overlapping window, rewrites rather than repeats.

The sites are the dataset's location layer's (``teehr.location_layer``), optionally
filtered on its attributes (``where``), or a list given with ``sites``. Outside Prefect,
the same two teehr-core calls make a one-off ingest from a notebook.
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pyarrow as pa
from prefect import flow, get_run_logger, runtime, task
from prefect.blocks.system import Secret
from teehr_core.fetch import usgs
from teehr_core.warehouse import combine, location_keys, write_timeseries

from flows.catalog import catalog

#: The Prefect Secret block with the USGS Water Data API key (higher rate limits).
PAT_BLOCK = "api-usgs-pat"


@task(retries=2, retry_delay_seconds=60, persist_result=False,
      task_run_name="fetch sites {first}-{last} of {total}")  # fmt: skip
def fetch(
    sites: list[str], start: datetime, end: datetime, service: usgs.Service, hourly: bool,
    first: int, last: int, total: int,
) -> pa.Table:  # fmt: skip
    """One request's worth of sites; retried, so a blip doesn't fail the run."""
    return pa.concat_tables(usgs.fetch_streamflow(
        sites, start, end, service=service, hourly=hourly, batch_sites=len(sites)
    ))  # fmt: skip


def _use_pat() -> None:
    log = get_run_logger()
    try:
        os.environ["API_USGS_PAT"] = Secret.load(PAT_BLOCK).get()
    except ValueError:  # no block
        log.warning("no '%s' Secret block: fetching without an API key", PAT_BLOCK)


@flow(name="ingest-usgs-streamflow", log_prints=True)
def ingest_usgs_streamflow(
    dataset: str = "usgs_streamflow",
    namespace: str = "public",
    sites: list[str] | None = None,
    where: str | None = None,
    lookback_days: float = 1,
    end: datetime | None = None,
    service: usgs.Service = "iv",
    hourly: bool = True,
    batch_sites: int = usgs.BATCH_SITES,
    commit_rows: int = 1_000_000,
) -> dict[str, Any]:
    """Fetch the sites' streamflow for ``lookback_days`` before ``end`` and write it.

    ``sites`` (``usgs-01646500`` or ``01646500``) default to the location layer's keys,
    filtered by ``where`` (a PyIceberg row filter on its attributes, e.g.
    ``"is_active == True and has_inst_discharge == True"``). ``end`` defaults to the end of
    the current hour, UTC. ``service``: ``iv`` instantaneous (on the hour with ``hourly``)
    or ``dv`` daily. ``batch_sites`` sites per request; ``commit_rows`` rows per commit.
    """
    log = get_run_logger()
    _use_pat()
    cat = catalog()
    if sites is None:
        sites = [k for k in location_keys(cat, namespace, dataset, where)
                 if k.lower().startswith("usgs-")]  # fmt: skip
    sites = list(dict.fromkeys(sites))
    if end is None:
        end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = end - timedelta(days=lookback_days)
    log.info("USGS %s: %d sites, %s to %s, into %s.%s", service, len(sites), start, end,
             namespace, dataset)  # fmt: skip

    batches = (
        fetch(sites[i : i + batch_sites], start, end, service, hourly,
              i + 1, min(i + batch_sites, len(sites)), len(sites))
        for i in range(0, len(sites), batch_sites)
    )  # fmt: skip
    columns = {f.name for f in cat.load_table((namespace, dataset)).schema().fields}
    missing = [c for c in ("approval_status", "qualifier") if c not in columns]
    if missing:
        log.warning("%s.%s has no %s column(s): not kept", namespace, dataset,
                    " or ".join(missing))  # fmt: skip
        batches = (b.drop_columns(missing) for b in batches)
    written = write_timeseries(
        cat, namespace, dataset, combine(batches, commit_rows),
        producer=f"prefect:{runtime.flow_run.name or 'local'}",
        unit=usgs.UNIT, location_of=lambda key: key,
    )  # fmt: skip
    log.info("wrote %d rows in %d commit(s); %d new series; months %s", written.rows,
             written.batches, written.series_added, ", ".join(written.months) or "-")  # fmt: skip
    return {"sites": len(sites), "start": start.isoformat(), "end": end.isoformat(),
            "rows": written.rows, "commits": written.batches,
            "series_added": written.series_added, "snapshot_id": written.snapshot_id}  # fmt: skip
