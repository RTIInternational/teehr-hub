# Migration 0011: Declare real Iceberg sort orders on the core timeseries tables

Migrations [0002](../0002) and [0006](../0006) set a `write.sort-order` **table property**. That is not an
Iceberg property — Iceberg's sort order is first-class table metadata, set with `ALTER TABLE ... WRITE ORDERED BY`.
The property was stored as an inert custom key and never affected how data was written.

The 0002 README claims "so all future writes maintain the sort order automatically." That is incorrect and this
migration supersedes it.

## Scope

Core tables only — `primary_timeseries` and `secondary_timeseries`. Non-core tables are created and configured by
the workflow or notebook that owns them, not here:

| table | owner | state |
|---|---|---|
| `fcst_joined_timeseries` | `prefect-workflows/workflows/metrics/utils/joined_forecast_utils.py` | already passes `write_ordered_by`; correct |
| `sim_joined_timeseries` | `warehouse/remote/03_preprocessing/simulation/01_create_joined_timeseries.ipynb` | no `partition_by` or `write_ordered_by`; needs fixing at that call site |

## How to tell whether a table really has a sort order

`SHOW TBLPROPERTIES` on a table with a declared sort order reports a read-only **`sort-order`** key (no `write.`
prefix) reflecting the real metadata. A `write.sort-order` key is the inert custom property and means nothing.

Do **not** use `sort_order_id` from the `$files` metadata table. Spark's Iceberg writer leaves it at `0` on every
file whether or not the data is sorted — verified locally on Iceberg 1.10.1 / Spark 4.0 (see Evidence).

## Evidence

Measured against the remote warehouse via Trino on 2026-09-21:

- A single-gage, 3-month query against `primary_timeseries` scanned **17,030,839 rows to return 708**
  (`Filtered: 100.00%`), reading 100% of all three candidate files (24.95 MB of 25.68 MB physical input).
- Those files hold ~5M rows each in a **single Parquet row group**, so neither row-group nor page statistics can
  skip anything while the data is unclustered.

Verified locally against Iceberg 1.10.1 / Spark 4.0.1 with a Hadoop catalog — 20,000 shuffled rows, one file:

| table config | inversions in written file | `sort_order_id` |
|---|---|---|
| no sort order | 10,000 / 19,999 | 0 |
| `WRITE ORDERED BY` | **0 / 19,999** | 0 |
| `WRITE ORDERED BY` + `distribution-mode=range` | **0 / 19,999** | 0 |
| `WRITE ORDERED BY` + `distribution-mode=hash` | **0 / 19,999** | 0 |

`WRITE ORDERED BY` sorts the data; `sort_order_id` is uninformative either way.

## Changes

### `01_set_sort_orders.sql`

| table | sort order |
|---|---|
| `primary_timeseries` | `location_id, value_time` |
| `secondary_timeseries` | `location_id, reference_time, value_time` |

`location_id` leads deliberately. `value_time` is already a partition field (`months(value_time)`), so leading with
it sorts within a range partition pruning has already isolated. `location_id` is the high-cardinality column the
dashboards filter on and that nothing currently prunes.

### `02_set_write_properties.sql`

Sets `write.parquet.row-group-size-bytes = 8 MiB` so files contain multiple row groups. Today every file is a
single row group, which makes sub-file skipping impossible regardless of sort order. This is the secondary lever;
sorting is the primary one.

## Leaving the inert properties in place

`primary_timeseries` and `secondary_timeseries` keep their `write.sort-order` and `write.target-file-size-bytes`
properties from 0002/0006. They are redundant once the real sort order is declared, but harmless, and
`get_rewrite_settings` still reads `write.sort-order` as a fallback. Removing them is a separate cleanup.

## Applying

Run `warehouse/remote/04_maintenance/00_apply_migrations.ipynb`. These statements are metadata-only and apply
instantly. They govern **future** writes.

## Rewriting existing data

Existing files stay unsorted until rewritten:

```sql
CALL iceberg.system.rewrite_data_files(
    table => 'teehr.primary_timeseries',
    strategy => 'sort',
    options => map('rewrite-all', 'true')
)
```

Note `warehouse/remote/04_maintenance/03_rewrite_timeseries.ipynb` is **not** suitable as written: it sorts by
`value_time` first (the partition column) and passes an ad-hoc `sort_order` rather than relying on the table's
declared order. It also targets tables that at 1.02 and 1.18 files per partition have nothing to compact — the
file sizes are capped by partition granularity, not by missing compaction.

Rewrite one table first and re-measure before committing to all ~74 GB.

## Verifying

```sql
SHOW TBLPROPERTIES iceberg.teehr.primary_timeseries;
```

Expect a `sort-order` key of `location_id ASC NULLS LAST, value_time ASC NULLS LAST`.

Read amplification on the query shape that motivated this — compare `Input:` rows against `Output:` rows, which
today is 17,030,839 to 708:

```sql
EXPLAIN ANALYZE
SELECT location_id, value_time, value FROM iceberg.teehr.primary_timeseries
WHERE location_id = 'usgs-01013500'
  AND value_time >= TIMESTAMP '2024-01-01' AND value_time < TIMESTAMP '2024-04-01'
ORDER BY value_time;
```

## Known gotcha

Projecting the `partition` struct alongside other columns in `primary_timeseries$files` fails in Trino with
`Wrong class, expected java.lang.CharSequence, but was java.lang.Integer` — an artifact of a voided `location_id`
field left in the partition spec. Filter on `file_path` with `regexp_extract` instead.

## Still open

With partitions averaging 15.3 MB on `primary_timeseries`, the partition spec is too fine for the 512 MB file
target, which caps what compaction and row-group sizing can achieve. Coarsening `months(value_time)` to
`years(value_time)` would give 116 partitions at a 94.6 MB median / 372.9 MB max and make the `location_id` sort
substantially more effective. `secondary_timeseries` is **not** a candidate: its high-volume forecast
configurations already sit at 156–636 MB monthly, and yearly would push them to 2.4–5.4 GB while only lifting the
long tail of low-volume configurations from 0.32 MB to ~4 MB.

That is a larger migration with a full data rewrite and is deliberately not included here.
