"""Smoke test: the NRDS ingest flow against a throwaway local catalog and a fake S3, in the v1 image.

    docker build --build-arg TEEHR_CORE_VERSION=<commit> -t teehr-prefect-v1:test prefect-workflows/v1
    docker run --rm -v "$PWD/prefect-workflows/v1/tests:/smoke:ro" teehr-prefect-v1:test \
        sh -c "pip install -q --user 'sqlalchemy>=2'; python /smoke/smoke_ingest_nrds.py"
"""

import io
import tempfile
import urllib.error
from datetime import UTC, datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq
from pyiceberg.catalog.sql import SqlCatalog
from teehr_core import warehouse as wh
from teehr_core.fetch import nrds
from teehr_core.model.dataset_types import layer_columns, series_columns, timeseries_columns

import flows.ingest_nrds as ingest

tmp = tempfile.mkdtemp()
cat = SqlCatalog("t", uri=f"sqlite:///{tmp}/c.db", warehouse=f"file://{tmp}/w")
cat.create_namespace("public")


def make(name, columns, key, props):
    schema = wh.iceberg_schema(columns, key)
    return cat.create_table(("public", name), schema=schema,
                            properties=wh.table_properties(wh.Layout(properties=props)))


# Two active gages (and an inactive one), their crosswalk to nrds22 reaches (and an nwm31 link,
# ignored), and the four NRDS datasets sharing one series table.
attrs = [{"name": n, "type": "boolean", "required": False, "doc": None}
         for n in ("is_active", "has_inst_discharge")]
gages = make("usgs_gages", layer_columns(attrs), ["location_key"], {"teehr.type": "layer"})
point = bytes.fromhex("0101000000000000000000f03f000000000000f03f")
gages.append(pa.table({
    "location_key": ["usgs-01", "usgs-02", "usgs-03"], "name": [None] * 3, "geometry": [point] * 3,
    **{c: [1.0] * 3 for c in ("bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax")},
    "is_active": [True, True, False], "has_inst_discharge": [True, True, True]},
    schema=gages.schema().as_arrow()))
bare, key = timeseries_columns([], "instant")
make("usgs_inst_streamflow", bare, key, {"teehr.type": "timeseries", "teehr.unit": "m3/s",
                                         "teehr.location_layer": "usgs_gages"})
make("usgs_nrds22", [{"name": n, "type": "string", "required": True, "doc": None}
                     for n in ("left_key", "right_key")], [], {"teehr.type": "crosswalk"})
cat.load_table(("public", "usgs_nrds22")).append(pa.table({
    "left_key": ["usgs-01", "usgs-02", "usgs-03", "usgs-01"],
    "right_key": ["nrds22-101", "nrds22-202", "nrds22-303", "nwm31-101"]},
    schema=cat.load_table(("public", "usgs_nrds22")).schema().as_arrow()))
make("nrds_v22_cfenom_short_range_series", series_columns(), ["series_key"],
     {"teehr.type": "series"})
for model in ("cfe_nom", "lstm_0"):
    for configuration in ("short_range", "medium_range"):
        cols, key = timeseries_columns(["reference_time"], "instant")
        make(ingest.dataset_name(model, configuration), cols, key, {
            "teehr.type": "timeseries", "teehr.unit": "m3/s",
            "teehr.series_table": "nrds_v22_cfenom_short_range_series"})

# A fake bucket of t-route files (feature ids 101, 202, 303; two VPUs), its times two hours
# after the cycle as the DataStream's are.
DAY = datetime(2026, 11, 24, tzinfo=UTC)
objects: dict[str, bytes] = {}


def troute(first, hours, flows, ids):
    rows = {"feature_id": [], "time": [], "type": [], "flow": []}
    for fid, flow in zip(ids, flows, strict=True):
        for h in range(hours):
            rows["feature_id"].append(fid)
            rows["time"].append((first + timedelta(hours=h)).replace(tzinfo=None))
            rows["type"].append("wb")
            rows["flow"].append(flow)
    buf = io.BytesIO()
    pq.write_table(pa.table({**rows, "time": pa.array(rows["time"], pa.timestamp("ns")),
                             "flow": pa.array(rows["flow"], pa.float32())}), buf)
    return buf.getvalue()


def add(model, configuration, cycle, member=None, days=1, hours=3):
    for vpu, ids in (("VPU_01", (101, 202)), ("VPU_02", (303,))):
        for d in range(days):
            first = DAY + timedelta(hours=cycle + 2, days=d)
            stamp = first - timedelta(hours=1)
            path = f"{cycle:02d}/" + (f"{member}/" if member else "")
            objects[f"outputs/{model}/{nrds.HYDROFABRIC}/ngen.{DAY:%Y%m%d}/{configuration}/{path}"
                    f"{vpu}/ngen-run/outputs/troute/troute_output_{stamp:%Y%m%d%H%M}.parquet"] = (
                troute(first, hours, [1.0 + cycle] * len(ids), ids))
        objects[f"outputs/{model}/{nrds.HYDROFABRIC}/ngen.{DAY:%Y%m%d}/{configuration}/{path}"
                f"{vpu}/datastream-metadata/execution.json"] = b"{}"


for cycle in (0, 1, 23):
    add("cfe_nom", "short_range", cycle)
for cycle in (0, 6):
    add("lstm_0", "medium_range", cycle, member="1", days=2)
    add("lstm_0", "medium_range", cycle, member="2", days=2)


def get(url):
    key = url.removeprefix(f"{nrds.URL}/")
    if key not in objects:
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    return objects[key]


nrds._get = get
nrds._list = lambda prefix: sorted(k for k in objects if k.startswith(prefix))
ingest.catalog = lambda: cat
END = DAY + timedelta(days=1)

sr = ingest.ingest_nrds_streamflow("cfe_nom", "short_range", end=END, batch_files=2)
print("SHORT RANGE", sr)
assert (sr["dataset"], sr["reaches"], sr["files"], sr["cycles"]) == (
    "nrds_v22_cfenom_short_range", 2, 6, 3), sr  # reaches 101, 202 (303's gage is inactive)
assert (sr["rows"], sr["series_added"]) == (18, 2), sr  # 3 cycles x 2 reaches x 3 hours
stored = cat.load_table(("public", "nrds_v22_cfenom_short_range")).scan().to_arrow()
first = min(r["value_time"] for r in stored.to_pylist() if r["reference_time"] == DAY)
assert first == DAY + timedelta(hours=2), first  # the files' times, as they are
again = ingest.ingest_nrds_streamflow("cfe_nom", "short_range", end=END)  # from 23z again
assert (again["start"], again["files"], again["rows"], again["series_added"]) == (
    (DAY + timedelta(hours=23)).isoformat(), 2, 6, 0), again
assert cat.load_table(("public", "nrds_v22_cfenom_short_range")).scan().to_arrow().num_rows == 18
print("SHORT RANGE OK")

mr = ingest.ingest_nrds_streamflow("lstm_0", "medium_range", end=END)
print("MEDIUM RANGE", mr)
assert (mr["dataset"], mr["files"], mr["cycles"], mr["rows"]) == (
    "nrds_v22_lstm0_medium_range", 8, 2, 24), mr  # member 1: 2 cycles x 2 days x 2 reaches x 3 h
print("MEDIUM RANGE OK")
