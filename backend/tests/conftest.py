"""Shared pytest fixtures.

The test suite runs against the real Postgres started by the project
``docker-compose.yml`` but uses a separate database (``dataprep_test``).

Two engines, two roles
----------------------

Tenant isolation depends on Row-Level Security, and Postgres SUPERUSERS
*always* bypass RLS — even with ``FORCE ROW LEVEL SECURITY``. Tests must
therefore connect as a non-superuser, otherwise an isolation regression
would silently pass. We use:

* ``admin_engine`` (``test_database_admin_url``) — owner role, runs
  Alembic migrations and TRUNCATE between tests.
* ``test_engine`` (``test_database_url``) — runtime ``dataprep_app`` role,
  used by every test query so RLS policies are exercised.

The ``session`` fixture starts each test with no GUCs set, so RLS-protected
tables return zero rows by default and tests must explicitly opt in to a
tenant/user context.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from app.config import settings
from app.core.rate_limit import limiter
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Truncate every domain table between tests. Order doesn't matter because
# we use CASCADE, but listing them keeps the intent explicit.
DOMAIN_TABLES: tuple[str, ...] = (
    "profile_runs",
    "dataset_grants",
    "datasets",
    "data_sources",
    "audit_log",
    "auth_tokens",
    "refresh_tokens",
    "mfa_recovery_codes",
    "mfa_methods",
    "tenant_memberships",
    "users",
    "tenants",
)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """One non-superuser engine per test session, schema rebuilt from migrations."""
    # Drop and recreate the schema using the admin role (runtime role lacks
    # the privilege to drop the schema).
    bootstrap = create_async_engine(settings.test_database_admin_url, echo=False)
    async with bootstrap.begin() as conn:
        await conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")
        await conn.exec_driver_sql("GRANT USAGE ON SCHEMA public TO dataprep_app")
    await bootstrap.dispose()

    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.test_database_admin_url)
    # Alembic's run_migrations_online uses asyncio.run internally; offload it
    # to a thread to avoid clashing with the running loop.
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    engine = create_async_engine(settings.test_database_url, echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_engine() -> AsyncIterator[AsyncEngine]:
    """Owner-role engine, used only for cleanup (TRUNCATE) between tests."""
    engine = create_async_engine(settings.test_database_admin_url, echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """slowapi keeps an in-process counter keyed by client IP. Tests all
    run from 127.0.0.1, so without this fixture the per-IP buckets fill
    up across the suite and ``/register`` (limit 10/hour) starts
    rejecting valid calls. Resetting before each test keeps the fixture
    interaction explicit."""
    limiter.reset()


@pytest_asyncio.fixture(loop_scope="session")
async def session(
    test_engine: AsyncEngine, admin_engine: AsyncEngine
) -> AsyncIterator[AsyncSession]:
    """Per-test AsyncSession; all tables are truncated on teardown."""
    sessionmaker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sessionmaker() as s:
        try:
            yield s
        finally:
            await s.rollback()
    async with admin_engine.begin() as conn:
        await conn.exec_driver_sql("TRUNCATE TABLE " + ", ".join(DOMAIN_TABLES) + " CASCADE")
