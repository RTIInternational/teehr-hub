"""Read plans from a grid's storage chunks, ensemble blocks, write groups and replace conditions."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

pytest.importorskip("teehr")
from prefect import flow  # noqa: E402
from prefect.testing.utilities import prefect_test_harness  # noqa: E402

from mean_areal_values import (  # noqa: E402
    _block_tasks, _cycle_batches, _write_groups, plan_reads, replace_filters,
)
from pixel_coverage_weights import like_prefix  # noqa: E402
from workflows.models.mean_areal_inputs import MeanArealValuesInput  # noqa: E402
from workflows.utils import repo_const as rc  # noqa: E402

TIMES = pd.date_range("2020-01-01", periods=20, freq="h")
CYCLES = pd.date_range("2026-10-01", periods=2, freq="6h")
MEMBERS, LEADS = [0, 1, 2], [0, 3, 6, 9, 12]


def _args(**kwargs):
    return MeanArealValuesInput(
        configuration_name="c", temp_dir_path="/tmp", location_id_prefix="huc_10", grid_variable_name="v",
        dest_bucket="b", base_prefix="p", x_dim="x", y_dim="y", **kwargs,
    )


def _analysis(chunks, shards=None):
    da = xr.DataArray(
        np.zeros((len(TIMES), 40, 30), "float32"), dims=("time", "y", "x"), coords={"time": TIMES}
    )
    da.encoding = {"chunks": chunks, **({"shards": shards} if shards else {})}
    return da


def _forecast(member_chunk):
    shape = (len(CYCLES), len(MEMBERS), len(LEADS), 8, 8)
    da = xr.DataArray(
        np.zeros(shape, "float32"), dims=(rc.REFERENCE_TIME, rc.MEMBER, rc.LEAD_TIME, "y", "x"),
        coords={rc.REFERENCE_TIME: CYCLES, rc.MEMBER: MEMBERS, rc.LEAD_TIME: LEADS},
    )
    da.encoding = {"chunks": (1, member_chunk, 2, 4, 4)}
    return da


@pytest.fixture(scope="module")
def harness():
    with prefect_test_harness():
        yield


def _plan(*plan_args, **plan_kwargs):
    @flow
    def run():
        return plan_reads(*plan_args, **plan_kwargs)
    return run()


PIXELS = (np.array([3, 10, 25, 38]), np.array([2, 9, 20, 28]))


def test_analysis_batches_hold_whole_chunks_and_prefer_shards(harness):
    """Batches are whole 6-step chunks from the axis start, rounded to whole 12-step shards when they fit."""
    plan = _plan(_analysis((6, 8, 8), (12, 8, 8)), _args(), TIMES, {}, *PIXELS, n_zones=4)
    starts = [TIMES.get_loc(batch[0]) for batch in plan.batches]
    assert all(start % 12 == 0 for start in starts)
    assert plan.chunk_shape == (8, 8)


def test_sparse_pixels_get_bigger_batches(harness):
    """Batches are sized by the largest read, so pixels in a few chunks allow more steps than pixels in every chunk."""
    def steps_per_batch(rows, cols):
        plan = _plan(_analysis((2, 8, 8)), _args(task_memory_gb=2e-5), TIMES, {}, rows, cols, n_zones=4)
        assert all(len(batch) % 2 == 0 or batch[-1] == TIMES[-1] for batch in plan.batches)
        return max(len(batch) for batch in plan.batches)

    dense = np.meshgrid(np.arange(0, 40, 4), np.arange(0, 32, 4), indexing="ij")
    assert steps_per_batch(*PIXELS) > steps_per_batch(dense[0].ravel(), dense[1].ravel())


def test_members_in_one_chunk_are_batched_and_read_together(harness):
    """With every member in one chunk, a batch is a cycle's block of leads across all members, read as one block."""
    da = _forecast(member_chunk=len(MEMBERS))
    fixed = {rc.MEMBER: np.array(MEMBERS), rc.LEAD_TIME: np.array(LEADS)}
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS], names=[rc.REFERENCE_TIME, *fixed])
    batches = _cycle_batches(steps, fixed, lead_steps=2)
    assert len(batches) == len(CYCLES) * 3  # lead blocks [0, 3], [6, 9], [12]
    assert all(set(b.get_level_values(rc.MEMBER)) == set(MEMBERS) for b in batches)

    tasks = _block_tasks(batches[0], da, rc.REFERENCE_TIME, fixed)
    assert len(tasks) == 1
    assert tasks[0].selection[rc.MEMBER] == slice(0, 3)
    assert list(tasks[0].step_columns["member"]) == ["0", "0", "1", "1", "2", "2"]

    plan = _plan(da, _args(), steps, fixed, np.array([1, 6]), np.array([1, 6]), n_zones=2)
    assert all(set(b.get_level_values(rc.MEMBER)) == set(MEMBERS) for b in plan.batches)


