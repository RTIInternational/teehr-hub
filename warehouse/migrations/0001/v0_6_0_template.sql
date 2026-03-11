CREATE TABLE units (
    name STRING,
    long_name STRING
) USING iceberg;

CREATE TABLE configurations (
    name STRING,
    type STRING,
    description STRING
) USING iceberg;

CREATE TABLE variables (
    name STRING,
    long_name STRING
) USING iceberg;

CREATE TABLE attributes (
    name STRING,
    description STRING,
    type STRING
) USING iceberg;

CREATE TABLE locations (
    id STRING,
    name STRING,
    geometry BINARY
) USING iceberg;

CREATE TABLE location_crosswalks (
    primary_location_id STRING,
    secondary_location_id STRING
) USING iceberg;

CREATE TABLE primary_timeseries (
    reference_time TIMESTAMP,
    value_time TIMESTAMP,
    configuration_name STRING,
    unit_name STRING,
    variable_name STRING,
    value FLOAT,
    location_id STRING
) USING iceberg;

CREATE TABLE secondary_timeseries (
    reference_time TIMESTAMP,
    value_time TIMESTAMP,
    configuration_name STRING,
    unit_name STRING,
    variable_name STRING,
    value FLOAT,
    location_id STRING,
    member STRING
) USING iceberg;

CREATE TABLE location_attributes(
    location_id STRING,
    attribute_name STRING,
    value STRING
) USING iceberg;

INSERT INTO units VALUES
    ("m^3/s", "Cubic Meters Per Second"),
    ("ft^3/s", "Cubic Feet Per Second"),
    ("km^2", "Square Kilometers"),
    ("mm/s", "Millimeters Per Second");

INSERT INTO variables VALUES
    ("streamflow", "Hourly Instantaneous Streamflow"),
    ("streamflow_hourly_inst", "Hourly Instantaneous Streamflow"),
    ("streamflow_daily_mean", "Daily Mean Streamflow"),
    ("rainfall_hourly_rate", "Hourly Rainfall Rate");