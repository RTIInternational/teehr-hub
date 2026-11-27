"""Ingest USGS streamflow observations into a v1 timeseries dataset (``public.usgs_streamflow``).

The template for v1 ingests (ADR-0019 in teehr-cloud-core): a teehr-core source
(:mod:`teehr_core.fetch.usgs`) yields rows a batch of sites at a time, and
:func:`flows.write.write_rows` writes them straight into the registered dataset as the
flows' service account. Each commit is upserted on the dataset's key, so a re-run, or an
overlapping window, rewrites rather than repeats.

The sites are the dataset's location layer's (``teehr.location_layer``), optionally
filtered on its attributes (``where``), or a list given with ``sites``. Outside Prefect,
the same two teehr-core calls make a one-off ingest from a notebook.

:func:`backfill_usgs_streamflow` fills whole records from the USGS bulk Parquet files
instead (a rebuild, or a reload of months USGS has since approved): staged by month, each
month written whole, then topped up from the API where each site's file ends.
"""

import os
import tempfile
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from itertools import islice
from typing import Any

import pyarrow as pa
from prefect import flow, get_run_logger, task
from prefect.blocks.system import Secret
from teehr_core.fetch import usgs
from teehr_core.warehouse import location_keys, stage_by_month, staged_months

from flows.catalog import catalog
from flows.write import write_rows

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
    written = write_rows(cat, namespace, dataset, batches, unit=usgs.UNIT,
                         location_of=lambda key: key, commit_rows=commit_rows)  # fmt: skip
    return {"sites": len(sites), "start": start.isoformat(), "end": end.isoformat(), **written}


def _sites(cat: Any, namespace: str, dataset: str, sites: list[str] | None,
           where: str | None) -> list[str]:  # fmt: skip
    """``sites``, or the dataset's location layer's USGS keys (filtered by ``where``)."""
    if sites is None:
        sites = [k for k in location_keys(cat, namespace, dataset, where)
                 if k.lower().startswith("usgs-")]  # fmt: skip
    return list(dict.fromkeys(sites))


@task(persist_result=False, task_run_name="stage {total} sites' bulk files")
def stage_sites(
    sites: list[str], start: datetime | None, end: datetime | None, service: usgs.Service,
    hourly: bool, directory: str, workers: int, total: int, buffer_sites: int = 50,
) -> dict[str, datetime]:  # fmt: skip
    """Download each site's bulk file and stage the rows by month; each site's last time.

    Rows are held for ``buffer_sites`` sites, then staged together: one file per month
    per buffer, not per site (thousands of sites over decades of months).
    """
    log = get_run_logger()

    def one(site: str) -> tuple[str, pa.Table | None]:
        began = time.monotonic()
        for attempt in range(3):
            try:
                rows = next(usgs.read_bulk([site], start, end, service=service, hourly=hourly))
                break
            except Exception as err:  # a download blip: try again, then give up on the site
                if attempt == 2:
                    log.warning("%s: bulk file failed: %s", site, err)
                    return site, None
        if not rows.num_rows:  # teehr-core's own log of why doesn't reach Prefect from threads
            log.warning("%s: no rows (no bulk file, or none in the range)", site)
            return site, None
        log.info("%s: %d rows in %.0f s", site, rows.num_rows, time.monotonic() - began)
        return site, rows

    last_times: dict[str, datetime] = {}
    held: list[pa.Table] = []
    staged = done = 0
    todo = iter(sites)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # A few downloads ahead of the staging, not all of them: finished ones wait in memory.
        running = {pool.submit(one, s) for s in islice(todo, 2 * workers)}
        while running:
            finished, running = wait(running, return_when=FIRST_COMPLETED)
            for future in finished:
                site, rows = future.result()
                done += 1
                if rows is not None:
                    held.append(rows)
                    last_times[site] = max(rows["value_time"].to_pylist())
                following = next(todo, None)
                if following is not None:
                    running.add(pool.submit(one, following))
            if held and (len(held) >= buffer_sites or not running):
                staged += stage_by_month([pa.concat_tables(held)], directory)
                held = []
                log.info("staged %d of %d sites: %d rows", done, len(sites), staged)
    return last_times


