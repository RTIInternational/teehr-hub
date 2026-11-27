"""Smoke test: the NWM ingest flow against a throwaway local catalog and a fake GCS, in the v1 image.

    docker build --build-arg TEEHR_CORE_VERSION=<commit> -t teehr-prefect-v1:test prefect-workflows/v1
    docker run --rm -v "$PWD/prefect-workflows/v1/tests:/smoke:ro" teehr-prefect-v1:test \
        sh -c "pip install -q --user 'sqlalchemy>=2'; python /smoke/smoke_ingest_nwm.py"
"""

import io
import tempfile
import urllib.error
from datetime import UTC, datetime, timedelta

import h5py
import numpy as np
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog
from teehr_core import warehouse as wh
from teehr_core.fetch import nwm
from teehr_core.model.dataset_types import layer_columns, series_columns, timeseries_columns

import flows.ingest_nwm as ingest

tmp = tempfile.mkdtemp()
cat = SqlCatalog("t", uri=f"sqlite:///{tmp}/c.db", warehouse=f"file://{tmp}/w")
cat.create_namespace("public")


def make(name, columns, key, props):
    schema = wh.iceberg_schema(columns, key)
    return cat.create_table(("public", name), schema=schema,
                            properties=wh.table_properties(wh.Layout(properties=props)))


# The gages (CONUS and Alaska), their crosswalk to nwm31 reaches, and three nwm31 datasets
# sharing one series table.
attr = {"name": "state_name", "type": "string", "required": False, "doc": None}
gages = make("usgs_gages", layer_columns([attr]), ["location_key"], {"teehr.type": "layer"})
point = bytes.fromhex("0101000000000000000000f03f000000000000f03f")
gages.append(pa.table({
    "location_key": ["usgs-01", "usgs-02", "usgs-03"], "name": [None] * 3, "geometry": [point] * 3,
    **{c: [1.0] * 3 for c in ("bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax")},
    "state_name": ["Virginia", "Alaska", None]}, schema=gages.schema().as_arrow()))
bare, key = timeseries_columns([], "instant")
make("usgs_streamflow", bare, key, {"teehr.type": "timeseries", "teehr.unit": "m3/s",
                                    "teehr.location_layer": "usgs_gages"})
make("usgs_nwm31", [{"name": n, "type": "string", "required": True, "doc": None}
                    for n in ("left_key", "right_key")], [], {"teehr.type": "crosswalk"})
cat.load_table(("public", "usgs_nwm31")).append(pa.table({
    "left_key": ["usgs-01", "usgs-02", "usgs-03", "usgs-01"],
    "right_key": ["nwm31-101", "nwm31-202", "nwm31-303", "nwm30-101"]},
    schema=cat.load_table(("public", "usgs_nwm31")).schema().as_arrow()))
make("nwm31_series", series_columns(), ["series_key"], {"teehr.type": "series"})
for name, optional in [("nwm31_short_range", ["reference_time"]),
                       ("nwm31_medium_range", ["reference_time", "member"]),
                       ("nwm31_analysis_assim_alaska_no_da", [])]:
    cols, key = timeseries_columns(optional, "instant")
    make(name, cols, key, {"teehr.type": "timeseries", "teehr.unit": "m3/s",
                           "teehr.series_table": "nwm31_series"})

# A fake bucket of channel_rt files (feature ids 101, 202, 303).
DAY = datetime(2026, 11, 24, tzinfo=UTC)
objects: dict[str, bytes] = {}


