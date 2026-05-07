"""SQL Server probe — handles on-prem (``mssql``) and Azure SQL
(``mssql_azure``).

We use ``pyodbc`` (synchronous) wrapped in ``asyncio.to_thread`` so
the event loop never blocks. Long-term we could swap to ``aioodbc``
but it's a thin layer on top of pyodbc and adds little except a
threadpool the asyncio runtime would manage anyway.

ODBC driver
-----------

Both kinds use the Microsoft ODBC Driver 18 (``msodbcsql18``). The
operator must install it on the host that runs the worker; on Linux
this is ``apt-get install msodbcsql18``, on Windows the MSI from
microsoft.com. We check by attempting a connection — if the driver
is missing, pyodbc raises ``pyodbc.InterfaceError(IM002, ...)`` and
we surface the message verbatim.

Azure differences
-----------------

* Azure forces TLS — ``Encrypt=yes`` is mandatory; we set it
  unconditionally for ``mssql_azure``.
* Azure uses ``<server>.database.windows.net`` as the host.
* Azure SQL servers reject databases other than the one targeted in
  the DSN (no cross-DB queries), but introspection works the same.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pyodbc

from app.data.parsers.common import InferredColumn, InferredSchema
from app.data.probes import ProbeResult, TableInfo

_PROBE_TIMEOUT_SECONDS = 8.0
_SAMPLE_LIMIT = 5

# System schemas / databases we hide from the picker. Both on-prem
# and Azure expose these.
_SYSTEM_SCHEMAS = ("sys", "INFORMATION_SCHEMA", "guest")


def _build_dsn(config: dict[str, Any], *, azure: bool) -> str:
    """Build an ODBC connection string."""
    parts = [
        "Driver={ODBC Driver 18 for SQL Server}",
        f"Server={config['host']},{config.get('port', 1433)}",
        f"Database={config['database']}",
        f"Uid={config['user']}",
        f"Pwd={config.get('password', '')}",
    ]
    sslmode = config.get("sslmode", "require" if azure else "disable")
    if azure or sslmode in ("require", "verify-ca", "verify-full"):
        parts.append("Encrypt=yes")
        # Azure terminates TLS on a Microsoft-issued cert — no need
        # to verify the server cert chain by default. The "verify"
        # variants opt back in.
        if sslmode in ("require",) or (azure and sslmode == "require"):
            parts.append("TrustServerCertificate=yes")
        else:
            parts.append("TrustServerCertificate=no")
    else:
        parts.append("Encrypt=no")
    parts.append(f"Connection Timeout={int(_PROBE_TIMEOUT_SECONDS)}")
    return ";".join(parts)


def _connect_sync(config: dict[str, Any], *, azure: bool) -> pyodbc.Connection:
    return pyodbc.connect(_build_dsn(config, azure=azure), timeout=int(_PROBE_TIMEOUT_SECONDS))


async def _async_connect(config: dict[str, Any], *, azure: bool) -> pyodbc.Connection:
    return await asyncio.to_thread(_connect_sync, config, azure=azure)


# ---------------------------------------------------------------------------
# Probe entry points — match the postgres module signatures.
# The factory functions below produce closures we register in the
# service layer's ``_probe_for`` dispatch.
# ---------------------------------------------------------------------------


def _build_probe(*, azure: bool) -> Any:
    """Return an object exposing ``test_connection``, ``list_tables``,
    ``introspect_table`` for the given on-prem / Azure variant."""

    async def test_connection(config: dict[str, Any]) -> ProbeResult:
        try:
            conn = await _async_connect(config, azure=azure)
        except pyodbc.InterfaceError as e:
            return ProbeResult(ok=False, error=f"Driver / interface error: {e}")
        except pyodbc.OperationalError as e:
            return ProbeResult(ok=False, error=f"Operational error: {e}")
        except pyodbc.Error as e:
            return ProbeResult(ok=False, error=str(e))
        try:
            await asyncio.to_thread(_select_one, conn)
        except Exception as e:
            await asyncio.to_thread(conn.close)
            return ProbeResult(ok=False, error=str(e))
        await asyncio.to_thread(conn.close)
        return ProbeResult(ok=True)

    async def list_tables(config: dict[str, Any]) -> list[TableInfo]:
        conn = await _async_connect(config, azure=azure)
        try:
            rows = await asyncio.to_thread(_fetch_tables, conn)
        finally:
            await asyncio.to_thread(conn.close)
        return [
            TableInfo(
                schema=r[0],
                name=r[1],
                estimated_rows=int(r[2]) if r[2] is not None and r[2] >= 0 else None,
            )
            for r in rows
            if r[0] not in _SYSTEM_SCHEMAS
        ]

    async def sample_rows(
        config: dict[str, Any], schema: str, table: str, limit: int
    ) -> list[dict[str, Any]]:
        conn = await _async_connect(config, azure=azure)
        try:
            cols = await asyncio.to_thread(_fetch_columns, conn, schema, table)
            rows = await asyncio.to_thread(_fetch_sample_n, conn, schema, table, int(limit))
        finally:
            await asyncio.to_thread(conn.close)
        col_names = [c[0] for c in cols]
        return [dict(zip(col_names, row, strict=False)) for row in rows]

    async def introspect_table(config: dict[str, Any], schema: str, table: str) -> InferredSchema:
        conn = await _async_connect(config, azure=azure)
        try:
            cols = await asyncio.to_thread(_fetch_columns, conn, schema, table)
            sample = await asyncio.to_thread(_fetch_sample, conn, schema, table)
        finally:
            await asyncio.to_thread(conn.close)
        sample_dicts = [dict(zip([c[0] for c in cols], row, strict=False)) for row in sample]
        columns: list[InferredColumn] = []
        for c in cols:
            name, dtype, nullable = c[0], c[1], c[2]
            sample_values = [
                "" if (val := row.get(name)) is None else str(val) for row in sample_dicts
            ]
            columns.append(
                InferredColumn(
                    name=name,
                    dtype=dtype,
                    nullable=bool(nullable),
                    sample_values=sample_values,
                )
            )
        return InferredSchema(
            columns=columns,
            row_count_estimate=None,
            sample_rows=sample_dicts,
        )

    # Mimic a module surface: an object with the three coroutines.
    class _Probe:
        pass

    p = _Probe()
    p.test_connection = test_connection  # type: ignore[attr-defined]
    p.list_tables = list_tables  # type: ignore[attr-defined]
    p.introspect_table = introspect_table  # type: ignore[attr-defined]
    p.sample_rows = sample_rows  # type: ignore[attr-defined]
    return p


# ---------------------------------------------------------------------------
# Sync helpers — called via asyncio.to_thread.
# ---------------------------------------------------------------------------


def _select_one(conn: pyodbc.Connection) -> None:
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        cur.close()


def _fetch_tables(conn: pyodbc.Connection) -> list[tuple[str, str, int | None]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT s.name AS schema_name,
                   t.name AS table_name,
                   p.row_count AS estimated_rows
            FROM sys.tables t
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            LEFT JOIN (
                SELECT object_id, SUM(row_count) AS row_count
                FROM sys.dm_db_partition_stats
                WHERE index_id IN (0, 1)
                GROUP BY object_id
            ) p ON p.object_id = t.object_id
            ORDER BY s.name, t.name
            """
        )
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]
    finally:
        cur.close()