def test_members_chunked_separately_may_be_split(harness):
    """With one member per chunk, a one-unit budget gives batches of one member's lead chunk."""
    da = _forecast(member_chunk=1)
    fixed = {rc.MEMBER: np.array(MEMBERS), rc.LEAD_TIME: np.array(LEADS)}
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS], names=[rc.REFERENCE_TIME, *fixed])
    plan = _plan(da, _args(task_memory_gb=1e-9), steps, fixed, np.array([1, 6]), np.array([1, 6]), n_zones=2)
    assert all(b.get_level_values(rc.MEMBER).nunique() == 1 for b in plan.batches)
    assert max(len(b) for b in plan.batches) == 2  # the lead chunk


def test_write_groups_never_split_a_forecast_cycle():
    """A forecast cycle's batches always land in one write; analysis writes may split anywhere."""
    fixed = {rc.MEMBER: np.array(MEMBERS), rc.LEAD_TIME: np.array(LEADS)}
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS], names=[rc.REFERENCE_TIME, *fixed])
    batches = _cycle_batches(steps, fixed, lead_steps=2)
    groups = _write_groups(batches, _args(append_dim=rc.REFERENCE_TIME, max_rows_per_write=1), 1, forecast=True)
    assert len(groups) == len(CYCLES)
    for group in groups:
        assert pd.Index([c for b in group for c in b.get_level_values(rc.REFERENCE_TIME)]).nunique() == 1

    analysis = [TIMES[i:i + 5] for i in range(0, 20, 5)]
    assert len(_write_groups(analysis, _args(max_rows_per_write=1), 1, forecast=False)) == 4


def test_replace_filters_cover_exactly_the_write():
    analysis = replace_filters(_args(), "rainrate_hourly_mean", TIMES[2:5])
    assert analysis == [
        {"column": "configuration_name", "operator": "=", "value": "c"},
        {"column": "variable_name", "operator": "=", "value": "rainrate_hourly_mean"},
        {"column": "location_id", "operator": "like", "value": "huc\\_10-%"},
        {"column": "value_time", "operator": ">=", "value": pd.Timestamp("2020-01-01 02:00")},
        {"column": "value_time", "operator": "<=", "value": pd.Timestamp("2020-01-01 04:00")},
    ]
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS], names=[rc.REFERENCE_TIME, rc.MEMBER, rc.LEAD_TIME])
    forecast = replace_filters(_args(append_dim=rc.REFERENCE_TIME), "p", steps)
    assert forecast[-2:] == [
        {"column": "reference_time", "operator": ">=", "value": pd.Timestamp("2026-10-01 00:00")},
        {"column": "reference_time", "operator": "<=", "value": pd.Timestamp("2026-10-01 06:00")},
    ]
    assert not {f["column"] for f in forecast} & {"unit_name", "member"}


def test_like_prefix_escapes_wildcards():
    """Reads and replace filters select exactly the layer's ids, even for prefixes with LIKE wildcards."""
    assert like_prefix("huc_10") == "huc\\_10-%"
    assert like_prefix("usgs") == "usgs-%"
