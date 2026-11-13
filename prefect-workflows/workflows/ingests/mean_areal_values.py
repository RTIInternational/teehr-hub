"""Calculate mean areal values of location polygons from a grid using pixel coverage weights.

``calculate_mean_areal_values`` reads one of our Icechunk repos. ``mean_areal_for_grid`` does the work for any
lazily opened grid, so flows for outside sources (e.g. AORC, dynamical.org) open theirs and call it.

Batches follow the grid's storage chunks (``plan_reads``) and are computed with ``utils.mean_areal_kernel``,
either on the Prefect pod or as Spark ``mapInArrow`` tasks that write straight to the warehouse.
"""
import contextlib
import functools
import math
import time
from dataclasses import dataclass

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
from teehr.fetching.nwm.grid_utils import build_weights_matrix
from teehr.utils.concurrency import resolve_budget, resolve_cpu_workers, run_concurrent_map

from utils import time_grid as tg
from utils.grid_spec import GridSpec, open_grid_dataset, read_grid_spec
from utils import mean_areal_kernel
from utils.mean_areal_kernel import BlockTask, GridWeights, arrow_task_runner, run_block_task
from workflows.utils.repo_const import MEMBER, STATUS_COORD
from workflows.utils.time_utils import to_naive_utc
from workflows.utils.common_utils import initialize_evaluation
from workflows.models.ingest_gridded_data_input import VARIABLE_AND_UNIT_MAPPER
from workflows.models.mean_areal_inputs import MeanArealValuesInput
from pixel_coverage_weights import (
    ARROW_CONFIGS, WEIGHTS_TABLE_NAME, get_readonly_repo_store, like_prefix, resolve_grid_name,
    write_dataframe_to_warehouse,
)

# Bytes per weighted pixel and step while averaging: weighted_sums_from_matrix's float64 copy, NaN mask,
# zero-filled copy and missing weights
AVERAGING_BYTES_PER_PIXEL = 25
# Steps averaged at once, which caps those copies whatever the batch size
MAX_SLICE_STEPS = 256
# Filled by the warehouse writer, not the mean areal tasks
AUDIT_COLUMNS = ("created_at", "updated_at")


def _written_steps(da: xr.DataArray, args: MeanArealValuesInput) -> xr.DataArray:
    """Grid steps that hold data (time-grid slots not yet written are skipped), within start_dt..end_dt."""
    dim = args.append_dim
    if STATUS_COORD in da.coords:
        da = da.isel({dim: da[STATUS_COORD].values != tg.UNWRITTEN})
    start = to_naive_utc(args.start_dt) if args.start_dt is not None else None
    end = to_naive_utc(args.end_dt) if args.end_dt is not None else None
    return da.sel({dim: slice(start, end)})


def _written_forecast_steps(da: xr.DataArray, args: MeanArealValuesInput, fixed: dict) -> pd.MultiIndex:
    """Forecast steps that hold data, for cycles within start_dt..end_dt.

    Steps not yet written, and those the source never publishes (``NOT_EXPECTED``), are skipped. Cycles are
    selected first, so a long archive costs only the requested window.
    """
    dim = args.append_dim
    cycles = da[dim].to_index()
    keep = np.ones(len(cycles), bool)
    if args.start_dt is not None:
        keep &= cycles >= to_naive_utc(args.start_dt)
    if args.end_dt is not None:
        keep &= cycles <= to_naive_utc(args.end_dt)
    da = da.isel({dim: np.flatnonzero(keep)})
    step_dims = (dim, *fixed)
    steps = pd.MultiIndex.from_product([da[d].to_index() for d in step_dims], names=step_dims)
    if STATUS_COORD in da.coords:
        return steps[da[STATUS_COORD].transpose(*step_dims).values.reshape(-1) >= 0]
    return steps


def _step_columns(steps: pd.Index, dim: str) -> dict[str, np.ndarray]:
    """Timeseries columns of each step: its value_time, and a forecast's reference_time and member."""
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
    return columns


def _area_weights(weights_df: pd.DataFrame, da: xr.DataArray, y_dim: str) -> pd.Series:
    """Coverage fractions scaled by pixel area on geographic grids, whose pixels shrink with latitude."""
    if da.rio.crs is None:
        raise ValueError("The grid has no CRS.")
    weights = weights_df["fraction_covered"].astype("float64")
    if da.rio.crs.is_geographic:
        weights = weights * np.cos(np.deg2rad(da[y_dim].values[weights_df["row"].to_numpy()]))
    return weights


