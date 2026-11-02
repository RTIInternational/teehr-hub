"""Names and values our gridded IceChunk repos store, which everything reading them relies on.

This is the repos' on-disk contract. Changing a value breaks existing repos and their readers:
these flows, teehr-cloud-core's xpublish provider (which keeps its own copies) and outside users.
Add new names here; change an existing one only together with a migration of existing repos.
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
# When each slot was first written, last written, and its source file's last modified time
AUDIT_COORDS = ("created_at", "updated_at", "source_last_modified")
STEP_COORDS = (STATUS_COORD, *AUDIT_COORDS)
