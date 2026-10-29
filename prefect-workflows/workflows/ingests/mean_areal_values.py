"""Calculate mean areal values of location polygons from an Icechunk grid using pixel coverage weights."""
import contextlib
import functools
import time

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
import zarr
from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from scipy import sparse
from teehr import Configuration, Evaluation, Unit, Variable
from teehr.fetching.const import UNIT_NAME
from teehr.fetching.nwm.grid_utils import build_weights_matrix, weighted_average_from_matrix
from teehr.fetching.utils import grid_window_memory
from teehr.utils.concurrency import resolve_budget, resolve_cpu_workers, run_concurrent_map

from utils import grid_utils as gu
from utils import time_grid as tg
from workflows.utils.data_status import STATUS_COORD
from workflows.utils.time_utils import to_naive_utc
from workflows.utils.common_utils import initialize_evaluation
from workflows.models.ingest_gridded_data_input import VARIABLE_AND_UNIT_MAPPER
from workflows.models.mean_areal_inputs import MeanArealValuesInput
from pixel_coverage_weights import (
    WEIGHTS_TABLE_NAME, get_readonly_repo_store, resolve_grid_name, write_dataframe_to_warehouse
)


def _written_steps(da: xr.DataArray, args: MeanArealValuesInput) -> xr.DataArray:
    """Grid steps that hold data (time-grid slots not yet written are skipped), within start_dt..end_dt."""
    dim = args.append_dim
    if STATUS_COORD in da.coords:
        da = da.isel({dim: da[STATUS_COORD].values != tg.UNWRITTEN})
    start = to_naive_utc(args.start_dt) if args.start_dt is not None else None
    end = to_naive_utc(args.end_dt) if args.end_dt is not None else None
    return da.sel({dim: slice(start, end)})


def _area_weights(weights_df: pd.DataFrame, da: xr.DataArray, y_dim: str) -> pd.Series:
    """Coverage fractions scaled by pixel area on geographic grids, whose pixels shrink with latitude."""
    if da.rio.crs is None:
        raise ValueError("The grid has no CRS.")
    weights = weights_df["fraction_covered"].astype("float64")
    if da.rio.crs.is_geographic:
        weights = weights * np.cos(np.deg2rad(da[y_dim].values[weights_df["row"].to_numpy()]))
    return weights


