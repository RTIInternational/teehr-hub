"""Tests for the mean areal values and pixel coverage weights flows. Needs teehr and pyspark."""
import functools

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box

pytest.importorskip("teehr")
pytest.importorskip("pyspark")
from prefect import flow  # noqa: E402
from prefect.testing.utilities import prefect_test_harness  # noqa: E402
from teehr.fetching.nwm.grid_utils import build_weights_matrix  # noqa: E402
from teehr.utils.concurrency import run_concurrent_map  # noqa: E402

from mean_areal_values import _area_weights, _mean_areal_batch, _written_steps  # noqa: E402
from pixel_coverage_weights import filter_polygons_by_coverage, resolve_grid_name  # noqa: E402
from utils import grid_utils as gu  # noqa: E402
from utils import time_grid as tg  # noqa: E402
from workflows.models.mean_areal_inputs import MeanArealValuesInput  # noqa: E402

TIMES = pd.date_range("2000-01-01", periods=6, freq="D")


def _args(**kwargs):
    return MeanArealValuesInput(
        configuration_name="c", temp_dir_path="/tmp", location_id_prefix="p", grid_variable_name="v",
        dest_bucket="b", base_prefix="p", **kwargs,
    )


def _grid(status):
    return xr.DataArray(np.arange(6.0), dims="time", coords={"time": TIMES, "status": ("time", np.array(status, "int8"))})


def test_skips_unwritten_slots():
    da = _written_steps(_grid([2, -1, 2, 1, -1, 0]), _args())
    assert list(da.time.values) == list(TIMES[[0, 2, 3, 5]].values)


def test_window():
    da = _written_steps(_grid([2] * 6), _args(start_dt="2000-01-02", end_dt="2000-01-04"))
    assert list(da.time.values) == list(TIMES[1:4].values)


def test_repo_without_status_keeps_all_steps():
    da = xr.DataArray(np.arange(6.0), dims="time", coords={"time": TIMES})
    assert da.equals(_written_steps(da, _args()))


def test_defaults_to_upsert():
    assert _args().write_mode == "upsert"


def _lat_lon_grid(values, crs="EPSG:4326"):
    n_time, n_lat, n_lon = values.shape
    da = xr.DataArray(
        values, dims=("time", "lat", "lon"),
        coords={
            "time": pd.date_range("2000-01-01", periods=n_time, freq="D"),
            "lat": np.linspace(30.0, 50.0, n_lat),
            "lon": np.linspace(-110.0, -100.0, n_lon),
        },
    )
    return da.rio.set_spatial_dims(x_dim="lon", y_dim="lat").rio.write_crs(crs)


def test_area_weights_only_scale_geographic_grids():
    weights = pd.DataFrame({"row": [0, 4], "fraction_covered": [1.0, 1.0]})
    values = np.zeros((1, 5, 3))
    geographic = _area_weights(weights, _lat_lon_grid(values), "lat")
    assert geographic.tolist() == pytest.approx(np.cos(np.deg2rad([30.0, 50.0])).tolist())
    projected = _area_weights(weights, _lat_lon_grid(values, crs="EPSG:5070"), "lat")
    assert projected.tolist() == [1.0, 1.0]


def test_concurrent_batches_match_direct_calculation(tmp_path):
    """Shard-aligned batches read concurrently from zarr, with fill values and NaN pixels, match numpy."""
    rng = np.random.default_rng(0)
    values = rng.random((10, 6, 8)).astype("float32")
    values[3, 1, 2] = np.nan  # a's only pixel in row 1: a drops below coverage that step
    values[:, 5, 7] = np.nan  # outside both locations
    grid = _lat_lon_grid(values)
    gu.restore_grid_mapping_attrs(grid.to_dataset(name="v")).to_zarr(
        tmp_path / "grid.zarr", zarr_format=3, encoding={"v": {"chunks": (1, 4, 4), "_FillValue": -9999.0}}
    )
    da = xr.open_zarr(tmp_path / "grid.zarr", decode_coords="all", chunks=None)["v"]
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")

    weights = pd.DataFrame({
        "location_id": ["p-a", "p-a", "p-a", "p-b", "p-b"],
        "row": [0, 0, 1, 0, 4],
        "col": [1, 2, 2, 2, 6],  # pixel (0, 2) is shared
        "fraction_covered": [1.0, 1.0, 0.5, 0.25, 1.0],
    })
    weights["weight"] = _area_weights(weights, da, "lat")
    matrix, rows, cols, location_ids = build_weights_matrix(weights)
    window = (int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1)
    args = _args(x_dim="lon", y_dim="lat", min_valid_coverage=0.9)
    times = da.time.to_index()
    batches = tg.shard_batches(times, times, 4)
    frames = run_concurrent_map(
        functools.partial(
            _mean_areal_batch, da=da, args=args, window=window, rows=rows, cols=cols, matrix=matrix,
            location_ids=location_ids,
        ),
        batches,
        max_workers=len(batches),
    )
    got = pd.concat(frames).set_index(["value_time", "location_id"])["value"]

    cos_lat = np.cos(np.deg2rad(grid.lat.values))
    expected = {}
    for t, time in enumerate(times):
        for loc, group in weights.groupby("location_id"):
            w = group.fraction_covered.to_numpy() * cos_lat[group.row]
            v = values[t, group.row, group.col]
            valid = ~np.isnan(v)
            if w[~valid].sum() <= 0.1 * w.sum():
                expected[(time, loc)] = (w[valid] * v[valid]).sum() / w[valid].sum()
    assert len(got) == len(expected) == 19  # a is NaN on step 3, so dropped
    for key, value in expected.items():
        assert got[key] == pytest.approx(value, rel=1e-6)


