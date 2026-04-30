import logging

from pyspark.sql import functions as F


from teehr.fetching.const import (
    NWM30_ANALYSIS_CONFIG
)

logger = logging.getLogger(__name__)

LOCATION_ID_PREFIX = "usgsbasin"
DEFAULT_VARIABLE_NAME = "RAINRATE"

# Maps NWM version string to the corresponding analysis config dict
NWM_VERSION_ANALYSIS_CONFIG = {
    "nwm30": NWM30_ANALYSIS_CONFIG
}
NWM30_WEIGHTS_VARIABLE_NAME = "rainfall_hourly_rate"

# Regex patterns for parsing datetime info from GCS filepaths
DATE_PATTERN = r"nwm\.(\d{8})"
HOUR_PATTERN = r"\.t(\d{2})z"
LEAD_PATTERN = r"\.f(\d{3})\."
TM_PATTERN = r"\.tm(\d+)\."
FILE_CHUNK_SIZE = 100  # The max. number of files to process in each chunk

def cache_weights_view(
    ev,
    location_id_prefix: str,
    weights_domain_name: str,
    weights_variable_name: str,
) -> None:
    """Create and cache a Spark temporary view of pixel coverage weights.

    Reads directly from the remote iceberg.teehr.grid_pixel_coverage_weights
    table, filtering to the specified location prefix, configuration name, and
    variable name, and materializes the result into Spark's in-memory cache
    for fast repeated joins.

    Parameters
    ----------
    ev : RemoteReadWriteEvaluation
        Active TEEHR evaluation instance.
    location_id_prefix : str
        Location ID prefix to filter weights (e.g. "usgsbasin").
    weights_domain_name : str
        Domain name to filter weights (e.g. "nwm30_alaska_forcing").
    weights_variable_name : str
        Variable name to filter weights (e.g. "rainfall_hourly_rate").
    """
    logger.info(
        f"Caching pixel coverage weights view for prefix '{location_id_prefix}', "
        f"domain '{weights_domain_name}', variable '{weights_variable_name}'"
    )
    ev.spark.sql(f"""
        CREATE OR REPLACE TEMPORARY VIEW fractions_view AS
        SELECT fraction_covered, location_id, position_index
        FROM iceberg.teehr.grid_pixel_coverage_weights
        WHERE location_id LIKE '{location_id_prefix}-%'
          AND domain_name = '{weights_domain_name}'
          AND variable_name = '{weights_variable_name}'
    """)
    ev.spark.sql("CACHE TABLE fractions_view")
    logger.info("Pixel coverage weights view cached successfully")

    # Create a small broadcast-friendly DataFrame of distinct position indices
    distinct_positions = ev.spark.sql(
        "SELECT DISTINCT position_index FROM fractions_view"
    )
    distinct_positions.cache()
    logger.info(f"Cached {distinct_positions.count()} distinct position indices for pre-filtering")
    return distinct_positions    

def parse_value_and_reference_times_from_path(nc_sdf, is_analysis: bool):
    """Parse value_time and reference_time from NWM NetCDF GCS filepaths.

    Adds ``value_time`` and ``reference_time`` columns to the DataFrame by
    extracting datetime components from the filepath using regex patterns.

    For analysis/assimilation configurations, ``value_time`` is computed as
    the cycle z-hour minus the tmXX lookback offset, and ``reference_time``
    is set to None. For forecast configurations, ``value_time`` is the cycle
    z-hour plus the lead hours offset, and ``reference_time`` is the cycle
    z-hour timestamp.

    Parameters
    ----------
    nc_sdf : pyspark.sql.DataFrame
        Spark DataFrame with a ``filepath`` column containing GCS URIs of NWM
        NetCDF files.
    is_analysis : bool
        True for analysis/assimilation configs (value_time = cycle z-hour minus
        tmXX offset); False for forecast configs (value_time = z-hour + lead offset).

    Returns
    -------
    pyspark.sql.DataFrame
        Input DataFrame with ``value_time`` and ``reference_time`` columns added.
    """
    if is_analysis:
        # value_time = cycle z-hour minus tmXX lookback offset
        # Use Python API (not SQL f-string) to avoid Spark SQL backslash-escape consuming
        # regex metacharacters like \d in the pattern string.
        cycle_ts = F.to_timestamp(
            F.concat(
                F.regexp_extract("filepath", DATE_PATTERN, 1),
                F.lit(" "),
                F.regexp_extract("filepath", HOUR_PATTERN, 1),
                F.lit(":00")
            ),
            "yyyyMMdd HH:mm"
        )
        tm_hours = F.regexp_extract("filepath", TM_PATTERN, 1).cast("int")
        nc_sdf = nc_sdf.withColumn(
            "value_time",
            (F.unix_timestamp(cycle_ts) - tm_hours * 3600).cast("timestamp")
        ).withColumn(
            "reference_time",
            F.lit(None).cast("timestamp")
        )
    else:
        # value_time = cycle z-hour + lead hours
        cycle_ts = F.to_timestamp(
            F.concat(
                F.regexp_extract("filepath", DATE_PATTERN, 1),
                F.lit(" "),
                F.regexp_extract("filepath", HOUR_PATTERN, 1),
                F.lit(":00"),
            ),
            "yyyyMMdd HH:mm",
        )
        lead_hours = F.regexp_extract("filepath", LEAD_PATTERN, 1).cast("int")
        nc_sdf = nc_sdf.withColumn(
            "value_time",
            (F.unix_timestamp(cycle_ts) + lead_hours * 3600).cast("timestamp")
        ).withColumn(
            "reference_time",
            cycle_ts
        )
    return nc_sdf