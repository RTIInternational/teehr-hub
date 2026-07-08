from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
import numpy as np
import xarray as xr
import pandas as pd

from teehr import Evaluation

from workflows.utils.common_utils import initialize_evaluation
from models.mean_areal_inputs import MeanArealValuesInput
from pixel_coverage_weights import get_readonly_repo_store, write_dataframe_to_warehouse


@task(timeout_seconds=60 * 10)
def format_to_teehr_timeseries(
    results: pd.DataFrame,
    value_time_array: np.ndarray,
    configuration_name: str,
    variable_name: str,
    reference_time: str,
    unit_name: str,
    timeseries_table_name: str,
    member: str = None,
):
    """Format the results to the teehr timeseries table format."""
    logger = get_run_logger()
    logger.info(f"Formatting results to the '{timeseries_table_name}' teehr timeseries table format.")
    all_ids = np.array([data["location_id"] for data in results])
    all_values = np.array([data["values"] for data in results])
    num_locations = len(all_ids)
    array_length = all_values.shape[1]

    if timeseries_table_name == "primary_timeseries":
        final_df = pd.DataFrame({
            "value_time": np.tile(value_time_array, num_locations),
            "value": all_values.ravel(),
            "location_id": np.repeat(all_ids, array_length),
            "configuration_name": configuration_name,
            "variable_name": variable_name,
            "reference_time": reference_time,
            "unit_name": unit_name,
        })
    elif timeseries_table_name == "secondary_timeseries":
        final_df = pd.DataFrame({
            "value_time": np.tile(value_time_array, num_locations),
            "value": all_values.ravel(),
            "location_id": np.repeat(all_ids, array_length),
            "configuration_name": configuration_name,
            "variable_name": variable_name,
            "reference_time": reference_time,
            "unit_name": unit_name,
            "member": member,
        })
    else:
        raise ValueError(f"Invalid timeseries_table_name: {timeseries_table_name}. Must be 'primary_timeseries' or 'secondary_timeseries'.")
    return final_df


@task(timeout_seconds=60 * 10)
def flatten_dataarray(dataarray: xr.DataArray, append_dim: str) -> xr.DataArray:
    """Flatten a 3D DataArray into a 2D DataArray with dimensions (time, pixel_index)."""
    logger = get_run_logger()
    logger.info("Flattening the 3D DataArray into a 2D DataArray with dimensions (time, pixel_index).")
    x_dim = dataarray.rio.x_dim
    y_dim = dataarray.rio.y_dim
    dataarray = dataarray.sortby(x_dim, ascending=True)
    dataarray = dataarray.sortby(y_dim, ascending=False)
    dataarray = dataarray.transpose(append_dim, y_dim, x_dim)
    flat_da = dataarray.stack(position_index=[y_dim, x_dim])
    flat_da = flat_da.reset_index("position_index", drop=True)
    flat_da = flat_da.drop_vars([y_dim, x_dim], errors="ignore")
    logger.info("Flattening complete. The resulting DataArray has dimensions: " + str(flat_da.dims))
    return flat_da


