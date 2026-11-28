"""Smoke test: the NWPS RFC ingest flow against a throwaway local catalog and a fake API, in the v1 image.

    docker build --build-arg TEEHR_CORE_VERSION=<commit> -t teehr-prefect-v1:test prefect-workflows/v1
    docker run --rm -v "$PWD/prefect-workflows/v1/tests:/smoke:ro" teehr-prefect-v1:test \
        sh -c "pip install -q --user 'sqlalchemy>=2'; python /smoke/smoke_ingest_nwps.py"
"""

import tempfile
import urllib.error
from datetime import UTC, datetime, timedelta

import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog
from teehr_core import warehouse as wh
from teehr_core.fetch import nwps
from teehr_core.model.dataset_types import layer_columns, series_columns, timeseries_columns

import flows.ingest_nwps as ingest

tmp = tempfile.mkdtemp()
cat = SqlCatalog("t", uri=f"sqlite:///{tmp}/c.db", warehouse=f"file://{tmp}/w")
cat.create_namespace("public")


def make(name, columns, key, props):
    schema = wh.iceberg_schema(columns, key)
    return cat.create_table(("public", name), schema=schema,
                            properties=wh.table_properties(wh.Layout(properties=props)))


# Four active gages (and an inactive one), their crosswalk to RFC gauges, the RFC dataset.
attr = {"name": "is_active", "type": "boolean", "required": False, "doc": None}
gages = make("usgs_gages", layer_columns([attr]), ["location_key"], {"teehr.type": "layer"})
point = bytes.fromhex("0101000000000000000000f03f000000000000f03f")
sites = ["usgs-01", "usgs-02", "usgs-03", "usgs-04", "usgs-05"]
gages.append(pa.table({
    "location_key": sites, "name": [None] * 5, "geometry": [point] * 5,
    **{c: [1.0] * 5 for c in ("bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax")},
    "is_active": [True, True, True, True, False]}, schema=gages.schema().as_arrow()))
bare, key = timeseries_columns([], "instant")
make("usgs_inst_streamflow", bare, key, {"teehr.type": "timeseries", "teehr.unit": "m3/s",
                                         "teehr.location_layer": "usgs_gages"})
make("usgs_nwpsrfc", [{"name": n, "type": "string", "required": True, "doc": None}
                      for n in ("left_key", "right_key")], [], {"teehr.type": "crosswalk"})
cat.load_table(("public", "usgs_nwpsrfc")).append(pa.table({
    "left_key": sites, "right_key": ["nwpsrfc-hour1", "nwpsrfc-three1", "nwpsrfc-six1",
                                     "nwpsrfc-stage1", "nwpsrfc-off1"]},
    schema=cat.load_table(("public", "usgs_nwpsrfc")).schema().as_arrow()))
make("nwpsrfc_streamflow_forecast_series", series_columns(), ["series_key"],
     {"teehr.type": "series"})
cols, key = timeseries_columns(["reference_time"], "instant")
make("nwpsrfc_streamflow_forecast", cols, key, {
    "teehr.type": "timeseries", "teehr.unit": "m3/s",
    "teehr.series_table": "nwpsrfc_streamflow_forecast_series"})

# A fake API: hourly, 3-hourly (with a no-data value) and 6-hourly forecasts, a stage-only
# gauge, and the inactive gage's gauge (never asked for).
NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
asked = []


def response(lid, step_hours, values, start=NOW):
    return {"secondaryName": "Flow", "secondaryUnits": "kcfs", "data": [
        {"validTime": f"{start + timedelta(hours=step_hours * i):%Y-%m-%dT%H:%M:%SZ}",
         "secondary": v} for i, v in enumerate(values, 1)]}


api = {"HOUR1": response("HOUR1", 1, [1.0, 1.1, 1.2]),
       "THREE1": response("THREE1", 3, [2.0, -999, 2.2, 2.3]),
       "SIX1": response("SIX1", 6, [3.0, 3.1]),
       "STAGE1": {"secondaryName": "Stage", "secondaryUnits": "ft", "data": []}}


def fake_forecast(lid):
    lid = nwps.lid_of(lid)
    asked.append(lid)
    if lid == "BROKEN1":
        raise urllib.error.URLError("timed out")
    return nwps.to_forecast(lid, api[lid])


nwps.forecast = fake_forecast
ingest.catalog = lambda: cat

out = ingest.ingest_nwps_rfc_streamflow(where="is_active == True")
print("RESULT", out)
assert sorted(asked) == ["HOUR1", "SIX1", "STAGE1", "THREE1"], asked
assert (out["gauges"], out["forecasts"], out["without"], out["failed"]) == (4, 3, 1, 0), out
assert out["steps"] == {"PT1H": 1, "PT3H": 1, "PT6H": 1} and out["rows"] == 8, out
stored = cat.load_table(("public", "nwpsrfc_streamflow_forecast")).scan().to_arrow().to_pylist()
refs = {r["series_key"]: r["reference_time"] for r in stored}
assert refs == {"nwpsrfc-hour1": NOW, "nwpsrfc-three1": NOW, "nwpsrfc-six1": NOW}, refs
three = sorted(r["value_time"] for r in stored if r["series_key"] == "nwpsrfc-three1")
assert three == [NOW + timedelta(hours=h) for h in (3, 9, 12)], three  # no-data dropped
series = cat.load_table(("public", "nwpsrfc_streamflow_forecast_series")).scan().to_arrow()
assert {(r["series_key"], r["resolution"]) for r in series.to_pylist()} == {
    ("nwpsrfc-hour1", "PT1H"), ("nwpsrfc-three1", "PT3H"), ("nwpsrfc-six1", "PT6H")}
print("FIRST OK")

# The next hour: only HOUR1 has a new forecast; the others are skipped, not rewritten.
api["HOUR1"] = response("HOUR1", 1, [1.5, 1.6], start=NOW + timedelta(hours=1))
again = ingest.ingest_nwps_rfc_streamflow(where="is_active == True")
assert (again["forecasts"], again["unchanged"], again["rows"]) == (1, 2, 2), again
print("AGAIN OK")

# A stored forecast with a later reference time (legacy's, from a forecast whose first days
# were no-data) doesn't hide a new one.
table = cat.load_table(("public", "nwpsrfc_streamflow_forecast"))
later = NOW + timedelta(days=5)
table.append(pa.table({"series_key": ["nwpsrfc-six1"], "reference_time": [later],
                       "value_time": [later + timedelta(hours=6)], "value": [9.0]},
                      schema=table.schema().as_arrow()))
api["SIX1"] = response("SIX1", 6, [3.2, 3.3], start=NOW + timedelta(hours=6))
again = ingest.ingest_nwps_rfc_streamflow(where="is_active == True")
assert (again["forecasts"], again["unchanged"], again["rows"]) == (1, 2, 2), again
print("LATER OK")

# Too many failures: what was fetched is written, then the run fails.
api["HOUR1"] = response("HOUR1", 1, [1.7, 1.8], start=NOW + timedelta(hours=2))
try:
    ingest.ingest_nwps_rfc_streamflow(gauges=["HOUR1", "BROKEN1"], max_failed=0.25)
except RuntimeError as err:
    assert "1 of 2 gauges failed" in str(err), err
else:
    raise AssertionError("expected the run to fail")
stored = cat.load_table(("public", "nwpsrfc_streamflow_forecast")).scan().to_arrow()
assert len({r for r in stored["reference_time"].to_pylist()}) == 5  # NOW, +1 h, +2 h, +6 h, +5 d
print("FAILURES OK")
