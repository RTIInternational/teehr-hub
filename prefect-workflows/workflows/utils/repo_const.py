"""Names and values our gridded Icechunk repos store, which everything reading them relies on.

This is the repos' on-disk contract. Changing a value breaks existing repos and their readers:
these flows, teehr-cloud-core's xpublish provider (which keeps its own copies) and outside users.
Add new names here; change an existing one only together with a migration of existing repos.
Described for other developers in teehr-cloud-core's docs/gridded-repo-contract.md.
"""
import numpy as np

# --- Root group attributes ---
# The time grid: append axis, its first slot and its step
APPEND_DIM_ATTR = "append_dim"
TIME_ORIGIN_ATTR = "time_origin"
TIME_STEP_ATTR = "time_step"
GRID_ATTRS = (APPEND_DIM_ATTR, TIME_ORIGIN_ATTR, TIME_STEP_ATTR)
# Repos with the same grid_name are pixel-aligned; it keys the pixel coverage weights
GRID_NAME_ATTR = "grid_name"
# The group readers use: DATA_GROUP_PATH or REFERENCES_GROUP_PATH
DATA_GROUP_ATTR = "data_group"
# The teehr configuration the repo holds, and its timeseries table ("primary" or "secondary")
CONFIGURATION_NAME_ATTR = "configuration_name"
TIMESERIES_TYPE_ATTR = "timeseries_type"
# Dims after the append dim, in order, e.g. ["member", "lead_time"]; missing means none (analysis)
FIXED_DIMS_ATTR = "fixed_dims"
# On-disk layout: 1 is the analysis time grid, 2 adds fixed axes (forecasts); missing means 1.
# Bump it for a change existing readers can't handle.
LAYOUT_VERSION_ATTR = "layout_version"
FORECAST_LAYOUT_VERSION = 2

# --- Groups ---
# Virtual references to the source files; always written
REFERENCES_GROUP_PATH = "/references"
# Materialized copy of the references; also the data group of repos without DATA_GROUP_ATTR
DATA_GROUP_PATH = "/data"
# Coarser levels of the data group, one subgroup per block size, e.g. /overviews/2
OVERVIEW_GROUP_PATH = "/overviews"

# --- Per-step coordinates ---
# Data status, a CF status_flag ancillary variable; ordered worst to best, so a higher value is more final
STATUS_COORD = "status"
STATUS_MEANINGS = ["early", "provisional", "stable"]
STATUS_ATTRS = {
    "standard_name": "status_flag",
    "long_name": "data status",
    "flag_values": np.arange(len(STATUS_MEANINGS), dtype="int8"),
    "flag_meanings": " ".join(STATUS_MEANINGS),
}
# Status of a time-grid slot not yet written
UNWRITTEN = -1
# Status of a forecast step the source never publishes, e.g. leads past a member's horizon
NOT_EXPECTED = -2
# Forecast repos also name the slot states in the flags, so outside readers can interpret them
FORECAST_STATUS_ATTRS = {
    **STATUS_ATTRS,
    "flag_values": np.arange(NOT_EXPECTED, len(STATUS_MEANINGS), dtype="int8"),
    "flag_meanings": " ".join(["not_expected", "unwritten", *STATUS_MEANINGS]),
}
# When each slot was first written, last written, and its source file's last modified time
AUDIT_COORDS = ("created_at", "updated_at", "source_last_modified")
STEP_COORDS = (STATUS_COORD, *AUDIT_COORDS)

# --- Forecast coordinates ---
# Forecast repos append along reference_time; member (ensembles only) and lead_time are fixed axes
REFERENCE_TIME = "reference_time"
MEMBER = "member"
LEAD_TIME = "lead_time"
# Reference time plus lead time, a 2-D coordinate on (reference_time, lead_time)
VALUE_TIME = "value_time"
# CF meaning of the forecast coordinates; variable names stay teehr's. In CF the T axis is valid
# time, so reference_time gets no axis.
FORECAST_COORD_ATTRS = {
    REFERENCE_TIME: {"standard_name": "forecast_reference_time", "long_name": "forecast reference time"},
    MEMBER: {"standard_name": "realization", "long_name": "ensemble member", "units": "1"},
    LEAD_TIME: {"standard_name": "forecast_period", "long_name": "forecast lead time", "units": "hours"},
    VALUE_TIME: {"standard_name": "time", "long_name": "valid time"},
}
