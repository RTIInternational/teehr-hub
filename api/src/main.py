import asyncio
import logging
import time
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .api_key_store import ApiKeyStore
from .auth import KeycloakJWTValidator, resolve_identity
from .config import config
from .models import HealthResponse
from .rate_limit import InMemoryRateLimiter
from .routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("teehr-api")

app = FastAPI(
    title="TEEHR Dashboard API",
    version="0.1.0",
    timeout=config.REQUEST_TIMEOUT,
    swagger_ui_init_oauth={
        "clientId": config.KEYCLOAK_SWAGGER_CLIENT_ID,
        "usePkceWithAuthorizationCodeGrant": True,
        "scopes": "openid profile email",
    },
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=(
            "TEEHR Dashboard API. Use Swagger 'Authorize' with either a Keycloak "
            "bearer token or an API key in x-api-key header."
        ),
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste Keycloak access token",
    }
    security_schemes["OAuth2Keycloak"] = {
        "type": "oauth2",
        "description": "Login with Keycloak via Authorization Code + PKCE",
        "flows": {
            "authorizationCode": {
                "authorizationUrl": config.KEYCLOAK_AUTH_URL,
                "tokenUrl": config.KEYCLOAK_TOKEN_URL,
                "scopes": {
                    "openid": "OpenID Connect scope",
                    "profile": "User profile",
                    "email": "User email",
                },
            }
        },
    }
    security_schemes["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "x-api-key",
        "description": "TEEHR API key",
    }

    public_paths = {"/health", "/openapi.json", "/docs", "/redoc"}
    for path, path_item in openapi_schema.get("paths", {}).items():
        if path in public_paths:
            continue
        for method, operation in path_item.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
            }:
                continue
            operation.setdefault(
                "security",
                [
                    {"OAuth2Keycloak": ["openid", "profile", "email"]},
                    {"BearerAuth": []},
                    {"ApiKeyAuth": []},
                ],
            )

    # Auth route overrides
    auth_me = openapi_schema.get("paths", {}).get("/auth/me", {}).get("get")
    if auth_me:
        auth_me["security"] = [
            {"OAuth2Keycloak": ["openid", "profile", "email"]},
            {"BearerAuth": []},
            {"ApiKeyAuth": []},
        ]

    auth_keys_get = openapi_schema.get("paths", {}).get("/auth/api-keys", {}).get("get")
    if auth_keys_get:
        auth_keys_get["security"] = [
            {"OAuth2Keycloak": ["openid", "profile", "email"]},
            {"BearerAuth": []},
        ]

    auth_keys_post = openapi_schema.get("paths", {}).get("/auth/api-keys", {}).get("post")
    if auth_keys_post:
        auth_keys_post["security"] = [
            {"OAuth2Keycloak": ["openid", "profile", "email"]},
            {"BearerAuth": []},
        ]

    auth_keys_delete = openapi_schema.get("paths", {}).get("/auth/api-keys/{key_id}", {}).get("delete")
    if auth_keys_delete:
        auth_keys_delete["security"] = [
            {"OAuth2Keycloak": ["openid", "profile", "email"]},
            {"BearerAuth": []},
        ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.on_event("startup")
async def startup_event():
    app.state.jwt_validator = KeycloakJWTValidator()
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.api_key_store = ApiKeyStore(config.API_KEYS_DB_DSN)
    await app.state.api_key_store.startup()


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.api_key_store.shutdown()

# CORS middleware to allow frontend requests - MUST be first middleware
# Get the allowed origins from config
cors_origins_env = config.CORS_ORIGINS

if cors_origins_env == "*":
    # In development, allow all origins
    allow_origins = ["*"]
    allow_credentials = False
else:
    # In production, use specific origins from environment
    allow_origins = [origin.strip() for origin in cors_origins_env.split(",")]
    allow_credentials = True

logger.info(
    "Configured CORS origins=%s allow_credentials=%s",
    allow_origins,
    allow_credentials,
)

# Add CORS middleware FIRST - this is critical
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)


@app.middleware("http")
async def auth_context_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    exempt_paths = (
        path == "/health"
        or path == "/openapi.json"
        or path.startswith("/docs")
        or path.startswith("/redoc")
    )

    # Keep auth optional while attaching identity for routes that need it.
    request.state.identity = await resolve_identity(request)

    # Require authentication for all non-diagnostic API paths.
    if not exempt_paths and not request.state.identity.is_authenticated:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
        )

    # Exempt health/docs/openapi from limiter for diagnostics.
    if not exempt_paths:
        app.state.rate_limiter.check(request.state.identity, request.url.path)

    return await call_next(request)


# Add timeout middleware for long-running requests
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Add timeout handling for long-running requests."""
    start_time = time.time()

    try:
        # Set a timeout for request processing
        response = await asyncio.wait_for(
            call_next(request), timeout=config.REQUEST_TIMEOUT
        )

        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        # Log slow requests
        if process_time > 10:
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.url.path} "
                f"took {process_time:.3f}s"
            )
        elif process_time > 5:
            logger.info(
                f"MEDIUM REQUEST: {request.method} {request.url.path} "
                f"took {process_time:.3f}s"
            )

        return response
    except TimeoutError:
        logger.error(
            f"REQUEST TIMEOUT: {request.method} {request.url.path} "
            f"after {time.time() - start_time:.3f}s"
        )
        return JSONResponse(
            status_code=504,
            content={
                "detail": f"Request timed out after {config.REQUEST_TIMEOUT} "
                f"seconds. Try reducing the data range or adding more filters."
            },
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        logger.error(f"REQUEST ERROR: {request.method} {request.url.path} - {str(e)}")
        return JSONResponse(
            status_code=500, content={"detail": f"Internal server error: {str(e)}"}
        )


app.include_router(router)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy", timestamp=datetime.utcnow(), version="0.1.0"
    )
