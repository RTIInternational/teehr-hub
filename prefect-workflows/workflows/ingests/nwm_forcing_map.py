"""Prefect workflow to calculate Mean Areal Precipitation (MAP) from NWM forcing grids.

Uses Apache Sedona's RS_FromNetCDF to read NetCDF files directly from GCS and computes
weighted averages using pixel coverage weights stored in the remote Iceberg warehouse.

Supports both analysis/assimilation (e.g. forcing_analysis_assim) and forecast
(e.g. forcing_short_range, forcing_medium_range) NWM forcing configurations.
"""
import time
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Union, List, Iterable

import pandas as pd
from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from pyspark.sql import functions as F

from teehr import Configuration
from teehr.fetching.utils import (
    format_nwm_configuration_metadata,
    build_remote_nwm_filelist,
)
from teehr.fetching.const import (
    NWM30_ANALYSIS_CONFIG,
    NWM_VARIABLE_MAPPER,
    VARIABLE_NAME
)
from teehr.utils.utils import remove_dir_if_exists
from workflows.utils.common_utils import initialize_evaluation


LOOKBACK_DAYS = 1
LOCATION_ID_PREFIX = "usgsbasin"
DEFAULT_VARIABLE_NAME = "RAINRATE"

# Maps NWM version string to the corresponding analysis config dict
NWM_VERSION_ANALYSIS_CONFIG = {
    "nwm30": NWM30_ANALYSIS_CONFIG,
}
NWM30_WEIGHTS_VARIABLE_NAME = "rainfall_hourly_rate"

