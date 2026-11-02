"""Forecast ingest: NWM forecast listings, step blocks, and ingest_gridded_data writing forecast /references."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr
import zarr

pytest.importorskip("teehr")
pytest.importorskip("h5netcdf")
icechunk = pytest.importorskip("icechunk")
from prefect.testing.utilities import prefect_test_harness  # noqa: E402

import ingest_gridded_data as ing  # noqa: E402
from utils import time_grid as tg  # noqa: E402
from workflows.models import gridded_sources as gs  # noqa: E402
from workflows.models.ingest_gridded_data_input import IngestGriddedDataInput  # noqa: E402
from workflows.utils import repo_const as rc  # noqa: E402

NWM_CONUS_CRS = "+proj=lcc +lat_0=40 +lon_0=-97 +lat_1=30 +lat_2=60 +x_0=0 +y_0=0 +R=6370000 +units=m +no_defs"
SHORT_RANGE = {"type": "nwm", "nwm_configuration": "forcing_short_range"}
ORIGIN = gs.NWMForcing(nwm_configuration="forcing_short_range").time_origin()
CYCLES = pd.date_range(ORIGIN, periods=4, freq="h")
LEADS = list(range(1, 19))


def rate(c, lead, reissued=False):
    """Rain rate (mm/s) published for cycle ``c`` and lead; a re-issued file has a different value."""
    return np.float32(c * 1e-3 + lead * 1e-5 + (5e-3 if reissued else 0))


# --- Source ---

def test_nwm_forecast_source_shape():
    short = gs.NWMForcing(nwm_configuration="forcing_short_range")
    medium = gs.NWMForcing(nwm_configuration="forcing_medium_range")
    assert short.time_step == pd.Timedelta("1h") and medium.time_step == pd.Timedelta("6h")
    assert short.fixed_axes() == {rc.LEAD_TIME: LEADS} and len(medium.lead_times()) == 240
    assert short.append_dim() == rc.REFERENCE_TIME and short.timeseries_type() == "secondary"
    assert short.repository_name() == "nwm31_forcing_short_range" and short.grid_name() == "nwm30_conus_forcing"
    # The first medium-range cycle of the version, on the 00/06/12/18z grid
    start = pd.Timestamp(gs.NWMForcing.version_start["nwm31"])
    assert medium.time_origin() >= start and medium.time_origin().hour % 6 == 0
    assert medium.time_origin() - start < pd.Timedelta("6h")
    analysis = gs.NWMForcing()
    assert analysis.fixed_axes() == {} and analysis.append_dim() == "time" and analysis.timeseries_type() == "primary"


@pytest.mark.parametrize("configuration", ["short_range", "medium_range_mem1"])
def test_nwm_unsupported_configurations(configuration):
    with pytest.raises(ValueError):
        gs.NWMForcing(nwm_configuration=configuration)


def test_nwm_forecast_listing_is_by_step(monkeypatch):
    keys = [f"nwm.20260922/forcing_short_range/nwm.t{h:02d}z.short_range.forcing.f{lead:03d}.conus.nc"
            for h in (0, 1) for lead in (1, 2)]
    plan = type("Plan", (), {"component_paths": [f"gcs://national-water-model/{key}" for key in keys]})
    seen = {}
    monkeypatch.setattr(gs, "plan_nwm_grid_fetch", lambda **kw: seen.update(kw) or plan)
    monkeypatch.setattr(gs.NWMForcing, "_last_modified", lambda self, u: {})
    source = gs.NWMForcing(nwm_configuration="forcing_short_range", bucket="s3://noaa-nwm-pds")
    listing = source.list_files(pd.Timestamp("2026-09-22"), pd.Timestamp("2026-09-22T01:00"))
    assert seen["t_minus_hours"] is None
    assert listing.index.names == [rc.REFERENCE_TIME, rc.LEAD_TIME]
    assert list(listing.index) == [(pd.Timestamp("2026-09-22T00:00"), 1), (pd.Timestamp("2026-09-22T00:00"), 2),
                                   (pd.Timestamp("2026-09-22T01:00"), 1), (pd.Timestamp("2026-09-22T01:00"), 2)]
    assert listing["url"].iloc[0] == f"s3://noaa-nwm-pds/{keys[0]}"


# --- Blocks ---

def _steps(rows, names=(rc.REFERENCE_TIME, rc.LEAD_TIME)):
    return pd.MultiIndex.from_tuples(rows, names=list(names))


def test_complete_cycles_are_one_block():
    steps = _steps([(c, lead) for c in CYCLES for lead in LEADS])
    blocks = tg.step_blocks(steps, {rc.LEAD_TIME: LEADS})
    assert len(blocks) == 1 and blocks[0].equals(steps)


def test_partial_cycles_split_into_lead_runs():
    rows = [(CYCLES[0], lead) for lead in (1, 2, 5, 6)] + [(CYCLES[1], lead) for lead in (1, 2)]
    blocks = tg.step_blocks(_steps(rows), {rc.LEAD_TIME: LEADS})
    assert sorted((list(b.get_level_values(0).unique()), list(b.get_level_values(1).unique())) for b in blocks) == [
        ([CYCLES[0]], [5, 6]), ([CYCLES[0], CYCLES[1]], [1, 2])]


def test_members_get_their_own_blocks():
    rows = [(c, m, lead) for c in CYCLES[:2] for m in (0, 1) for lead in (1, 2, 3)]
    blocks = tg.step_blocks(_steps(rows, (rc.REFERENCE_TIME, rc.MEMBER, rc.LEAD_TIME)), {rc.MEMBER: [0, 1], rc.LEAD_TIME: [1, 2, 3]})
    assert len(blocks) == 2 and all(len(b) == 6 for b in blocks)


# --- Ingest ---

@pytest.fixture(scope="module")
def harness():
    with prefect_test_harness():
        yield


@pytest.fixture
def nwm(tmp_path, monkeypatch):
    """Forecast files shaped like NWM short range forcing on local storage; returns publish(c, lead, ...)."""
    src = tmp_path / "src"
    src.mkdir()
    prefix = f"file://{src}/"
    published = {}

    def publish(c, lead, modified="2026-01-01", reissued=False):
        cycle = CYCLES[c]
        # Laid out as in the buckets: nwm.<day>/<configuration>/nwm.t<HH>z.<...>.f<LLL>.conus.nc
        key = f"nwm.{cycle:%Y%m%d}/forcing_short_range/nwm.t{cycle:%H}z.short_range.forcing.f{lead:03d}.conus.nc"
        (src / key).parent.mkdir(parents=True, exist_ok=True)
        # NWM files carry their valid time and their cycle as 1-length dims
        xr.Dataset(
            {"RAINRATE": (("time", "y", "x"), np.full((1, 8, 10), rate(c, lead, reissued), "float32"), {"units": "mm s^-1"})},
            coords={"time": [cycle + pd.Timedelta(hours=lead)], "reference_time": [cycle],
                    "y": np.arange(8) * 1000.0, "x": np.arange(10) * 1000.0},
        ).to_netcdf(src / key, engine="h5netcdf")
        published[(cycle, lead)] = {rc.REFERENCE_TIME: cycle, rc.LEAD_TIME: lead, "url": f"{prefix}{key}",
                                    "status": "stable", "last_modified": pd.Timestamp(modified)}

    def list_files(self, start_dt, end_dt):
        rows = [r for (cycle, _), r in published.items() if start_dt <= cycle <= end_dt]
        return gs._listing(rows, (rc.REFERENCE_TIME, rc.LEAD_TIME))

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
    return publish, open_repo


def _run(mode="append", **kwargs):
    ing.ingest_gridded_data(IngestGriddedDataInput(**{
        "source": SHORT_RANGE, "start_dt": CYCLES[0].isoformat(), "end_dt": CYCLES[-1].isoformat(), "write_mode": mode,
        "write_materialized": False, "build_overviews_on_ingest": False, "fallback_source_crs": NWM_CONUS_CRS,
        "dest_bucket": "unused", "base_prefix": "unused", "ignore_unreadable_file": False, **kwargs,
    }))


def _refs(open_repo):
    store = open_repo().readonly_session("main").store
    return xr.open_zarr(store, group="references", consolidated=False, chunks=None), zarr.open_group(store, mode="r").attrs


def test_forecast_ingest_writes_steps_and_fills_partial_cycles(harness, nwm):
    publish, open_repo = nwm
    for lead in LEADS:
        publish(0, lead)
    for lead in LEADS[:6]:
        publish(1, lead)
    _run()
    refs, attrs = _refs(open_repo)
    assert attrs[rc.APPEND_DIM_ATTR] == rc.REFERENCE_TIME and attrs[rc.FIXED_DIMS_ATTR] == [rc.LEAD_TIME]
    assert attrs[rc.LAYOUT_VERSION_ATTR] == rc.FORECAST_LAYOUT_VERSION and attrs[rc.TIMESERIES_TYPE_ATTR] == "secondary"
    assert attrs[rc.CONFIGURATION_NAME_ATTR] == "nwm31_forcing_short_range"
    assert refs[rc.REFERENCE_TIME].attrs.get("axis") is None and refs[rc.LEAD_TIME].values.tolist() == LEADS
    assert refs["status"].attrs["flag_meanings"].startswith("not_expected unwritten")
    rain = refs["rainrate_hourly_mean"].isel(y=0, x=0).values
    assert np.allclose(rain[0], [rate(0, lead) for lead in LEADS])
    assert np.allclose(rain[1, :6], [rate(1, lead) for lead in LEADS[:6]]) and np.isnan(rain[1, 6:]).all()
    assert (refs["status"].values[1, 6:] == rc.UNWRITTEN).all()
    assert (refs["value_time"].values[1] == CYCLES[1] + pd.to_timedelta(LEADS, unit="h")).all()

    # The rest of cycle 1 arrives and cycle 3 is published with one lead missing; append fills them in
    for lead in LEADS[6:]:
        publish(1, lead)
    for lead in LEADS[:-1]:
        publish(3, lead)
    _run()
    refs, _ = _refs(open_repo)
    rain = refs["rainrate_hourly_mean"].isel(y=0, x=0).values
    assert np.allclose(rain[1], [rate(1, lead) for lead in LEADS])
    assert np.allclose(rain[3, :-1], [rate(3, lead) for lead in LEADS[:-1]]) and np.isnan(rain[3, -1])
    assert (refs["status"].values[2] == rc.UNWRITTEN).all()


def test_forecast_upsert_rewrites_reissued_steps(harness, nwm):
    publish, open_repo = nwm
    for lead in LEADS:
        publish(0, lead)
    _run()
    before = _refs(open_repo)[0]
    created, untouched = before["created_at"].values[0, 4], before["updated_at"].values[0, 0]
    publish(0, 5, modified="2026-02-01", reissued=True)
    _run(mode="upsert")
    refs, _ = _refs(open_repo)
    assert np.isclose(float(refs["rainrate_hourly_mean"].isel({rc.REFERENCE_TIME: 0, "y": 0, "x": 0}).sel(lead_time=5)),
                      rate(0, 5, reissued=True))
    assert refs["created_at"].values[0, 4] == created and refs["updated_at"].values[0, 4] > created
    # Untouched steps keep their write
    assert refs["updated_at"].values[0, 0] == untouched


def test_forecast_ingest_needs_references_only_for_now(harness, nwm):
    with pytest.raises(ValueError, match="materialized"):
        _run(write_materialized=True)
