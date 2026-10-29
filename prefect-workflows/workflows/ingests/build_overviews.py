from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
import time
import icechunk as ic
import numpy as np
import pandas as pd
import xarray as xr
import zarr

from utils import grid_utils as gu
from utils import time_grid as tg
from workflows.models.ingest_gridded_data_input import (
    BuildOverviewsDataInput,
    PackedEncoding,
    OVERVIEW_GROUP_PATH,
    OVERVIEW_CHUNK_SIZE,
)


@flow(
    flow_run_name="build-overviews",
    timeout_seconds=3 * 60 * 60
)
def build_overviews(args: BuildOverviewsDataInput) -> None:
    """Build map overviews for the steps the data group changed, and write them into their slots.

    Reads the repo's data group (``/data``, or ``/references`` when not materialized), only the
    steps the overviews lack or hold from an older write, and averages blocks of
    ``overview_factors`` pixels on the data's own grid into ``/overviews/<factor>``. The tile
    server uses the data group as full resolution and the overviews as coarser levels, and
    reprojects each tile on request.

    Parameters
    ----------
    args : BuildOverviewsDataInput
        Pydantic model containing all flow parameters. See BuildOverviewsDataInput for field descriptions.
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

    first_level = f"{OVERVIEW_GROUP_PATH}/{args.overview_factors[0]}"
    stale = tg.stale_steps(data_meta, tg.read_step_metadata(store, first_level, dim))
    if len(stale) == 0:
        logger.info(f"{OVERVIEW_GROUP_PATH} is up to date.")
        return
    data_ds = gu.open_zarr_group(store=store, group_path=data_group)
    data_ds = data_ds.drop_vars([n for n in tg.STEP_COORDS if n in data_ds.variables])
    # Scalars such as the grid mapping ride along as coords; only gridded variables are averaged
    data_ds = data_ds.set_coords([v for v in data_ds.data_vars if data_ds[v].ndim == 0])
    # Values are decoded, with NaN for missing, as in /data; a source's own fill marker (e.g. -9999
    # in /references) would otherwise reach coarsening as a value
    for var in data_ds.data_vars:
        if np.issubdtype(data_ds[var].dtype, np.floating):
            data_ds[var].encoding.pop("missing_value", None)
            data_ds[var].encoding["_FillValue"] = np.nan
    _check_packing_units(data_ds, args.overview_encoding)

    # Batches of whole shards bound memory by the batch; each is committed, so a failed run resumes
    batches = tg.shard_batches(stale, data_meta.index, args.time_batch_size)
    logger.info(f"Building overviews for {len(stale)} step(s) in {len(batches)} batch(es).")
    started = time.perf_counter()
    for i, batch in enumerate(batches, start=1):
        batch_started = time.perf_counter()
        _write_overview_batch(repo, data_group, data_ds.sel({dim: batch}), data_meta.loc[batch], args)
        logger.info(
            f"Processed overview batch {i} of {len(batches)} ({len(batch)} step(s)) "
            f"in {time.perf_counter() - batch_started:.1f}s."
        )
    logger.info(f"Built overviews for {len(stale)} step(s) in {time.perf_counter() - started:.1f}s.")


def _check_packing_units(ds: xr.Dataset, overview_encoding: dict[str, PackedEncoding]) -> None:
    """Fail if a packing range is given in other units than its variable is stored in."""
    for var, packing in overview_encoding.items():
        stored_units = ds[var].attrs.get("units") if var in ds else None
        if var in ds and stored_units != packing.units:
            raise ValueError(
                f"overview_encoding for '{var}' is in '{packing.units}', but the variable is stored in '{stored_units}'."
            )


def _clip_to_packed_range(ds: xr.Dataset, overview_encoding: dict[str, PackedEncoding]) -> xr.Dataset:
    """Clip packed variables to their packing range, so values cannot wrap."""
    for var, packing in overview_encoding.items():
        if var in ds:
            ds[var] = ds[var].clip(packing.min_value, packing.max_value).assign_attrs(ds[var].attrs)
    return ds


def _overview_encoding(ds: xr.Dataset, args: BuildOverviewsDataInput) -> dict:
    """Chunk/shard encoding for a new overview level: packed where configured, float32 otherwise."""
    encoding = gu.create_encoding_config(
        ds,
        append_dim=args.append_dim,
        chunk_size=OVERVIEW_CHUNK_SIZE,
        # Tiles read one step at a time; shards span as many steps as /data's
        num_shard_chunks=args.num_shard_chunks * args.time_chunk_size,
        time_chunk_size=1,
    )
    for var in ds.data_vars:
        packing = args.overview_encoding.get(var)
        encoding[var].update(packing.to_encoding() if packing else {"dtype": "float32"})
    return encoding


def _coarsen(ds: xr.Dataset, factor: int) -> xr.Dataset:
    """Average ``factor`` x ``factor`` blocks of pixels, dropping a partial block at the far edges."""
    y_dim, x_dim = ds.attrs["spatial:dimensions"]
    level = ds.coarsen({y_dim: factor, x_dim: factor}, boundary="trim").mean(keep_attrs=True)
    # Encodings belong to the data group's arrays; each level gets its own when created
    for name in level.variables:
        level[name].encoding = {}
    level.attrs["spatial:transform"] = gu.spatial_transform(level)
    return level


@task(cache_policy=NO_CACHE)
def _write_overview_batch(
    repo: ic.Repository,
    data_group: str,
    ds_batch: xr.Dataset,
    batch_meta: pd.DataFrame,
    args: BuildOverviewsDataInput,
) -> None:
    """Average one batch of time steps into each overview level, and write them into their slots."""
    logger = get_run_logger()
    dim = args.append_dim
    ds_batch = ds_batch.load()

    rw_session = repo.writable_session("main")
    _, origin, time_step = tg.read_grid(rw_session.store)
    axis_end = xr.open_zarr(rw_session.store, group=data_group, consolidated=False)[dim].to_index()[-1]

    # The tile server reads the data group as the full-resolution level, so it needs the transform too
    group_attrs = zarr.open_group(rw_session.store, path=data_group.strip("/"), mode="a", zarr_format=3).attrs
    if "spatial:transform" not in group_attrs:
        group_attrs["spatial:transform"] = gu.spatial_transform(ds_batch)
        logger.info(f"Recorded spatial:transform on {data_group}.")

    for factor in args.overview_factors:
        level_ds = _clip_to_packed_range(_coarsen(ds_batch, factor), args.overview_encoding)
        group = f"{OVERVIEW_GROUP_PATH}/{factor}"
        existing = tg.read_step_metadata(rw_session.store, group, dim)
        if existing is None:
            tg.create_group(rw_session, group, level_ds, origin, time_step, dim, axis_end, encoding=_overview_encoding(level_ds, args))
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
        f"Committed {len(args.overview_factors)} overview levels ({len(batch_meta)} time step(s)) "
        f"to {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Overviews committed with snapshot ID: {snapshot_id}.")
