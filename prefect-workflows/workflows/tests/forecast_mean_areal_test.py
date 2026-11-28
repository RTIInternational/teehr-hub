"""Mean areal values of forecast grids: written steps, batches of (cycle, [member], lead) maps, and output columns."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

pytest.importorskip("teehr")
from teehr_icechunk.weights import build_weights_matrix  # noqa: E402

from mean_areal_values import _window  # noqa: E402
from teehr_icechunk.mean_areal_plan import area_weights, written_forecast_steps  # noqa: E402
from teehr_icechunk import grid_utils as gu  # noqa: E402
from teehr_icechunk import time_grid as tg  # noqa: E402
from teehr_icechunk.mean_areal_kernel import GridWeights  # noqa: E402
from workflows.models.mean_areal_inputs import MeanArealValuesInput  # noqa: E402
from teehr_icechunk import repo_const as rc  # noqa: E402

DIM = rc.REFERENCE_TIME
CYCLES = pd.date_range("2026-10-01", periods=3, freq="6h")
MEMBERS, LEADS = [0, 1], [1, 2, 3, 6]


def _written_forecast_steps(da, args, fixed):
    """The flow's written forecast steps for its run window."""
    return written_forecast_steps(da, args.append_dim, fixed, *_window(args))


def _args(**kwargs):
    return MeanArealValuesInput(
        configuration_name="c", temp_dir_path="/tmp", location_id_prefix="p", grid_variable_name="v",
        dest_bucket="b", base_prefix="p", append_dim=DIM, x_dim="lon", y_dim="lat", **kwargs,
    )


def _forecast_grid(tmp_path, ensemble=True):
    """A zarr-backed forecast grid on lat/lon; returns the lazily opened DataArray, its values and fixed axes."""
    fixed = {rc.MEMBER: MEMBERS, rc.LEAD_TIME: LEADS} if ensemble else {rc.LEAD_TIME: LEADS}
    dims = (DIM, *fixed, "lat", "lon")
    shape = (len(CYCLES), *(len(v) for v in fixed.values()), 5, 6)
    values = np.random.default_rng(0).random(shape).astype("float32")
    status = np.full(shape[:-2], 2, "int8")
    status[1, ..., -1] = rc.UNWRITTEN
    status[2, ..., 0] = rc.NOT_EXPECTED
    da = xr.DataArray(
        values, dims=dims,
        coords={DIM: CYCLES, **{d: np.asarray(v, "int32") for d, v in fixed.items()},
                "lat": np.linspace(30.0, 34.0, 5), "lon": np.linspace(-100.0, -95.0, 6),
                rc.STATUS_COORD: (dims[:-2], status)},
    ).rio.set_spatial_dims(x_dim="lon", y_dim="lat").rio.write_crs("EPSG:4326")
    gu.restore_grid_mapping_attrs(da.to_dataset(name="v")).to_zarr(
        tmp_path / "grid.zarr", zarr_format=3, encoding={"v": {"chunks": (1, *(1 for _ in fixed), 5, 6)}}
    )
    opened = xr.open_zarr(tmp_path / "grid.zarr", decode_coords="all", chunks=None)["v"]
    return opened.rio.set_spatial_dims(x_dim="lon", y_dim="lat"), values, fixed


def test_written_forecast_steps_skip_unwritten_and_not_expected(tmp_path):
    da, _, fixed = _forecast_grid(tmp_path)
    steps = _written_forecast_steps(da, _args(), fixed)
    assert steps.names == [DIM, rc.MEMBER, rc.LEAD_TIME]
    assert len(steps) == 3 * 2 * 4 - 2 - 2  # cycle 1 lead 6 unwritten, cycle 2 lead 1 not expected, both members
    assert (CYCLES[1], 0, 6) not in steps and (CYCLES[2], 1, 1) not in steps
    windowed = _written_forecast_steps(da, _args(start_dt=CYCLES[1].isoformat(), end_dt=CYCLES[1].isoformat()), fixed)
    assert set(windowed.get_level_values(DIM)) == {CYCLES[1]} and len(windowed) == 6


