"""Smoke test: the USGS ingest flow against a throwaway local catalog and a fake API, in the v1 image.

    docker build --build-arg TEEHR_CORE_VERSION=<commit> -t teehr-prefect-v1:test prefect-workflows/v1
    docker run --rm -v "$PWD/prefect-workflows/v1/tests:/smoke:ro" teehr-prefect-v1:test \
        sh -c "pip install -q --user 'sqlalchemy>=2'; python /smoke/smoke_ingest_usgs.py"
"""

import tempfile
from datetime import UTC, datetime, timedelta

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog
from teehr_core import warehouse as wh
from teehr_core.fetch import usgs
from teehr_core.model.dataset_types import layer_columns, series_columns, timeseries_columns

import flows.ingest_usgs as ingest

tmp = tempfile.mkdtemp()
cat = SqlCatalog("t", uri=f"sqlite:///{tmp}/c.db", warehouse=f"file://{tmp}/w")
cat.create_namespace("public")


def make(name, columns, key, props):
    schema = wh.iceberg_schema(columns, key)
    return cat.create_table(("public", name), schema=schema,
                            properties=wh.table_properties(wh.Layout(properties=props)))


cols, key = timeseries_columns(["approval_status", "qualifier"], "instant")
make("usgs_streamflow", cols, key, {
    "teehr.type": "timeseries", "teehr.unit": "m3/s", "teehr.series_table": "usgs_streamflow_series",
    "teehr.location_layer": "usgs_gauges"})
bare, _ = timeseries_columns([], "instant")
make("no_flags", bare, key, {
    "teehr.type": "timeseries", "teehr.unit": "m3/s", "teehr.series_table": "usgs_streamflow_series",
    "teehr.location_layer": "usgs_gauges"})
make("usgs_streamflow_series", series_columns(), ["series_key"], {"teehr.type": "series"})
attr = {"name": "is_active", "type": "boolean", "required": False, "doc": None}
gauges = make("usgs_gauges", layer_columns([attr]), ["location_key"], {"teehr.type": "layer"})
point = bytes.fromhex("0101000000000000000000f03f000000000000f03f")
gauges.append(pa.table({
    "location_key": ["usgs-01", "usgs-02", "usgs-03"], "name": [None] * 3, "geometry": [point] * 3,
    **{c: [1.0] * 3 for c in ("bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax")},
    "is_active": [True, True, False]}, schema=gauges.schema().as_arrow()))

END = datetime(2026, 11, 20, 3, tzinfo=UTC)
requests = []


def fake_request(service, sites, start, end):
    requests.append(sites)
    hours = pd.date_range(start, end - timedelta(hours=1), freq="h")
    return pd.DataFrame({
        "time_series_id": [f"ts-{s}" for s in sites for _ in hours],
        "monitoring_location_id": [f"USGS-{usgs.site_number(s)}" for s in sites for _ in hours],
        "time": [t for _ in sites for t in hours],
        "value": [100.0 for _ in sites for _ in hours],
        "approval_status": "Provisional",
        "qualifier": [["ICE"] for _ in sites for _ in hours]})


usgs._request = fake_request
ingest.catalog = lambda: cat

out = ingest.ingest_usgs_streamflow(where="is_active == True", end=END, lookback_days=0.125,
                                    batch_sites=1)
print("RESULT", out)
assert requests == [["usgs-01"], ["usgs-02"]], requests
assert (out["sites"], out["rows"], out["commits"], out["series_added"]) == (2, 6, 1, 2), out

again = ingest.ingest_usgs_streamflow(sites=["01"], end=END, lookback_days=0.125)
assert (again["rows"], again["series_added"]) == (3, 0), again
stored = cat.load_table(("public", "usgs_streamflow")).scan().to_arrow()
assert set(stored["approval_status"].to_pylist()) == {"Provisional"}
assert set(stored["qualifier"].to_pylist()) == {"ICE"}
assert stored.num_rows == 6 and round(stored["value"][0].as_py(), 4) == round(100 * usgs.CFS_TO_M3S, 4)
series = cat.load_table(("public", "usgs_streamflow_series")).scan().to_arrow().to_pylist()
assert {(s["series_key"], s["location_key"], s["location_layer"]) for s in series} == {
    ("usgs-01", "usgs-01", "usgs_gauges"), ("usgs-02", "usgs-02", "usgs_gauges")}, series
no_q = ingest.ingest_usgs_streamflow(dataset="no_flags", sites=["01"], end=END,
                                     lookback_days=0.125)
assert no_q["rows"] == 3, no_q
print("OK")

# The backfill: bulk files (the last one ending two days ago), staged and written a month at a
# time, then topped up from the API.
recent = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(days=2)
months_ago = recent - timedelta(days=40)


def fake_bulk(service, site):
    hours = pd.date_range(months_ago, recent, freq="6h")
    return pd.DataFrame({
        "time_series_id": "ts", "monitoring_location_id": f"USGS-{usgs.site_number(site)}",
        "time": hours, "value": "200", "approval_status": "Approved", "qualifier": None})


usgs._bulk_file = fake_bulk
requests.clear()
filled = ingest.backfill_usgs_streamflow(where="is_active == True")
print("BACKFILL", filled)
assert filled["with_data"] == 2 and filled["months"] >= 2, filled
assert filled["top_up"]["sites"] == 2 and requests, filled
stored = cat.load_table(("public", "usgs_streamflow")).scan().to_arrow()
statuses = set(stored["approval_status"].to_pylist())
assert statuses == {"Approved", "Provisional"}, statuses  # bulk, then the API's latest
older = stored.filter(pa.compute.less(stored["value_time"], pa.scalar(recent)))
assert {round(v, 4) for v in older["value"].to_pylist()} == {round(200 * usgs.CFS_TO_M3S, 4)}  # replaced
print("BACKFILL OK")