@pytest.fixture(scope="module")
def harness():
    with prefect_test_harness():
        yield


def test_coverage_filter_drops_polygon_mostly_outside_grid(harness):
    grid = _lat_lon_grid(np.zeros((1, 5, 5)))[0].rename({"lon": "x", "lat": "y"})
    west, south, east, north = grid.rio.bounds()
    polygons = gpd.GeoDataFrame(
        {"id": ["p-inside", "p-half"]},
        geometry=[box(west + 1, south + 1, west + 2, south + 2), box(west - 1, south + 1, west + 1, south + 2)],
        crs="EPSG:4326",
    )

    @flow
    def run():
        return filter_polygons_by_coverage(polygons, grid, min_coverage=0.9)

    assert run().id.tolist() == ["p-inside"]


def test_grid_name_from_args_then_repo_then_configuration_name(harness):
    import icechunk as ic

    @flow
    def run(stored, grid_name):
        store = ic.Repository.create(ic.in_memory_storage()).writable_session("main").store
        if stored is not None:
            tg.write_grid_attrs(store, {tg.GRID_NAME_ATTR: stored})
        return resolve_grid_name(store, grid_name, "c")

    assert run(None, None) == "c"
    assert run("g", None) == "g"
    assert run(None, "x") == "x"
    assert run("g", "g") == "g"
    with pytest.raises(ValueError):
        run("g", "x")


def test_generated_weights_index_a_lat_lon_grid():
    """Weights generated on a south-to-north lat/lon grid, renamed to x/y, reproduce exactextract's mean."""
    from exactextract import exact_extract
    from teehr.utilities.generate_weights import generate_weights_file

    rng = np.random.default_rng(1)
    # A projected CRS, so no latitude scaling and exactextract's plain mean is the reference
    grid = _lat_lon_grid(rng.random((1, 20, 30)).astype("float32"), crs="EPSG:5070")
    template = grid[0].rename({"lon": "x", "lat": "y"})
    west, south, east, north = template.rio.bounds()
    zones = gpd.GeoDataFrame(
        {"id": ["p-a", "p-b"]},
        geometry=[
            box(west + 1.3, south + 2.1, west + 4.7, south + 9.4),
            box(west + 5.2, south + 11.0, east - 1.1, north - 0.6),
        ],
        crs="EPSG:5070",
    )
    weights = generate_weights_file(
        zone_polygons=zones, template_dataset=template.to_dataset(name="v"), variable_name="v",
        output_weights_filepath=None, crs_wkt=template.rio.crs.to_wkt(), unique_zone_id="id",
    )
    weights = weights.rename(columns={"weight": "fraction_covered"})
    weights["weight"] = _area_weights(weights, grid, "lat")
    matrix, rows, cols, location_ids = build_weights_matrix(weights)
    window = (int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1)
    got = _mean_areal_batch(
        grid.time.to_index(), grid, _args(x_dim="lon", y_dim="lat"), window, rows, cols, matrix, location_ids
    ).set_index("location_id")["value"]

    expected = exact_extract(
        rast=template, vec=zones.rename(columns={"id": "zone"}), ops=["mean"], include_cols=["zone"], output="pandas"
    )
    for row in expected.itertuples():
        assert got[row.zone] == pytest.approx(row.mean, rel=1e-5)
