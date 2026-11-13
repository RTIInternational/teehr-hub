"""Openers of the AORC and dynamical.org mean areal flows, on local stand-ins for their sources."""
import icechunk as ic
import numpy as np
import pandas as pd
import pytest
import xarray as xr

pytest.importorskip("teehr")
from obstore.store import LocalStore  # noqa: E402
from prefect import flow  # noqa: E402
from prefect.testing.utilities import prefect_test_harness  # noqa: E402

import aorc_mean_areal_values as aorc  # noqa: E402
import dynamical_mean_areal_values as dyn  # noqa: E402
from workflows.models.external_grid_inputs import AORCMeanArealInput, DynamicalMeanArealInput  # noqa: E402
from workflows.utils import repo_const as rc  # noqa: E402

COMMON = dict(temp_dir_path="/tmp", location_id_prefix="huc10", dest_bucket="b", base_prefix="p")


@pytest.fixture(scope="module")
def harness():
    with prefect_test_harness():
        yield


@pytest.fixture
def aorc_year(tmp_path, monkeypatch):
    """A 2021 store laid out like NOAA's: Zarr v2, int16 with a scale_factor, chunked in time."""
    raw = np.arange(10 * 4 * 5, dtype="int16").reshape(10, 4, 5)
    ds = xr.Dataset(
        {"APCP_surface": (("time", "latitude", "longitude"), raw,
                          {"scale_factor": 0.1, "units": "kg/m^2", "long_name": "Total Precipitation"})},
        coords={
            "time": pd.date_range("2021-01-01", periods=10, freq="h"),
            "latitude": np.linspace(25.0, 25.03, 4), "longitude": np.linspace(-125.0, -124.96, 5),
        },
    )
    ds.APCP_surface.encoding = {"chunks": (6, 2, 5), "dtype": "int16"}
    ds.to_zarr(tmp_path / "2021.zarr", zarr_format=2, consolidated=True)
    # An empty directory for missing years, so a head reports the object missing as S3 does
    monkeypatch.setattr(aorc, "_year_store", lambda year: LocalStore(tmp_path / f"{year}.zarr", mkdir=True))
    return raw


def test_aorc_year_decodes_lazily_to_float32_with_crs(aorc_year):
    da = aorc.open_aorc_year(2021, "APCP_surface")
    assert da.dtype == np.float32
    assert da.encoding["chunks"] == (6, 2, 5)  # the read plan follows the stored chunks
    assert da.rio.crs.to_epsg() == 4326
    np.testing.assert_allclose(da.isel(time=7).values, aorc_year[7] * 0.1, rtol=1e-6)


def test_aorc_known_variable_gets_teehr_names_unless_set():
    teehr_names = ("rainrate_hourly_mean", "mm/s", 1 / 3600)
    args = aorc.with_teehr_names(AORCMeanArealInput(**COMMON))
    assert (args.variable_name, args.unit_name, args.value_scale) == teehr_names
    # As Prefect's run form sends them: every field, defaults included
    form = aorc.with_teehr_names(AORCMeanArealInput(**COMMON, variable_name=None, unit_name=None, value_scale=1.0))
    assert (form.variable_name, form.unit_name, form.value_scale) == teehr_names
    kept = aorc.with_teehr_names(
        AORCMeanArealInput(**COMMON, variable_name="rainrate_hourly_mean", unit_name="mm/hr", value_scale=1.0)
    )
    assert (kept.unit_name, kept.value_scale) == ("mm/hr", 1.0)
    with pytest.raises(ValueError, match="unit_name"):
        aorc.with_teehr_names(AORCMeanArealInput(**COMMON, variable_name="rainrate_hourly_mean"))
    with pytest.raises(ValueError, match="variable_name"):
        aorc.with_teehr_names(AORCMeanArealInput(**COMMON, unit_name="mm/hr"))
    with pytest.raises(ValueError, match="variable_name"):
        aorc.with_teehr_names(AORCMeanArealInput(**COMMON, grid_variable_name="TMP_2maboveground"))


def test_aorc_available_years_skip_missing_stores(aorc_year, harness):
    @flow
    def run():
        return aorc.available_years(2020, 2022)
    assert run() == [2021]


def test_dynamical_repo_opens_with_canonical_dims(tmp_path, monkeypatch, harness):
    """A GEFS-like repo (init_time, ensemble_member, timedelta lead_time) opens with canonical forecast dims."""
    shape = (2, 3, 4, 3, 5)
    ds = xr.Dataset(
        {"precipitation_surface": (("init_time", "ensemble_member", "lead_time", "latitude", "longitude"),
                                   np.random.default_rng(0).random(shape).astype("float32"), {"units": "kg m-2 s-1"})},
        coords={
            "init_time": pd.date_range("2026-10-01", periods=2, freq="D"),
            "ensemble_member": np.arange(3),
            "lead_time": pd.to_timedelta([0, 3, 6, 9], unit="h"),
            "latitude": [40.0, 39.75, 39.5], "longitude": np.linspace(-100.0, -99.0, 5),
        },
    ).rio.write_crs("EPSG:4326")
    repo = ic.Repository.create(ic.local_filesystem_storage(str(tmp_path / "repo")))
    session = repo.writable_session("main")
    ds.precipitation_surface.encoding["chunks"] = (1, 3, 2, 3, 5)
    ds.to_zarr(session.store, zarr_format=3, consolidated=False)
    session.commit("gefs-like")

    monkeypatch.setattr(dyn, "resolve_stac_icechunk", lambda url, asset: ("bucket", "prefix"))
    monkeypatch.setattr(dyn.ic, "s3_storage", lambda **kwargs: ic.local_filesystem_storage(str(tmp_path / "repo")))
    args = DynamicalMeanArealInput(
        **COMMON, configuration_name="gefs", grid_variable_name="precipitation_surface",
        stac_collection_url="https://example.org/collection.json", grid_name="gefs_test",
    )

    @flow
    def run():
        return dyn.open_dynamical_grid(args)
    da, spec = run()
    assert da.dims == (rc.REFERENCE_TIME, rc.MEMBER, rc.LEAD_TIME, "latitude", "longitude")
    assert spec.fixed_dims == (rc.MEMBER, rc.LEAD_TIME) and spec.data_group == "/"
    assert da[rc.LEAD_TIME].values.tolist() == [0, 3, 6, 9]
    assert da.encoding["chunks"] == (1, 3, 2, 3, 5)
    assert da.rio.crs.to_epsg() == 4326
