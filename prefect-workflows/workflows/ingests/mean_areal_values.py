"""Calculate mean areal values of location polygons from a grid using pixel coverage weights.

``calculate_mean_areal_values`` reads one of our Icechunk repos; flows for outside grids (e.g. AORC, dynamical.org)
open theirs and call ``prepare_mean_areal`` and ``mean_areal_for_grid`` the same way.

A run splits the grid's written steps into segments along its append axis (``teehr_icechunk.zonal``) and runs them
in this run or as ``process-gridded-segment`` child runs (``max_child_runs``). A segment reads its blocks in worker
processes and stages them as Parquet under ``temp_dir_path``; this run loads each finished segment into the
warehouse and removes it. Spark is only used here, to read the weights and load the staged values.
"""
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import rioxarray  # noqa: F401
import xarray as xr
from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from prefect.runtime import flow_run
from teehr import Configuration, Evaluation
from teehr.evaluation.write import AUDIT_COLUMNS
from teehr_icechunk import zonal
from teehr_icechunk.grid_spec import GridSpec, open_grid_dataset, read_grid_spec
from teehr_icechunk.mean_areal_kernel import GridWeights
from teehr_icechunk.mean_areal_plan import area_weights, written_forecast_steps, written_steps
from teehr_icechunk.prefect import runner
from teehr_icechunk.repo_const import MEMBER
from teehr_icechunk.segments import Segment, SegmentResult, raise_failed
from teehr_icechunk.weights import build_weights_matrix

from workflows.utils.time_utils import to_naive_utc
from workflows.utils.common_utils import initialize_evaluation
from workflows.models.mean_areal_inputs import MeanArealValuesInput
from workflows.utils.teehr_mapping import TeehrMapping, lead_variable_names, mapping_from_attrs, resolve_teehr_mapping
from pixel_coverage_weights import (
    ARROW_CONFIGS, WEIGHTS_TABLE_NAME, get_readonly_repo_store, like_prefix, resolve_grid_name,
    write_dataframe_to_warehouse,
)
from process_gridded_segment import CHILD_DEPLOYMENT

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)

# This module's child-run stage (process-gridded-segment imports it to run a segment)
STAGE = "mean_areal_values"


def _window(args: MeanArealValuesInput) -> tuple:
    """The run's start_dt and end_dt as naive UTC (None when unset)."""
    return tuple(to_naive_utc(t) if t is not None else None for t in (args.start_dt, args.end_dt))


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
    """An evaluation (Spark in local mode) to read the weights and load the staged values."""
    return initialize_evaluation(temp_dir_path=args.temp_dir_path, start_spark_cluster=False,
                                 update_configs=ARROW_CONFIGS)


def _write(ev: Evaluation, data, args: MeanArealValuesInput, variable_names: list[str], steps: pd.Index):
    """Write one segment's rows with the flow's write mode."""
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


def resolve_mapping(grid_da: xr.DataArray, args: MeanArealValuesInput,
                    mapping: TeehrMapping | None = None) -> TeehrMapping:
    """The teehr variable, unit and conversion of the grid variable: ``mapping`` for outside grids, else the
    ``teehr:*`` attributes our repos carry, as the run's arguments override them."""
    return resolve_teehr_mapping(args, mapping or mapping_from_attrs(grid_da.attrs), grid_da.attrs)


@dataclass(frozen=True)
class MeanArealTarget:
    """What a run writes, and where its segments stage: the teehr variable and unit, and the staging directory
    holding the weights and the output schema."""

    mapping: TeehrMapping
    staging_dir: str
    n_locations: int
    n_pixels: int


def _output_schema(ev: Evaluation, args: MeanArealValuesInput) -> pa.Schema:
    """The timeseries table's columns as Arrow, so staged files load without conversion."""
    from pyspark.sql.pandas.types import to_arrow_schema
    from pyspark.sql.types import StructType

    catalog = args.catalog_name or ev.active_catalog.catalog_name
    namespace = args.namespace_name or ev.active_catalog.namespace_name
    table_schema = ev.spark.table(f"{catalog}.{namespace}.{args.timeseries_table_name}").schema
    return to_arrow_schema(StructType([field for field in table_schema if field.name not in AUDIT_COLUMNS]))


