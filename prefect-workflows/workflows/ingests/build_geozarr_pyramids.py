from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
import icechunk as ic
import numpy as np
import pandas as pd
import xarray as xr
from topozarr import create_pyramid
import rioxarray  # noqa: F401 (rio accessor)

from utils import grid_utils as gu
from utils import time_grid as tg
from workflows.models.ingest_gridded_data_input import (
    BuildPyramidsDataInput,
    PackedEncoding,
    PYRAMID_GROUP_PATH,
    PYRAMID_CHUNK_SIZE,
)


@flow(
    flow_run_name="build-pyramids",
    timeout_seconds=3 * 60 * 60
)
def build_pyramids(args: BuildPyramidsDataInput) -> None:
    """Build multiscale pyramids for the steps the data group changed, and write them into their slots.

    Reads the repo's data group (``/raw_data``, or ``/references`` when not materialized), only the
    steps the pyramids lack or hold from an older write, reprojects to web mercator, creates
    downsampled pyramid levels, and writes them on the repo's time grid (creating the levels on the
    first run).

    Parameters
    ----------
    args : BuildPyramidsDataInput
        Pydantic model containing all flow parameters. See BuildPyramidsDataInput for field descriptions.
    """
    logger = get_run_logger()

    storage = gu.build_icechunk_s3_storage(
        bucket=args.dest_bucket,
        prefix=f"{args.base_prefix}/{args.configuration_name}",
        **args.s3_storage_kwargs
    )
    # The data group may be /references, whose chunks live in the source; the ingest flow's args carry its credentials
    source = getattr(args, "source", None)
    repo = gu.open_repo_for_reading(storage, source.credentials() if source else None)
    logger.info(
        f"Icechunk repo opened at: {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}."
    )

    dim = args.append_dim
    store = repo.readonly_session("main").store
    data_group = gu.read_data_group(store)
    data_meta = tg.read_step_metadata(store, data_group, dim)
    if data_meta is None:
        logger.info(f"No data found in {data_group}.")
        return

    # topozarr names levels by their index in args.factors, not by factor
    first_level = f"{PYRAMID_GROUP_PATH}/0"
    stale = tg.stale_steps(data_meta, tg.read_step_metadata(store, first_level, dim))
    if len(stale) == 0:
        logger.info(f"{PYRAMID_GROUP_PATH} is up to date.")
        return
    data_ds = gu.open_zarr_group(store=store, group_path=data_group)
    data_ds = data_ds.drop_vars([n for n in tg.STEP_COORDS if n in data_ds.variables])
    # Values are decoded, with NaN for missing, as in /raw_data; a source's own fill marker (e.g. -9999
    # in /references) would otherwise reach reprojection and coarsening as the fill to skip
    for var in data_ds.data_vars:
        if np.issubdtype(data_ds[var].dtype, np.floating):
            data_ds[var].encoding.pop("missing_value", None)
            data_ds[var].encoding["_FillValue"] = np.nan
    _check_packing_units(data_ds, args.pyramid_encoding)

    # Batches of whole shards bound memory by the batch; each is committed, so a failed run resumes
    batches = tg.shard_batches(stale, data_meta.index, args.time_batch_size)
    logger.info(f"Building pyramids for {len(stale)} step(s) in {len(batches)} batch(es).")
    for i, batch in enumerate(batches, start=1):
        _write_pyramid_batch(repo, data_ds.sel({dim: batch}), data_meta.loc[batch], args)
        logger.info(f"Processed pyramid batch {i} of {len(batches)} ({len(batch)} step(s)).")


def _check_packing_units(ds: xr.Dataset, pyramid_encoding: dict[str, PackedEncoding]) -> None:
    """Fail if a packing range is given in other units than its variable is stored in."""
    for var, packing in pyramid_encoding.items():
        stored_units = ds[var].attrs.get("units") if var in ds else None
        if var in ds and stored_units != packing.units:
            raise ValueError(
                f"pyramid_encoding for '{var}' is in '{packing.units}', but the variable is stored in '{stored_units}'."
            )


def _clip_to_packed_range(ds: xr.Dataset, pyramid_encoding: dict[str, PackedEncoding]) -> xr.Dataset:
    """Clip packed variables to their packing range, so values cannot wrap."""
    for var, packing in pyramid_encoding.items():
        if var in ds:
            ds[var] = ds[var].clip(packing.min_value, packing.max_value).assign_attrs(ds[var].attrs)
    return ds


def _pyramid_encoding(ds: xr.Dataset, args: BuildPyramidsDataInput) -> dict:
    """Chunk/shard encoding for a new pyramid level, with any per-variable packing applied."""
    encoding = gu.create_encoding_config(
        ds,
        append_dim=args.append_dim,
        chunk_size=PYRAMID_CHUNK_SIZE,
        # Tiles read one step at a time; shards span as many steps as /raw_data's
        num_shard_chunks=args.num_shard_chunks * args.time_chunk_size,
        time_chunk_size=1,
    )
    for var, packing in args.pyramid_encoding.items():
        if var in encoding:
            encoding[var].update(packing.to_encoding())
    return encoding


