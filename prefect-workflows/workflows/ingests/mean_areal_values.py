"""Calculate mean areal values of location polygons from a grid using pixel coverage weights.

``calculate_mean_areal_values`` reads one of our Icechunk repos. ``mean_areal_for_grid`` does the work for any
lazily opened grid, so flows for outside sources (e.g. AORC, dynamical.org) open theirs and call it.

Batches follow the grid's storage chunks (``plan_reads``) and are computed with ``teehr_icechunk.mean_areal_kernel`` as Spark
``mapInArrow`` tasks that write straight to the warehouse: on executors with ``start_spark_cluster``, else in Spark
local mode on the Prefect pod.
"""
import logging
import math
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from teehr import Configuration, Evaluation
from teehr.evaluation.write import AUDIT_COLUMNS
import teehr_icechunk
from teehr_icechunk import time_grid as tg
from teehr_icechunk.concurrency import resolve_budget, resolve_cpu_workers
from teehr_icechunk.grid_spec import GridSpec, open_grid_dataset, read_grid_spec
from teehr_icechunk.mean_areal_kernel import BlockTask, GridWeights, arrow_task_runner
from teehr_icechunk.mean_areal_plan import (
    MAX_SLICE_STEPS, area_weights, plan_reads, positions, written_forecast_steps, written_steps,
)
from teehr_icechunk.repo_const import MEMBER
from teehr_icechunk.weights import build_weights_matrix

from workflows.utils.time_utils import to_naive_utc
from workflows.utils.common_utils import initialize_evaluation
from workflows.models.mean_areal_inputs import MeanArealValuesInput
from workflows.utils.teehr_mapping import TeehrMapping, lead_variable_names, mapping_from_attrs, resolve_teehr_mapping
from pixel_coverage_weights import (
    ARROW_CONFIGS, WEIGHTS_TABLE_NAME, get_readonly_repo_store, like_prefix, resolve_grid_name,
    write_dataframe_to_warehouse,
)

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)

# Attempts per Spark task in local mode, which otherwise never retries a failed task (e.g. a transient S3 error)
LOCAL_TASK_ATTEMPTS = 3


def _window(args: MeanArealValuesInput) -> tuple:
    """The run's start_dt and end_dt as naive UTC (None when unset)."""
    return tuple(to_naive_utc(t) if t is not None else None for t in (args.start_dt, args.end_dt))


def _step_columns(steps: pd.Index, dim: str, lead_names: dict | None = None) -> dict[str, np.ndarray]:
    """Timeseries columns of each step: its value_time, a forecast's reference_time and member, and with
    ``lead_names`` its variable_name by lead."""
    if not isinstance(steps, pd.MultiIndex):
        return {"value_time": steps.values}
    cycles = steps.get_level_values(dim)
    columns = {
        "value_time": (cycles + pd.to_timedelta(steps.get_level_values(steps.names[-1]), unit="h")).values,
        "reference_time": cycles.values,
    }
    if MEMBER in steps.names:
        # teehr's member is a string
        columns["member"] = steps.get_level_values(MEMBER).astype(str).values
    if lead_names is not None:
        columns["variable_name"] = steps.get_level_values(steps.names[-1]).map(lead_names).values.astype(str)
    return columns


def _block_tasks(batch: pd.Index, da: xr.DataArray, dim: str, fixed: dict,
                 lead_names: dict | None = None) -> list[BlockTask]:
    """The batch as rectangular blocks of ``isel`` positions, with each block's step columns.

    Forecast members sharing their cycles and leads form one block, so a chunk holding every member is read once.
    """
    if not fixed:
        return [BlockTask({dim: positions(da[dim], batch)}, _step_columns(batch, dim))]
    lead_dim = list(fixed)[-1]
    merged: dict[tuple, list] = {}
    for block in tg.step_blocks(batch, fixed):
        key = (tuple(block.get_level_values(dim).unique()), tuple(block.get_level_values(lead_dim).unique()))
        merged.setdefault(key, []).extend(block.get_level_values(MEMBER).unique() if MEMBER in fixed else [])
    tasks = []
    for (cycles, leads), block_members in merged.items():
        levels = [list(cycles), *([sorted(set(block_members))] if MEMBER in fixed else []), list(leads)]
        steps = pd.MultiIndex.from_product(levels, names=batch.names)
        selection = {name: positions(da[name], level) for name, level in zip(batch.names, levels)}
        tasks.append(BlockTask(selection, _step_columns(steps, dim, lead_names)))
    return tasks


