"""FastAPI application factory.

Layers 5-6 will register middleware, the ``/auth`` router, exception handlers,
and rate limiters here. For layer 1 we expose a minimal app with a health
endpoint so the dev server can start before any domain code exists.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.config import settings
from app.logging_config import configure_logging

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="dataprep",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env.value}

    return app


app = create_app()
