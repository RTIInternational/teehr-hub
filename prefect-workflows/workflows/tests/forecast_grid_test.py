"""Tests for forecast (fixed-axis) time grids and grid specs, and that analysis repos are unchanged."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr
import zarr

pytest.importorskip("h5netcdf")
icechunk = pytest.importorskip("icechunk")
from obspec_utils.registry import ObjectStoreRegistry  # noqa: E402
from obstore.store import LocalStore  # noqa: E402
from virtualizarr import open_virtual_dataset  # noqa: E402
from virtualizarr.parsers import HDFParser  # noqa: E402

from utils import grid_spec as gs  # noqa: E402
from utils import time_grid as tg  # noqa: E402
from workflows.utils import repo_const as rc  # noqa: E402

GOLDEN = Path(__file__).parent / "fixtures" / "analysis_grid_golden.json"
ORIGIN, STEP = pd.Timestamp("1981-10-01"), pd.Timedelta("1D")
DAYS = pd.date_range(ORIGIN, periods=12, freq="D")
MODIFIED = np.datetime64("2026-01-01", "ms")


def _virtual_repo(tmp_path, files):
    """A repo whose virtual chunk container serves ``files`` (name -> Dataset) from tmp_path/src."""
    src = tmp_path / "src"
    src.mkdir()
    for name, ds in files.items():
        ds.to_netcdf(src / name, engine="h5netcdf")
    prefix = f"file://{src}/"
    config = icechunk.RepositoryConfig.default()
    config.set_virtual_chunk_container(icechunk.VirtualChunkContainer(prefix, icechunk.local_filesystem_store(str(src))))
    repo = icechunk.Repository.create(
        icechunk.local_filesystem_storage(str(tmp_path / "repo")), config=config,
        authorize_virtual_chunk_access={prefix: icechunk.credentials.LocalFileSystemAccess},
    )
    registry = ObjectStoreRegistry({prefix: LocalStore(str(src))})

    def open_file(name, loadable):
        return open_virtual_dataset(f"{prefix}{name}", registry=registry, parser=HDFParser(), loadable_variables=loadable)

    return repo, open_file


# --- Analysis repos are unchanged ---

def _build_analysis_repo(tmp_path):
    """An analysis repo built only through the analysis API: out-of-order and upserted references, then /data."""
    files = {
        f"f_{d:%Y%m%d}.nc": xr.Dataset(
            {"SWE": (("time", "lat", "lon"), np.full((1, 4, 6), d.dayofyear, "float32"))},
            coords={"time": [d], "lat": np.arange(4.0), "lon": np.arange(6.0)},
        )
        for d in DAYS
    }
    repo, open_file = _virtual_repo(tmp_path, files)

    def open_days(days):
        parts = [open_file(f"f_{d:%Y%m%d}.nc", ["time", "lat", "lon"]) for d in days]
        return xr.concat(parts, dim="time", coords="minimal", compat="override", combine_attrs="override")

    for days, status in ((DAYS[6:9], 2), (DAYS[1:3], 1), (DAYS[1:2], 2)):
        session = repo.writable_session("main")
        stored = tg.read_step_metadata(session.store, "references", "time")
        ds = open_days(days)
        if stored is None:
            tg.create_group(session, "references", ds, ORIGIN, STEP, "time", days[-1], virtual=True)
            stored = tg.read_step_metadata(session.store, "references", "time")
        else:
            tg.ensure_axis(session, "references", days[-1], STEP, "time")
        ds = tg.with_step_metadata(ds, "time", [status] * len(days), np.full(len(days), MODIFIED), tg.utc_now(), stored)
        tg.region_write(session, "references", ds, "time", virtual=True)
        session.commit("refs")

    session = repo.writable_session("main")
    refs_meta = tg.read_step_metadata(session.store, "references", "time")
    refs = xr.open_zarr(session.store, group="references", consolidated=False, chunks=None).drop_vars(list(rc.STEP_COORDS))
    tg.create_group(session, "data", refs, ORIGIN, STEP, "time", refs_meta.index[-1],
                    encoding={"SWE": {"chunks": (1, 4, 6), "shards": (4, 4, 6)}})
    stale = tg.stale_steps(refs_meta, tg.read_step_metadata(session.store, "data", "time"))
    for batch in tg.shard_batches(stale, refs_meta.index, 4):
        m = refs_meta.loc[batch]
        part = tg.with_step_metadata(refs.sel(time=batch).load(), "time", m.status.to_numpy(),
                                     m.source_last_modified.to_numpy(), m.updated_at.to_numpy(),
                                     tg.read_step_metadata(session.store, "data", "time"))
        tg.region_write(session, "data", part, "time")
    session.commit("data")
    return repo


def _analysis_snapshot(repo) -> dict:
    """Everything stored about an analysis repo that doesn't depend on when it was written."""
    store = repo.readonly_session("main").store
    root = zarr.open_group(store, mode="r", zarr_format=3)
    snap = {}
    for group in ("references", "data"):
        g = root[group]
        snap[f"{group}/attrs"] = dict(g.attrs)
        for name, arr in sorted(g.arrays()):
            meta = arr.metadata.to_dict()
            meta.pop("attributes", None)
            snap[f"{group}/{name}"] = {"meta": meta, "attrs": dict(arr.attrs)}
            if name in ("time", "status", "SWE", "lat", "lon"):
                values = arr[:]
                snap[f"{group}/{name}"]["values"] = np.where(np.isnan(values), None, values).tolist() if values.dtype.kind == "f" else values.tolist()
    return json.loads(json.dumps(snap, default=str))