@task(cache_policy=NO_CACHE)
def _write_pyramid_batch(
    repo: ic.Repository,
    ds_batch: xr.Dataset,
    batch_meta: pd.DataFrame,
    args: BuildPyramidsDataInput,
) -> None:
    """Reproject one batch of time steps, build its pyramid levels, and write them into their slots."""
    logger = get_run_logger()
    dim = args.append_dim

    # Set spatial dims and reproject to web mercator
    ds_mercator = gu.reproject_dataset(
        dataset=ds_batch,
        target_crs=args.target_crs,
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        fallback_crs=args.fallback_source_crs
    )
    logger.info(f"Reprojected {len(ds_batch.indexes[args.append_dim].unique())} time step(s) to {args.target_crs}.")

    # Create multiscale pyramids for the new slice
    pyramid = create_pyramid(
        ds_mercator,
        factors=args.factors,
        x_dim="x",
        y_dim="y",
        method=args.pyramid_method,
    )
    dt = pyramid.as_datatree()
    logger.info(f"Created pyramids with {len(dt.children)} levels and factors: {args.factors}.")

    rw_session = repo.writable_session("main")
    _, origin, time_step = tg.read_grid(rw_session.store)
    axis_end = xr.open_zarr(rw_session.store, group=gu.read_data_group(rw_session.store), consolidated=False)[dim].to_index()[-1]

    # The parent '/pyramids' group holds the 'multiscales' block, written once
    if not gu.group_contains_data(rw_session.store, f"{PYRAMID_GROUP_PATH}/0"):
        logger.info(f"Writing root GeoZarr pyramid metadata to: {PYRAMID_GROUP_PATH}")
        xr.Dataset(attrs=dt.attrs).to_zarr(
            rw_session.store, group=PYRAMID_GROUP_PATH, mode="w", zarr_format=3, consolidated=False
        )

    layout = pyramid.attrs.get("multiscales", {}).get("layout", [])

    for level_name, level_tree_node in dt.children.items():
        attrs = level_tree_node.attrs.copy()

        # Inject GeoZarr spatial transform and shape attrs for xpublish-tiles
        level_idx = int(level_name)
        if level_idx < len(layout):
            level_layout = layout[level_idx]
            attrs["spatial:transform"] = level_layout["spatial:transform"]
            if "spatial:shape" in level_layout:
                attrs["spatial:shape"] = level_layout["spatial:shape"]
        if "proj:code" in pyramid.attrs:
            attrs["proj:code"] = pyramid.attrs["proj:code"]

        level_ds = level_tree_node.to_dataset()
        # Drop scalar (0-D) data variables
        level_ds = level_ds.drop_vars(
            [v for v in level_ds.data_vars if level_ds[v].ndim == 0]
        )
        level_ds = gu.standardize_and_inject_geozarr(
            level_ds.rio.write_crs(args.target_crs),  # pyramid levels are in target_crs
            x_dim="x",
            y_dim="y",
        )
        level_ds.attrs.update(attrs)
        level_ds = _clip_to_packed_range(level_ds, args.pyramid_encoding)
        level_ds = level_ds.drop_vars([n for n in tg.STEP_COORDS if n in level_ds.variables])

        group = f"{PYRAMID_GROUP_PATH}/{level_name}"
        existing = tg.read_step_metadata(rw_session.store, group, dim)
        if existing is None:
            tg.create_group(rw_session, group, level_ds, origin, time_step, dim, axis_end, encoding=_pyramid_encoding(level_ds, args))
            logger.info(f"Created {group} on a {time_step} grid from {origin} to {axis_end}.")
            existing = tg.read_step_metadata(rw_session.store, group, dim)
        else:
            added = tg.ensure_axis(rw_session, group, axis_end, time_step, dim)
            if added:
                logger.info(f"Extended {group} by {added} slot(s) to {axis_end}.")
        level_ds = tg.with_step_metadata(
            level_ds,
            dim,
            status=batch_meta["status"].to_numpy(),
            source_last_modified=batch_meta["source_last_modified"].to_numpy(),
            # The data group's write time, so the step is current until that group changes again
            updated_at=batch_meta["updated_at"].to_numpy(),
            existing=existing,
        )
        tg.region_write(rw_session, group, level_ds, dim)

    snapshot_id = rw_session.commit(
        f"Committed {len(dt.children)} pyramid levels ({len(batch_meta)} time step(s)) "
        f"to {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Pyramids committed with snapshot ID: {snapshot_id}.")
