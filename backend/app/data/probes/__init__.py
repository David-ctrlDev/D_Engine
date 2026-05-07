"""Probes — connectors that talk to live data sources.

Each probe exposes the same minimal surface so the service layer
treats them interchangeably:

* :func:`test_connection` — open a connection, run a no-op query,
  return ``ProbeResult`` (status + optional error).
* :func:`list_tables` — enumerate user-visible tables. Returns plain
  ``TableInfo`` records that the frontend renders in a picker.
* :func:`introspect_table` — fetch column names + types for one
  table, in the same :class:`InferredSchema` shape the file parsers
  return.

Slice C wires postgres only. mssql / mssql_azure (slice D) reuse
the same interface from a separate module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Outcome of a connection test. Carries an error string when
    ``ok is False`` — the frontend surfaces it verbatim so a typo'd
    DSN gives the user the postgres error directly."""

    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TableInfo:
    """One row in the table picker. Estimates only — exact counts come
    from a profile run."""

    schema: str
    name: str
    estimated_rows: int | None


__all__ = ["ProbeResult", "TableInfo"]
