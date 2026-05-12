"""Alembic environment, async-aware.

The DSN is sourced from ``app.config.settings`` so that ``alembic.ini`` does
not have to know about environment files. Models are imported here so
``Base.metadata`` reflects every table in the project.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from app.auth import models
from app.config import settings
from app.data import models as _data_models
from app.db.base import Base
from app.llm import models as _llm_models
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Honour an explicit URL set by callers (e.g. test fixtures) before falling
# back to the application settings. The placeholder shipped in alembic.ini
# (``driver://user:pass@host/dbname``) counts as "unset" for this purpose.
#
# Migrations always run as the admin/owner role (``database_admin_url``); the
# regular ``database_url`` is for runtime app traffic, where RLS must apply.
_existing_url = config.get_main_option("sqlalchemy.url")
if not _existing_url or _existing_url.startswith("driver://"):
    config.set_main_option("sqlalchemy.url", settings.database_admin_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(_do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