def test_analysis_repo_matches_golden(tmp_path):
    """An analysis repo built by this code stores exactly what main's code stored (attrs, encoding, step metadata)."""
    assert _analysis_snapshot(_build_analysis_repo(tmp_path)) == json.loads(GOLDEN.read_text())


# --- Forecast grids: (reference_time, [member], lead_time) ---

DIM = "reference_time"
REFS = pd.date_range("2026-10-01", periods=4, freq="6h")
FC_STEP = pd.Timedelta("6h")
MEMBERS, LEADS = [0, 1], [1, 2, 3, 6]
ENSEMBLE = {"member": MEMBERS, "lead_time": LEADS}
DETERMINISTIC = {"lead_time": LEADS}
FILE_DIMS = [DIM, "member", "lead_time", "y", "x"]


def _value(r, m, lead):
    """Each step's value identifies it: 100 * cycle index + 10 * member + lead."""
    return 100 * r + 10 * m + lead


@pytest.fixture
def forecast(tmp_path):
    """One file per (cycle, member, lead), and a builder of virtual blocks of them."""
    files = {
        f"c{r}_m{m}_l{lead}.nc": xr.Dataset(
            {"RAINRATE": (FILE_DIMS, np.full((1, 1, 1, 3, 4), _value(r, m, lead), "float32"))},
            coords={DIM: [ref], "member": np.array([m], "int32"), "lead_time": np.array([lead], "int32"),
                    "y": np.arange(3.0), "x": np.arange(4.0)},
        )
        for r, ref in enumerate(REFS) for m in MEMBERS for lead in LEADS
    }
    repo, open_file = _virtual_repo(tmp_path, files)
    kw = {"coords": "minimal", "compat": "override", "combine_attrs": "override"}

    def block(cycles, members=MEMBERS, leads=LEADS, ensemble=True):
        out = []
        for r in cycles:
            per_member = [
                xr.concat([open_file(f"c{r}_m{m}_l{lead}.nc", FILE_DIMS) for lead in leads], dim="lead_time", **kw)
                for m in members
            ]
            ds = xr.concat(per_member, dim="member", **kw)
            out.append(ds if ensemble else ds.isel(member=0, drop=True))
        return xr.concat(out, dim=DIM, **kw)

    return repo, block


