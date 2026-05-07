"""Shared types for all file parsers.

We deliberately keep these types small and JSON-friendly: they are
serialised straight into ``Dataset.inferred_schema`` (a JSONB column),
returned from the API to the frontend, and (later) handed to the LLM
as part of the agent prompt. Pydantic models would also work but plain
dicts keep the schema column human-readable in psql.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InferredColumn:
    """A single column's inferred type and a couple of sample values.

    ``dtype`` is the polars type name (``"String"``, ``"Int64"``,
    ``"Float64"``, ``"Datetime"`` …). We pass it through verbatim
    because the frontend already understands the polars vocabulary
    after the user uploads their first file — keeping it stable means
    we don't have to re-translate when we add parquet / xlsx.
    """

    name: str
    dtype: str
    nullable: bool
    sample_values: list[str]


@dataclass(frozen=True, slots=True)
class InferredSchema:
    """The output of every parser: the per-column types plus a couple
    of dataset-level numbers the UI shows up front."""

    columns: list[InferredColumn]
    row_count_estimate: int | None
    sample_rows: list[dict[str, Any]]

    def to_jsonb(self) -> dict[str, Any]:
        """JSON-friendly form for ``Dataset.inferred_schema``.

        ``dataclasses.asdict`` does the right thing recursively for
        ``InferredColumn``. We don't include ``sample_rows`` in the
        JSONB column today — they can be large and we only need them
        for the immediate API response — but the field is here so we
        can opt in later without a migration.
        """
        return {
            "columns": [asdict(c) for c in self.columns],
            "row_count_estimate": self.row_count_estimate,
        }


__all__ = ["InferredColumn", "InferredSchema"]
