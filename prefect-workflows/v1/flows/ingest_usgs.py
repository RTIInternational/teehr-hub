"""Ingest USGS streamflow observations into a v1 timeseries dataset (``public.usgs_streamflow``).

The template for v1 ingests (ADR-0019 in teehr-cloud-core): a teehr-core source
(:mod:`teehr_core.fetch.usgs`) yields rows a batch of sites at a time, and teehr-core's
writer (:func:`teehr_core.warehouse.write_timeseries`) writes them straight into the
registered dataset as the flows' service account. Each commit is upserted on the dataset's
key, so a re-run, or an overlapping window, rewrites rather than repeats.

The sites are the dataset's location layer's (``teehr.location_layer``), optionally
filtered on its attributes (``where``), or a list given with ``sites``. Outside Prefect,
the same two teehr-core calls make a one-off ingest from a notebook.

:func:`backfill_usgs_streamflow` fills whole records from the USGS bulk Parquet files
instead (a rebuild, or a reload of months USGS has since approved): staged by month, each
month written whole, then topped up from the API where the files end.
"""

import os
import tempfile
import time
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from prefect import flow, get_run_logger, runtime, task
from prefect.blocks.system import Secret
from teehr_core.fetch import usgs
from teehr_core.warehouse import (
    combine,
    location_keys,
    stage_by_month,
    staged_months,
    write_timeseries,
)

from flows.catalog import catalog

#: The Prefect Secret block with the USGS Water Data API key (higher rate limits).
PAT_BLOCK = "api-usgs-pat"
#: The optional columns the rows carry, kept when the dataset has them.
FLAGS = ("approval_status", "qualifier")


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
    start: datetime | None = None,
    service: usgs.Service = "iv",
    hourly: bool = True,
    batch_sites: int = usgs.BATCH_SITES,
    commit_rows: int = 1_000_000,
) -> dict[str, Any]:
    """Fetch the sites' streamflow for ``lookback_days`` before ``end`` and write it.

    ``sites`` (``usgs-01646500`` or ``01646500``) default to the location layer's keys,
    filtered by ``where`` (a PyIceberg row filter on its attributes, e.g.
    ``"is_active == True and has_inst_discharge == True"``). ``end`` defaults to the end of
    the current hour, UTC; ``start``, if given, instead of ``lookback_days``. ``service``:
    ``iv`` instantaneous (on the hour with ``hourly``) or ``dv`` daily. ``batch_sites`` sites per request; ``commit_rows`` rows per commit.
    """
    log = get_run_logger()
    _use_pat()
    cat = catalog()
    sites = _sites(cat, namespace, dataset, sites, where)
    if end is None:
        end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = start or end - timedelta(days=lookback_days)
    log.info("USGS %s: %d sites, %s to %s, into %s.%s", service, len(sites), start, end,
             namespace, dataset)  # fmt: skip

    batches = (
        fetch(sites[i : i + batch_sites], start, end, service, hourly,
              i + 1, min(i + batch_sites, len(sites)), len(sites))
        for i in range(0, len(sites), batch_sites)
    )  # fmt: skip
    written = write_timeseries(
        cat, namespace, dataset, combine(_fit(cat, namespace, dataset, batches), commit_rows),
        producer=f"prefect:{runtime.flow_run.name or 'local'}",
        unit=usgs.UNIT, location_of=lambda key: key,
    )  # fmt: skip
    log.info("wrote %d rows in %d commit(s); %d new series; months %s", written.rows,
             written.batches, written.series_added, ", ".join(written.months) or "-")  # fmt: skip
    return {"sites": len(sites), "start": start.isoformat(), "end": end.isoformat(),
            "rows": written.rows, "commits": written.batches,
            "series_added": written.series_added, "snapshot_id": written.snapshot_id}  # fmt: skip


def _sites(cat: Any, namespace: str, dataset: str, sites: list[str] | None,
           where: str | None) -> list[str]:  # fmt: skip
    """``sites``, or the dataset's location layer's USGS keys (filtered by ``where``)."""
    if sites is None:
        sites = [k for k in location_keys(cat, namespace, dataset, where)
                 if k.lower().startswith("usgs-")]  # fmt: skip
    return list(dict.fromkeys(sites))


def _fit(cat: Any, namespace: str, dataset: str, batches: Iterable[pa.Table]) -> Iterator[pa.Table]:
    """The batches without the flag columns the dataset doesn't have."""
    columns = {f.name for f in cat.load_table((namespace, dataset)).schema().fields}
    missing = [c for c in FLAGS if c not in columns]
    if missing:
        get_run_logger().warning("%s.%s has no %s column(s): not kept", namespace, dataset,
                                 " or ".join(missing))  # fmt: skip
    for batch in batches:
        yield batch.drop_columns(missing) if missing else batch