def prepare_mean_areal(ev: Evaluation, grid_da: xr.DataArray, args: MeanArealValuesInput,
                       grid_name: str, mapping: TeehrMapping | None = None) -> MeanArealTarget:
    """Register the domain values and stage the weights and output schema, once per run (shared by every grid
    read, e.g. each year). The caller removes ``staging_dir`` when the run is done.

    ``grid_da`` is any lazily opened variable of the grid; its latitudes and attributes are used. ``mapping`` names
    it the teehr way, for outside grids; our repos carry theirs as ``teehr:*`` attributes.
    """
    mapping = resolve_mapping(grid_da, args, mapping)
    if MEMBER in grid_da.dims and args.timeseries_table_name == "primary_timeseries":
        raise ValueError("Ensemble members have no column in primary_timeseries; write them to secondary_timeseries.")
    weights_df = read_weights_from_warehouse(ev=ev, location_id_prefix=args.location_id_prefix, grid_name=grid_name)
    weights_df["weight"] = area_weights(weights_df, grid_da, args.y_dim)
    matrix, rows, cols, location_ids = build_weights_matrix(weights_df)
    weights = GridWeights(matrix.tocsc(), rows, cols, location_ids)
    check_locations(ev=ev, args=args, location_ids=weights.location_ids)
    # Only after the checks: registering skips existing names, so a wrong entry would stick
    register_domain_values(ev=ev, args=args, mapping=mapping)
    register_location_crosswalks(ev=ev, args=args, location_ids=weights.location_ids)

    # One directory per run on the shared volume, so child runs on other pods see it
    staging_dir = Path(args.temp_dir_path, "mean-areal", str(flow_run.get_id() or uuid.uuid4().hex))
    staging_dir.mkdir(parents=True, exist_ok=True)
    zonal.save_weights(staging_dir / zonal.WEIGHTS_FILE, weights)
    zonal.save_schema(staging_dir / zonal.SCHEMA_FILE, _output_schema(ev, args))
    return MeanArealTarget(mapping, str(staging_dir), weights.location_ids.size, weights.rows.size)


def zonal_work(grid_da: xr.DataArray, spec: GridSpec, args: MeanArealValuesInput, mapping: TeehrMapping,
               staging_dir: str, stage: str, start=None, end=None) -> zonal.ZonalWork | None:
    """The work on the grid's written steps from ``start`` to ``end`` (naive UTC); None when none are written.

    Built the same way in the parent, over the run's window, and in each child, over its segment.
    """
    fixed = {d: grid_da[d].values for d in spec.fixed_dims}
    lead_names = None
    if fixed:
        written = written_forecast_steps(grid_da, args.append_dim, fixed, start, end)
        if mapping.variable is None:
            # Named by the interval each lead covers; leads covering none (lead 0) are skipped
            lead_dim = list(fixed)[-1]
            lead_names = lead_variable_names(fixed[lead_dim], mapping, grid_da.attrs)
            written = written[written.get_level_values(lead_dim).isin(list(lead_names))]
    elif mapping.variable is None:
        raise ValueError(f"'{args.grid_variable_name}' is named by forecast step interval, but the grid has no leads.")
    else:
        written = written_steps(grid_da, args.append_dim, start, end)[args.append_dim].to_index()
    if len(written) == 0:
        return None
    constants = {"configuration_name": args.configuration_name, "unit_name": mapping.unit.name}
    if mapping.variable is not None:
        constants["variable_name"] = mapping.variable.name
    return zonal.ZonalWork(
        grid_da, written, args.append_dim, fixed, args.y_dim, args.x_dim, staging_dir, args.task_memory_gb,
        lead_names=lead_names,
        kernel_kwargs={"min_coverage": args.min_valid_coverage, "scale": mapping.scale, "offset": mapping.offset,
                       "constants": constants},
        child_parameters={"stage": stage, "args": args.model_dump(mode="json"), "staging_dir": staging_dir},
    )