@pytest.mark.parametrize("ensemble", [True, False])
def test_forecast_batch_means_and_columns(tmp_path, ensemble, batch_means):
    da, values, fixed = _forecast_grid(tmp_path, ensemble)
    weights = pd.DataFrame({
        "location_id": ["p-a", "p-a", "p-b"], "row": [0, 1, 3], "col": [1, 1, 4], "fraction_covered": [1.0, 0.5, 1.0],
    })
    weights["weight"] = area_weights(weights, da, "lat")
    grid_weights = GridWeights(*build_weights_matrix(weights))
    args = _args()
    steps = _written_forecast_steps(da, args, fixed)
    # Shards of 2 leads, batches of up to 4 steps: leads are not contiguous within some batches
    frames = [
        batch_means(batch, da, args, grid_weights, fixed)
        for batch in tg.step_batches(steps, fixed, shard_leads=2, max_steps=4)
    ]
    df = pd.concat(frames, ignore_index=True)
    assert len(df) == len(steps) * 2

    cos_lat = np.cos(np.deg2rad(da.lat.values))
    for step in steps:
        cycle, lead = step[0], step[-1]
        member = step[1] if ensemble else None
        index = (list(CYCLES).index(cycle), *([MEMBERS.index(member)] if ensemble else []), LEADS.index(lead))
        rows_for = df[(df.reference_time == cycle) & (df.value_time == cycle + pd.Timedelta(hours=lead))]
        if ensemble:
            rows_for = rows_for[rows_for.member == str(member)]
        for loc, group in weights.groupby("location_id"):
            w = group.fraction_covered.to_numpy() * cos_lat[group.row]
            expected = (w * values[index][group.row, group.col]).sum() / w.sum()
            assert rows_for.set_index("location_id").loc[loc, "value"] == pytest.approx(expected, rel=1e-6)
    assert ("member" in df) == ensemble


def test_forecast_values_default_to_secondary_timeseries():
    assert _args().timeseries_table_name == "secondary_timeseries"


def test_child_segments_stage_the_parents_steps(tmp_path):
    """A child reworks its segment from the grid, clipped to the run's window, and stages exactly the parent's
    steps of that segment, in the table's columns."""
    import pyarrow as pa
    from teehr_icechunk import zonal
    from teehr_icechunk.grid_spec import GridSpec
    from mean_areal_values import compute_segment, zonal_work
    from workflows.utils.teehr_mapping import MM_PER_S, RAINRATE_HOURLY_MEAN, TeehrMapping

    da, _, fixed = _forecast_grid(tmp_path)
    weights = pd.DataFrame({"location_id": ["p-a", "p-b"], "row": [0, 3], "col": [1, 4], "fraction_covered": [1.0, 1.0]})
    weights["weight"] = area_weights(weights, da, "lat")
    staging = tmp_path / "staging"
    staging.mkdir()
    zonal.save_weights(staging / zonal.WEIGHTS_FILE, GridWeights(*build_weights_matrix(weights)))
    timestamp = pa.timestamp("us", tz="UTC")
    zonal.save_schema(staging / zonal.SCHEMA_FILE, pa.schema([
        ("reference_time", timestamp), ("value_time", timestamp), ("value", pa.float32()), ("unit_name", pa.string()),
        ("location_id", pa.string()), ("member", pa.string()), ("configuration_name", pa.string()),
        ("variable_name", pa.string()),
    ]))
    spec = GridSpec(append_dim=DIM, fixed_dims=tuple(fixed))
    mapping = TeehrMapping(MM_PER_S, RAINRATE_HOURLY_MEAN)
    # The run ends at the second cycle, but its one segment holds all three
    args = _args(end_dt=CYCLES[1].isoformat(), segment_steps=3)

    parent = zonal_work(da, spec, args, mapping, str(staging), "mean_areal_values", *_window(args))
    [segment] = zonal.plan_zonal_segments(da, parent.written, DIM, args.segment_steps)
    assert segment.end == CYCLES[2]
    assert parent.parameters(segment) == {"stage": "mean_areal_values", "args": args.model_dump(mode="json"),
                                          "staging_dir": str(staging), "segment": segment.to_dict()}

    compute_segment(da, spec, args, mapping, segment.to_dict(), str(staging), "mean_areal_values")
    staged = pd.read_parquet(zonal.segment_dir(staging, segment))
    assert len(staged) == len(parent.written) * 2
    assert set(staged.reference_time.dt.tz_localize(None)) == {CYCLES[0], CYCLES[1]}
    assert set(staged.variable_name) == {"rainrate_hourly_mean"} and set(staged.unit_name) == {"mm/s"}