@task(persist_result=False, task_run_name="stage {total} sites' bulk files")
def stage_sites(
    sites: list[str], start: datetime | None, end: datetime | None, service: usgs.Service,
    hourly: bool, directory: str, workers: int, total: int,
) -> dict[str, datetime]:  # fmt: skip
    """Download each site's bulk file and stage its rows by month; each site's last time."""
    log = get_run_logger()

    def one(site: str) -> tuple[str, datetime | None, int]:
        began = time.monotonic()
        for attempt in range(3):
            try:
                rows = next(usgs.read_bulk([site], start, end, service=service, hourly=hourly))
                break
            except Exception as err:  # a download blip: try again, then give up on the site
                if attempt == 2:
                    log.warning("%s: bulk file failed: %s", site, err)
                    return site, None, 0
        if not rows.num_rows:  # teehr-core's own log of why doesn't reach Prefect from threads
            log.warning("%s: no rows (no bulk file, or none in the range)", site)
            return site, None, 0
        staged = stage_by_month([rows], directory)
        log.info("%s: %d rows in %.0f s", site, staged, time.monotonic() - began)
        return site, max(rows["value_time"].to_pylist()), staged

    last_times: dict[str, datetime] = {}
    staged = done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for site, last, count in pool.map(one, sites):
            done += 1
            staged += count
            if last is not None:
                last_times[site] = last
            if done % 100 == 0 or done == len(sites):
                log.info("staged %d of %d sites: %d rows", done, len(sites), staged)
    return last_times


def _logged(batches: Iterable[pa.Table]) -> Iterator[pa.Table]:
    """The batches of whole months, each logged (its months and rows) as it's written."""
    log = get_run_logger()
    began, rows = time.monotonic(), 0
    for i, batch in enumerate(batches, 1):
        months = pc.unique(pc.strftime(batch["value_time"], format="%Y-%m")).to_pylist()
        rows += batch.num_rows
        log.info("commit %d: %s..%s, %d rows (%d so far, %.0f s)", i, min(months),
                 max(months), batch.num_rows, rows, time.monotonic() - began)  # fmt: skip
        yield batch


@flow(name="backfill-usgs-streamflow", log_prints=True)
def backfill_usgs_streamflow(
    dataset: str = "usgs_streamflow",
    namespace: str = "public",
    sites: list[str] | None = None,
    where: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    service: usgs.Service = "iv",
    hourly: bool = True,
    workers: int = 4,
    stage_dir: str | None = None,
    top_up: bool = True,
    commit_rows: int = 5_000_000,
) -> dict[str, Any]:
    """Fill the sites' whole record (or ``start`` to ``end``) from the USGS bulk files.

    Every site's file is staged by month (``stage_dir``, default a temporary folder), then
    each month is written whole, **replacing** that month: rows of sites not staged for it
    are deleted. So run it for every site of the dataset (the default), or limit the months
    with ``start``/``end`` to ones the files cover for all of them.

    The files lag the API (continuous values by months, varying by site). With ``top_up``,
    the API then fills from the earliest last time among sites still reporting (a file
    ending within the last year) up to now, refilling the months the files only partly cover.

    Months are written whole, joined into commits of at least ``commit_rows`` rows (fewer
    commits for small or early months).
    """
    log = get_run_logger()
    _use_pat()
    cat = catalog()
    sites = _sites(cat, namespace, dataset, sites, where)
    log.info("USGS %s bulk: %d sites into %s.%s", service, len(sites), namespace, dataset)
    with tempfile.TemporaryDirectory(dir=stage_dir) as directory:
        last_times = stage_sites(sites, start, end, service, hourly, directory, workers,
                                 len(sites))  # fmt: skip
        months = _logged(combine(staged_months(directory), commit_rows))
        written = write_timeseries(
            cat, namespace, dataset, _fit(cat, namespace, dataset, months),
            producer=f"prefect:{runtime.flow_run.name or 'local'}",
            unit=usgs.UNIT, location_of=lambda key: key, replace_months=True,
        )  # fmt: skip
    log.info("bulk: wrote %d rows, %d months, %d new series; %d of %d sites had data",
             written.rows, written.batches, written.series_added, len(last_times),
             len(sites))  # fmt: skip
    result: dict[str, Any] = {"sites": len(sites), "with_data": len(last_times),
                              "rows": written.rows, "months": written.batches,
                              "series_added": written.series_added}  # fmt: skip
    now = datetime.now(UTC)
    reporting = [t for t in last_times.values() if t > now - timedelta(days=365)]
    if top_up and reporting:
        since = min(reporting).replace(minute=0, second=0, microsecond=0)
        log.info("top-up from the API: %d sites still reporting, from %s", len(reporting),
                 since)  # fmt: skip
        result["top_up"] = ingest_usgs_streamflow(
            dataset=dataset, namespace=namespace, sites=sites, start=since,
            service=service, hourly=hourly,
        )  # fmt: skip
    return result
