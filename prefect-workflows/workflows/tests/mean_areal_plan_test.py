"""Ensemble blocks, write groups and replace conditions of the mean areal flow (read plans: teehr-icechunk)."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

pytest.importorskip("teehr")
from mean_areal_values import _block_tasks, _write_groups, replace_filters  # noqa: E402
from pixel_coverage_weights import like_prefix  # noqa: E402
from workflows.models.mean_areal_inputs import MeanArealValuesInput  # noqa: E402
from teehr_icechunk import repo_const as rc  # noqa: E402
from teehr_icechunk.mean_areal_plan import cycle_batches  # noqa: E402

TIMES = pd.date_range("2020-01-01", periods=20, freq="h")
CYCLES = pd.date_range("2026-10-01", periods=2, freq="6h")
MEMBERS, LEADS = [0, 1, 2], [0, 3, 6, 9, 12]


def _args(**kwargs):
    return MeanArealValuesInput(
        configuration_name="c", temp_dir_path="/tmp", location_id_prefix="huc_10", grid_variable_name="v",
        dest_bucket="b", base_prefix="p", x_dim="x", y_dim="y", **kwargs,
    )


def _forecast(member_chunk):
    shape = (len(CYCLES), len(MEMBERS), len(LEADS), 8, 8)
    da = xr.DataArray(
        np.zeros(shape, "float32"), dims=(rc.REFERENCE_TIME, rc.MEMBER, rc.LEAD_TIME, "y", "x"),
        coords={rc.REFERENCE_TIME: CYCLES, rc.MEMBER: MEMBERS, rc.LEAD_TIME: LEADS},
    )
    da.encoding = {"chunks": (1, member_chunk, 2, 4, 4)}
    return da


def test_members_in_one_chunk_are_read_together():
    """With every member in one chunk, a cycle's block of leads across all members is read as one block."""
    da = _forecast(member_chunk=len(MEMBERS))
    fixed = {rc.MEMBER: np.array(MEMBERS), rc.LEAD_TIME: np.array(LEADS)}
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS], names=[rc.REFERENCE_TIME, *fixed])
    batches = cycle_batches(steps, fixed, lead_steps=2)
    tasks = _block_tasks(batches[0], da, rc.REFERENCE_TIME, fixed)
    assert len(tasks) == 1
    assert tasks[0].selection[rc.MEMBER] == slice(0, 3)
    assert list(tasks[0].step_columns["member"]) == ["0", "0", "1", "1", "2", "2"]


def test_forecast_blocks_carry_each_leads_variable_name():
    """With names by lead, every step's variable_name column is its lead's name."""
    da = _forecast(member_chunk=len(MEMBERS))
    fixed = {rc.MEMBER: np.array(MEMBERS), rc.LEAD_TIME: np.array(LEADS)}
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS[1:]], names=[rc.REFERENCE_TIME, *fixed])
    lead_names = {3: "p_3h", 6: "p_3h", 9: "p_3h", 12: "p_3h"}
    for task in _block_tasks(steps, da, rc.REFERENCE_TIME, fixed, lead_names):
        assert set(task.step_columns["variable_name"]) == {"p_3h"}
        assert len(task.step_columns["variable_name"]) == len(task.step_columns["value_time"])


def test_write_groups_never_split_a_forecast_cycle():
    """A forecast cycle's batches always land in one write; analysis writes may split anywhere."""
    fixed = {rc.MEMBER: np.array(MEMBERS), rc.LEAD_TIME: np.array(LEADS)}
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS], names=[rc.REFERENCE_TIME, *fixed])
    batches = cycle_batches(steps, fixed, lead_steps=2)
    groups = _write_groups(batches, _args(append_dim=rc.REFERENCE_TIME, max_rows_per_write=1), 1, forecast=True)
    assert len(groups) == len(CYCLES)
    for group in groups:
        assert pd.Index([c for b in group for c in b.get_level_values(rc.REFERENCE_TIME)]).nunique() == 1

    analysis = [TIMES[i:i + 5] for i in range(0, 20, 5)]
    assert len(_write_groups(analysis, _args(max_rows_per_write=1), 1, forecast=False)) == 4


def test_replace_filters_cover_exactly_the_write():
    analysis = replace_filters(_args(), ["rainrate_hourly_mean"], TIMES[2:5])
    assert analysis == [
        {"column": "configuration_name", "operator": "=", "value": "c"},
        {"column": "variable_name", "operator": "in", "value": ["rainrate_hourly_mean"]},
        {"column": "location_id", "operator": "like", "value": "huc\\_10-%"},
        {"column": "value_time", "operator": ">=", "value": pd.Timestamp("2020-01-01 02:00")},
        {"column": "value_time", "operator": "<=", "value": pd.Timestamp("2020-01-01 04:00")},
    ]
    steps = pd.MultiIndex.from_product([CYCLES, MEMBERS, LEADS], names=[rc.REFERENCE_TIME, rc.MEMBER, rc.LEAD_TIME])
    forecast = replace_filters(_args(append_dim=rc.REFERENCE_TIME), ["p_3h", "p_6h"], steps)
    assert {"column": "variable_name", "operator": "in", "value": ["p_3h", "p_6h"]} in forecast
    assert forecast[-2:] == [
        {"column": "reference_time", "operator": ">=", "value": pd.Timestamp("2026-10-01 00:00")},
        {"column": "reference_time", "operator": "<=", "value": pd.Timestamp("2026-10-01 06:00")},
    ]
    assert not {f["column"] for f in forecast} & {"unit_name", "member"}


def test_like_prefix_escapes_wildcards():
    """Reads and replace filters select exactly the layer's ids, even for prefixes with LIKE wildcards."""
    assert like_prefix("huc_10") == "huc\\_10-%"
    assert like_prefix("usgs") == "usgs-%"