# Regex patterns for parsing datetime info from GCS filepaths
DATE_PATTERN = r"nwm\.(\d{8})"
HOUR_PATTERN = r"\.t(\d{2})z"
LEAD_PATTERN = r"\.f(\d{3})\."
TM_PATTERN = r"\.tm(\d+)\."
FILE_CHUNK_SIZE = 100  # The max. number of files to process in each chunk


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 10)
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
    logger = get_run_logger()
    logger.info(
        f"Caching pixel coverage weights view for prefix '{location_id_prefix}', "
        f"domain '{weights_domain_name}', variable '{weights_variable_name}'"
    )
    ev.spark.sql(f"""
        CREATE OR REPLACE TEMPORARY VIEW fractions_view AS
        SELECT fraction_covered, location_id, position_index, domain_name, variable_name
        FROM iceberg.teehr.grid_pixel_coverage_weights
        WHERE location_id LIKE '{location_id_prefix}-%'
          AND domain_name = '{weights_domain_name}'
          AND variable_name = '{weights_variable_name}'
    """)
    ev.spark.sql("CACHE TABLE fractions_view")
    logger.info("Pixel coverage weights view cached successfully")


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


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 60)
def compute_and_write_map(
    ev,
    filepaths: Iterable[str],
    nwm_variable_name: str,
    teehr_config_name: str,
    teehr_unit_name: str,
    teehr_variable_name: str,
    is_analysis: bool,
    nwm_cache_dir: Path,
    chunk_start: str,
    chunk_end: str,
    output_type: str,
    weights_domain_name: str,
    member: str = None,
) -> None:
    """Compute mean areal precipitation (MAP) and write to a parquet cache file.

    Uses Apache Sedona's RS_FromNetCDF to read NWM forcing NetCDF files from
    GCS, explodes pixel values, joins with the cached fractions_view, and
    computes a coverage-weighted average per location and timestep. Results
    are written to a parquet file named by the chunk's start and end datetimes
    inside nwm_cache_dir. Call ev._load.from_cache() after all chunks are
    processed to load the full dataset into the warehouse.

    Parameters
    ----------
    ev : RemoteReadWriteEvaluation
        Active TEEHR evaluation instance.
    filepaths : list or np.array of str
        GCS URIs of the NWM NetCDF files to process.
    nwm_variable_name : str
        NetCDF variable name to extract (e.g. "RAINRATE").
    teehr_config_name : str
        TEEHR configuration name to write (e.g. "nwm30_forcing_analysis_assim").
    teehr_unit_name : str
        Unit name to write (e.g. "mm/s").
    teehr_variable_name : str
        TEEHR variable name to write (e.g. "rainfall_hourly_rate").
    is_analysis : bool
        True for analysis/assimilation configs (value_time = cycle z-hour minus tmXX offset);
        False for forecast configs (value_time = z-hour + lead offset).
    nwm_cache_dir : Path
        Directory to write parquet cache files.
    chunk_start : str
        Start filename of the chunk, used to name the output parquet file.
    chunk_end : str
        End filename of the chunk, used to name the output parquet file.
    output_type : str
        Type of timeseries to write (e.g. "primary" or "secondary").
    weights_domain_name : str
        Domain name to filter pixel coverage weights table (e.g. "nwm30_conus_forcing").
    member : str, optional
        Member name to write (e.g. "0"). Only used when output_type is "secondary".
    """
    logger = get_run_logger()
    t0 = time.time()
    logger.info(f"Processing {len(filepaths)} NWM forcing files")
    # Ensure filepaths are list of strings
    fpath_list = [str(fp) for fp in filepaths]
    # Read NetCDF files via Sedona and extract the target variable as a raster
    nc_sdf = (
        ev.spark.read.format("binaryFile")
        .load(fpath_list)
        .selectExpr(
            f"RS_FromNetCDF(content, '{nwm_variable_name}', 'x', 'y') as raster",
            "path as filepath",
        )
    )
    logger.info("Parsing value_time and reference_time from filepaths.")
    nc_sdf = parse_value_and_reference_times_from_path(nc_sdf, is_analysis)

    logger.info("Exploding raster pixels.")
    raster_exp_sdf = nc_sdf.selectExpr(
        "posexplode(RS_BandAsArray(raster, 1))",
        "value_time",
        "reference_time",
    ).selectExpr(
        "value_time",
        "reference_time",
        "col as value",
        "CAST(pos AS BIGINT) as position_index",
    )
    raster_exp_sdf.createOrReplaceTempView("raster_values")

    # Compute coverage-weighted average per location and timestep
    map_results = ev.spark.sql(f"""
        SELECT /*+ BROADCAST(w) */
            w.location_id,
            CAST(r.value_time AS TIMESTAMP_NTZ) AS value_time,
            CAST(SUM(r.value * w.fraction_covered) / SUM(w.fraction_covered) AS FLOAT) AS value,
            CAST(r.reference_time AS TIMESTAMP_NTZ) AS reference_time,
            '{teehr_unit_name}' AS unit_name,
            '{teehr_variable_name}' AS variable_name,
            '{teehr_config_name}' AS configuration_name
        FROM
            raster_values AS r
        JOIN
            fractions_view AS w ON r.position_index = w.position_index
        WHERE
            w.domain_name = '{weights_domain_name}'
        GROUP BY
            w.location_id, r.value_time, r.reference_time
    """)
    if output_type == "secondary":
        map_results = map_results.withColumn("member", F.lit(member))
    out_path = nwm_cache_dir / f"{chunk_start}_to_{chunk_end}"
    map_results.write.parquet(out_path.as_posix())
    logger.info(f"Wrote chunk to cache: {out_path.name}")

    ev.spark.catalog.dropTempView("raster_values")
    elapsed = (time.time() - t0) / 60
    logger.info(
        f"Processed {len(filepaths)} files and wrote MAP to cache in {elapsed:.2f} min"
    )


