"""Rate limiter factory.

In v0 we use slowapi with an in-process backend. The settings expose
``RATE_LIMIT_BACKEND=redis`` and ``REDIS_URL`` so the production deploy
swaps to Redis without changing call sites; the wiring just isn't on yet
because Redis isn't connected to the app.

In tests (``APP_ENV=test``) the limiter is *enabled* but the per-endpoint
limits are generous enough that login fixtures don't trip over them. If a
specific test needs to disable a limit, override the dependency on the
endpoint's router.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import RateLimitBackend, settings


def _storage_uri() -> str:
    if settings.rate_limit_backend is RateLimitBackend.redis:
        return settings.redis_url
    return "memory://"


limiter: Limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri(),
    default_limits=[],  # apply per-endpoint, not globally
    strategy="fixed-window",
)