def top_up_groups(
    sites: list[str], last_times: dict[str, datetime], now: datetime,
    horizon: timedelta = timedelta(days=365),
) -> list[tuple[datetime, list[str]]]:  # fmt: skip
    """Group the sites to top up from the API by the month their bulk file ends.

    The files lag the API by months, varying by site. Each group is fetched from its
    earliest last time, so a few sites whose files end early don't drag every site's window
    back with them. Sites whose files ended before ``horizon`` have stopped reporting and
    are skipped; sites with no file (none, or its download failed) start ``horizon`` back.

    Parameters
    ----------
    sites : list[str]
        The backfill's sites.
    last_times : dict[str, datetime]
        Each staged site's last time in its file (:func:`stage_sites`).
    now : datetime
        The top-up's end.
    horizon : timedelta, default 365 days
        How recent a site's last time must be to count as still reporting.

    Returns
    -------
    list[tuple[datetime, list[str]]]
        Each group's start (its earliest last time, to the hour) and sites, earliest first.

    Examples
    --------
    >>> now = datetime(2026, 11, 27, tzinfo=UTC)
    >>> top_up_groups(["usgs-01", "usgs-02", "usgs-03", "usgs-04"], {
    ...     "usgs-01": datetime(2026, 6, 30, 23, 15, tzinfo=UTC),
    ...     "usgs-02": datetime(2026, 6, 12, 4, 0, tzinfo=UTC),
    ...     "usgs-03": datetime(2025, 1, 1, tzinfo=UTC)}, now)  # doctest: +NORMALIZE_WHITESPACE
    [(datetime.datetime(2025, 11, 27, 0, 0, tzinfo=datetime.timezone.utc), ['usgs-04']),
     (datetime.datetime(2026, 6, 12, 4, 0, tzinfo=datetime.timezone.utc),
      ['usgs-01', 'usgs-02'])]
    """
    groups: dict[tuple[int, int], list[str]] = defaultdict(list)
    starts: dict[tuple[int, int], datetime] = {}
    for site in sites:
        last = last_times.get(site)
        if last is None:
            last = now - horizon
        elif last <= now - horizon:
            continue
        month = (last.year, last.month)
        groups[month].append(site)
        start = last.replace(minute=0, second=0, microsecond=0)
        starts[month] = min(starts.get(month, start), start)
    return [(starts[m], groups[m]) for m in sorted(groups)]


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

    Every site's file is staged by month, then each month is written whole, **replacing**
    that month: rows of sites not staged for it are deleted. So run it for every site of the
    dataset (the default), or limit the months with ``start``/``end`` to ones the files cover
    for all of them.

    The files lag the API by months, varying by site. With ``top_up``, the API then fills
    each still-reporting site from where its file ends up to now, a group of sites per month
    their files end in (:func:`top_up_groups`), each group an :func:`ingest_usgs_streamflow`
    subflow run.

    Parameters
    ----------
    dataset : str, default "usgs_streamflow"
    namespace : str, default "public"
    sites : list[str], optional
        ``usgs-01646500`` or ``01646500``; defaults to the dataset's location layer's keys.
    where : str, optional
        A row filter on the location layer's attributes, e.g. ``"has_inst_discharge == True"``.
    start, end : datetime, optional
        Limit the files' rows to this window; the whole record by default.
    service : {"iv", "dv"}, default "iv"
        Instantaneous or daily values.
    hourly : bool, default True
        Keep only instantaneous values on the hour.
    workers : int, default 4
        Files downloaded at once.
    stage_dir : str, optional
        Where to stage the months; a temporary folder by default.
    top_up : bool, default True
        Fill from the API where the files end.
    commit_rows : int, default 5_000_000
        The fewest rows in each commit (whole months; fewer commits for small months).

    Returns
    -------
    dict
        ``sites``, ``with_data`` (sites with a file), :func:`flows.write.write_rows`'
        summary, and, with ``top_up``, ``top_up``: its ``groups``, ``sites``, ``rows`` and
        ``series_added``.

    Examples
    --------
    Every gage with instantaneous discharge, whole record, then topped up:

    >>> backfill_usgs_streamflow(where="has_inst_discharge == True")

    Reload the months USGS approved since the last backfill, without a top-up:

    >>> backfill_usgs_streamflow(where="has_inst_discharge == True",
    ...                          start=datetime(2025, 1, 1, tzinfo=UTC), top_up=False)
    """
    log = get_run_logger()
    _use_pat()
    cat = catalog()
    sites = _sites(cat, namespace, dataset, sites, where)
    log.info("USGS %s bulk: %d sites into %s.%s", service, len(sites), namespace, dataset)
    with tempfile.TemporaryDirectory(dir=stage_dir) as directory:
        last_times = stage_sites(sites, start, end, service, hourly, directory, workers,
                                 len(sites))  # fmt: skip
        written = write_rows(cat, namespace, dataset, staged_months(directory),
                             unit=usgs.UNIT, location_of=lambda key: key,
                             commit_rows=commit_rows, replace_months=True)  # fmt: skip
    log.info("bulk: %d of %d sites had data", len(last_times), len(sites))
    result: dict[str, Any] = {"sites": len(sites), "with_data": len(last_times), **written}
    groups = top_up_groups(sites, last_times, datetime.now(UTC)) if top_up else []
    if groups:
        log.info("top-up from the API: %d sites in %d groups, from %s",
                 sum(len(g) for _, g in groups), len(groups),
                 ", ".join(f"{s:%Y-%m-%d %H:%M} ({len(g)})" for s, g in groups))  # fmt: skip
        topped = [
            ingest_usgs_streamflow.with_options(flow_run_name=f"top-up from {since:%Y-%m-%d}")(
                dataset=dataset, namespace=namespace, sites=group, start=since,
                service=service, hourly=hourly,
            )
            for since, group in groups
        ]  # fmt: skip
        result["top_up"] = {"groups": len(groups), "sites": sum(t["sites"] for t in topped),
                            "rows": sum(t["rows"] for t in topped),
                            "series_added": sum(t["series_added"] for t in topped)}  # fmt: skip
    return result
