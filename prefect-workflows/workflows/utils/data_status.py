"""Per-timestep data status, stored as a CF ``status_flag`` ancillary variable."""
import numpy as np
import xarray as xr

from workflows.utils.repo_const import STATUS_ATTRS, STATUS_COORD, STATUS_MEANINGS


def with_status(ds: xr.Dataset, status: str, dim: str = "time") -> xr.Dataset:
    """Flag every step of ``ds`` along ``dim`` with ``status``, linked from each data variable."""
    flag = xr.DataArray(
        np.full(ds.sizes[dim], STATUS_MEANINGS.index(status), dtype="int8"), dims=dim, attrs=STATUS_ATTRS
    )
    ds = ds.assign_coords({STATUS_COORD: flag})
    for var in ds.data_vars:
        if dim in ds[var].dims:
            ds[var].attrs["ancillary_variables"] = STATUS_COORD
    return ds
