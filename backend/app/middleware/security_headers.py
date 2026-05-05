"""HTTP security headers applied to every response.

The list is conservative for an API server (no inline scripts, no images,
no frames). When we serve HTML in the future we'll loosen ``Content-Security-Policy``
in the rendering layer rather than here.

HSTS is only emitted in production — in dev (``http://localhost``) it would
poison the browser cache for the developer's own domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        )
        # API-only baseline; safe to override per-route.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response
