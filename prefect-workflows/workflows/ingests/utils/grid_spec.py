"""What readers need to know about a gridded Icechunk repo's shape, and its data in a canonical form.

Our repos describe themselves in root attributes; a repo we didn't write is described by an
``override`` (e.g. a registry entry) with the same keys. Readers take the shape from here, never
from dimension names, and address dims by name, never by position.
"""
from dataclasses import dataclass, field

import icechunk as ic
import numpy as np
import xarray as xr

from utils import grid_utils as gu
from utils import time_grid as tg
from workflows.utils.repo_const import (
    APPEND_DIM_ATTR,
    DATA_GROUP_ATTR,
    FIXED_DIMS_ATTR,
    FORECAST_COORD_ATTRS,
    FORECAST_LAYOUT_VERSION,
    GRID_NAME_ATTR,
    LAYOUT_VERSION_ATTR,
    LEAD_TIME,
    VALUE_TIME,
)

# On-disk layouts these readers understand: 1 is the analysis time grid (also when the attribute is
# missing), 2 adds forecast axes. Any other value is refused rather than guessed at.
KNOWN_LAYOUT_VERSIONS = (1, FORECAST_LAYOUT_VERSION)


@dataclass(frozen=True)
class GridSpec:
    append_dim: str
    # Dims after the append dim, e.g. ("member", "lead_time"); empty for analysis repos
    fixed_dims: tuple[str, ...] = ()
    layout_version: int = 1
    data_group: str = "/data"
    grid_name: str | None = None
    # Source dim name -> canonical name, for repos we didn't write
    renames: dict = field(default_factory=dict)


def read_grid_spec(store: ic.IcechunkStore, override: dict | None = None) -> GridSpec:
    """The repo's grid spec from its root attributes, with ``override`` taking precedence."""
    attrs = {**tg.read_root_attrs(store), **(override or {})}
    version = attrs.get(LAYOUT_VERSION_ATTR, 1)
    if version not in KNOWN_LAYOUT_VERSIONS:
        raise ValueError(f"Unknown layout_version {version!r}; this code reads {list(KNOWN_LAYOUT_VERSIONS)}.")
    return GridSpec(
        append_dim=attrs.get(APPEND_DIM_ATTR, "time"),
        fixed_dims=tuple(attrs.get(FIXED_DIMS_ATTR, ())),
        layout_version=version,
        data_group=attrs.get(DATA_GROUP_ATTR) or gu.read_data_group(store),
        grid_name=attrs.get(GRID_NAME_ATTR),
        renames=dict(attrs.get("renames", {})),
    )


def open_grid_dataset(store: ic.IcechunkStore, spec: GridSpec) -> xr.Dataset:
    """The repo's data group with canonical forecast dims, integer-hour ``lead_time`` and a ``value_time``."""
    ds = xr.open_zarr(store, group=spec.data_group, consolidated=False, chunks=None, decode_coords="all")
    ds = ds.rename({k: v for k, v in spec.renames.items() if k in ds.variables})
    lead = LEAD_TIME
    if lead in ds.coords and np.issubdtype(ds[lead].dtype, np.timedelta64):
        hours = ds[lead].values / np.timedelta64(1, "h")
        if not np.array_equal(hours, np.round(hours)):
            raise ValueError(f"{lead} isn't in whole hours: {ds[lead].values[:5]}")
        ds = ds.assign_coords({lead: (lead, hours.astype("int32"), {**ds[lead].attrs, "units": "hours"})})
    if lead in ds.dims and VALUE_TIME not in ds.coords:
        dim = spec.append_dim
        ds = ds.assign_coords({VALUE_TIME: ((dim, lead), tg.value_times(ds[dim].values, ds[lead].values),
                                               FORECAST_COORD_ATTRS[VALUE_TIME])})
    return ds