def channel_rt(valid, flows):
    buf = io.BytesIO()
    with h5py.File(buf, "w") as h5:
        h5.attrs["NWM_version_number"] = np.bytes_("v3.1")
        h5["feature_id"] = np.array([101, 202, 303], dtype=np.int64)
        f = h5.create_dataset("streamflow", data=np.array([round(v * 100) for v in flows], np.int32))
        f.attrs["scale_factor"] = np.array([0.01], np.float32)
        f.attrs["add_offset"] = np.array([0.0], np.float32)
        f.attrs["_FillValue"] = np.array([-999900], np.int32)
        h5["time"] = np.array([int((valid - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() // 60)],
                              np.int32)
    return buf.getvalue()


for cycle in (0, 12):
    for lead in (1, 2, 3):
        t = DAY + timedelta(hours=cycle + lead)
        objects[f"nwm.20261124/short_range/nwm.t{cycle:02d}z.short_range.channel_rt.f{lead:03d}"
                ".conus.nc"] = channel_rt(t, [1.0 + lead, 2.0, 3.0])
        objects[f"nwm.20261124/medium_range_mem1/nwm.t{cycle:02d}z.medium_range.channel_rt_1."
                f"f{lead:03d}.conus.nc"] = channel_rt(t, [10.0 + lead, 20.0, 30.0])
for cycle in (0, 1):
    for tm in (0, 1, 2):
        objects[f"nwm.20261124/analysis_assim_alaska_no_da/nwm.t{cycle:02d}z.analysis_assim_no_da"
                f".channel_rt.tm{tm:02d}.alaska.nc"] = channel_rt(
                    DAY + timedelta(hours=cycle - tm), [0.0, cycle * 10 + tm, 0.0])


def get(url):
    name = url.removeprefix(nwm.FILE_URL.format(name=""))
    if name not in objects:
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    return objects[name]


nwm._get = get
nwm._list = lambda prefix: sorted(n for n in objects if n.startswith(prefix))
ingest.catalog = lambda: cat
END = DAY + timedelta(days=1)

assert ingest.dataset_name("medium_range_alaska_mem1") == "nwm31_medium_range_alaska"

sr = ingest.ingest_nwm_streamflow("short_range", end=END, batch_files=2)
print("SHORT RANGE", sr)
assert (sr["dataset"], sr["reaches"], sr["files"]) == ("nwm31_short_range", 1, 6), sr
assert (sr["rows"], sr["series_added"]) == (6, 1), sr  # CONUS: reach 101 only (not AK, not null)
assert ingest.latest_cycle(cat, "public", "nwm31_short_range") == DAY + timedelta(hours=12)
again = ingest.ingest_nwm_streamflow("short_range", end=END)  # from the latest cycle: 12z again
assert (again["start"], again["files"], again["rows"], again["series_added"]) == (
    (DAY + timedelta(hours=12)).isoformat(), 3, 3, 0), again
stored = cat.load_table(("public", "nwm31_short_range")).scan().to_arrow()
assert stored.num_rows == 6 and set(stored["series_key"].to_pylist()) == {"nwm31-101"}
assert sorted(stored["reference_time"].to_pylist()) == [DAY] * 3 + [DAY + timedelta(hours=12)] * 3

mr = ingest.ingest_nwm_streamflow("medium_range_mem1", end=END)
assert (mr["dataset"], mr["rows"]) == ("nwm31_medium_range", 6), mr
stored = cat.load_table(("public", "nwm31_medium_range")).scan().to_arrow()
assert set(stored["member"].to_pylist()) == {"1"}
assert sorted(stored["value"].to_pylist()) == [11.0, 11.0, 12.0, 12.0, 13.0, 13.0]

aa = ingest.ingest_nwm_streamflow("analysis_assim_alaska_no_da", end=END)
assert (aa["reaches"], aa["rows"]) == (1, 4), aa  # Alaska: reach 202; times -2h..1h, once each
stored = cat.load_table(("public", "nwm31_analysis_assim_alaska_no_da")).scan().to_arrow()
assert "reference_time" not in stored.column_names
assert sorted((r["value_time"] - DAY, r["value"]) for r in stored.to_pylist()) == [
    (timedelta(hours=h), v) for h, v in [(-2, 2.0), (-1, 12.0), (0, 11.0), (1, 10.0)]]
try:  # medium range rows have a member: refused up front for a dataset without one
    ingest.ingest_nwm_streamflow("medium_range_mem1", dataset="nwm31_short_range", end=END)
    raise AssertionError("no member column, but no error")
except ValueError as err:
    assert "has no member column" in str(err), err
assert ingest.latest_cycle(cat, "public", "nwm31_analysis_assim_alaska_no_da") == DAY + timedelta(hours=1)
aa = ingest.ingest_nwm_streamflow("analysis_assim_alaska_no_da", end=END)  # cycle 1 again
assert (aa["files"], aa["rows"]) == (3, 3), aa
stored = cat.load_table(("public", "nwm31_analysis_assim_alaska_no_da")).scan().to_arrow()
assert sorted((r["value_time"] - DAY, r["value"]) for r in stored.to_pylist()) == [
    (timedelta(hours=h), v) for h, v in [(-2, 2.0), (-1, 12.0), (0, 11.0), (1, 10.0)]]
series = cat.load_table(("public", "nwm31_series")).scan().to_arrow()
assert sorted(series["series_key"].to_pylist()) == ["nwm31-101", "nwm31-202"]
assert set(series["location_key"].to_pylist()) == {None}
print("OK")
