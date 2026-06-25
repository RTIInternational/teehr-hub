from prefect import flow, get_run_logger
import icechunk as ic
from icechunk.xarray import to_icechunk
import xarray as xr
from topozarr import create_pyramid
import rioxarray
import zarr

from utils import grid_utils as gu
from models.ingest_gridded_data_input import IngestGriddedDataInput


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

    # Read the full materialized dataset (lazy)
    ro_session = repo.readonly_session("main")
    ds = xr.open_zarr(
        ro_session.store,
        group=args.raw_data_group,
        consolidated=False,
        decode_coords="all"
    )
    all_dims = ds.indexes[args.append_dim].unique()
    logger.info(f"Read materialized data from group: {args.raw_data_group}.")

    # Determine which time steps are not yet in the pyramid store
    first_level = str(args.factors[0])
    try:
        existing_level_ds = xr.open_zarr(
            ro_session.store,
            group=f"{args.pyramids_data_group}/{first_level}",
            consolidated=False
        )
        level_dims = existing_level_ds.indexes[args.append_dim].unique()
        new_dims = all_dims.difference(level_dims)
        is_new_pyramid = False
        logger.info(
            f"Found {len(level_dims)} existing pyramid time step(s). "
            f"{len(new_dims)} new step(s) to process."
        )
    except (FileNotFoundError, KeyError):
        is_new_pyramid = True
        logger.info(f"No existing pyramids found. Building from scratch for {len(all_dims)} time step(s).")
        new_dims = all_dims

    if new_dims.empty:
        logger.info("No new data to pyramid. Skipping.")
        return

    # Slice to only the new time steps before reprojecting
    ds_new = ds.sel({args.append_dim: new_dims})

    # Set spatial dims and reproject to web mercator
    # TODO: workaround. This should no longer be needed?
    if "time_str" in ds_new.variables:
        ds_new = ds_new.drop_vars("time_str")
    ds_new = ds_new.rio.set_spatial_dims(x_dim=args.x_dim, y_dim=args.y_dim)
    ds_new = ds_new.rio.write_crs(ds_new.rio.crs)
    ds_mercator = ds_new.rio.reproject(args.target_crs)
    ds_mercator = ds_mercator.proj.assign_crs(spatial_ref=args.target_crs)
    logger.info(f"Reprojected {len(new_dims)} time step(s) to {args.target_crs}.")

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

    session = repo.writable_session("main")

    # This ensures the parent '/pyramids' group contains the 'multiscales' block
    if is_new_pyramid:
        logger.info(f"Writing root GeoZarr pyramid metadata to: {args.pyramids_data_group}")
        root_metadata_ds = xr.Dataset(attrs=dt.attrs)

        # Safely write it directly into the parent group path of the Icechunk store
        root_metadata_ds.to_zarr(
            session.store,
            group=args.pyramids_data_group,
            mode="w",
            zarr_format=3,  # Icechunk works natively with Zarr v3 specs
            consolidated=False
        )

    layout = pyramid.attrs.get("multiscales", {}).get("layout", [])

    for level_name, level_tree_node in dt.children.items():
        attrs = level_tree_node.attrs.copy()

        # Inject GeoZarr spatial attrs for xpublish-tiles
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
        level_ds.attrs.update(attrs)

        encoding_config = gu.create_encoding_config(
            level_ds,
            append_dim=args.append_dim,
            chunk_size=args.chunk_size,
            num_shard_chunks=args.num_shard_chunks,
        )
        group_path = f"{args.pyramids_data_group}/{level_name}"

        logger.info(f"Writing pyramid level '{level_name}' to: {group_path} (mode='{write_mode}').")
        to_icechunk(
            level_ds,
            session,
            group=group_path,
            encoding=encoding_config,
            align_chunks=True,
            mode=write_mode,
            append_dim=append_dim_arg,
        )


    snapshot_id = session.commit(
        f"Committed {len(dt.children)} pyramid levels ({len(new_dims)} new time step(s)) "
        f"to {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Pyramids committed with snapshot ID: {snapshot_id}.")
