import time
from collections import defaultdict

from fastapi import HTTPException

from .auth import AuthIdentity
from .config import config


class InMemoryRateLimiter:
    def __init__(self):
        self._counts = defaultdict(int)

    def _key(self, identity: AuthIdentity, route_key: str, minute_bucket: int) -> str:
        return f"{minute_bucket}:{route_key}:{identity.auth_type}:{identity.subject}"

    def _limit_for(self, identity: AuthIdentity) -> int | None:
        if "admin" in identity.roles:
            return None
        if identity.is_authenticated:
            return config.AUTH_RATE_LIMIT_RPM
        return config.ANON_RATE_LIMIT_RPM

    def check(self, identity: AuthIdentity, route_key: str):
        limit = self._limit_for(identity)
        if limit is None:
            return

        minute_bucket = int(time.time() // 60)
        key = self._key(identity, route_key, minute_bucket)
        self._counts[key] += 1

        # Cheap periodic cleanup to avoid unbounded growth.
        if len(self._counts) > 50000:
            valid_prefix = f"{minute_bucket}:"
            self._counts = defaultdict(
                int,
                {k: v for k, v in self._counts.items() if k.startswith(valid_prefix)},
            )

        if self._counts[key] > limit:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Rate limit exceeded. "
                    "Authenticate for a higher limit or retry next minute."
                ),
            )