def _kernel_kwargs(args: MeanArealValuesInput, chunk_shape: tuple[int, int] | None, scale: float = 1.0,
                   offset: float = 0.0, **extra) -> dict:
    """``mean_areal_block`` settings."""
    return dict(
        y_dim=args.y_dim, x_dim=args.x_dim, chunk_shape=chunk_shape, max_slice_steps=MAX_SLICE_STEPS,
        min_coverage=args.min_valid_coverage, scale=scale, offset=offset, **extra,
    )


def _write_groups(batches: list[pd.Index], args: MeanArealValuesInput, n_zones: int, forecast: bool) -> list[list]:
    """Consecutive batches written together, about ``max_rows_per_write`` rows each.

    A forecast cycle is never split across writes, so each write's replace condition (by cycle) covers only its
    own rows; analysis writes cover disjoint time ranges wherever they split.
    """
    dim = args.append_dim
    groups, current, n_rows = [], [], 0
    for i, batch in enumerate(batches):
        current.append(batch)
        n_rows += len(batch) * n_zones
        nxt = batches[i + 1] if i + 1 < len(batches) else None
        at_boundary = nxt is None or not forecast or (
            nxt.get_level_values(dim).min() > batch.get_level_values(dim).max()
        )
        if at_boundary and (nxt is None or n_rows >= args.max_rows_per_write):
            groups.append(current)
            current, n_rows = [], 0
    return groups


def replace_filters(args: MeanArealValuesInput, variable_names: list[str], steps: pd.Index) -> list[dict]:
    """The rows one write replaces: this configuration, its variables and location layer, over the write's steps.

    Every row the write produces matches them. Unit and member are left out on purpose: a rerun must also remove
    rows written in an earlier unit, or for members it no longer produces.
    """
    if isinstance(steps, pd.MultiIndex):
        time_column, times = "reference_time", steps.get_level_values(args.append_dim)
    else:
        time_column, times = "value_time", steps
    return [
        {"column": "configuration_name", "operator": "=", "value": args.configuration_name},
        {"column": "variable_name", "operator": "in", "value": variable_names},
        {"column": "location_id", "operator": "like", "value": like_prefix(args.location_id_prefix)},
        {"column": time_column, "operator": ">=", "value": pd.Timestamp(times.min())},
        {"column": time_column, "operator": "<=", "value": pd.Timestamp(times.max())},
    ]


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
            {"column": "location_id", "operator": "like", "value": like_prefix(location_id_prefix)},
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
def check_locations(ev: Evaluation, args: MeanArealValuesInput, location_ids: np.ndarray):
    """Every weighted location must exist where we write, since timeseries writes skip foreign-key validation."""
    locations = ev.table("locations", namespace_name=args.namespace_name, catalog_name=args.catalog_name)
    known = {
        row["id"] for row in locations.filter(
            filters=[{"column": "id", "operator": "like", "value": like_prefix(args.location_id_prefix)}]
        ).to_sdf().select("id").collect()
    }
    missing = set(location_ids) - known
    if missing:
        raise ValueError(
            f"{len(missing)} weighted location(s) aren't in the locations table, e.g. {sorted(missing)[:5]}."
        )


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 10)
def register_domain_values(
    ev: Evaluation,
    args: MeanArealValuesInput,
    mapping: TeehrMapping,
):
    """Add the configuration, variables and unit to the warehouse if they don't exist."""
    logger = get_run_logger()
    timeseries_type = "primary" if args.timeseries_table_name == "primary_timeseries" else "secondary"
    configuration = Configuration(
        name=args.configuration_name,
        timeseries_type=timeseries_type,
        description=f"Mean areal values from the {args.configuration_name} grid",
    )
    entries = [
        ("configurations", configuration),
        *(("variables", variable) for variable in mapping.variables),
        ("units", mapping.unit),
    ]
    for table_name, entry in entries:
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