def _write(repo, ds, fixed, status=2, group="references", virtual=True):
    """Write a block of steps into ``group``, creating it on the first call."""
    session = repo.writable_session("main")
    stored = tg.read_step_metadata(session.store, group, DIM)
    if stored is None:
        tg.create_group(session, group, ds, REFS[0], FC_STEP, DIM, ds[DIM].to_index()[-1], virtual=virtual, fixed=fixed)
        stored = tg.read_step_metadata(session.store, group, DIM)
    else:
        tg.ensure_axis(session, group, ds[DIM].to_index()[-1], FC_STEP, DIM)
    fixed_dims = tuple(fixed)
    n = int(np.prod([ds.sizes[d] for d in (DIM, *fixed_dims)]))
    status = np.broadcast_to(status, n)
    ds = tg.with_step_metadata(ds, DIM, status, np.full(n, MODIFIED), tg.utc_now(), stored, fixed_dims=fixed_dims)
    tg.region_write(session, group, ds, DIM, virtual=virtual, fixed_dims=fixed_dims)
    session.commit("write")


def _open(repo, group="references"):
    return xr.open_zarr(repo.readonly_session("main").store, group=group, consolidated=False, chunks=None)


def test_forecast_group_layout(forecast):
    repo, block = forecast
    _write(repo, block([1]), ENSEMBLE)
    ds = _open(repo)
    assert dict(ds.sizes) == {DIM: 2, "member": 2, "lead_time": 4, "y": 3, "x": 4}
    assert ds["lead_time"].dtype == np.int32 and list(ds["lead_time"].values) == LEADS
    assert ds["lead_time"].attrs == rc.FORECAST_COORD_ATTRS["lead_time"]
    assert ds["member"].attrs == rc.FORECAST_COORD_ATTRS["member"]
    assert ds[DIM].attrs == rc.FORECAST_COORD_ATTRS[DIM]  # no CF T axis on the reference time
    assert ds["value_time"].dims == (DIM, "lead_time")
    assert (ds["value_time"].values == tg.value_times(REFS[:2], LEADS)).all()
    assert ds["status"].dims == (DIM, "member", "lead_time")
    assert (ds["status"].values[0] == rc.UNWRITTEN).all() and (ds["status"].values[1] == 2).all()
    rain = ds["RAINRATE"].isel(y=0, x=0).values
    assert np.isnan(rain[0]).all()
    assert rain[1].tolist() == [[_value(1, m, lead) for lead in LEADS] for m in MEMBERS]


def test_partial_cycles_fill_in_and_select_by_step(forecast):
    repo, block = forecast
    _write(repo, block([2], members=[0], leads=[1, 2]), ENSEMBLE, status=1)
    _write(repo, block([2], members=[0], leads=[3, 6]), ENSEMBLE)
    _write(repo, block([2], members=[1], leads=[1, 2, 3]), ENSEMBLE)
    ds = _open(repo)
    assert ds["status"].sel({DIM: REFS[2]}).values.tolist() == [[1, 1, 2, 2], [2, 2, 2, rc.UNWRITTEN]]
    assert ds["RAINRATE"].sel({DIM: REFS[2], "member": 0, "lead_time": 6}).isel(y=0, x=0) == _value(2, 0, 6)
    assert np.isnan(ds["RAINRATE"].sel({DIM: REFS[2], "member": 1, "lead_time": 6}).isel(y=0, x=0))

    stored = tg.read_step_metadata(repo.readonly_session("main").store, "references", DIM)
    assert stored.index.names == [DIM, "member", "lead_time"] and len(stored) == 3 * 2 * 4
    steps = pd.MultiIndex.from_tuples([(REFS[2], 0, 1), (REFS[2], 0, 3), (REFS[2], 1, 6)], names=stored.index.names)
    listing = pd.DataFrame({"status": ["stable", "stable", "stable"],
                            "last_modified": pd.to_datetime(["2026-01-01", "2026-06-01", "2026-01-01"])}, index=steps)
    assert list(tg.select_source_steps(listing, stored, "append").index) == [steps[2]]
    # (0, 1) became more final, (0, 3) was re-issued, (1, 6) is new
    assert list(tg.select_source_steps(listing, stored, "upsert").index) == list(steps)


