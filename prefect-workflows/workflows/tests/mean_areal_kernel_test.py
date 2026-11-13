"""Mean areal values read one grid block at a time, and the Spark task runner shipped to executors."""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest
import xarray as xr

pytest.importorskip("teehr")
from teehr.fetching.nwm.grid_utils import build_weights_matrix, weighted_average_from_matrix  # noqa: E402

from utils import mean_areal_kernel  # noqa: E402
from utils.mean_areal_kernel import (  # noqa: E402
    BlockTask, GridWeights, arrow_task_runner, mean_areal_block, run_block_task,
)

PREFECT_WORKFLOWS = Path(__file__).resolve().parents[2]


def _weights(n_rows: int, n_cols: int) -> pd.DataFrame:
    """Three zones over overlapping, partly covered pixels."""
    rng = np.random.default_rng(1)
    frames = []
    for zone, (r0, r1, c0, c1) in {"z-a": (0, 4, 0, 3), "z-b": (2, 7, 2, 6), "z-c": (5, n_rows, 1, n_cols)}.items():
        rows, cols = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing="ij")
        frames.append(pd.DataFrame({
            "location_id": zone,
            "row": rows.ravel(),
            "col": cols.ravel(),
            "weight": rng.uniform(0.2, 1.0, rows.size).astype("float32"),
        }))
    return pd.concat(frames, ignore_index=True)


@pytest.fixture
def lazy_grid(tmp_path):
    """A (member, time, y, x) grid with NaNs, stored chunked and opened lazily."""
    rng = np.random.default_rng(0)
    data = rng.random((2, 6, 9, 7)).astype("float32")
    data[0, 2, 3, 2] = np.nan
    data[1, :, 6:, 4:] = np.nan
    ds = xr.Dataset(
        {"p": (("member", "time", "y", "x"), data)},
        coords={"time": pd.date_range("2020-01-01", periods=6, freq="h")},
    )
    ds.p.encoding = {"chunks": (1, 3, 3, 4)}
    ds.to_zarr(tmp_path / "g.zarr", zarr_format=3, consolidated=False)
    return data, xr.open_zarr(tmp_path / "g.zarr", consolidated=False, chunks=None).p


def _expected(data, weights_df, min_coverage):
    matrix, rows, cols, location_ids = build_weights_matrix(weights_df)
    flat = data.reshape(-1, data.shape[-2], data.shape[-1])
    means = weighted_average_from_matrix(matrix, flat[:, rows, cols], min_coverage)
    return GridWeights(matrix, rows, cols, location_ids), means


@pytest.mark.parametrize("band_edges, max_slice_steps", [
    (None, 256),          # one band, one slice
    ([0, 3, 6, 9], 256),  # bands on chunk rows
    ([0, 3, 6, 9], 5),    # bands and step slices not dividing the steps
])
def test_block_matches_full_read(lazy_grid, band_edges, max_slice_steps):
    """Banded, sliced reads give the same means as reading everything at once."""
    data, da = lazy_grid
    weights, means = _expected(data, _weights(9, 7), 0.5)
    steps = pd.MultiIndex.from_product([range(2), da.time.values], names=["member", "time"])

    table = mean_areal_block(
        da, weights, "y", "x",
        step_columns={
            "member": steps.get_level_values("member").astype(str).values,
            "value_time": steps.get_level_values("time").values,
        },
        band_edges=band_edges,
        max_slice_steps=max_slice_steps,
        min_coverage=0.5,
    )
    got = table.to_pandas().set_index(["member", "value_time", "location_id"])["value"]
    expected = pd.Series(
        means.ravel(),
        index=pd.MultiIndex.from_arrays([
            np.repeat(steps.get_level_values("member").astype(str), 3),
            np.repeat(steps.get_level_values("time"), 3),
            np.tile(weights.location_ids, len(steps)),
        ], names=got.index.names),
    ).dropna()
    assert not got.index.duplicated().any()
    pd.testing.assert_series_equal(got.sort_index(), expected.sort_index(), check_names=False, rtol=1e-6)