def mean_areal_evaluation(args: MeanArealValuesInput) -> Evaluation:
    """An evaluation whose Spark session suits the mean areal tasks."""
    # A task's Python worker: its task budget plus room for Arrow buffers
    task_bytes = 1.5 * args.task_memory_gb * 1e9
    python_gb = math.ceil(task_bytes * args.executor_cores / 1e9)
    configs = {
        **ARROW_CONFIGS,
        # Executor pod memory beyond the JVM heap: each Python worker's task budget plus room for Arrow buffers, and
        # 1 GB for the JVM's own overhead. Not spark.executor.pyspark.memory, which caps each worker's virtual
        # memory, and zarr's and Icechunk's threads reserve far more of that than they use
        "spark.executor.memoryOverhead": f"{python_gb + 1}g",
        # A duplicate task attempt would only re-read the grid
        "spark.speculation": "false",
    }
    if not args.start_spark_cluster:
        # Local mode on the Prefect pod: as many tasks at once as fit in its memory, not one per core
        workers = resolve_budget(io=resolve_cpu_workers(), memory_per_item=int(task_bytes)).io
        configs["spark.master"] = f"local[{workers},{LOCAL_TASK_ATTEMPTS}]"
        get_run_logger().info(f"Spark local mode with {workers} task(s) at once.")
    return initialize_evaluation(
        temp_dir_path=args.temp_dir_path,
        start_spark_cluster=args.start_spark_cluster,
        executor_instances=args.executor_instances,
        executor_cores=args.executor_cores,
        executor_memory=args.executor_memory,
        update_configs=configs,
    )


def _write(ev: Evaluation, data, args: MeanArealValuesInput, variable_names: list[str], steps: pd.Index):
    """Write one group's rows with the flow's write mode."""
    write_dataframe_to_warehouse(
        ev=ev,
        dataframe=data,
        table_name=args.timeseries_table_name,
        write_mode=args.write_mode,
        catalog_name=args.catalog_name,
        namespace_name=args.namespace_name,
        replace_filters=(
            replace_filters(args, variable_names, steps) if args.write_mode == "replace_where" else None
        ),
    )


def _compute_on_spark(ev, da, args, plan, groups, weights: GridWeights, fixed: dict, constants: dict,
                      mapping: TeehrMapping, lead_names: dict | None):
    """Batches run as Spark mapInArrow tasks, computed once per group and written to the warehouse."""
    from pyspark import cloudpickle
    from pyspark.sql import Observation
    from pyspark.sql import functions as F
    from pyspark.sql.pandas.types import to_arrow_schema
    from pyspark.sql.types import StructType

    logger = get_run_logger()
    catalog = args.catalog_name or ev.active_catalog.catalog_name
    namespace = args.namespace_name or ev.active_catalog.namespace_name
    table_schema = ev.spark.table(f"{catalog}.{namespace}.{args.timeseries_table_name}").schema
    schema = StructType([field for field in table_schema if field.name not in AUDIT_COLUMNS])
    dim = args.append_dim
    da = da.transpose(dim, *fixed, args.y_dim, args.x_dim)
    # Executors don't have our workflow code, so send the kernel's code with each task
    # Executors don't have teehr-icechunk; ship the kernel (and the weights helpers it uses) by value
    cloudpickle.register_pickle_by_value(teehr_icechunk)
    for i, group in enumerate(groups, start=1):
        tasks = [block for batch in group for block in _block_tasks(batch, da, dim, fixed, lead_names)]
        run = arrow_task_runner(tasks, da, weights, **_kernel_kwargs(
            args, plan.chunk_shape, mapping.scale, mapping.offset, constants=constants, schema=to_arrow_schema(schema)
        ))
        stats = Observation(f"mean_areal_{i}")
        sdf = (
            # One task per partition, so tasks spread evenly over the workers
            ev.spark.range(len(tasks), numPartitions=len(tasks))
            .selectExpr("CAST(id AS INT) AS task")
            .mapInArrow(run, schema)
            .observe(stats, F.count(F.lit(1)).alias("rows"), F.min("value").alias("min"), F.max("value").alias("max"))
            # The write reads its input more than once (sampling for the table's sort order, upsert's MERGE), so
            # keep the rows rather than recompute the grid each time
            .persist()
        )
        steps = group[0].append(group[1:])
        started = time.perf_counter()
        try:
            _write(ev, sdf, args, [variable.name for variable in mapping.variables], steps)
        finally:
            sdf.unpersist()
        logger.info(
            f"Group {i}/{len(groups)}: {len(tasks)} task(s), {len(steps)} step(s) through {steps[-1]} in "
            f"{time.perf_counter() - started:.1f}s; {stats.get}."
        )


@dataclass(frozen=True)
class MeanArealTarget:
    """What a run writes: the weights of its locations on the grid, and the teehr variable and unit."""

    weights: GridWeights
    mapping: TeehrMapping


