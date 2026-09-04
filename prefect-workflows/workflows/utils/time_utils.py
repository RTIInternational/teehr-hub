"""Shared datetime handling for the ingest flows."""
from datetime import datetime, UTC
from typing import Union

import pandas as pd


def to_naive_utc(
    dt: Union[str, datetime, pd.Timestamp, None]
) -> datetime:
    """Normalize a flow datetime argument to a tz-naive UTC datetime.

    The Prefect UI sends datetimes as ISO strings that usually carry an offset,
    and ``datetime.fromisoformat`` keeps it. TEEHR's fetching code compares
    those values against tz-naive pandas Periods, so anything tz-aware raises
    "Cannot compare tz-naive and tz-aware timestamps". Offsets are converted to
    UTC rather than dropped.

    Parameters
    ----------
    dt : Union[str, datetime, pd.Timestamp, None]
        The value to normalize. None means now.

    Returns
    -------
    datetime
        A tz-naive datetime in UTC.
    """
    if dt is None:
        return datetime.now(UTC).replace(tzinfo=None)

    ts = pd.Timestamp(dt)
    if ts.tz is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()
