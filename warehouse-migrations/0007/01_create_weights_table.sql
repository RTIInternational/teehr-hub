CREATE TABLE IF NOT EXISTS grid_pixel_coverage_weights (
    fraction_covered DOUBLE,
    row INT,
    col INT,
    location_id STRING,
    position_index BIGINT,
    configuration_name STRING,
    variable_name STRING,
    domain_name STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
USING iceberg;