def prepare_mean_areal(ev: Evaluation, grid_da: xr.DataArray, args: MeanArealValuesInput,
                       grid_name: str, mapping: TeehrMapping | None = None) -> MeanArealTarget:
    """Register the domain values and load the weights, once per run (shared by every grid read, e.g. each year).

    ``grid_da`` is any lazily opened variable of the grid; its latitudes and attributes are used. ``mapping`` names
    it the teehr way, for outside grids; our repos carry theirs as ``teehr:*`` attributes.
    """
    mapping = resolve_teehr_mapping(args, mapping or mapping_from_attrs(grid_da.attrs), grid_da.attrs)
    if MEMBER in grid_da.dims and args.timeseries_table_name == "primary_timeseries":
        raise ValueError("Ensemble members have no column in primary_timeseries; write them to secondary_timeseries.")
    weights_df = read_weights_from_warehouse(ev=ev, location_id_prefix=args.location_id_prefix, grid_name=grid_name)
    weights_df["weight"] = area_weights(weights_df, grid_da, args.y_dim)
    matrix, rows, cols, location_ids = build_weights_matrix(weights_df)
    # Column-sliced per read by every task, so convert once
    weights = GridWeights(matrix.tocsc(), rows, cols, location_ids)
    check_locations(ev=ev, args=args, location_ids=weights.location_ids)
    # Only after the checks: registering skips existing names, so a wrong entry would stick
    register_domain_values(ev=ev, args=args, mapping=mapping)
    register_location_crosswalks(ev=ev, args=args, location_ids=weights.location_ids)
    return MeanArealTarget(weights, mapping)


def mean_areal_for_grid(ev: Evaluation, grid_da: xr.DataArray, spec: GridSpec, args: MeanArealValuesInput,
                        target: MeanArealTarget):
    """Mean areal values of a lazily opened grid variable, written to the warehouse.

    ``grid_da`` has CF-decoded values, a CRS and the spec's dims; ``args.append_dim`` must be the spec's.
    """
    logger = get_run_logger()
    mapping = target.mapping
    fixed = {d: grid_da[d].values for d in spec.fixed_dims}
    lead_names = None
    if fixed:
        written = written_forecast_steps(grid_da, args.append_dim, fixed, *_window(args))
        if mapping.variable is None:
            # Named by the interval each lead covers; leads covering none (lead 0) are skipped
            lead_dim = list(fixed)[-1]
            lead_names = lead_variable_names(fixed[lead_dim], mapping)
            written = written[written.get_level_values(lead_dim).isin(list(lead_names))]
    elif mapping.variable is None:
        raise ValueError(f"'{args.grid_variable_name}' is named by forecast step interval, but the grid has no leads.")
    else:
        written = written_steps(grid_da, args.append_dim, *_window(args))[args.append_dim].to_index()
    if len(written) == 0:
        logger.info("No written grid steps in the requested window.")
        return

    weights = target.weights
    plan = plan_reads(
        grid_da, written, fixed, weights.rows, weights.cols, weights.location_ids.size,
        dim=args.append_dim, y_dim=args.y_dim, x_dim=args.x_dim, task_memory_gb=args.task_memory_gb,
    )
    groups = _write_groups(plan.batches, args, weights.location_ids.size, forecast=bool(fixed))
    logger.info(
        f"Computing {len(written)} step(s) for {weights.location_ids.size} location(s) from {weights.rows.size} "
        f"pixel(s) in {len(groups)} write(s)."
    )
    constants = {"configuration_name": args.configuration_name, "unit_name": mapping.unit.name}
    if mapping.variable is not None:
        constants["variable_name"] = mapping.variable.name
    _compute_on_spark(ev, grid_da, args, plan, groups, weights, fixed, constants, mapping, lead_names)


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
    get_run_logger().info("Starting mean areal values calculation flow.")
    ev = mean_areal_evaluation(args)
    store = get_readonly_repo_store(
        dest_bucket=args.dest_bucket,
        base_prefix=args.base_prefix,
        configuration_name=args.configuration_name,
        s3_storage_kwargs=args.s3_storage_kwargs
    )
    spec = read_grid_spec(store)
    # The repo's own append axis, so a forecast repo needs no extra settings
    args = args.model_copy(update={"append_dim": spec.append_dim})
    grid_da = open_grid_dataset(store, spec)[args.grid_variable_name].rio.set_spatial_dims(
        x_dim=args.x_dim, y_dim=args.y_dim
    )
    target = prepare_mean_areal(
        ev, grid_da, args, grid_name=resolve_grid_name(store, args.grid_name, args.configuration_name)
    )
    mean_areal_for_grid(ev, grid_da, spec, args, target)
    get_run_logger().info("Mean areal values calculation flow completed.")