def mean_areal_for_grid(ev: Evaluation, grid_da: xr.DataArray, spec: GridSpec, args: MeanArealValuesInput,
                        target: MeanArealTarget, stage: str = STAGE):
    """Mean areal values of a lazily opened grid variable, written to the warehouse segment by segment.

    ``grid_da`` has CF-decoded values, a CRS and the spec's dims; ``args.append_dim`` must be the spec's. ``stage``
    names the flow module whose ``run_mean_areal_segment`` reopens the grid in a child run.
    """
    logger = get_run_logger()
    work = zonal_work(grid_da, spec, args, target.mapping, target.staging_dir, stage, *_window(args))
    if work is None:
        logger.info("No written grid steps in the requested window.")
        return
    segments = zonal.plan_zonal_segments(grid_da, work.written, args.append_dim, args.segment_steps)
    logger.info(
        f"Computing {len(work.written)} step(s) for {target.n_locations} location(s) from {target.n_pixels} "
        f"pixel(s) in {len(segments)} segment(s)."
    )
    variable_names = [variable.name for variable in target.mapping.variables]

    def load(result: SegmentResult):
        try:
            if result.error is None:
                _load_segment(ev, args, variable_names, work, result.segment)
        finally:
            zonal.remove_segment(target.staging_dir, result.segment)

    raise_failed(runner(args, CHILD_DEPLOYMENT).run(work, segments, on_done=load))


def _load_segment(ev: Evaluation, args: MeanArealValuesInput, variable_names: list[str], work: zonal.ZonalWork,
                  segment: Segment):
    """Load a finished segment's staged values into the warehouse, replacing its steps' rows."""
    logger = get_run_logger()
    path = zonal.segment_dir(work.staging_dir, segment)
    steps = segment.select(work.written, args.append_dim)
    if not any(path.glob("*.parquet")):
        logger.info(f"Segment {segment.start} to {segment.end} has no values to load.")
        return
    _write(ev, ev.spark.read.parquet(str(path)), args, variable_names, steps)
    logger.info(f"Loaded segment {segment.start} to {segment.end} ({len(steps)} step(s)).")


def compute_segment(grid_da: xr.DataArray, spec: GridSpec, args: MeanArealValuesInput, mapping: TeehrMapping,
                    segment: dict, staging_dir: str, stage: str):
    """A child run's work: one segment of the run's window, staged for the parent to load."""
    segment = Segment.from_dict(segment)
    start, end = _window(args)
    start = segment.start if start is None else max(start, segment.start)
    end = segment.end if end is None else min(end, segment.end)
    work = zonal_work(grid_da, spec, args, mapping, staging_dir, stage, start, end)
    if work is not None:
        work(segment)


def open_repo_grid(args: MeanArealValuesInput) -> tuple[xr.DataArray, GridSpec, str]:
    """The run's variable of one of our repos, lazily opened, with its spec and grid name."""
    store = get_readonly_repo_store(
        dest_bucket=args.dest_bucket,
        base_prefix=args.base_prefix,
        configuration_name=args.configuration_name,
        s3_storage_kwargs=args.s3_storage_kwargs
    )
    spec = read_grid_spec(store)
    grid_da = open_grid_dataset(store, spec)[args.grid_variable_name].rio.set_spatial_dims(
        x_dim=args.x_dim, y_dim=args.y_dim
    )
    return grid_da, spec, resolve_grid_name(store, args.grid_name, args.configuration_name)


def run_mean_areal_segment(args: dict, segment: dict, staging_dir: str):
    """Run one segment in a child run (``process-gridded-segment``)."""
    args = MeanArealValuesInput.model_validate(args)
    grid_da, spec, _ = open_repo_grid(args)
    compute_segment(grid_da, spec, args, resolve_mapping(grid_da, args), segment, staging_dir, STAGE)


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
    grid_da, spec, grid_name = open_repo_grid(args)
    # The repo's own append axis, so a forecast repo needs no extra settings
    args = args.model_copy(update={"append_dim": spec.append_dim})
    target = prepare_mean_areal(ev, grid_da, args, grid_name=grid_name)
    try:
        mean_areal_for_grid(ev, grid_da, spec, args, target)
    finally:
        shutil.rmtree(target.staging_dir, ignore_errors=True)
    get_run_logger().info("Mean areal values calculation flow completed.")
