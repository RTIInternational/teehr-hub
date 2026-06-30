"""
xpublish REST service for icechunk gridded data.

Serves raster tiles via TilesPlugin (reads from /pyramids group) and
point queries via CfEdrPlugin (reads from /raw_data group).

Environment variables:
  ICECHUNK_REPOS         Comma-separated list of repo names.
                         Example: "ua-swann-4km,nwm30-forcing-analysis-assim"
  ICECHUNK_BUCKET        S3 bucket that holds all icechunk repos.
                         Example: "warehouse" (local) or "ciroh-rti-public-data" (remote)
  ICECHUNK_PREFIX        Base prefix path; each repo lives at {prefix}/{name}.
                         Example: "icechunk-ingests"
  ICECHUNK_BRANCH        Branch to open for all repos (default: main)
  ICECHUNK_STORAGE_MODE  "local" for minio/kind, "remote" for AWS S3 (default: remote)
  CORS_ORIGINS           Comma-separated list of allowed CORS origins
  DATASET_CACHE_TTL      Seconds to cache dataset metadata before re-opening from icechunk
                         (default: 60). Set to 0 to disable caching (re-open on every request).

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

import numpy as np
import xpublish
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from xpublish_edr import CfEdrPlugin
from xpublish_tiles import lib as xpublish_tiles_lib
from xpublish_tiles.xpublish.tiles import TilesPlugin

from .auth import KeycloakJWTValidator, resolve_identity
from .provider import IcechunkDatasetProvider, RepoConfig

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def parse_repo_configs() -> list[RepoConfig]:
    """
    Parse repo configs from ICECHUNK_REPOS (comma-separated names),
    ICECHUNK_BUCKET (shared S3 bucket), and ICECHUNK_PREFIX (base prefix).
    Each repo's full prefix is constructed as "{ICECHUNK_PREFIX}/{name}".
    """
    repos_env = os.getenv("ICECHUNK_REPOS", "").strip()
    bucket = os.getenv("ICECHUNK_BUCKET", "").strip()
    prefix = os.getenv("ICECHUNK_PREFIX", "").strip()
    if not repos_env:
        raise RuntimeError("ICECHUNK_REPOS is required: comma-separated list of repo names")
    if not bucket:
        raise RuntimeError("ICECHUNK_BUCKET is required: S3 bucket name")
    if not prefix:
        raise RuntimeError("ICECHUNK_PREFIX is required: base prefix path for icechunk repos")
    configs = []
    for name in repos_env.split(","):
        name = name.strip()
        if not name:
            continue
        configs.append(RepoConfig(name=name, bucket=bucket, prefix=f"{prefix}/{name}"))
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
    cache_ttl = float(os.getenv("DATASET_CACHE_TTL", "60"))

    repo_configs = parse_repo_configs()
    storage_kwargs = build_storage_kwargs()

    logger.info(
        "Storage mode: %s | repos: %s | cache_ttl: %ss",
        storage_mode,
        [(r.name, r.bucket, r.prefix) for r in repo_configs],
        cache_ttl,
    )

    provider = IcechunkDatasetProvider(
        repo_configs=repo_configs,
        storage_kwargs=storage_kwargs,
        branch=branch,
        cache_ttl_seconds=cache_ttl,
    )

    rest = xpublish.Rest(
        datasets={},
        plugins={
            "icechunk-provider": provider,
            "tiles": TilesPlugin(),
            "edr": CfEdrPlugin(),
        },
    )

    api_app = rest.app

    # --- Custom discovery endpoints consumed by the frontend ---

    @api_app.get("/dataset-keys")
    def list_dataset_keys():
        # Return only the tiles-capable dataset names (not the _raw_data variants).
        return {"datasets": [cfg.name for cfg in repo_configs]}

    @api_app.get("/dataset-variables/{dataset_id}")
    def dataset_variables(dataset_id: str):
        pyramid_dt = provider.get_datatree_for_dataset(dataset_id)
        if pyramid_dt is None:
            raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset_id}'")
        children = list(pyramid_dt.children.keys())
        if children:
            variables = list(pyramid_dt[children[0]].data_vars.keys())
            logger.info("Variables for dataset '%s': %s", dataset_id, variables)
            return {"dataset_id": dataset_id, "variables": variables}
        # Pyramid has no children yet (empty repo) — fall back to raw_data variables.
        raw_dt = provider.get_datatree_for_dataset(f"{dataset_id}_raw_data")
        if raw_dt is None:
            raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset_id}'")
        return {"dataset_id": dataset_id, "variables": list(raw_dt.dataset.data_vars.keys())}

    @api_app.get("/datasets/{dataset_id}/coords/{coord_name}")
    def dataset_coord_values(dataset_id: str, coord_name: str):
        # Coords (including time) live in the /raw_data group, not /pyramids.
        raw_dt = provider.get_datatree_for_dataset(f"{dataset_id}_raw_data")
        if raw_dt is None:
            raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset_id}'")
        ds = raw_dt.dataset
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
        return {"status": "ok", "datasets": provider.dataset_ids()}

    return app


app = build_app()
