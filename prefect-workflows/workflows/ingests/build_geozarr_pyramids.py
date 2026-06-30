from prefect import flow, get_run_logger
import icechunk as ic
from icechunk.xarray import to_icechunk
import xarray as xr
from topozarr import create_pyramid
import rioxarray  # noqa: rio accessor
import zarr

from utils import grid_utils as gu
from models.ingest_gridded_data_input import (
    IngestGriddedDataInput,
    RAW_DATA_GROUP_PATH,
    PYRAMID_GROUP_PATH
)


@flow(
    flow_run_name="build-pyramids",
    timeout_seconds=60 * 60
)
def build_pyramids(args: IngestGriddedDataInput) -> None:
    """Build multiscale pyramids incrementally for newly ingested data and write them to an IceChunk repository.

    Reads only time steps not yet present in the pyramid store, reprojects to web
    mercator, creates downsampled pyramid levels, and appends to the existing
    pyramid groups (or creates them on the first run).

    Parameters
    ----------
    args : IngestGriddedDataInput
        Pydantic model containing all flow parameters. See IngestGriddedDataInput for field descriptions.
    """
    logger = get_run_logger()

    storage = ic.s3_storage(
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
    first_level = str(args.factors[0])
    if not gu.group_contains_data(rw_session.store, RAW_DATA_GROUP_PATH):
        logger.info(f"No data found in {RAW_DATA_GROUP_PATH}. Shutting down.")
        return

    if not gu.group_contains_data(rw_session.store, f"{PYRAMID_GROUP_PATH}/{first_level}"):
        is_new_pyramid = True
        logger.info(f"No existing pyramids found. Building for all data in {RAW_DATA_GROUP_PATH}.")
        ds_new = xr.open_zarr(
            rw_session.store,
            group=RAW_DATA_GROUP_PATH,
            consolidated=False,
            decode_coords="all"
        )
    else:
        is_new_pyramid = False
        logger.info(f"Existing pyramids found. Checking for new data against {RAW_DATA_GROUP_PATH}.")
        existing_ds = xr.open_zarr(
            store=rw_session.store,
            group=RAW_DATA_GROUP_PATH,
            consolidated=False
        )
        incoming_ds = xr.open_zarr(
            rw_session.store,
            group=f"{PYRAMID_GROUP_PATH}/{first_level}",
            consolidated=False
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

    # Set spatial dims and reproject to web mercator
    ds_mercator = gu.reproject_dataset(
        dataset=ds_new,
        target_crs=args.target_crs,
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        source_crs=args.source_crs
    )
    logger.info(f"Reprojected {len(ds_new.indexes[args.append_dim].unique())} time step(s) to {args.target_crs}.")

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

    # Write each pyramid level — mode="w" on first run, mode="a" for incremental appends
    write_mode = "w" if is_new_pyramid else "a"
    append_dim_arg = None if is_new_pyramid else args.append_dim

    rw_session = repo.writable_session("main")

    # This ensures the parent '/pyramids' group contains the 'multiscales' block
    if is_new_pyramid:
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

        level_ds = gu.rechunk_dataset(
            level_tree_node.to_dataset(), args.append_dim, args.chunk_size
        )
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

        # Check to see if data exists
        group_path = f"{PYRAMID_GROUP_PATH}/{level_name}"
        if gu.group_contains_data(rw_session.store, group_path):
            encoding_config = None
            write_mode = "a"
        else:
            encoding_config = gu.create_encoding_config(
                level_ds,
                append_dim=args.append_dim,
                chunk_size=args.chunk_size,
                num_shard_chunks=args.num_shard_chunks,
            )
            write_mode = "w"


        logger.info(f"Writing pyramid level '{level_name}' to: {group_path} (mode='{write_mode}').")
        to_icechunk(
            level_ds,
            rw_session,
            group=group_path,
            encoding=encoding_config,
            align_chunks=True,
            mode=write_mode,
            append_dim=append_dim_arg,
        )


    snapshot_id = rw_session.commit(
        f"Committed {len(dt.children)} pyramid levels ({len(level_ds[args.append_dim])} new time step(s)) "
        f"to {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Pyramids committed with snapshot ID: {snapshot_id}.")
