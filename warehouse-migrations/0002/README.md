# Migration 0002: Partitioning and Sort Order

This migration adds partitioning and sort order to the `primary_timeseries` and `secondary_timeseries` tables for improved query performance.

## Changes

### Partitioning
- **primary_timeseries**: Monthly partitioning on `value_time`
- **secondary_timeseries**: Monthly partitioning on `value_time`

### Sort Order
- **primary_timeseries**: `value_time ASC, location_id ASC`
- **secondary_timeseries**: `value_time ASC, reference_time ASC, location_id ASC`

### Table Properties
Sets `write.distribution-mode = 'range'` and `write.sort-order` so all future writes maintain the sort order automatically.

## How to Apply

### Step 1: Apply Metadata Changes (Instant)

Run the SQL statements in `add_partitioning_and_sort_order.sql` via Spark SQL. These are metadata-only changes and execute instantly.

### Step 2: Rewrite Existing Data

Handle data rewrite manually via notebook or let routine maintenance (`routine_table_maintenance.py` with `strategy='sort'`) reorganize data over time.

### Step 3: Verify

```sql
SHOW TBLPROPERTIES iceberg.teehr.primary_timeseries;
```

Should show:
```
write.distribution-mode  | range
write.sort-order         | value_time ASC NULLS LAST, location_id ASC NULLS LAST
```

## Performance Impact

- Queries filtering on `value_time` will benefit from partition pruning
- Queries filtering on `location_id` within a time range will benefit from sorted data skipping
- Write performance may be slightly slower due to sorting, but read performance will improve significantly