def test_block_scale_constants_and_schema(lazy_grid):
    """Means are converted, constants added, and columns cast to the schema."""
    data, da = lazy_grid
    block = da.isel(member=0, time=slice(0, 3))
    weights, means = _expected(data[0, :3], _weights(9, 7), 1.0)
    schema = pa.schema([
        pa.field("reference_time", pa.timestamp("us"), nullable=True),
        pa.field("value_time", pa.timestamp("us"), nullable=False),
        pa.field("value", pa.float32(), nullable=False),
        pa.field("variable_name", pa.string(), nullable=False),
        pa.field("location_id", pa.string(), nullable=False),
    ])
    table = mean_areal_block(
        block, weights, "y", "x",
        step_columns={"value_time": block.time.values},
        scale=3600.0, offset=1.0,
        constants={"variable_name": "rainrate"},
        schema=schema,
    )
    assert table.schema == schema
    assert table["reference_time"].null_count == table.num_rows
    assert set(table["variable_name"].to_pylist()) == {"rainrate"}
    np.testing.assert_allclose(
        np.sort(table["value"].to_numpy()), np.sort(means[~np.isnan(means)] * 3600.0 + 1.0), rtol=1e-6,
    )


def test_block_rejects_misaligned_step_columns(lazy_grid):
    """Step columns must describe every step of the block."""
    _, da = lazy_grid
    weights, _ = _expected(np.zeros((1, 9, 7)), _weights(9, 7), 1.0)
    with pytest.raises(ValueError, match="step_columns"):
        mean_areal_block(da.isel(member=0), weights, "y", "x", step_columns={"value_time": da.time.values[:2]})


def test_arrow_task_runner_runs_where_workflows_is_not_importable(lazy_grid, tmp_path):
    """The mapInArrow function, pickled as the mean areal flow ships it, runs in a process that can't import our code."""
    pytest.importorskip("pyspark")
    from pyspark import cloudpickle

    data, da = lazy_grid
    weights, _ = _expected(data, _weights(9, 7), 0.5)
    tasks = [
        BlockTask(
            selection={"member": [m], "time": slice(t, t + 3)},
            step_columns={"value_time": da.time.values[t:t + 3], "member": np.full(3, str(m))},
        )
        for m in range(2) for t in (0, 3)
    ]
    runner = arrow_task_runner(tasks, da, weights, y_dim="y", x_dim="x", min_coverage=0.5)
    # As the mean areal flow does
    cloudpickle.register_pickle_by_value(mean_areal_kernel)
    (tmp_path / "runner.pkl").write_bytes(cloudpickle.dumps(runner))

    # Like an executor: the same libraries, but not prefect-workflows on the path
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p and not p.startswith(str(PREFECT_WORKFLOWS))
    )
    child = (
        "import pickle, sys, pyarrow as pa\n"
        "runner = pickle.loads(open(sys.argv[1], 'rb').read())\n"
        "inputs = [pa.record_batch({'task': [0, 1]}), pa.record_batch({'task': [2, 3]})]\n"
        "pa.parquet.write_table(pa.Table.from_batches(list(runner(iter(inputs)))), sys.argv[2])\n"
        "assert not any(m == 'utils' or m.startswith(('utils.', 'workflows')) for m in sys.modules)\n"
    )
    subprocess.run(
        [sys.executable, "-c", "import pyarrow.parquet\n" + child, str(tmp_path / "runner.pkl"),
         str(tmp_path / "out.parquet")],
        cwd=tmp_path, env=env, check=True,
    )
    got = pd.read_parquet(tmp_path / "out.parquet")

    expected = pd.concat([
        run_block_task(task, da, weights, y_dim="y", x_dim="x", min_coverage=0.5).to_pandas() for task in tasks
    ], ignore_index=True)
    pd.testing.assert_frame_equal(got, expected)
