from prefect import flow, get_run_logger
import icechunk as ic
import numpy as np
from icechunk.xarray import to_icechunk
import xarray as xr
from topozarr import create_pyramid
import rioxarray  # noqa: rio accessor
import zarr

from utils import grid_utils as gu
from workflows.models.ingest_gridded_data_input import (
    BuildPyramidsDataInput,
    PackedEncoding,
    RAW_DATA_GROUP_PATH,
    PYRAMID_GROUP_PATH
)


@flow(
    flow_run_name="build-pyramids",
    timeout_seconds=60 * 60
)
def build_pyramids(args: BuildPyramidsDataInput) -> None:
    """Build multiscale pyramids incrementally for newly ingested data and write them to an IceChunk repository.

    Reads only time steps not yet present in the pyramid store, reprojects to web
    mercator, creates downsampled pyramid levels, and appends to the existing
    pyramid groups (or creates them on the first run).

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
    repo = ic.Repository.open(storage)
    logger.info(
        f"Icechunk repo opened at: {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}."
    )

    rw_session = repo.writable_session("main")
    # Determine which time steps are not yet in the pyramid store
    first_level = "0"  # topozarr names levels by their index in args.factors, not by factor
    if not gu.group_contains_data(store=rw_session.store, group_path=RAW_DATA_GROUP_PATH):
        logger.info(f"No data found in {RAW_DATA_GROUP_PATH}. Shutting down.")
        return

    if not gu.group_contains_data(
        store=rw_session.store,
        group_path=PYRAMID_GROUP_PATH,
        sub_group_name=first_level
    ):
        is_new_pyramid = True
        logger.info(f"No existing pyramids found in {PYRAMID_GROUP_PATH}/{first_level}. Building for all data in {RAW_DATA_GROUP_PATH}.")
        ds_new = gu.open_zarr_group(
            store=rw_session.store,
            group_path=RAW_DATA_GROUP_PATH
        )
    else:
        is_new_pyramid = False
        logger.info(f"Existing pyramids found. Checking for new data against {RAW_DATA_GROUP_PATH}.")
        incoming_ds = gu.open_zarr_group(
            store=rw_session.store,
            group_path=RAW_DATA_GROUP_PATH
        )
        existing_ds = gu.open_zarr_group(
            store=rw_session.store,
            group_path=f"{PYRAMID_GROUP_PATH}/{first_level}"
        )
        ds_new = gu.filter_for_new_data(
            incoming_ds=incoming_ds,
            existing_ds=existing_ds,
            append_dim=args.append_dim,
        )
        if ds_new is None:
            logger.info(f"No new data steps found in {RAW_DATA_GROUP_PATH}. Shutting down.")
            return
        logger.info(f"Found {len(ds_new[args.append_dim])} new time step(s) to process.")

    # Process time steps in batches so memory stays bounded by the batch, not the backlog.
    # Each batch is committed, so a failed run resumes from the last committed batch.
    ds_new = ds_new.sortby(args.append_dim)
    num_steps = len(ds_new[args.append_dim])
    for start in range(0, num_steps, args.time_batch_size):
        ds_batch = ds_new.isel({args.append_dim: slice(start, start + args.time_batch_size)})
        _write_pyramid_batch(repo, ds_batch, args, write_root_metadata=is_new_pyramid and start == 0)
        logger.info(f"Processed time steps {start + 1}-{start + len(ds_batch[args.append_dim])} of {num_steps}.")


def _clip_to_packed_range(ds: xr.Dataset, pyramid_encoding: dict[str, PackedEncoding]) -> xr.Dataset:
    """Clip packed variables to the range their integer dtype can hold, so values cannot wrap."""
    for var, packing in pyramid_encoding.items():
        if var not in ds:
            continue
        info = np.iinfo(packing.dtype)
        lo, hi = info.min, info.max
        if packing.fill_value == hi:
            hi -= 1
        elif packing.fill_value == lo:
            lo += 1
        lo_val = packing.add_offset + packing.scale_factor * lo
        hi_val = packing.add_offset + packing.scale_factor * hi
        ds[var] = ds[var].clip(lo_val, hi_val).assign_attrs(ds[var].attrs)
    return ds


def _write_pyramid_batch(
    repo: ic.Repository,
    ds_batch: xr.Dataset,
    args: BuildPyramidsDataInput,
    write_root_metadata: bool,
) -> None:
    """Reproject one batch of time steps, build its pyramid levels, and append them to the repository."""
    logger = get_run_logger()

    # Set spatial dims and reproject to web mercator
    ds_mercator = gu.reproject_dataset(
        dataset=ds_batch,
        target_crs=args.target_crs,
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        source_crs=args.source_crs
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

    # This ensures the parent '/pyramids' group contains the 'multiscales' block
    if write_root_metadata:
        logger.info(f"Writing root GeoZarr pyramid metadata to: {PYRAMID_GROUP_PATH}")
        root_metadata_ds = xr.Dataset(attrs=dt.attrs)

        # Safely write it directly into the parent group path of the Icechunk store
        root_metadata_ds.to_zarr(
            rw_session.store,
            group=PYRAMID_GROUP_PATH,
            mode="w",
            zarr_format=3,  # Icechunk works natively with Zarr v3 specs
            consolidated=False
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
            level_ds,
            source_crs=args.target_crs,  # pyramids are already in target_crs (web mercator)
            x_dim="x",
            y_dim="y",
        )
        level_ds.attrs.update(attrs)
        level_ds = _clip_to_packed_range(level_ds, args.pyramid_encoding)

        logger.info("Updated GeoZarr attributes for pyramid level: %s", level_name)
        # Create the level on first write, append to it afterwards
        if gu.group_contains_data(
            store=rw_session.store,
            group_path=PYRAMID_GROUP_PATH,
            sub_group_name=level_name
        ):
            encoding_config = None
            write_mode = "a"
            append_dim = args.append_dim
        else:
            encoding_config = gu.create_encoding_config(
                level_ds,
                append_dim=args.append_dim,
                chunk_size=args.chunk_size,
                num_shard_chunks=args.num_shard_chunks,
            )
            for var, packing in args.pyramid_encoding.items():
                if var in encoding_config:
                    encoding_config[var].update(packing.to_encoding())
            write_mode = "w"
            append_dim = None

        group_path = f"{PYRAMID_GROUP_PATH}/{level_name}"
        logger.info(f"Writing pyramid level '{level_name}' to: {group_path} (mode='{write_mode}').")
        level_ds = level_ds.sortby(args.append_dim)
        to_icechunk(
            level_ds,
            rw_session,
            group=group_path,
            encoding=encoding_config,
            align_chunks=True,
            mode=write_mode,
            append_dim=append_dim,
        )

    snapshot_id = rw_session.commit(
        f"Committed {len(dt.children)} pyramid levels ({len(level_ds[args.append_dim])} new time step(s)) "
        f"to {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Pyramids committed with snapshot ID: {snapshot_id}.")
