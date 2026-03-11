-- Migration 0002: Add partitioning and sort order to timeseries tables
-- 
-- This migration adds:
-- 1. Monthly partitioning on value_time for both primary and secondary timeseries
-- 2. Sort order (value_time, location_id) for optimized query performance
--
-- Note: These are metadata-only changes (instant). 
-- After applying, run the rewrite_data_files procedure to reorganize existing data.
-- See: rewrite_timeseries_data.sql

--------------------------------------------------------------------------------
-- PRIMARY TIMESERIES
--------------------------------------------------------------------------------

-- Add monthly partitioning on value_time
ALTER TABLE primary_timeseries ADD PARTITION FIELD months(value_time);

-- Set sort order and distribution mode for future writes
ALTER TABLE primary_timeseries SET TBLPROPERTIES (
    'write.distribution-mode' = 'range',
    'write.sort-order' = 'value_time ASC NULLS LAST, location_id ASC NULLS LAST'
);

--------------------------------------------------------------------------------
-- SECONDARY TIMESERIES
--------------------------------------------------------------------------------

-- Add monthly partitioning on value_time
ALTER TABLE secondary_timeseries ADD PARTITION FIELD months(value_time);

-- Set sort order and distribution mode for future writes
-- Uses value_time + reference_time since secondary data often queries by forecast reference
ALTER TABLE secondary_timeseries SET TBLPROPERTIES (
    'write.distribution-mode' = 'range',
    'write.sort-order' = 'value_time ASC NULLS LAST, reference_time ASC NULLS LAST, location_id ASC NULLS LAST'
);
