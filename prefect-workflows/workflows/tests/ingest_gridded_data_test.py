"""End-to-end test of ingest_gridded_data (references -> raw_data -> pyramids) on local repos.

Uses the NWM source pointed at local hourly netCDF files shaped like NWM forcing. Needs teehr and Prefect.
"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr
import zarr

pytest.importorskip("teehr")
pytest.importorskip("h5netcdf")
icechunk = pytest.importorskip("icechunk")
from prefect.testing.utilities import prefect_test_harness  # noqa: E402

import build_geozarr_pyramids as bp  # noqa: E402
import ingest_gridded_data as ing  # noqa: E402
from workflows.models import gridded_sources as gs  # noqa: E402
from workflows.models.ingest_gridded_data_input import IngestGriddedDataInput  # noqa: E402

NWM_CONUS_CRS = "+proj=lcc +lat_0=40 +lon_0=-97 +lat_1=30 +lat_2=60 +x_0=0 +y_0=0 +R=6370000 +units=m +no_defs"
ORIGIN = pd.Timestamp(gs.NWMForcing.version_start["nwm31"])
HOURS = pd.date_range(ORIGIN, periods=90, freq="h")
# Packed pyramid resolution for rainrate_hourly_mean (max_value 0.075 in uint16)
PACKED_TOL = 2 * 0.075 / 65535


def rate(i, reissued=False):
    """Rain rate (mm/s) published for hour ``i``; a re-issued file has a different value."""
    return np.float32((i + 1) * 1e-4 + (5e-3 if reissued else 0))


@pytest.fixture(scope="module")
def harness():
    with prefect_test_harness():
        yield


@pytest.fixture
def nwm(tmp_path, monkeypatch):
    """NWM source and repo on local storage; returns publish(i, value, modified) and an opener."""
    src = tmp_path / "src"
    src.mkdir()
    prefix = f"file://{src}/"
    published = {}

    def publish(i, value, modified):
        t = HOURS[i]
        name = f"nwm.{t:%Y%m%d}.t{t:%H}z.analysis_assim.forcing.tm00.conus.nc"
        # NWM's y increases northward
        xr.Dataset(
            {"RAINRATE": (("time", "y", "x"), np.full((1, 40, 50), value, "float32"), {"units": "mm s^-1"})},
            coords={"time": [t], "y": np.arange(40) * 1000.0, "x": np.arange(50) * 1000.0 - 25000.0},
        ).to_netcdf(src / name, engine="h5netcdf")
        published[t] = {"time": t, "url": f"{prefix}{name}", "status": "stable", "last_modified": pd.Timestamp(modified)}

    def list_files(self, start_dt, end_dt):
        return gs._listing([r for t, r in published.items() if start_dt <= t <= end_dt])

    config = icechunk.RepositoryConfig.default()
    config.set_virtual_chunk_container(icechunk.VirtualChunkContainer(prefix, icechunk.local_filesystem_store(str(src))))
    storage = icechunk.local_filesystem_storage(str(tmp_path / "repo"))
    access = {prefix: icechunk.credentials.LocalFileSystemAccess}

    def open_repo(*_, **__):
        if icechunk.Repository.exists(storage):
            return icechunk.Repository.open(storage, config=config, authorize_virtual_chunk_access=access)
        return icechunk.Repository.create(storage, config=config, authorize_virtual_chunk_access=access)

    monkeypatch.setattr(gs.NWMForcing, "source_bucket", prefix.rstrip("/"))
    monkeypatch.setattr(gs.NWMForcing, "store_kwargs", {})
    monkeypatch.setattr(gs.NWMForcing, "list_files", list_files)
    monkeypatch.setattr(ing.gu, "configure_icechunk_s3_repo", open_repo)
    monkeypatch.setattr(bp.gu, "build_icechunk_s3_storage", lambda **_: storage)
    monkeypatch.setattr(bp.gu, "open_repo_for_reading", open_repo)
    return publish, open_repo


def _run(start, end, mode="append", write_materialized=True):
    ing.ingest_gridded_data(IngestGriddedDataInput(
        source={"type": "nwm"}, start_dt=start.isoformat(), end_dt=end.isoformat(), write_mode=mode,
        write_materialized=write_materialized, fallback_source_crs=NWM_CONUS_CRS,
        factors=[1, 2], dest_bucket="unused", base_prefix="unused", ignore_unreadable_file=False,
    ))


def _groups(open_repo, groups):
    store = open_repo().readonly_session("main").store
    return {g: xr.open_zarr(store, group=g, consolidated=False) for g in groups}


def test_nwm_listing_valid_times(monkeypatch):
    """Valid time is the file's cycle hour minus its tm hour; duplicate valid times raise."""
    bucket = gs.NWMForcing.source_bucket
    urls = [
        f"gcs://national-water-model/nwm.20260922/forcing_analysis_assim/nwm.t{h:02d}z.analysis_assim.forcing.tm00.conus.nc"
        for h in (0, 1)
    ]
    plan = type("Plan", (), {"component_paths": urls})
    monkeypatch.setattr(gs, "plan_nwm_grid_fetch", lambda **_: plan)
    modified = pd.Timestamp("2026-09-22T03:00")
    monkeypatch.setattr(gs.NWMForcing, "_last_modified", lambda self, u: {url: modified for url in u})

    listing = gs.NWMForcing().list_files(pd.Timestamp("2026-09-22"), pd.Timestamp("2026-09-22T01:00"))
    assert list(listing.index) == [pd.Timestamp("2026-09-22T00:00"), pd.Timestamp("2026-09-22T01:00")]
    assert listing["url"].str.startswith(f"{bucket}/").all()
    assert (listing["status"] == "stable").all() and (listing["last_modified"] == modified).all()

    # tm01 of the 01z cycle is the same valid time as tm00 of the 00z cycle
    plan.component_paths = [urls[0], urls[1].replace("tm00", "tm01")]
    with pytest.raises(ValueError, match="more than one file"):
        gs.NWMForcing(t_minus_hours=[0, 1]).list_files(pd.Timestamp("2026-09-22"), pd.Timestamp("2026-09-22T01:00"))


