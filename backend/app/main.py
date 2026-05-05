"""FastAPI application factory.

Wiring order (matters):

1. ``configure_logging`` runs in lifespan startup so the redaction filter
   is installed before any handler emits.
2. CORS — must be the *outermost* middleware so preflight responses get
   the right headers even when something later raises.
3. Security headers — applied to every response after CORS.
4. The auth router lives under ``/api/v1/auth`` (registered in layer 6).

The ``rate_limit.limiter`` instance is attached to ``app.state`` so
endpoint decorators (``@limiter.limit("...")``) can find it.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.core.rate_limit import limiter
from app.logging_config import configure_logging
from app.middleware.security_headers import SecurityHeadersMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import Request
    from fastapi.responses import Response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def _rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="dataprep",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    # Rate limiter — attach instance + register exception handler + middleware.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # Security headers (inner of the two we add).
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS — outermost. allow_credentials=True is required for cookie auth
    # and forces explicit origins (browsers refuse "*" with credentials).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o).rstrip("/") for o in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env.value}

    # The /api/v1/auth router is registered in layer 6.
    return app


app = create_app()
