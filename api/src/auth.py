import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt

from .config import config


logger = logging.getLogger("teehr-api.auth")


def _to_list(value: str | list | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _allowed_audiences() -> list[str]:
    return [
        audience.strip()
        for audience in config.KEYCLOAK_ALLOWED_AUDIENCES.split(",")
        if audience.strip()
    ]


@dataclass
class AuthIdentity:
    subject: str
    auth_type: str
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)

    @property
    def is_authenticated(self) -> bool:
        return self.auth_type in {"jwt", "api_key"}


class KeycloakJWTValidator:
    def __init__(self):
        self._jwks_cache: dict | None = None
        self._jwks_cache_time = 0.0
        self._jwks_cache_ttl = 300
        self._jwks_url_cache: str | None = None
        self._jwks_url_cache_time = 0.0
        self._jwks_url_cache_ttl = 3600
        self._refresh_lock = asyncio.Lock()

    async def _get_jwks_url(self) -> str:
        if config.KEYCLOAK_JWKS_URL:
            return config.KEYCLOAK_JWKS_URL

        now = time.time()
        if self._jwks_url_cache and (now - self._jwks_url_cache_time) < self._jwks_url_cache_ttl:
            return self._jwks_url_cache

        openid_cfg_url = (
            f"{config.KEYCLOAK_ISSUER_URL}/.well-known/openid-configuration"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(openid_cfg_url)
            response.raise_for_status()
            data = response.json()
            self._jwks_url_cache = data["jwks_uri"]
            self._jwks_url_cache_time = now
            return self._jwks_url_cache

    async def _get_jwks(self) -> dict:
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self._jwks_cache

        async with self._refresh_lock:
            now = time.time()
            if self._jwks_cache and (now - self._jwks_cache_time) < self._jwks_cache_ttl:
                return self._jwks_cache

            jwks_url = await self._get_jwks_url()
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = now
                return self._jwks_cache

    async def validate(self, token: str) -> AuthIdentity:
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise HTTPException(status_code=401, detail="JWT missing key id")

            jwks = await self._get_jwks()
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if key is None:
                self._jwks_cache = None
                jwks = await self._get_jwks()
                key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)

            if key is None:
                raise HTTPException(status_code=401, detail="Unable to find signing key")

            decode_options = {"verify_aud": False}
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=config.KEYCLOAK_ISSUER_URL,
                options=decode_options,
            )

            allowed_audiences = _allowed_audiences()
            token_audiences = _to_list(claims.get("aud"))
            token_azp = claims.get("azp")
            if allowed_audiences:
                audience_match = any(aud in allowed_audiences for aud in token_audiences)
                azp_match = token_azp in allowed_audiences
                if not audience_match and not azp_match:
                    raise HTTPException(status_code=401, detail="Invalid access token")

            roles = claims.get("realm_access", {}).get("roles", [])
            scopes = claims.get("scope", "").split() if claims.get("scope") else []
            subject = claims.get("sub")
            if not subject:
                raise HTTPException(status_code=401, detail="JWT missing subject")

            return AuthIdentity(
                subject=subject,
                auth_type="jwt",
                roles=roles,
                scopes=scopes,
            )
        except httpx.HTTPError as exc:
            logger.error("Keycloak connectivity error during token validation: %s", str(exc))
            raise HTTPException(
                status_code=503,
                detail="Authentication provider temporarily unavailable",
            ) from exc
        except JWTError as exc:
            logger.warning("JWT validation failed")
            raise HTTPException(status_code=401, detail="Invalid access token") from exc


async def resolve_identity(request: Request) -> AuthIdentity:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        identity = await request.app.state.jwt_validator.validate(token)
        return identity

    api_key = request.headers.get("x-api-key")
    if api_key:
        identity = await request.app.state.api_key_store.validate_key(api_key)
        if identity:
            return identity
        raise HTTPException(status_code=401, detail="Invalid API key")

    return AuthIdentity(subject="anonymous", auth_type="anonymous", roles=["anonymous"])


async def get_request_identity(request: Request) -> AuthIdentity:
    identity = getattr(request.state, "identity", None)
    if identity:
        return identity
    identity = await resolve_identity(request)
    request.state.identity = identity
    return identity


async def get_authenticated_identity(
    identity: AuthIdentity = Depends(get_request_identity),
) -> AuthIdentity:
    if not identity.is_authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    return identity


async def get_admin_identity(
    identity: AuthIdentity = Depends(get_authenticated_identity),
) -> AuthIdentity:
    # Restrict key management to interactive admin JWT identities.
    if identity.auth_type != "jwt":
        raise HTTPException(status_code=403, detail="Admin JWT required")
    if "admin" not in identity.roles:
        raise HTTPException(status_code=403, detail="Admin role required")
    return identity