def test_new_cycles_get_value_times(forecast):
    repo, block = forecast
    _write(repo, block([0]), ENSEMBLE)
    _write(repo, block([3]), ENSEMBLE)
    ds = _open(repo)
    assert ds.sizes[DIM] == 4
    assert (ds["value_time"].values == tg.value_times(REFS, LEADS)).all()
    assert (ds["status"].values[1:3] == rc.UNWRITTEN).all()


def test_deterministic_forecast_has_no_member(forecast):
    repo, block = forecast
    _write(repo, block([1, 2], ensemble=False), DETERMINISTIC)
    ds = _open(repo)
    assert "member" not in ds.dims and ds["status"].dims == (DIM, "lead_time")
    assert ds["RAINRATE"].isel(y=0, x=0).values[2].tolist() == [_value(2, 0, lead) for lead in LEADS]
    stored = tg.read_step_metadata(repo.readonly_session("main").store, "references", DIM)
    assert stored.index.names == [DIM, "lead_time"]


def test_not_expected_steps_are_skipped_by_readers_but_writable(forecast):
    repo, block = forecast
    _write(repo, block([1], members=[0, 1], leads=[1, 2, 3]), ENSEMBLE)
    # Mark member 1's lead 6 as never published: metadata only, no data
    meta_only = block([1], members=[1], leads=[6]).drop_vars("RAINRATE")
    # Metadata has no virtual arrays, so it goes through the plain (non-virtual) writer
    _write(repo, meta_only, ENSEMBLE, status=rc.NOT_EXPECTED, virtual=False)
    stored = tg.read_step_metadata(repo.readonly_session("main").store, "references", DIM)
    assert stored.loc[(REFS[1], 1, 6), "status"] == rc.NOT_EXPECTED
    assert (REFS[1], 1, 6) not in tg.stale_steps(stored, None)
    listing = pd.DataFrame({"status": ["stable"], "last_modified": pd.to_datetime(["2026-01-01"])},
                           index=pd.MultiIndex.from_tuples([(REFS[1], 1, 6)], names=stored.index.names))
    assert len(tg.select_source_steps(listing, stored, "append")) == 1


def test_materialized_copy_of_stale_steps(forecast):
    repo, block = forecast
    _write(repo, block([1]), ENSEMBLE)
    _write(repo, block([2], members=[0], leads=[1, 2]), ENSEMBLE)
    store = repo.readonly_session("main").store
    refs_meta = tg.read_step_metadata(store, "references", DIM)
    stale = tg.stale_steps(refs_meta, None)
    assert len(stale) == 8 + 2
    refs = _open(repo).drop_vars([*rc.STEP_COORDS, "value_time"])
    session = repo.writable_session("main")
    tg.create_group(session, "data", refs, REFS[0], FC_STEP, DIM, refs_meta.index.get_level_values(DIM)[-1],
                    encoding={"RAINRATE": {"chunks": (1, 1, 1, 3, 4)}}, fixed=ENSEMBLE)
    data_meta = tg.read_step_metadata(session.store, "data", DIM)
    for ref, member in sorted({(r, m) for r, m, _ in stale}):
        leads = sorted(lead for r, m, lead in stale if (r, m) == (ref, member))
        part = refs.sel({DIM: [ref], "member": [member], "lead_time": leads}).load()
        m = refs_meta.loc[[(ref, member, lead) for lead in leads]]
        part = tg.with_step_metadata(part, DIM, m.status.to_numpy(), m.source_last_modified.to_numpy(),
                                     m.updated_at.to_numpy(), data_meta, fixed_dims=("member", "lead_time"))
        tg.region_write(session, "data", part, DIM, fixed_dims=("member", "lead_time"))
    session.commit("data")
    data = _open(repo, "data")
    assert data["status"].sel({DIM: REFS[2]}).values.tolist() == [[2, 2, -1, -1], [-1, -1, -1, -1]]
    assert float(data["RAINRATE"].sel({DIM: REFS[1], "member": 1, "lead_time": 6}).isel(y=0, x=0)) == _value(1, 1, 6)
    assert len(tg.stale_steps(refs_meta, tg.read_step_metadata(repo.readonly_session("main").store, "data", DIM))) == 0