@task(timeout_seconds=60 * 10)
def calculate_all_polygons(flat_da, weights_df):
    """
    flat_da: The 2D Xarray DataArray pre-flattened to dimensions: (time, position_index)
    weights_df: The Pandas DataFrame containing 'position_index', 'fraction_covered', and 'location_id'
    """
    logger = get_run_logger()
    logger.info("Calculating mean areal values for all polygons.")
    swe_matrix = flat_da.values
    results = []
    gp = weights_df.groupby("location_id")
    for location_id, df in gp:
        inds = df.position_index.values
        weights = df.fraction_covered.values
        pixel_matrix = swe_matrix[:, inds]
        weighted_sum = np.sum(pixel_matrix * weights, axis=1)
        total_weight = np.sum(weights)
        time_series_result = weighted_sum / total_weight
        results.append({
            "location_id": location_id,
            "values": time_series_result
        })
    logger.info(f"Completed calculating mean areal values for {len(results)} polygons.")
    if len(results) == 0:
        logger.error("No results were calculated. The results list is empty.")
        raise ValueError("No results were calculated. The results list is empty.")
    return results


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 10)
def read_weights_from_warehouse(
    ev: Evaluation,
    location_id_prefix: str,
    weights_domain_name: str,
    weights_variable_name: str
):
    """Get the pixel coverage weights DataFrame from the iceberg warehouse table."""
    logger = get_run_logger()
    logger.info(
        f"Reading pixel coverage weights for domain '{weights_domain_name}' "
        f"and locations '{location_id_prefix}' and variable '{weights_variable_name}' "
        "from the iceberg warehouse table."
    )
    df = ev.spark.sql(f"""
        SELECT fraction_covered, location_id, position_index
        FROM iceberg.teehr.grid_pixel_coverage_weights
        WHERE location_id LIKE '{location_id_prefix}-%'
          AND domain_name = '{weights_domain_name}'
          AND variable_name = '{weights_variable_name}'
    """).toPandas()
    logger.info(f"Retrieved {len(df)} rows of pixel coverage weights from the warehouse table.")
    if len(df) == 0:
        logger.error(
            f"No pixel coverage weights were found for domain '{weights_domain_name}' "
            f"and location prefix '{location_id_prefix}' and variable name '{weights_variable_name}'."
        )
        raise ValueError(
            f"No pixel coverage weights were found for domain '{weights_domain_name}' "
            f"and location prefix '{location_id_prefix}' and variable name '{weights_variable_name}'."
        )
    return df

@flow(
    name="calculate-mean-areal-values",
    description="Calculate mean areal values for a given grid and polygon layer."
)
def calculate_mean_areal_values(args: MeanArealValuesInput):
    """Calculate mean areal values for a given grid and polygon layer.
    
    Parameters
    ----------
    args : MeanArealValuesInput
        Input arguments for the flow.
    """
    logger = get_run_logger()
    logger.info("Starting mean areal values calculation flow.")

    # Initialize the evaluation context
    ev = initialize_evaluation(
        temp_dir_path=args.temp_dir_path,
        start_spark_cluster=args.start_spark_cluster,
        update_configs={
            "spark.sql.execution.arrow.pyspark.enabled": "true"
        }
    )

    # Read the pixel coverage weights from the iceberg warehouse table
    teehr_variable_name = args.variable_and_unit_mapper.variable_name[args.grid_variable_name].name
    weights_df = read_weights_from_warehouse(
        ev=ev,
        location_id_prefix=args.location_id_prefix,
        weights_domain_name=args.domain_name,
        weights_variable_name=teehr_variable_name
    )

    # Read all timesteps of the grid from the Icechunk repo
    store = get_readonly_repo_store(
        dest_bucket=args.dest_bucket,
        base_prefix=args.base_prefix,
        configuration_name=args.configuration_name,
        s3_storage_kwargs=args.s3_storage_kwargs
    )

    grid_template_da = xr.open_zarr(
        store,
        group="raw_data",
        decode_coords="all"
    )[args.grid_variable_name]

    # Flatten the 3D DataArray into a 2D DataArray with dimensions (time, pixel_index)
    flat_da = flatten_dataarray(grid_template_da, append_dim=args.append_dim)

    # Calculate mean areal values for each polygon at each timestep
    mean_areal_values_results = calculate_all_polygons(flat_da, weights_df)

    grid_unit_name = grid_template_da.attrs.get("units", None)
    if grid_unit_name is None:
        raise ValueError(f"Grid variable '{args.grid_variable_name}' does not have a 'units' attribute.")
    teehr_unit_name = args.variable_and_unit_mapper.unit_name[grid_unit_name].name

    # Format to teehr timeseries table format
    mean_areal_values_df = format_to_teehr_timeseries(
        results=mean_areal_values_results,
        value_time_array=flat_da[args.append_dim].values,
        configuration_name=args.configuration_name,
        variable_name=teehr_variable_name,
        reference_time=None,  # Placeholder for reference_time column
        unit_name=teehr_unit_name,
        timeseries_table_name=args.timeseries_table_name
    )

    # Write the mean areal values to the iceberg warehouse primary or secondary timeseries table
    write_dataframe_to_warehouse(
        ev=ev,
        dataframe=mean_areal_values_df,
        table_name=args.timeseries_table_name,
        write_mode="append",
    )
    logger.info("Mean areal values calculation flow completed.")