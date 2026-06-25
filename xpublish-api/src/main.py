"""
xpublish REST service for icechunk gridded data.

Serves raster tiles via TilesPlugin (reads from /pyramids group) and
point queries via CfEdrPlugin (reads from /raw_data group).

Environment variables:
  ICECHUNK_REPOS         Comma-separated list of name:bucket:prefix triplets.
                         Example: "ua_swann_4km:warehouse:icechunk-ingests/ua_swann_4km"
                         Multiple: "ds1:bucket:prefix1,ds2:bucket:prefix2"
  ICECHUNK_BRANCH        Branch to open for all repos (default: main)
  ICECHUNK_STORAGE_MODE  "local" for minio/kind, "remote" for AWS S3 (default: remote)
  CORS_ORIGINS           Comma-separated list of allowed CORS origins

  Local (ICECHUNK_STORAGE_MODE=local):
    ICECHUNK_ENDPOINT_URL   MinIO endpoint (default: http://minio:9000)
    AWS_DEFAULT_REGION      Region (default: us-east-1)
    AWS_ACCESS_KEY_ID       MinIO access key
    AWS_SECRET_ACCESS_KEY   MinIO secret key

  Remote (ICECHUNK_STORAGE_MODE=remote):
    AWS_*                   Standard AWS credential env vars or IRSA

  Keycloak (JWT auth):
    KEYCLOAK_ISSUER_URL       Keycloak realm URL (external)
    KEYCLOAK_JWKS_URL         JWKS endpoint override (use internal cluster URL)
    KEYCLOAK_ALLOWED_AUDIENCES  Comma-separated accepted aud/azp values
"""

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

import icechunk as ic
import numpy as np
import xarray as xr
import xpublish
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from xpublish_edr import CfEdrPlugin
from xpublish_tiles import lib as xpublish_tiles_lib
from xpublish_tiles.xpublish.tiles import TilesPlugin
from xpublish_tiles.multiscale import assign_leaf_xpublish_ids

from .auth import KeycloakJWTValidator, resolve_identity

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

@dataclass
class RepoConfig:
    name: str
    bucket: str
    prefix: str


def parse_repo_configs() -> list[RepoConfig]:
    """
    Parse ICECHUNK_REPOS env var: comma-separated name:bucket:prefix triplets.
    Each entry is split on the first two colons so prefixes with colons are safe.
    """
    repos_env = os.getenv("ICECHUNK_REPOS", "").strip()
    if not repos_env:
        raise RuntimeError(
            "ICECHUNK_REPOS is required. "
            "Format: name:bucket:prefix  (comma-separate multiple repos)"
        )
    configs = []
    for entry in repos_env.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":", 2)
        if len(parts) != 3:
            raise ValueError(
                f"ICECHUNK_REPOS entry '{entry}' must be in name:bucket:prefix format"
            )
        configs.append(RepoConfig(name=parts[0].strip(), bucket=parts[1].strip(), prefix=parts[2].strip()))
    if not configs:
        raise RuntimeError("ICECHUNK_REPOS contained no valid entries")
    return configs


def build_storage_kwargs() -> dict:
    """
    Return kwargs for ic.s3_storage() based on ICECHUNK_STORAGE_MODE.

    - "local":  explicit endpoint + credentials via standard AWS_* env vars,
                plus minio-specific flags (allow_http, force_path_style, endpoint_url).
    - "remote": from_env=True — reads AWS_* env vars or uses IRSA on EKS.
    """
    mode = os.getenv("ICECHUNK_STORAGE_MODE", "remote")
    if mode == "local":
        kwargs: dict = {
            "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            "allow_http": True,
            "endpoint_url": os.getenv("ICECHUNK_ENDPOINT_URL", "http://minio:9000"),
            "force_path_style": True,
        }
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if access_key:
            kwargs["access_key_id"] = access_key
        if secret_key:
            kwargs["secret_access_key"] = secret_key
        return kwargs
    return {"from_env": True}


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    app.state.jwt_validator = KeycloakJWTValidator()
    try:
        yield
    finally:
        # Clean up xpublish-tiles module-level executor to avoid leaked semaphores.
        xpublish_tiles_lib.EXECUTOR.shutdown(wait=False, cancel_futures=True)
        xpublish_tiles_lib._semaphores.clear()
        xpublish_tiles_lib._data_load_semaphores.clear()


