"""Smoke test: the derived-dataset flow against a throwaway local catalog, in the v1 image.

    docker build --build-arg TEEHR_CORE_VERSION=<commit> -t teehr-prefect-v1:test prefect-workflows/v1
    docker run --rm -v "$PWD/prefect-workflows/v1/tests:/smoke:ro" teehr-prefect-v1:test \
        sh -c "pip install -q --user 'sqlalchemy>=2'; python /smoke/smoke_derived.py"
"""

import tempfile
from datetime import UTC, datetime, timedelta
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog
from teehr_core import warehouse as wh
from teehr_core.model.dataset_types import derived_columns, timeseries_columns, series_columns
import flows.derived as d

tmp = tempfile.mkdtemp()
cat = SqlCatalog("t", uri=f"sqlite:///{tmp}/c.db", warehouse=f"file://{tmp}/w")
cat.create_namespace("public")
def make(name, columns, key, props):
    schema = wh.iceberg_schema(columns, key)
    return cat.create_table(("public", name), schema=schema, properties=wh.table_properties(wh.Layout(properties=props)))
cols, key = timeseries_columns([], "instant")
obs = make("usgs_streamflow", cols, key, {"teehr.type": "timeseries", "teehr.role": "observed", "teehr.series_table": "usgs_streamflow_series"})
ser = make("usgs_streamflow_series", series_columns(), ["series_key"], {"teehr.type": "series"})
T0 = datetime(2026, 1, 1, tzinfo=UTC)
rows = pa.table({"series_key": [k for k in ("a", "b") for _ in range(100)],
                 "value_time": pa.array([T0 + timedelta(hours=h) for _ in range(2) for h in range(100)], pa.timestamp("us", tz="UTC")),
                 "value": [float(h) for _ in range(2) for h in range(100)]})
obs.append(wh.conform(rows, cols))
ser.append(wh.conform(pa.table({"series_key": ["a", "b"]}), series_columns()))
pc, pk = derived_columns("percentiles")
make("usgs_streamflow_percentiles", pc, pk, {"teehr.type": "percentiles"})
d.catalog = lambda: cat
out = d.build_derived_dataset(params={"min_years": 0, "levels": [50, 90]})
print("RESULT", out)
t = cat.load_table(("public", "usgs_streamflow_percentiles"))
print(t.scan().to_arrow().to_pylist())
print({k: v for k, v in t.current_snapshot().summary.additional_properties.items() if k.startswith("teehr")})