@dataclass(frozen=True)
class ReadPlan:
    """Batches of steps, the row bands their window is read in, and the memory one batch needs."""

    batches: list[pd.Index]
    band_edges: list[int]
    batch_bytes: int


def _chunk_layout(da: xr.DataArray) -> dict[str, tuple[int, int]]:
    """Each dim's stored inner chunk and shard length; empty for a grid without chunk encoding."""
    chunks = da.encoding.get("chunks")
    if chunks is None:
        return {}
    shards = da.encoding.get("shards") or chunks
    return {dim: (int(c), int(s)) for dim, c, s in zip(da.dims, chunks, shards)}


def _cycle_batches(steps: pd.MultiIndex, fixed: dict, lead_steps: int) -> list[pd.MultiIndex]:
    """Forecast steps by cycle and block of ``lead_steps`` leads, all members together."""
    dim, *fixed_dims = steps.names
    lead_pos = pd.Index(fixed[fixed_dims[-1]]).get_indexer(steps.get_level_values(fixed_dims[-1]))
    keys = pd.MultiIndex.from_arrays([steps.get_level_values(dim), lead_pos // lead_steps])
    return [steps[group.to_numpy()] for _, group in pd.Series(np.arange(len(steps)), index=keys).groupby(level=[0, 1])]


def plan_reads(
    da: xr.DataArray,
    args: MeanArealValuesInput,
    written: pd.Index,
    fixed: dict,
    rows: np.ndarray,
    cols: np.ndarray,
    n_zones: int,
) -> ReadPlan:
    """Batches and row bands from the grid's storage layout and ``task_memory_gb``.

    A batch holds whole inner chunks along the append axis (forecasts: the lead axis), so no chunk is decoded
    twice, and whole shards when they fit; members stored in one chunk are read together. The window is read in
    bands of whole chunk rows, sized so one chunk's worth of steps fits the budget. Explicit
    ``time_chunk_size``/``num_shard_chunks`` give fixed batches of that many steps in one band, as before.
    """
    logger = get_run_logger()
    dim = args.append_dim
    layout = _chunk_layout(da)
    y0, y1, x0, x1 = int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1
    lead_dim = list(fixed)[-1] if fixed else dim
    members_together = MEMBER in fixed and layout.get(MEMBER, (1, 1))[0] >= len(fixed[MEMBER])
    members = len(fixed[MEMBER]) if members_together else 1
    legacy = bool({"time_chunk_size", "num_shard_chunks"} & args.model_fields_set)
    unit, shard = (args.time_chunk_size * args.num_shard_chunks,) * 2 if legacy else layout.get(lead_dim, (1, 1))
    chunk_rows, chunk_cols = layout.get(args.y_dim, (y1 - y0, 0))[0], layout.get(args.x_dim, (x1 - x0, 0))[0]
    budget = args.task_memory_gb * 1e9

    def batch_bytes(steps: int, band_rows: int) -> int:
        band_pixels = rows.size * min(1.0, band_rows / (y1 - y0))
        per_step = band_rows * (x1 - x0) * da.dtype.itemsize * 2 + band_pixels * da.dtype.itemsize + 16 * n_zones
        return int(steps * per_step + min(steps, MAX_SLICE_STEPS) * band_pixels * AVERAGING_BYTES_PER_PIXEL)

    unit_steps = unit * members
    band_rows = y1 - y0
    while not legacy and band_rows > chunk_rows and batch_bytes(unit_steps, band_rows) > budget:
        band_rows = max(chunk_rows, band_rows // 2 // chunk_rows * chunk_rows)
    if batch_bytes(unit_steps, band_rows) > budget:
        logger.warning(
            f"One read unit ({unit_steps} steps x {band_rows} rows) needs "
            f"{batch_bytes(unit_steps, band_rows) / 1e9:.1f} GB, over task_memory_gb={args.task_memory_gb}."
        )
    units = 1 if legacy else max(1, int(budget // batch_bytes(unit_steps, band_rows)))
    lead_steps = unit * units
    if not legacy and lead_steps >= shard:
        lead_steps = lead_steps // shard * shard
    if band_rows >= y1 - y0:
        band_edges = [y0, y1]
    else:
        start = y0 // chunk_rows * chunk_rows
        band_edges = [y0, *range(start + band_rows, y1, band_rows), y1]

    if not fixed:
        batches = tg.shard_batches(written, da[dim].to_index(), lead_steps)
    elif members_together and not legacy:
        batches = _cycle_batches(written, fixed, lead_steps)
    else:
        batches = tg.step_batches(written, fixed, lead_steps, lead_steps)
    if chunk_rows and chunk_cols:
        touched = (math.ceil(y1 / chunk_rows) - y0 // chunk_rows) * (math.ceil(x1 / chunk_cols) - x0 // chunk_cols)
        used = len(set(zip(rows // chunk_rows, cols // chunk_cols)))
        logger.info(f"The window touches {touched} spatial chunk(s); {used} hold weighted pixels.")
    steps_per_batch = max(len(batch) for batch in batches)
    logger.info(
        f"Read plan: {len(batches)} batch(es) of up to {steps_per_batch} step(s), {len(band_edges) - 1} row band(s)"
        f"{' (fixed by time_chunk_size/num_shard_chunks)' if legacy else ''}."
    )
    return ReadPlan(batches, band_edges, batch_bytes(steps_per_batch, band_rows))


def _positions(coord: xr.DataArray, values) -> slice | np.ndarray:
    """``isel`` positions of ``values`` on ``coord``, as a slice when contiguous."""
    positions = coord.to_index().get_indexer(values)
    if (positions < 0).any():
        raise ValueError(f"Values not on the grid's {coord.name} axis.")
    if len(positions) and (np.diff(positions) == 1).all():
        return slice(int(positions[0]), int(positions[-1]) + 1)
    return positions


def _block_tasks(batch: pd.Index, da: xr.DataArray, dim: str, fixed: dict) -> list[BlockTask]:
    """The batch as rectangular blocks of ``isel`` positions, with each block's step columns.

    Forecast members sharing their cycles and leads form one block, so a chunk holding every member is read once.
    """
    if not fixed:
        return [BlockTask({dim: _positions(da[dim], batch)}, _step_columns(batch, dim))]
    lead_dim = list(fixed)[-1]
    merged: dict[tuple, list] = {}
    for block in tg.step_blocks(batch, fixed):
        key = (tuple(block.get_level_values(dim).unique()), tuple(block.get_level_values(lead_dim).unique()))
        merged.setdefault(key, []).extend(block.get_level_values(MEMBER).unique() if MEMBER in fixed else [])
    tasks = []
    for (cycles, leads), block_members in merged.items():
        levels = [list(cycles), *([sorted(set(block_members))] if MEMBER in fixed else []), list(leads)]
        steps = pd.MultiIndex.from_product(levels, names=batch.names)
        selection = {name: _positions(da[name], level) for name, level in zip(batch.names, levels)}
        tasks.append(BlockTask(selection, _step_columns(steps, dim)))
    return tasks


def _kernel_kwargs(args: MeanArealValuesInput, band_edges: list[int], **extra) -> dict:
    """``mean_areal_block`` settings shared by both backends."""
    return dict(
        y_dim=args.y_dim, x_dim=args.x_dim, band_edges=band_edges, max_slice_steps=MAX_SLICE_STEPS,
        min_coverage=args.min_valid_coverage, scale=args.value_scale, offset=args.value_offset, **extra,
    )


def _mean_areal_batch(
    batch: pd.Index,
    da: xr.DataArray,
    args: MeanArealValuesInput,
    window: tuple[int, int, int, int],
    rows: np.ndarray,
    cols: np.ndarray,
    matrix: sparse.csr_matrix,
    location_ids: np.ndarray,
    fixed: dict | None = None,
    band_edges: list[int] | None = None,
) -> pd.DataFrame:
    """Mean areal values of one batch of steps, as long rows without NaN values.

    The window is read in ``band_edges`` row bands, by default one band of the window's rows.
    """
    fixed = fixed or {}
    dim = args.append_dim
    da = da.transpose(dim, *fixed, args.y_dim, args.x_dim)
    weights = GridWeights(matrix, rows, cols, location_ids)
    kwargs = _kernel_kwargs(args, band_edges or list(window[:2]))
    return pd.concat(
        [run_block_task(block, da, weights, **kwargs).to_pandas() for block in _block_tasks(batch, da, dim, fixed)],
        ignore_index=True,
    )


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 30, retries=2)
def compute_batch_group(batches: list[pd.Index], workers: int, batch_kwargs: dict) -> pd.DataFrame:
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


def _sql_literal(value) -> str:
    """A Spark SQL literal for a string or a naive timestamp."""
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return f"TIMESTAMP_NTZ '{pd.Timestamp(value).isoformat(sep=' ')}'"
    return "'" + str(value).replace("'", "''") + "'"


def replace_condition(args: MeanArealValuesInput, variable_name: str, steps: pd.Index) -> str:
    """The rows one write replaces: this configuration, variable and location layer, over the write's steps.

    Every row the write produces matches it. Unit and member are left out on purpose: a rerun must also remove
    rows written in an earlier unit, or for members it no longer produces.
    """
    parts = [
        f"configuration_name = {_sql_literal(args.configuration_name)}",
        f"variable_name = {_sql_literal(variable_name)}",
        f"startswith(location_id, {_sql_literal(args.location_id_prefix + '-')})",
    ]
    if isinstance(steps, pd.MultiIndex):
        cycles = steps.get_level_values(args.append_dim)
        parts.append(f"reference_time BETWEEN {_sql_literal(cycles.min())} AND {_sql_literal(cycles.max())}")
    else:
        parts.append(f"value_time BETWEEN {_sql_literal(steps.min())} AND {_sql_literal(steps.max())}")
    return " AND ".join(parts)


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
def check_locations(ev: Evaluation, location_ids: np.ndarray, location_id_prefix: str):
    """Every weighted location must exist, since timeseries writes skip foreign-key validation."""
    known = {
        row["id"] for row in ev.locations.filter(
            filters=[{"column": "id", "operator": "like", "value": like_prefix(location_id_prefix)}]
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
    variable_name: str,
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
        "variables": Variable(name=variable_name, long_name=variable_long_name),
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


def mean_areal_evaluation(args: MeanArealValuesInput) -> Evaluation:
    """An evaluation whose Spark session suits the chosen backend."""
    configs = dict(ARROW_CONFIGS)
    if args.backend == "spark":
        configs.update({
            # Python workers hold the grid batches; give each its task budget plus room for Arrow buffers
            "spark.executor.pyspark.memory": f"{math.ceil(1.5 * args.task_memory_gb * args.executor_cores)}g",
            # A duplicate task attempt would only re-read the grid
            "spark.speculation": "false",
        })
    return initialize_evaluation(
        temp_dir_path=args.temp_dir_path,
        start_spark_cluster=args.start_spark_cluster,
        executor_instances=args.executor_instances,
        executor_cores=args.executor_cores,
        executor_memory=args.executor_memory,
        update_configs=configs,
    )


def _write(ev: Evaluation, data, args: MeanArealValuesInput, variable_name: str, steps: pd.Index):
    """Write one group's rows with the flow's write mode."""
    write_dataframe_to_warehouse(
        ev=ev,
        dataframe=data,
        table_name=args.timeseries_table_name,
        write_mode=args.write_mode,
        catalog_name=args.catalog_name,
        namespace_name=args.namespace_name,
        replace_condition=(
            replace_condition(args, variable_name, steps) if args.write_mode == "replace_where" else None
        ),
    )


def _compute_locally(ev, da, args, plan, groups, weights: GridWeights, fixed: dict, constants: dict):
    """Batches computed concurrently on the Prefect pod, written group by group from pandas."""
    logger = get_run_logger()
    # Zarr already reads each batch's chunks concurrently; more batches mostly add decode CPU
    workers = resolve_budget(io=args.batch_workers or resolve_cpu_workers(), memory_per_item=plan.batch_bytes).io
    if args.max_read_memory_gb is not None:
        workers = max(1, min(workers, int(args.max_read_memory_gb * 1e9 // plan.batch_bytes)))
    logger.info(f"Computing {len(plan.batches)} batch(es) on the Prefect pod, {workers} at a time.")
    window = (
        int(weights.rows.min()), int(weights.rows.max()) + 1, int(weights.cols.min()), int(weights.cols.max()) + 1
    )
    batch_kwargs = dict(
        da=da, args=args, window=window, rows=weights.rows, cols=weights.cols, matrix=weights.matrix,
        location_ids=weights.location_ids, fixed=fixed, band_edges=plan.band_edges,
    )
    for group in groups:
        frames = [
            compute_batch_group(batches=group[s:s + workers], workers=workers, batch_kwargs=batch_kwargs)
            for s in range(0, len(group), workers)
        ]
        df = pd.concat(frames, ignore_index=True)
        if df.empty:
            continue
        for name, value in constants.items():
            df[name] = value
        # Forecast batches fill these per step
        if "reference_time" not in df:
            df["reference_time"] = None
        if args.timeseries_table_name != "primary_timeseries" and "member" not in df:
            df["member"] = None
        logger.info(f"Writing {len(df)} rows; values {df['value'].min():.6g} to {df['value'].max():.6g}.")
        _write(ev, df, args, constants["variable_name"], group[0].append(group[1:]))


def _compute_on_spark(ev, da, args, plan, groups, weights: GridWeights, fixed: dict, constants: dict):
    """Batches run as Spark mapInArrow tasks, one Spark job and warehouse write per group."""
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
    cloudpickle.register_pickle_by_value(mean_areal_kernel)
    for i, group in enumerate(groups, start=1):
        tasks = [block for batch in group for block in _block_tasks(batch, da, dim, fixed)]
        run = arrow_task_runner(
            tasks, da, weights, **_kernel_kwargs(args, plan.band_edges, constants=constants,
                                                 schema=to_arrow_schema(schema))
        )
        stats = Observation(f"mean_areal_{i}")
        sdf = (
            ev.spark.createDataFrame([(t,) for t in range(len(tasks))], "task int")
            .repartition(len(tasks))
            .mapInArrow(run, schema)
            .observe(stats, F.count(F.lit(1)).alias("rows"), F.min("value").alias("min"), F.max("value").alias("max"))
        )
        steps = group[0].append(group[1:])
        started = time.perf_counter()
        _write(ev, sdf, args, constants["variable_name"], steps)
        logger.info(
            f"Group {i}/{len(groups)}: {len(tasks)} task(s), {len(steps)} step(s) through {steps[-1]} in "
            f"{time.perf_counter() - started:.1f}s; {stats.get}."
        )


@dataclass(frozen=True)
class MeanArealTarget:
    """What a run writes: the weights of its locations on the grid, and the teehr variable and unit."""

    weights: GridWeights
    variable_name: str
    unit_name: str


def prepare_mean_areal(ev: Evaluation, grid_da: xr.DataArray, args: MeanArealValuesInput,
                       grid_name: str) -> MeanArealTarget:
    """Register the domain values and load the weights, once per run (shared by every grid read, e.g. each year).

    ``grid_da`` is any lazily opened variable of the grid; its latitudes and attributes are used.
    """
    variable_name = args.variable_name or args.grid_variable_name
    unit_name = args.unit_name or grid_da.attrs.get("units")
    if unit_name is None:
        raise ValueError(f"Grid variable '{args.grid_variable_name}' has no 'units' attribute; set unit_name.")
    register_domain_values(
        ev=ev,
        args=args,
        variable_name=variable_name,
        variable_long_name=grid_da.attrs.get("long_name", variable_name),
        unit_name=unit_name,
    )
    weights_df = read_weights_from_warehouse(ev=ev, location_id_prefix=args.location_id_prefix, grid_name=grid_name)
    weights_df["weight"] = _area_weights(weights_df, grid_da, args.y_dim)
    weights = GridWeights(*build_weights_matrix(weights_df))
    check_locations(ev=ev, location_ids=weights.location_ids, location_id_prefix=args.location_id_prefix)
    register_location_crosswalks(ev=ev, args=args, location_ids=weights.location_ids)
    return MeanArealTarget(weights, variable_name, unit_name)


def mean_areal_for_grid(ev: Evaluation, grid_da: xr.DataArray, spec: GridSpec, args: MeanArealValuesInput,
                        target: MeanArealTarget):
    """Mean areal values of a lazily opened grid variable, written to the warehouse.

    ``grid_da`` has CF-decoded values, a CRS and the spec's dims; ``args.append_dim`` must be the spec's.
    """
    logger = get_run_logger()
    fixed = {d: grid_da[d].values for d in spec.fixed_dims}
    if MEMBER in fixed and args.timeseries_table_name == "primary_timeseries":
        raise ValueError("Ensemble members have no column in primary_timeseries; write them to secondary_timeseries.")
    if fixed:
        written = _written_forecast_steps(grid_da, args, fixed)
    else:
        written = _written_steps(grid_da, args)[args.append_dim].to_index()
    if len(written) == 0:
        logger.info("No written grid steps in the requested window.")
        return

    weights = target.weights
    plan = plan_reads(grid_da, args, written, fixed, weights.rows, weights.cols, weights.location_ids.size)
    groups = _write_groups(plan.batches, args, weights.location_ids.size, forecast=bool(fixed))
    logger.info(
        f"Computing {len(written)} step(s) for {weights.location_ids.size} location(s) from {weights.rows.size} "
        f"pixel(s) in {len(groups)} write(s), backend '{args.backend}'."
    )
    constants = {
        "configuration_name": args.configuration_name,
        "variable_name": target.variable_name,
        "unit_name": target.unit_name,
    }
    compute = _compute_on_spark if args.backend == "spark" else _compute_locally
    zarr_config = (
        zarr.config.set({"async.concurrency": args.zarr_concurrency})
        if args.zarr_concurrency else contextlib.nullcontext()
    )
    with zarr_config:
        compute(ev, grid_da, args, plan, groups, weights, fixed, constants)


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
