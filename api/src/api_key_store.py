import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime

import asyncpg

from .auth import AuthIdentity
from .config import config


class ApiKeyStore:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def startup(self):
        self._pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    owner_sub TEXT NOT NULL,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    scopes TEXT[] DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    revoked_at TIMESTAMPTZ
                );
                """
            )

    async def shutdown(self):
        if self._pool:
            await self._pool.close()

    def _hash_key(self, plaintext: str) -> str:
        digest = hmac.new(
            config.API_KEY_HASH_SALT.encode("utf-8"),
            plaintext.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest

    def _new_api_key(self) -> str:
        return f"{config.API_KEY_PREFIX}{secrets.token_urlsafe(32)}"

    async def create_key(self, owner_sub: str, name: str, scopes: list[str] | None = None):
        if self._pool is None:
            raise RuntimeError("API key store is not initialized")

        plaintext = self._new_api_key()
        key_hash = self._hash_key(plaintext)
        key_id = str(uuid.uuid4())
        scopes = scopes or []

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO api_keys (id, owner_sub, name, key_hash, scopes)
                VALUES ($1, $2, $3, $4, $5)
                """,
                key_id,
                owner_sub,
                name,
                key_hash,
                scopes,
            )

        return {
            "id": key_id,
            "name": name,
            "api_key": plaintext,
            "scopes": scopes,
        }

    async def validate_key(self, plaintext: str) -> AuthIdentity | None:
        if self._pool is None:
            raise RuntimeError("API key store is not initialized")

        key_hash = self._hash_key(plaintext)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT owner_sub, scopes, revoked_at
                FROM api_keys
                WHERE key_hash = $1
                """,
                key_hash,
            )

        if row is None or row["revoked_at"] is not None:
            return None

        return AuthIdentity(
            subject=row["owner_sub"],
            auth_type="api_key",
            scopes=row["scopes"] or [],
            roles=["api-key"],
        )

    async def list_keys(self, owner_sub: str):
        if self._pool is None:
            raise RuntimeError("API key store is not initialized")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, scopes, created_at, revoked_at
                FROM api_keys
                WHERE owner_sub = $1
                ORDER BY created_at DESC
                """,
                owner_sub,
            )

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "scopes": row["scopes"] or [],
                "created_at": row["created_at"].isoformat(),
                "revoked_at": (
                    row["revoked_at"].isoformat() if row["revoked_at"] else None
                ),
            }
            for row in rows
        ]

    async def revoke_key(self, owner_sub: str, key_id: str) -> bool:
        if self._pool is None:
            raise RuntimeError("API key store is not initialized")

        now = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE api_keys
                SET revoked_at = $1
                WHERE id = $2 AND owner_sub = $3 AND revoked_at IS NULL
                """,
                now,
                key_id,
                owner_sub,
            )

        return result.endswith("1")