@flow(
    flow_run_name="ingest-nwm-forcing-map",
    timeout_seconds=60 * 60 * 4,
)
def ingest_nwm_forcing_map(
    temp_dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp, None] = None,
    num_lookback_days: Union[int, None] = LOOKBACK_DAYS,
    nwm_configuration: str = "forcing_analysis_assim",
    nwm_version: str = "nwm30",
    nwm_variable_name: str = DEFAULT_VARIABLE_NAME,
    teehr_unit_name: str = "mm/s",
    location_id_prefix: str = LOCATION_ID_PREFIX,
    start_spark_cluster: bool = False,
    file_chunk_size: int = FILE_CHUNK_SIZE,
    target_table_name: str = "primary_timeseries",
    t_minus_hours: Union[List[int], None] = None,
    member: Union[str, None] = None,
) -> None:
    """Calculate Mean Areal Precipitation from NWM forcing grids and write to TEEHR.

    Reads NWM forcing NetCDF files directly from GCS using Apache Sedona, computes
    a coverage-weighted average per location using pixel weights from the remote
    iceberg.teehr.grid_pixel_coverage_weights table, and appends results to the
    primary_timeseries table in the warehouse.

    Supports both analysis/assimilation configs (e.g. forcing_analysis_assim) and
    forecast configs (e.g. forcing_short_range, forcing_medium_range).

    Parameters
    ----------
    temp_dir_path : str or Path
        Path for TEEHR temporary evaluation files.
    end_dt : str, datetime, pd.Timestamp, or None
        End of the processing window. Defaults to the current UTC time.
    num_lookback_days : int or None
        Number of days to look back from end_dt. If None, the start date is
        determined from the latest value_time already in primary_timeseries
        for this configuration, or the latest reference_time in secondary_timeseries
        for this configuration.
    nwm_configuration : str
        NWM forcing configuration to process (e.g. "forcing_analysis_assim",
        "forcing_short_range", "forcing_medium_range").
    nwm_version : str
        NWM version string (e.g. "nwm30").
    nwm_variable_name : str
        NetCDF variable name to extract (e.g. "RAINRATE", "T2D").
    teehr_unit_name : str
        TEEHR unit name for the output timeseries (e.g. "mm/s", "K").
        Defaults to "mm/s" for RAINRATE.
    location_id_prefix : str
        Location ID prefix to filter pixel coverage weights (e.g. "usgsbasin").
    start_spark_cluster : bool
        Whether to start a Kubernetes Spark cluster (True) or run locally (False).
    file_chunk_size : int
        Number of files to process per chunk. Larger values use more memory
        but reduce overhead.
    target_table_name : str
        Name of the target table in the TEEHR-Cloud warehouse to write the results to.
        Can be "primary_timeseries" or "secondary_timeseries".
    t_minus_hours : List[int]
        Specifies the look-back hours to include if an assimilation
        configuration is specified.
    member : str, optional
        Member name to write to secondary_timeseries (e.g. "0").
    """
    logger = get_run_logger()

    if end_dt is None:
        end_dt = datetime.now(UTC).replace(tzinfo=None)
    elif isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        enable_gcs=True,
        gcs_project_id="anonymous"
    )
    ev_config = format_nwm_configuration_metadata(
        nwm_config_name=nwm_configuration,
        nwm_version=nwm_version,
    )

    variable_mapper = NWM_VARIABLE_MAPPER
    ev_variable_name = variable_mapper[VARIABLE_NAME].get(
            nwm_variable_name, {}
    ).get("name", nwm_variable_name)

    analysis_config_dict = NWM_VERSION_ANALYSIS_CONFIG.get(nwm_version, NWM30_ANALYSIS_CONFIG)
    is_analysis = nwm_configuration in analysis_config_dict

    if target_table_name == "primary_timeseries":
        output_type = "primary"
        latest_time_field_name = "value_time"
    else:
        output_type = "secondary"
        latest_time_field_name = "reference_time"

    if num_lookback_days is None:
        logger.info(
            "No lookback days provided, determining start date from latest "
            f"{latest_time_field_name} in {target_table_name}"
        )
        result = ev.spark.sql(f"""
            SELECT MAX({latest_time_field_name}) AS latest_time
            FROM iceberg.teehr.{target_table_name}
            WHERE configuration_name = '{ev_config["name"]}'
        """).collect()
        latest_time = result[0].asDict()["latest_time"] if result else None
        if latest_time is not None:
            start_dt = latest_time + timedelta(hours=1)
        else:
            start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    else:
        logger.info(
            f"Setting start date to {num_lookback_days} days before end date"
        )
        start_dt = end_dt - timedelta(days=num_lookback_days)

    logger.info(f"Processing NWM forcing MAP from {start_dt} to {end_dt}")

    # Add configuration to warehouse if it doesn't already exist
    config_exists = not ev.configurations.filter(
        {
            "column": "name",
            "operator": "=",
            "value": ev_config["name"],
        }
    ).to_sdf().rdd.isEmpty()
    if not config_exists:
        ev.configurations.add(
            Configuration(
                name=ev_config["name"],
                timeseries_type=output_type,
                description=ev_config["description"],
            )
        )

    nwm_cache_dir = Path(ev.cache_dir) / "fetching" / ev_config["name"]
    remove_dir_if_exists(nwm_cache_dir)
    nwm_cache_dir.mkdir(parents=True, exist_ok=True)

    if "hawaii" in nwm_configuration:
        weights_domain_name = "nwm30_hawaii_forcing"
    elif "alaska" in nwm_configuration:
        weights_domain_name = "nwm30_alaska_forcing"
    elif "puertorico" in nwm_configuration:
        weights_domain_name = "nwm30_puertorico_forcing"
    else:
        weights_domain_name = "nwm30_conus_forcing"

    cache_weights_view(
        ev=ev,
        location_id_prefix=location_id_prefix,
        weights_domain_name=weights_domain_name,
        weights_variable_name=NWM30_WEIGHTS_VARIABLE_NAME,
    )

    filepaths = build_remote_nwm_filelist(
        configuration=nwm_configuration,
        output_type="forcing",
        start_dt=start_dt,
        end_dt=end_dt,
        analysis_config_dict=analysis_config_dict,
        t_minus_hours=t_minus_hours,
        ignore_missing_file=False,
        prioritize_analysis_value_time=False,
        drop_overlapping_assimilation_values=True,
        ingest_days=None
    )
    # For sedona the filepath must start with 'gs' instead of 'gcs'
    filepaths = sorted([fp.replace("gcs://", "gs://") for fp in filepaths])
    chunked_filepaths = [
        filepaths[i:i+file_chunk_size] for i in range(0, len(filepaths), file_chunk_size)
    ]

    logger.info(
        f"Processing {len(filepaths)} file(s) in {len(chunked_filepaths)} chunk(s) "
        f"of up to {file_chunk_size} file(s) per chunk"
    )
    for filepath_chunk in chunked_filepaths:
        logger.info(
            f"Chunk {filepath_chunk[0]} – {filepath_chunk[-1]}: "
            f"{len(filepath_chunk)} file(s)"
        )
        chunk_start = f"{Path(filepath_chunk[0]).parent.parent.name}_{Path(filepath_chunk[0]).stem}"
        chunk_end = f"{Path(filepath_chunk[-1]).parent.parent.name}_{Path(filepath_chunk[-1]).stem}"
        compute_and_write_map(
            ev=ev,
            filepaths=filepath_chunk,
            nwm_variable_name=nwm_variable_name,
            teehr_config_name=ev_config["name"],
            teehr_unit_name=teehr_unit_name,
            teehr_variable_name=ev_variable_name,
            is_analysis=is_analysis,
            nwm_cache_dir=nwm_cache_dir,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            output_type=output_type,
            member=member,
            weights_domain_name=weights_domain_name
        )

    logger.info("Loading cached MAP data into the warehouse")
    ev._load.from_cache(
        in_path=nwm_cache_dir,
        table_name=target_table_name,
    )
    logger.info("Successfully completed NWM forcing MAP ingestion")
    ev.spark.stop()
