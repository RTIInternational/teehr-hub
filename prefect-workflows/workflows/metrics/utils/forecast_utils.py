from typing import List
import logging

from prefect import get_run_logger

import teehr
from pyspark.sql import DataFrame

logging.getLogger("teehr").setLevel(logging.INFO)


def join_forecast_timeseries(
    ev: teehr.Evaluation,
    forecast_configuration_names: List[str]
) -> DataFrame:
    """Join secondary forecasts with primary timeseries.

    Notes
    -----
    - Joins secondary timeseries whose configuration names are
      in the provided list to primary timeseries via the location
      crosswalk.
    """
    logger = get_run_logger()

    logger.info("Creating joined forecast timeseries table...")
    # Build the WHERE clause for configuration filtering
    where_clause = ""
    if forecast_configuration_names:
        # Convert list to SQL IN clause format
        config_list = "', '".join(forecast_configuration_names)
        where_clause = f"WHERE sf.configuration_name IN ('{config_list}')"
        logger.info(
            f"Filtering to configurations: {forecast_configuration_names}"
        )

    joined_sdf = ev.sql(f"""
        SELECT
            sf.reference_time
            , sf.value_time as value_time
            , pf.location_id as primary_location_id
            , sf.location_id as secondary_location_id
            , pf.value as primary_value
            , sf.value as secondary_value
            , sf.configuration_name
            , sf.unit_name
            , sf.variable_name
            , sf.member
        FROM secondary_timeseries sf
        JOIN location_crosswalks cf
            on cf.secondary_location_id = sf.location_id
        JOIN primary_timeseries pf
            on cf.primary_location_id = pf.location_id
            and sf.value_time = pf.value_time
            and sf.unit_name = pf.unit_name
            and sf.variable_name = pf.variable_name
        {where_clause}
        """,
        create_temp_views=[
            "secondary_timeseries",
            "location_crosswalks",
            "primary_timeseries"
        ]
    )
    logger.info("Joined timeseries table created.")
    return joined_sdf
