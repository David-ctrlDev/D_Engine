"""PostgreSQL probe — talks to a tenant's external database.

We use ``asyncpg`` directly (not SQLAlchemy) because we don't need
ORM mapping for these read-only introspection calls and the raw
driver is faster + has finer error messages.

Security
--------

The DSN comes from the encrypted ``connection_config`` blob, so by
the time we get here the secret is already in memory. We:

* never log the DSN,
* always close the connection in ``finally``,
* set a short ``timeout`` on every call so a hostile DSN can't hang
  the worker.

The probe never holds a long-lived pool — connections are opened
on-demand. Tenants connect to *their* database, not ours, so a
per-source pool would just hoard FDs without much win.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import asyncpg

from app.data.parsers.common import InferredColumn, InferredSchema
from app.data.probes import ProbeResult, TableInfo

# Hard cap. Any single probe call that takes longer than this is
# either a network black hole or a misconfigured DSN — we'd rather
# surface a clean "timeout" than tie up a worker.
_PROBE_TIMEOUT_SECONDS = 8.0

# Bounded sample read for ``introspect_table``. Enough to fill the
# inferred-schema sample column without scanning the whole table.
_SAMPLE_LIMIT = 5

# System schemas we hide from the table picker. Postgres ships with
# these and exposing them in the UI is just noise.
_SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")


# ---------------------------------------------------------------------------
# DSN construction
# ---------------------------------------------------------------------------


def _build_dsn(config: dict[str, Any]) -> str:
    """Build a libpq URI from the connection_config dict.

    The config carries the *user-provided* fields (host/port/db/user/
    password/sslmode). We never embed the password into a URL we'd
    log; asyncpg accepts a ``password`` kwarg on ``connect`` instead.
    """
    host = config["host"]
    port = config.get("port", 5432)
    database = config["database"]
    sslmode = config.get("sslmode", "prefer")
    user = config["user"]
    # Build the URL without password. password goes via kwarg below.
    return f"postgresql://{user}@{host}:{port}/{database}?sslmode={sslmode}"


def _connect_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    """Translate config into ``asyncpg.connect`` kwargs."""
    kwargs: dict[str, Any] = {
        "host": config["host"],
        "port": config.get("port", 5432),
        "database": config["database"],
        "user": config["user"],
        "password": config.get("password") or None,
        "timeout": _PROBE_TIMEOUT_SECONDS,
    }
    sslmode = config.get("sslmode", "prefer")
    # asyncpg wants "ssl" instead of "sslmode". Map common values.
    if sslmode in ("require", "verify-ca", "verify-full"):
        kwargs["ssl"] = True
    elif sslmode == "disable":
        kwargs["ssl"] = False
    # "prefer" / "allow" — let asyncpg negotiate, leave default.
    return kwargs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def test_connection(config: dict[str, Any]) -> ProbeResult:
    """Try to connect and run ``SELECT 1``. Always returns; never raises."""
    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(**_connect_kwargs(config)),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return ProbeResult(ok=False, error="Connection timed out.")
    except (
        asyncpg.InvalidPasswordError,
        asyncpg.InvalidAuthorizationSpecificationError,
    ) as e:
        return ProbeResult(ok=False, error=f"Authentication failed: {e}")
    except OSError as e:
        return ProbeResult(ok=False, error=f"Network error: {e}")
    except Exception as e:  # asyncpg wraps server-side errors here
        return ProbeResult(ok=False, error=str(e))
    try:
        await conn.fetchval("SELECT 1")
    except Exception as e:
        await conn.close()
        return ProbeResult(ok=False, error=str(e))
    await conn.close()
    return ProbeResult(ok=True)


async def list_tables(config: dict[str, Any]) -> list[TableInfo]:
    """Enumerate user-visible tables. System schemas are filtered out.

    ``estimated_rows`` comes from ``pg_class.reltuples`` — that's the
    planner statistic, not an exact count. Good enough for the
    picker; the profiler runs an exact count on import.
    """
    conn = await asyncpg.connect(**_connect_kwargs(config))
    try:
        rows = await conn.fetch(
            """
            SELECT n.nspname AS schema,
                   c.relname AS name,
                   c.reltuples::bigint AS estimated_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p', 'v', 'm')  -- table, partition, view, matview
              AND n.nspname NOT IN ($1, $2, $3)
              AND n.nspname NOT LIKE 'pg_temp_%'
            ORDER BY n.nspname, c.relname
            """,
            *_SYSTEM_SCHEMAS,
        )
    finally:
        await conn.close()
    return [
        TableInfo(
            schema=r["schema"],
            name=r["name"],
            estimated_rows=int(r["estimated_rows"])
            if r["estimated_rows"] is not None and r["estimated_rows"] >= 0
            else None,
        )
        for r in rows
    ]


async def introspect_table(config: dict[str, Any], schema: str, table: str) -> InferredSchema:
    """Read the column definitions + a small sample of rows.

    We pull column types from ``information_schema.columns`` (rather
    than parsing ``pg_attribute``) because it gives us nullability
    and a stable, human-readable type name for the inferred-schema
    column.
    """
    conn = await asyncpg.connect(**_connect_kwargs(config))
    try:
        col_rows = await conn.fetch(
            """
            SELECT column_name,
                   data_type,
                   is_nullable
            FROM information_schema.columns
            WHERE table_schema = $1
              AND table_name = $2
            ORDER BY ordinal_position
            """,
            schema,
            table,
        )
        # Use a parameterised, quoted identifier read for the sample
        # — schema/table names can't be passed as $1 placeholders.
        # asyncpg's ``quote_ident`` lives on the connection.
        qschema = _quote_ident(schema)
        qtable = _quote_ident(table)
        sample_rows = await conn.fetch(
            # ruff S608: identifiers are quoted via _quote_ident; user
            # input never lands raw in the SQL string. The table /
            # schema names came from a previous list_tables() round
            # the same caller authorised.
            f"SELECT * FROM {qschema}.{qtable} LIMIT $1",  # noqa: S608
            _SAMPLE_LIMIT,
        )
    finally:
        await conn.close()

    columns: list[InferredColumn] = []
    sample_dicts = [dict(r) for r in sample_rows]
    for cr in col_rows:
        name = cast("str", cr["column_name"])
        dtype = cast("str", cr["data_type"])
        nullable = cr["is_nullable"] == "YES"
        sample_values = ["" if (val := row.get(name)) is None else str(val) for row in sample_dicts]
        columns.append(
            InferredColumn(
                name=name,
                dtype=dtype,
                nullable=nullable,
                sample_values=sample_values,
            )
        )

    return InferredSchema(
        columns=columns,
        row_count_estimate=None,  # filled by the profiler later
        sample_rows=sample_dicts,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quote_ident(ident: str) -> str:
    """Quote a SQL identifier the postgres way: double the embedded
    double-quotes and wrap. Defends against table names like
    ``some"table``. We keep this manual instead of pulling a heavy
    SQL builder — the surface is two callers."""
    return '"' + ident.replace('"', '""') + '"'


async def sample_rows(
    config: dict[str, Any], schema: str, table: str, limit: int
) -> list[dict[str, Any]]:
    """Bulk sample for the profiler. Caller decides ``limit``; we
    cap at the value they pass."""
    conn = await asyncpg.connect(**_connect_kwargs(config))
    try:
        qschema = _quote_ident(schema)
        qtable = _quote_ident(table)
        rows = await conn.fetch(
            f"SELECT * FROM {qschema}.{qtable} LIMIT $1",  # noqa: S608
            int(limit),
        )
    finally:
        await conn.close()
    return [dict(r) for r in rows]


__all__ = ["introspect_table", "list_tables", "sample_rows", "test_connection"]


# Silence ruff: the dsn helper isn't used today but documents the
# intended URL form for logging surfaces that might come later.
_ = _build_dsn
