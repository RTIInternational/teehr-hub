"""Ingest RFC streamflow forecasts at gauges (NWPS) into a v1 timeseries dataset.

Into ``public.nwpsrfc_streamflow_forecast`` (legacy's configuration name): one dataset for
every RFC forecast, whatever its step (1, 3 or 6 hours; each series' ``resolution`` records the
step of its first forecast). Its series are ``nwpsrfc-<lid>``, with no location layer: the
``usgs_nwpsrfc`` crosswalk pairs them with the USGS gages, as ``usgs_nwm31`` does the NWM
reaches. :mod:`teehr_core.fetch.nwps` fetches each gauge's latest forecast from the NWPS API;
:func:`flows.write.write_rows` writes them.

As the legacy ingest did: the gauges are the crosswalk's, for the USGS gages matching
``where``; a forecast's reference time is one step before its first value; a forecast no newer
than its series' latest stored one is skipped (most gauges' forecasts change a few times a day,
and runs are hourly); a run fails when too many gauges couldn't be fetched. Unlike legacy,
3-hour forecasts and forecasts with missing times are kept (issue #258).
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import pyarrow as pa
from prefect import flow, get_run_logger
from pyiceberg.catalog import Catalog
from pyiceberg.expressions import GreaterThanOrEqual
from teehr_core.fetch import nwps

from flows.catalog import catalog
from flows.ingest_nwm import reaches
from flows.write import write_rows


def latest_forecasts(cat: Catalog, namespace: str, dataset: str,
                     since: datetime) -> dict[str, datetime]:  # fmt: skip
    """Each series' latest stored ``reference_time`` at or after ``since``.

    Parameters
    ----------
    cat : Catalog
        The warehouse catalog.
    namespace, dataset : str
        The forecast dataset.
    since : datetime
        Older forecasts aren't read (a series whose latest is older gets its next one written,
        which is the same).

    Returns
    -------
    dict[str, datetime]
        Series key to its latest reference time (UTC).

    Examples
    --------
    >>> latest_forecasts(cat, "public", "nwpsrfc_streamflow_forecast",
    ...                  datetime(2026, 11, 1, tzinfo=UTC))
    {'nwpsrfc-anaw1': datetime.datetime(2026, 11, 27, 12, 0, tzinfo=datetime.timezone.utc), ...}
    """
    stored = cat.load_table((namespace, dataset)).scan(
        row_filter=GreaterThanOrEqual("reference_time", since.isoformat()),
        selected_fields=("series_key", "reference_time"),
    ).to_arrow()  # fmt: skip
    if not stored.num_rows:
        return {}
    latest = stored.group_by("series_key").aggregate([("reference_time", "max")])
    times = latest["reference_time_max"].cast(pa.timestamp("us", "UTC")).to_pylist()
    return dict(zip(latest["series_key"].to_pylist(), times, strict=True))


@flow(name="ingest-nwps-rfc-streamflow", log_prints=True)
def ingest_nwps_rfc_streamflow(
    dataset: str = "nwpsrfc_streamflow_forecast",
    namespace: str = "public",
    crosswalk: str = "usgs_nwpsrfc",
    observed: str = "usgs_inst_streamflow",
    where: str = "is_active == True and has_inst_discharge == True",
    gauges: list[str] | None = None,
    workers: int = 16,
    lookback_days: float = 30,
    max_failed: float = 0.25,
    commit_rows: int = 1_000_000,
) -> dict[str, Any]:
    """Fetch the gauges' latest RFC forecasts and write the new ones.

    Parameters
    ----------
    dataset, namespace : str
        The forecast dataset.
    crosswalk : str, default "usgs_nwpsrfc"
        Pairs ``observed``'s gages (left) with the RFC gauges (right, ``nwpsrfc-<lid>``).
    observed : str, default "usgs_inst_streamflow"
        The dataset whose location layer holds the USGS gages.
    where : str
        A row filter on the USGS gages' layer: the RFC gauges of the gages matching it.
    gauges : list[str], optional
        RFC gauges (lids or series keys) instead of the crosswalk's.
    workers : int, default 16
        Requests to the NWPS API at once.
    lookback_days : float, default 30
        How far back to read the stored forecasts' reference times (to skip old ones).
    max_failed : float, default 0.25
        The run fails (after writing what it got) when more than this share of the gauges
        couldn't be fetched.
    commit_rows : int, default 1_000_000
        The fewest rows in each commit.

    Returns
    -------
    dict
        ``gauges``, ``forecasts`` (new ones written), ``unchanged``, ``without`` (no flow
        forecast), ``failed``, ``steps`` (forecasts per step) and
        :func:`flows.write.write_rows`' summary.

    Examples
    --------
    Every gauge of an active USGS gage with instantaneous discharge (the schedule's run):

    >>> ingest_nwps_rfc_streamflow()

    Two gauges:

    >>> ingest_nwps_rfc_streamflow(gauges=["ANAW1", "MUTC1"])
    """
    log = get_run_logger()
    cat = catalog()
    keys = ([nwps.series_key(g) for g in gauges] if gauges else
            reaches(cat, namespace, crosswalk, observed, where, nwps.PREFIX))  # fmt: skip
    if not keys:
        raise ValueError(f"no {nwps.PREFIX} gauges in {namespace}.{crosswalk} for {where!r}")
    since = datetime.now(UTC) - timedelta(days=lookback_days)
    latest = latest_forecasts(cat, namespace, dataset, since)
    log.info("NWPS: %d gauges into %s.%s (%d with a forecast since %s)", len(keys), namespace,
             dataset, len(latest), f"{since:%Y-%m-%d}")  # fmt: skip

    new: list[pa.Table] = []
    steps: dict[str, str] = {}
    unchanged, without, failed = 0, 0, []
    for key, got in nwps.forecasts(keys, workers=workers):
        if isinstance(got, Exception):
            failed.append(key)
            log.warning("%s: %s", key, got)
        elif got is None:
            without += 1
        elif key in latest and got.reference_time <= latest[key]:
            unchanged += 1
        else:
            new.append(got.rows)
            steps[key] = nwps.resolution(got.step)
    by_step = dict(sorted(Counter(steps.values()).items()))
    log.info("NWPS: %d new forecasts %s, %d unchanged, %d without a flow forecast, %d failed",
             len(new), by_step, unchanged, without, len(failed))  # fmt: skip

    written = write_rows(cat, namespace, dataset, new, unit=nwps.UNIT,
                         fields_of=lambda key: {"resolution": steps.get(key)},
                         commit_rows=commit_rows)  # fmt: skip
    result = {"gauges": len(keys), "forecasts": len(new), "unchanged": unchanged,
              "without": without, "failed": len(failed), "steps": by_step, **written}  # fmt: skip
    if len(failed) > max_failed * len(keys):
        raise RuntimeError(f"NWPS: {len(failed)} of {len(keys)} gauges failed "
                           f"(more than {max_failed:.0%}), e.g. {failed[:5]}: {result}")  # fmt: skip
    return result