def test_grid_name_on_new_and_existing_repos(harness, nwm):
    publish, open_repo = nwm
    for i in range(10):
        publish(i, rate(i), "2026-09-01")
    _run(HOURS[0], HOURS[4])
    assert ing.tg.read_grid_name(open_repo().readonly_session("main").store) == "nwm30_conus_forcing"

    # A repo created before grid_name existed gains it on its next ingest
    session = open_repo().writable_session("main")
    del zarr.open_group(session.store, mode="a", zarr_format=3).attrs["grid_name"]
    session.commit("Drop grid_name")
    _run(HOURS[5], HOURS[9])
    assert ing.tg.read_grid_name(open_repo().readonly_session("main").store) == "nwm30_conus_forcing"


@pytest.mark.parametrize("write_materialized", [True, False], ids=["materialized", "virtual"])
def test_backfill_in_any_order_then_upsert(harness, nwm, write_materialized):
    publish, open_repo = nwm
    data_group = "raw_data" if write_materialized else "references"
    groups = ("references", "raw_data", "pyramids/0", "pyramids/1") if write_materialized else ("references", "pyramids/0", "pyramids/1")
    for i in range(len(HOURS)):
        publish(i, rate(i), "2026-09-01")

    def run(start, end, mode="append"):
        _run(HOURS[start], HOURS[end], mode, write_materialized)

    run(50, 59)  # a later block first
    run(2, 11)  # then an earlier one
    g = _groups(open_repo, groups)
    expected = list(range(2, 12)) + list(range(50, 60))
    cf_xarray = pytest.importorskip("cf_xarray")  # noqa: F841  # registers .cf, as xpublish-edr uses it
    for ds in g.values():
        assert ds.time.to_index().is_monotonic_increasing
        assert ds.cf.axes["T"] == ["time"]  # xpublish-edr selects datetime through it
        assert list(np.flatnonzero(ds.status.values >= 0)) == expected
    data = g[data_group]
    for i in expected:
        assert float(data.rainrate_hourly_mean.isel(time=i, y=3, x=4)) == rate(i)
    assert abs(float(g["pyramids/0"].rainrate_hourly_mean.isel(time=55).max()) - rate(55)) < PACKED_TOL
    assert np.isnan(float(g["pyramids/0"].rainrate_hourly_mean.isel(time=30).max()))  # unwritten slots are missing, not 0

    before = {k: v.updated_at.values.copy() for k, v in g.items()}
    run(2, 59)  # fills the gap, leaves written hours alone
    after = _groups(open_repo, groups)
    for k in groups:
        assert ((after[k].updated_at.values == before[k]) | np.isnat(before[k])).all()
        assert (after[k].status.values[2:60] == 2).all()

    run(70, 79)  # past the end of the axis
    data = _groups(open_repo, groups)[data_group]
    assert data.sizes["time"] == 80 and data.status.values[70] == 2
    created = data.created_at.values[70]

    for i in range(70, 75):
        publish(i, rate(i, reissued=True), "2026-10-01")  # NOAA re-issues five hours
    written = data.updated_at.values[70:75].copy()
    run(70, 79, mode="append")
    data = _groups(open_repo, groups)[data_group]
    assert (data.updated_at.values[70:75] == written).all()  # append leaves them
    if write_materialized:
        assert float(data.rainrate_hourly_mean.isel(time=71, y=0, x=0)) == rate(71)
    # Not read back when virtual: a reference to a re-issued file can't be read until upsert rewrites it
    run(70, 79, mode="upsert")
    g = _groups(open_repo, groups)
    data = g[data_group]
    assert float(data.rainrate_hourly_mean.isel(time=71, y=0, x=0)) == rate(71, reissued=True)
    assert float(data.rainrate_hourly_mean.isel(time=76, y=0, x=0)) == rate(76)
    assert data.created_at.values[70] == created and data.updated_at.values[70] > created
    assert (data.updated_at.values[75:80] < data.updated_at.values[70]).all()  # untouched hours keep their write time
    for k in groups:
        assert list(g[k].status.values[70:80]) == [2] * 10
    assert abs(float(g["pyramids/0"].rainrate_hourly_mean.isel(time=71).max()) - rate(71, reissued=True)) < PACKED_TOL

    root = zarr.open_group(open_repo().readonly_session("main").store, mode="r", zarr_format=3).attrs
    assert {k: root[k] for k in ("append_dim", "time_origin", "time_step", "configuration_name", "timeseries_type", "data_group")} == {
        "append_dim": "time", "time_origin": ORIGIN.isoformat(), "time_step": pd.Timedelta("1h").isoformat(),
        "configuration_name": "nwm31_forcing_analysis_assim", "timeseries_type": "primary", "data_group": f"/{data_group}",
    }
