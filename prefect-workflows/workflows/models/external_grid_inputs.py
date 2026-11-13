"""Inputs of the mean areal and weights flows for grids read in place from outside sources (hub only)."""
from typing import Optional

from pydantic import Field

from workflows.models.mean_areal_inputs import MeanArealValuesInput
from workflows.utils import repo_const as rc


class AORCMeanArealInput(MeanArealValuesInput):
    """AORC v1.1 1 km forcing from NOAA's yearly Zarr stores (s3://noaa-nws-aorc-v1-1-1km)."""

    configuration_name: str = Field("aorc_v1_1", description="teehr configuration the values are written under")
    grid_variable_name: str = Field(
        "APCP_surface",
        description=(
            "AORC variable, e.g. APCP_surface. APCP_surface defaults to rainrate_hourly_mean in mm/s; set "
            "variable_name, unit_name and value_scale for the others"
        )
    )
    grid_name: Optional[str] = Field("aorc_v1_1_1km_conus", description="Grid the weights index")
    x_dim: str = "longitude"
    y_dim: str = "latitude"
    timeseries_table_name: str = "primary_timeseries"
    template_year: int = Field(2020, description="Year whose store is the weights template (all years share the grid)")


class DynamicalMeanArealInput(MeanArealValuesInput):
    """A dynamical.org Icechunk collection (e.g. GEFS), found through its STAC record."""

    stac_collection_url: str = Field(
        ..., description="STAC collection, e.g. https://stac.dynamical.org/noaa-gefs-forecast-35-day/collection.json"
    )
    asset: str = Field("icechunk", description="STAC asset holding the repo's s3:// href")
    region: str = Field("us-west-2", description="Region of the repo's bucket")
    endpoint_url: Optional[str] = Field(
        default=None,
        description=(
            "S3 endpoint for the repo, e.g. https://s3.dualstack.us-west-2.amazonaws.com so cross-region reads "
            "use IPv6 egress instead of the NAT gateway"
        )
    )
    branch: str = Field("main", description="Repo branch to read")
    grid_name: str = Field(..., description="Grid the weights index, e.g. gefs_0p25_global")
    num_lookback_days: Optional[int] = Field(
        default=None,
        gt=0,
        description="When start_dt isn't set, compute cycles from this many days ago (scheduled runs)"
    )
    append_dim: str = Field(rc.REFERENCE_TIME, description="The repo's append dim after renames")
    fixed_dims: list[str] = Field(
        [rc.MEMBER, rc.LEAD_TIME], description="The repo's dims after the append dim, after renames"
    )
    renames: dict[str, str] = Field(
        {"init_time": rc.REFERENCE_TIME, "ensemble_member": rc.MEMBER, "valid_time": rc.VALUE_TIME},
        description="Source names -> canonical names"
    )
    x_dim: str = "longitude"
    y_dim: str = "latitude"
    timeseries_table_name: str = "secondary_timeseries"
