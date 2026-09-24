import os
from pathlib import Path
from typing import Union
import subprocess

import obstore
from obstore.store import from_url
from prefect import task, flow, get_run_logger

from workflows.models.create_vector_tiles_inputs import VectorTilesInput
from workflows.utils.common_utils import initialize_evaluation


@task(timeout_seconds=60 * 5)
def upload_to_s3(
    source_filepath: Union[Path, str],
    target_bucket_name: str,
    target_prefix: str,
    target_filename: str,
    key: str,
    secret: str,
    endpoint_url: Union[str, None]
):
    """Write the file to S3."""
    logger = get_run_logger()
    target_prefix = target_prefix.strip("/")
    object_key = f"{target_prefix}/{target_filename}" if target_prefix else target_filename
    dest_s3_path = f"{target_bucket_name}/{object_key}"

    logger.info(f"Uploading {source_filepath} to s3://{dest_s3_path}")
    logger.info(f"Using S3 endpoint: {endpoint_url or 'default'}")
    # Anything left unset falls back to obstore's own env/IRSA credential chain,
    # so remote runs pick up the pod's role without explicit keys.
    config = {}
    if key:
        config["access_key_id"] = key
    if secret:
        config["secret_access_key"] = secret
    if endpoint_url:
        config["endpoint"] = endpoint_url

    # MinIO is served over plain HTTP in-cluster; obstore rejects http:// otherwise.
    client_options = {"allow_http": True} if str(endpoint_url).startswith("http://") else None

    store = from_url(
        f"s3://{target_bucket_name}/",
        config=config or None,
        client_options=client_options,
    )
    obstore.put(store, object_key, Path(source_filepath))
    logger.info(f"Finished uploading {source_filepath} to s3://{dest_s3_path}")


@task(timeout_seconds=60 * 10)
def create_pmtiles_archive(
    temp_filepath: Path,
    output_layer_name: str,
    pmtiles_archive_filepath: Union[Path, str],
):
    """Create a pmtiles archive using tippecanoe."""
    logger = get_run_logger()
    logger.info("Creating .pmtiles archive using tippecanoe")
    tippecanoe_cmd = [
        "tippecanoe",
        f"--output={str(pmtiles_archive_filepath)}",
        f"--layer={output_layer_name}",
        "--simplify-only-low-zooms",
        "--drop-rate=0",
        "--minimum-zoom=4",
        "--maximum-zoom=9",
        "--no-tile-size-limit",
        "--force",
        "--detect-shared-borders",
        "--generate-ids",
        "--quiet",
        "--no-progress-indicator",
        f"{temp_filepath}"
    ]
    logger.info("Running command: %s", " ".join(tippecanoe_cmd))

    process = subprocess.Popen(
        tippecanoe_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        if process.stdout:
            for line in process.stdout:
                logger.info("tippecanoe: %s", line.rstrip())

        return_code = process.wait()
    except Exception:
        process.kill()
        process.wait()
        raise

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, tippecanoe_cmd)

    logger.info(f"Finished writing .pmtiles archive to: {pmtiles_archive_filepath}")

@flow(
    flow_run_name="create-vector-tile-archive",
    timeout_seconds=60 * 60
)
def create_vector_tile_archive(args: VectorTilesInput) -> None:
    """Create pm-tiles archive from locations table layer."""
    logger = get_run_logger()

    ev = initialize_evaluation(
        temp_dir_path=args.temp_dir_path,
        start_spark_cluster=args.start_spark_cluster
    )

    # Filter the layer based on location_id prefix
    logger.info(f"Filtering the locations table by {args.location_id_prefix}-")
    gdf = ev.locations.filter(
        filters=[
            {
                "column": "id",
                "operator": "like",
                "value": f"{args.location_id_prefix}-%"
            }
        ]
    ).to_geopandas()

    # Save to temp FlatGeobuf file for tippecanoe
    fgb_filepath = Path(args.temp_dir_path, f"{args.output_layer_name}.fgb")
    logger.info(f"Saving {len(gdf)} features to {fgb_filepath}")
    gdf.to_file(fgb_filepath, driver="FlatGeobuf")

    # Convert to pmtiles archive using tippecanoe
    pmtiles_archive_name = f"{args.output_layer_name}.pmtiles"
    pmtiles_archive_filepath = Path(args.temp_dir_path, pmtiles_archive_name)
    create_pmtiles_archive(
        temp_filepath=fgb_filepath,
        output_layer_name=args.output_layer_name,
        pmtiles_archive_filepath=pmtiles_archive_filepath
    )

    s3_endpoint_url = os.getenv("REMOTE_CATALOG_S3_ENDPOINT")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Upload the pmtiles archive to S3
    upload_to_s3(
        source_filepath=pmtiles_archive_filepath,
        target_bucket_name=args.target_bucket_name,
        target_prefix=args.target_prefix,
        target_filename=pmtiles_archive_name,
        key=aws_access_key_id,
        secret=aws_secret_access_key,
        endpoint_url=s3_endpoint_url
    )

    return