def _fetch_columns(conn: pyodbc.Connection, schema: str, table: str) -> list[tuple[str, str, bool]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT column_name, data_type,
                   CASE WHEN is_nullable = 'YES' THEN 1 ELSE 0 END
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position
            """,
            schema,
            table,
        )
        return [(r[0], r[1], bool(r[2])) for r in cur.fetchall()]
    finally:
        cur.close()


def _quote_ident(ident: str) -> str:
    return "[" + ident.replace("]", "]]") + "]"


def _fetch_sample(conn: pyodbc.Connection, schema: str, table: str) -> list[tuple[Any, ...]]:
    return _fetch_sample_n(conn, schema, table, _SAMPLE_LIMIT)


def _fetch_sample_n(
    conn: pyodbc.Connection, schema: str, table: str, limit: int
) -> list[tuple[Any, ...]]:
    cur = conn.cursor()
    try:
        # SQL Server uses TOP, not LIMIT. Identifiers are bracket-quoted.
        sql = (
            f"SELECT TOP {int(limit)} * "  # noqa: S608
            f"FROM {_quote_ident(schema)}.{_quote_ident(table)}"
        )
        cur.execute(sql)
        return [tuple(row) for row in cur.fetchall()]
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Module-level probe instances. The service's ``_probe_for`` returns
# these for the matching DataSourceKind.
# ---------------------------------------------------------------------------


mssql = _build_probe(azure=False)
mssql_azure = _build_probe(azure=True)


__all__ = ["mssql", "mssql_azure"]
