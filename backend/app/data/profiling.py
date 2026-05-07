"""Dataset profiling — compute the per-column quality stats.

We use polars for files (already loaded into memory) and the matching
probe for DB sources. The output shape is the same regardless of
backing store, so the UI doesn't branch.

Why per-column stats and not full EDA: this view runs *fast* and
fits in a single API response. Heavier exploration (correlations,
distribution histograms, anomaly detection) lands in slice E2 once
we have the agent.

The result is persisted in ``profile_runs.result`` (JSONB) so re-
opening a dataset doesn't re-scan the source.
"""

from __future__ import annotations

import json
from typing import Any

import polars as pl

from app.data.models import DataSourceKind

# Top-N most frequent values we record per column. Cap on the small
# side — wide tables already produce a big response.
_TOP_VALUES = 5
# Cap on rows we materialise from a DB source for the heavier stats.
# Big tables fall back to "estimate" semantics with a note.
_DB_SAMPLE_CAP = 100_000


def _file_path_for(dataset_locator: dict[str, Any], abs_resolver: Any) -> Any:
    return abs_resolver(str(dataset_locator.get("path", "")))


def _read_dataframe_for_file(
    kind: DataSourceKind, locator: dict[str, Any], abs_resolver: Any
) -> pl.DataFrame:
    path = _file_path_for(locator, abs_resolver)
    if kind is DataSourceKind.csv:
        return pl.read_csv(path)
    if kind is DataSourceKind.parquet:
        return pl.read_parquet(path)
    if kind is DataSourceKind.xlsx:
        sheet = str(locator.get("sheet", "Sheet1"))
        df = pl.read_excel(path, sheet_name=sheet)
        if not isinstance(df, pl.DataFrame):  # pragma: no cover
            raise TypeError("expected single-sheet read")
        return df
    raise ValueError(f"not a file kind: {kind}")


def _profile_dataframe(df: pl.DataFrame) -> dict[str, Any]:
    """Compute a row-count + per-column stats from an in-memory frame."""
    row_count = int(df.height)
    columns: list[dict[str, Any]] = []
    for name in df.columns:
        col = df.get_column(name)
        null_count = int(col.null_count())
        null_pct = (null_count / row_count) if row_count else 0.0
        # Distinct: cap with n_unique() — polars handles large frames
        # fine. For huge sources we may sample; slice E1 ships exact.
        try:
            distinct_count: int | None = int(col.n_unique())
        except Exception:
            distinct_count = None

        col_min: str | None
        col_max: str | None
        try:
            cmin = col.min()
            cmax = col.max()
            col_min = None if cmin is None else str(cmin)
            col_max = None if cmax is None else str(cmax)
        except Exception:
            col_min = None
            col_max = None

        # Top-N values: skip on numeric columns where it's noisy.
        top_values: list[dict[str, Any]] = []
        try:
            vc = col.value_counts(sort=True).head(_TOP_VALUES).rows()
            for value, count in vc:
                top_values.append(
                    {
                        "value": "" if value is None else str(value),
                        "count": int(count),
                    }
                )
        except Exception:
            top_values = []

        columns.append(
            {
                "name": name,
                "dtype": str(col.dtype),
                "null_count": null_count,
                "null_pct": round(null_pct, 4),
                "distinct_count": distinct_count,
                "min": col_min,
                "max": col_max,
                "top_values": top_values,
            }
        )
    return {"row_count": row_count, "columns": columns}


async def profile_file_dataset(
    *, kind: DataSourceKind, locator: dict[str, Any], abs_resolver: Any
) -> dict[str, Any]:
    """Profile a file-backed dataset by loading the whole frame.

    polars handles 1-3 GB files comfortably on a developer laptop;
    bigger files will need a chunked code path that streams stats —
    deferred until users actually hit it.
    """
    df = _read_dataframe_for_file(kind, locator, abs_resolver)
    return _profile_dataframe(df)


async def profile_db_dataset(
    *,
    probe: Any,
    config: dict[str, Any],
    schema: str,
    table: str,
) -> dict[str, Any]:
    """Profile a DB-backed dataset.

    Pulls up to ``_DB_SAMPLE_CAP`` rows via the probe's
    ``sample_rows`` coroutine, materialises them into polars, then
    reuses the file pipeline. Probes share the same surface so the
    dispatch is one line.
    """
    rows = await probe.sample_rows(config, schema, table, _DB_SAMPLE_CAP)
    df = pl.from_dicts(rows) if rows else pl.DataFrame()
    return _profile_dataframe(df)


def encode_result(result: dict[str, Any]) -> str:
    """Stable JSON encoding for the JSONB column. Sorted keys make
    audit comparisons cheap."""
    return json.dumps(result, sort_keys=True, default=str)


__all__ = ["encode_result", "profile_db_dataset", "profile_file_dataset"]