def test_region_write_needs_contiguous_fixed_values(forecast):
    repo, block = forecast
    _write(repo, block([1]), ENSEMBLE)
    with pytest.raises(ValueError, match="contiguous"):
        _write(repo, block([2], leads=[1, 3]), ENSEMBLE)


def test_fixed_axes_must_match_the_source(forecast):
    repo, block = forecast
    _write(repo, block([1]), ENSEMBLE)
    store = repo.readonly_session("main").store
    tg.check_fixed_axes(store, "references", ENSEMBLE)
    with pytest.raises(ValueError, match="lead_time"):
        tg.check_fixed_axes(store, "references", {"member": MEMBERS, "lead_time": [1, 2, 3]})


# --- Grid specs and canonical datasets ---

def test_analysis_repo_spec_needs_no_new_attributes(tmp_path):
    repo = _build_analysis_repo(tmp_path)
    session = repo.writable_session("main")
    tg.write_grid_attrs(session.store, {"append_dim": "time", "time_origin": ORIGIN.isoformat(), "time_step": STEP.isoformat()})
    spec = gs.read_grid_spec(session.store)
    assert spec == gs.GridSpec(append_dim="time")
    ds = gs.open_grid_dataset(session.store, spec)
    assert "value_time" not in ds.coords and list(ds["SWE"].dims) == ["time", "lat", "lon"]


def test_forecast_repo_spec_and_dataset(forecast):
    repo, block = forecast
    _write(repo, block([1]), ENSEMBLE)
    session = repo.writable_session("main")
    tg.write_grid_attrs(session.store, {"append_dim": DIM, rc.FIXED_DIMS_ATTR: list(ENSEMBLE), rc.LAYOUT_VERSION_ATTR: 2,
                                        "data_group": "/references", rc.GRID_NAME_ATTR: "g"})
    spec = gs.read_grid_spec(session.store)
    assert spec.fixed_dims == ("member", "lead_time") and spec.layout_version == 2 and spec.data_group == "/references"
    ds = gs.open_grid_dataset(session.store, spec)
    assert ds["lead_time"].dtype == np.int32 and (ds["value_time"].values == tg.value_times(REFS[:2], LEADS)).all()


@pytest.mark.parametrize("version", [3, 0, -1, "two"])
def test_unknown_layout_is_refused(tmp_path, version):
    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(str(tmp_path)))
    session = repo.writable_session("main")
    tg.write_grid_attrs(session.store, {"append_dim": DIM, rc.LAYOUT_VERSION_ATTR: version})
    with pytest.raises(ValueError, match="Unknown layout_version"):
        gs.read_grid_spec(session.store)


def test_external_repo_is_normalized_by_override(tmp_path):
    """A repo laid out like dynamical.org's: other dim names, timedelta leads, no valid time stored."""
    leads = pd.to_timedelta([0, 3, 6, 246], unit="h")
    ext = xr.Dataset(
        {"precipitation_surface": (("init_time", "lead_time", "ensemble_member", "latitude", "longitude"),
                                   np.ones((2, 4, 3, 2, 2), "float32"))},
        coords={"init_time": REFS[:2], "lead_time": leads, "ensemble_member": np.arange(3, dtype="int16"),
                "latitude": [1.0, 0.0], "longitude": [0.0, 1.0]},
    )
    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(str(tmp_path)))
    session = repo.writable_session("main")
    ext.to_zarr(session.store, zarr_format=3, consolidated=False)
    override = {"append_dim": DIM, rc.FIXED_DIMS_ATTR: ["lead_time", "member"], "data_group": "/",
                "renames": {"init_time": DIM, "ensemble_member": "member"}}
    spec = gs.read_grid_spec(session.store, override)
    ds = gs.open_grid_dataset(session.store, spec)
    assert ds["precipitation_surface"].dims == (DIM, "lead_time", "member", "latitude", "longitude")
    assert ds["lead_time"].values.tolist() == [0, 3, 6, 246] and ds["lead_time"].attrs["units"] == "hours"
    assert ds["value_time"].values[1, 3] == REFS[1] + pd.Timedelta("246h")
