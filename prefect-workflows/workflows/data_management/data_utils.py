from workflows.utils.common_utils import table_exists
from prefect.cache_policies import NO_CACHE
from prefect import task, get_run_logger


@task(cache_policy=NO_CACHE)
def write_to_warehouse(ev, sdf, table_name, write_mode=None):
    """
    Helper function to write a Spark DataFrame to the warehouse.
    """
    logger = get_run_logger()
    if write_mode is None:
        write_mode = (
            "overwrite"
            if table_exists(ev=ev, table_name=table_name)
            else "create_or_replace"
        )
    logger.info(f"Writing dataFrame to warehouse table {table_name} with write mode {write_mode}...")
    ev._write.to_warehouse(
        source_data=sdf,
        table_name=table_name,
        write_mode=write_mode
    )
    logger.info(f"Finished writing dataFrame to warehouse table {table_name}.")