def _mean_areal_batch(
    batch: pd.DatetimeIndex,
    da: xr.DataArray,
    args: MeanArealValuesInput,
    window: tuple[int, int, int, int],
    rows: np.ndarray,
    cols: np.ndarray,
    matrix: sparse.csr_matrix,
    location_ids: np.ndarray,
) -> pd.DataFrame:
    """Mean areal values of one batch of steps, as long rows without NaN values."""
    y0, y1, x0, x1 = window
    # Read the bounding window through xarray, so fill values decode to NaN
    values = (
        da.sel({args.append_dim: batch})
        .isel({args.y_dim: slice(y0, y1), args.x_dim: slice(x0, x1)})
        .transpose(args.append_dim, args.y_dim, args.x_dim)
        .values
    )
    means = weighted_average_from_matrix(matrix, values[:, rows - y0, cols - x0], args.min_valid_coverage)
    df = pd.DataFrame({
        "value_time": np.repeat(batch.values, location_ids.size),
        "location_id": np.tile(location_ids, len(batch)),
        "value": means.ravel(),
    })
    return df.dropna(subset=["value"])


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 30, retries=2)
def compute_batch_group(batches: list[pd.DatetimeIndex], workers: int, batch_kwargs: dict) -> pd.DataFrame:
    """Mean areal values of a group of batches, read concurrently."""
    logger = get_run_logger()
    started = time.perf_counter()
    frames = run_concurrent_map(
        functools.partial(_mean_areal_batch, **batch_kwargs), batches, max_workers=workers
    )
    df = pd.concat(frames, ignore_index=True)
    n_steps = sum(len(batch) for batch in batches)
    logger.info(
        f"Computed {n_steps} step(s) through {batches[-1][-1]} in {time.perf_counter() - started:.1f}s "
        f"({len(df)} rows)."
    )
    return df


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 10)
def read_weights_from_warehouse(
    ev: Evaluation,
    location_id_prefix: str,
    grid_name: str
) -> pd.DataFrame:
    """Get the pixel coverage weights of the locations on this grid from the warehouse."""
    logger = get_run_logger()
    df = (
        ev.table(WEIGHTS_TABLE_NAME)
        .filter([
            {"column": "location_id", "operator": "like", "value": f"{location_id_prefix}-%"},
            {"column": "grid_name", "operator": "=", "value": grid_name},
        ])
        .to_sdf()
        .select("fraction_covered", "location_id", "row", "col")
        .toPandas()
    )
    logger.info(f"Retrieved {len(df)} rows of pixel coverage weights from the warehouse table.")
    if len(df) == 0:
        raise ValueError(
            f"No pixel coverage weights were found for grid '{grid_name}' and location prefix "
            f"'{location_id_prefix}'."
        )
    return df


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 10)
def register_domain_values(
    ev: Evaluation,
    args: MeanArealValuesInput,
    variable_long_name: str,
    unit_name: str,
):
    """Add the configuration, variable and unit to the warehouse if they don't exist."""
    logger = get_run_logger()
    timeseries_type = "primary" if args.timeseries_table_name == "primary_timeseries" else "secondary"
    unit_long_name = next(
        (unit["long_name"] for unit in VARIABLE_AND_UNIT_MAPPER[UNIT_NAME].values() if unit["name"] == unit_name),
        unit_name
    )
    entries = {
        "configurations": Configuration(
            name=args.configuration_name,
            timeseries_type=timeseries_type,
            description=f"Mean areal values from the {args.configuration_name} grid",
        ),
        "variables": Variable(name=args.grid_variable_name, long_name=variable_long_name),
        "units": Unit(name=unit_name, long_name=unit_long_name),
    }
    for table_name, entry in entries.items():
        table = ev.table(table_name, namespace_name=args.namespace_name, catalog_name=args.catalog_name)
        exists = not table.filter(
            {"column": "name", "operator": "=", "value": entry.name}
        ).to_sdf().rdd.isEmpty()
        if not exists:
            table.add(entry)
            logger.info(f"Added '{entry.name}' to the '{table_name}' table.")


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 10)
def register_location_crosswalks(ev: Evaluation, args: MeanArealValuesInput, location_ids: np.ndarray):
    """Crosswalk each location to itself, so API queries by location find its secondary timeseries."""
    table = ev.table("location_crosswalks", namespace_name=args.namespace_name, catalog_name=args.catalog_name)
    table.load_dataframe(
        pd.DataFrame({"primary_location_id": location_ids, "secondary_location_id": location_ids}),
        namespace_name=args.namespace_name,
        catalog_name=args.catalog_name,
        write_mode="append",
    )


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

    ev = initialize_evaluation(
        temp_dir_path=args.temp_dir_path,
        start_spark_cluster=args.start_spark_cluster,
        update_configs={
            "spark.sql.execution.arrow.pyspark.enabled": "true"
        }
    )

    store = get_readonly_repo_store(
        dest_bucket=args.dest_bucket,
        base_prefix=args.base_prefix,
        configuration_name=args.configuration_name,
        s3_storage_kwargs=args.s3_storage_kwargs
    )
    weights_df = read_weights_from_warehouse(
        ev=ev,
        location_id_prefix=args.location_id_prefix,
        grid_name=resolve_grid_name(store, args.grid_name, args.configuration_name)
    )
    grid_da = xr.open_zarr(
        store, group=gu.read_data_group(store), decode_coords="all", chunks=None
    )[args.grid_variable_name].rio.set_spatial_dims(x_dim=args.x_dim, y_dim=args.y_dim)
    written_da = _written_steps(grid_da, args)
    if written_da.sizes[args.append_dim] == 0:
        logger.info("No written grid steps in the requested window.")
        return

    # Ingest already stored the grid under teehr variable and unit names
    unit_name = grid_da.attrs.get("units")
    if unit_name is None:
        raise ValueError(f"Grid variable '{args.grid_variable_name}' does not have a 'units' attribute.")
    register_domain_values(
        ev=ev,
        args=args,
        variable_long_name=grid_da.attrs.get("long_name", args.grid_variable_name),
        unit_name=unit_name,
    )

    weights_df["weight"] = _area_weights(weights_df, grid_da, args.y_dim)
    matrix, rows, cols, location_ids = build_weights_matrix(weights_df)
    register_location_crosswalks(ev=ev, args=args, location_ids=location_ids)
    window = (int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1)

    # Shard-aligned batches, so each batch reads whole shards once
    batches = tg.shard_batches(
        written_da[args.append_dim].to_index(),
        grid_da[args.append_dim].to_index(),
        args.time_chunk_size * args.num_shard_chunks,
    )
    steps_per_batch = max(len(batch) for batch in batches)
    batch_bytes = steps_per_batch * grid_window_memory(window[1] - window[0], window[3] - window[2])
    # Zarr already reads each batch's chunks concurrently; more batches mostly add decode CPU
    workers = resolve_budget(io=args.batch_workers or resolve_cpu_workers(), memory_per_item=batch_bytes).io
    if args.max_read_memory_gb is not None:
        workers = max(1, min(workers, int(args.max_read_memory_gb * 1e9 // batch_bytes)))
    logger.info(
        f"Computing {written_da.sizes[args.append_dim]} step(s) for {location_ids.size} location(s) from "
        f"{rows.size} pixel(s) in {len(batches)} batch(es), {workers} at a time."
    )

    batch_kwargs = dict(
        da=grid_da, args=args, window=window, rows=rows, cols=cols, matrix=matrix, location_ids=location_ids
    )
    zarr_config = (
        zarr.config.set({"async.concurrency": args.zarr_concurrency})
        if args.zarr_concurrency else contextlib.nullcontext()
    )
    pending = []
    with zarr_config:
        for start in range(0, len(batches), workers):
            group = batches[start:start + workers]
            pending.append(compute_batch_group(batches=group, workers=workers, batch_kwargs=batch_kwargs))
            is_last = start + workers >= len(batches)
            if sum(len(df) for df in pending) < args.max_rows_per_write and not is_last:
                continue
            df = pd.concat(pending, ignore_index=True)
            pending = []
            if df.empty:
                continue
            df["configuration_name"] = args.configuration_name
            df["variable_name"] = args.grid_variable_name
            df["unit_name"] = unit_name
            df["reference_time"] = None
            if args.timeseries_table_name != "primary_timeseries":
                df["member"] = None
            write_dataframe_to_warehouse(
                ev=ev,
                dataframe=df,
                table_name=args.timeseries_table_name,
                write_mode=args.write_mode,
                catalog_name=args.catalog_name,
                namespace_name=args.namespace_name,
            )
            logger.info(f"Committed mean areal values through {group[-1][-1]}.")
    logger.info("Mean areal values calculation flow completed.")