def build_app() -> FastAPI:
    branch = os.getenv("ICECHUNK_BRANCH", "main")
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
    storage_mode = os.getenv("ICECHUNK_STORAGE_MODE", "remote")

    repo_configs = parse_repo_configs()
    storage_kwargs = build_storage_kwargs()

    logger.info(
        "Storage mode: %s | repos: %s",
        storage_mode,
        [(r.name, r.bucket, r.prefix) for r in repo_configs],
    )

    datasets: dict[str, xr.Dataset | xr.Datatree] = {}
    for cfg in repo_configs:
        logger.info(
            "Opening icechunk repo s3://%s/%s (branch=%s)", cfg.bucket, cfg.prefix, branch
        )
        # Context manager?
        storage = ic.s3_storage(bucket=cfg.bucket, prefix=cfg.prefix, **storage_kwargs)
        repo = ic.Repository.open(storage)
        session = repo.readonly_session(branch=branch)
        store = session.store

        # /pyramids group — used by TilesPlugin for raster tile serving.
        dt = xr.open_datatree(
            store,
            group="/pyramids",
            engine="zarr",
            decode_coords="all",
            consolidated=False
        )
        dt.attrs["_xpublish_id"] = cfg.name   # enables cache key in xpublish-tile
        assign_leaf_xpublish_ids(dt)   # propagates "ua_swann_4km/0", "ua_swann_4km/1", etc. cache keys to children
        datasets[cfg.name] = dt
        # /raw_data group — used by CfEdrPlugin for point queries.
        datasets[f"{cfg.name}_raw_data"] = xr.open_zarr(store, group="/raw_data", consolidated=False)

    logger.info("Registered datasets: %s", list(datasets.keys()))

    rest = xpublish.Rest(
        datasets=datasets,
        plugins={"tiles": TilesPlugin(), "edr": CfEdrPlugin()},
    )

    api_app = rest.app

    # --- Custom discovery endpoints consumed by the frontend ---
    @api_app.get("/dataset-keys")
    def list_dataset_keys():
        # Return only the tiles-capable dataset names (not the _raw_data variants).
        return {"datasets": [cfg.name for cfg in repo_configs]}

    @api_app.get("/dataset-variables/{dataset_id}")
    def dataset_variables(dataset_id: str):
        # Fix discovery: look at 0 child of the pyramid tree, or fall back to raw_data
        if dataset_id in datasets and hasattr(datasets[dataset_id], "children"):
            # topozarr creates children nodes named 'scale0', 'scale1', etc.
            first_child = list(datasets[dataset_id].children.keys())[0]
            variables = list(datasets[dataset_id][first_child].data_vars.keys())
            logger.info("Variables for dataset '%s': %s", dataset_id, variables)
            return {"dataset_id": dataset_id, "variables": variables}

        # Variables come from the /raw_data group; the /pyramids group root has none.
        raw_data_id = f"{dataset_id}_raw_data"
        if raw_data_id not in datasets:
            raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset_id}'")
        return {"dataset_id": dataset_id, "variables": list(datasets[raw_data_id].data_vars.keys())}

    @api_app.get("/datasets/{dataset_id}/coords/{coord_name}")
    def dataset_coord_values(dataset_id: str, coord_name: str):
        # Coords (including time) live in the /raw_data group, not /pyramids.
        raw_data_id = f"{dataset_id}_raw_data"
        if raw_data_id not in datasets:
            raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset_id}'")
        ds = datasets[raw_data_id]
        if coord_name not in ds.coords:
            raise HTTPException(status_code=404, detail=f"Coordinate '{coord_name}' not found")
        values = ds.coords[coord_name].values
        if values.ndim != 1:
            values = values.ravel()
        serialized = [
            np.datetime_as_string(v, unit="s") if isinstance(v, np.datetime64) else str(v)
            for v in values
        ]
        logger.info("Coordinate values for dataset '%s', coord '%s': %s", dataset_id, coord_name, serialized)
        return {"dataset_id": dataset_id, "coord_name": coord_name, "values": serialized}

    # --- api_app middleware (gzip only; CORS is on the outer app) ---

    api_app.add_middleware(GZipMiddleware, minimum_size=1000)

    # --- Outer app ---

    app = FastAPI(title="TEEHR xpublish API", lifespan=app_lifespan)
    app.mount("/api", api_app)

    # Auth middleware is registered first so it ends up innermost.
    # CORSMiddleware is added second so it ends up outermost — this ensures
    # that ALL responses (including 401s from auth) pass through CORSMiddleware
    # and receive the correct Access-Control-Allow-Origin header.
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path == "/health":
            return await call_next(request)

        request.state.identity = await resolve_identity(request)
        if not request.state.identity.is_authenticated:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        return await call_next(request)

    allow_credentials = cors_origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "datasets": list(datasets.keys())}

    return app


app = build_app()
