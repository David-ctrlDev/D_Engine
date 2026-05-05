"""Async engine + session factory.

We force the asyncpg driver: bcrypt-style sync DSNs are rejected at startup
so a misconfigured environment fails loudly instead of falling back to a
synchronous driver that would deadlock the event loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _require_asyncpg(url: str) -> str:
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError(
            "DATABASE_URL must use the asyncpg driver (expected scheme 'postgresql+asyncpg://...')."
        )
    return url


def create_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(
        _require_asyncpg(url or settings.database_url),
        echo=settings.sql_echo,
        pool_pre_ping=True,
    )


engine: AsyncEngine = create_engine()

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session bound to a single request."""
    async with async_session_maker() as session:
        yield session
