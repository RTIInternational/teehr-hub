-- DDL for analytics_runs tracking table
-- Run once to create the teehr_results schema and analytics_runs table
--
-- Execute via Trino:
--   trino --server http://trino:8080 --catalog iceberg --schema teehr_results < create_analytics_runs.sql

-- Create the results schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS iceberg.teehr_results;

-- Create the analytics_runs table
CREATE TABLE IF NOT EXISTS iceberg.teehr_results.analytics_runs (
    run_id VARCHAR NOT NULL,
    analytics_id VARCHAR NOT NULL,
    cache_key VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    parameters_json VARCHAR,
    result_table VARCHAR,
    created_at TIMESTAMP(6) WITH TIME ZONE,
    started_at TIMESTAMP(6) WITH TIME ZONE,
    finished_at TIMESTAMP(6) WITH TIME ZONE,
    error_message VARCHAR
)
WITH (
    format = 'PARQUET'
);

-- Index hint: While Iceberg doesn't support traditional indexes,
-- queries should filter on run_id (primary key) or (analytics_id, cache_key) for caching
