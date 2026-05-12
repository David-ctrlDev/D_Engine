"""``parse_dates`` — turn date-looking strings into proper datetime columns.

Args
----

``columns: list[str]`` (required)
``formats: list[str] | None``
    Optional candidate formats to try in order. Polars accepts strftime
    tokens. When omitted, we try a sensible default list that covers
    the common business shapes.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from app.transforms.types import OperationError, OperationResult

_DEFAULT_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
)


def parse_dates(frame: pl.DataFrame, args: dict[str, Any]) -> OperationResult:
    cols = args.get("columns")
    if not isinstance(cols, list) or not cols:
        raise OperationError("parse_dates necesita al menos una columna en 'columns'.")
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise OperationError(f"Estas columnas no existen: {', '.join(missing)}.")

    formats = args.get("formats") or list(_DEFAULT_FORMATS)
    if not isinstance(formats, list) or not formats:
        raise OperationError("'formats' debe ser una lista no vacía si se proporciona.")

    per_column: list[dict[str, Any]] = []
    new_frame = frame
    for col in cols:
        series = frame[col]
        if series.dtype != pl.Utf8:
            # Already parsed — skip.
            per_column.append(
                {
                    "column": col,
                    "matched_format": str(series.dtype),
                    "parsed_count": int(series.drop_nulls().len()),
                    "failed_count": 0,
                    "skipped": True,
                }
            )
            continue
        best_format: str | None = None
        best_parsed = 0
        best_series: pl.Series | None = None
        for fmt in formats:
            try:
                attempt = series.str.strptime(pl.Datetime, format=fmt, strict=False)
            except (pl.exceptions.ComputeError, ValueError):
                continue
            parsed = int(attempt.drop_nulls().len())
            if parsed > best_parsed:
                best_parsed = parsed
                best_format = fmt
                best_series = attempt
        non_null_total = int(series.drop_nulls().len())
        if best_series is None or best_parsed == 0:
            per_column.append(
                {
                    "column": col,
                    "matched_format": None,
                    "parsed_count": 0,
                    "failed_count": non_null_total,
                    "skipped": False,
                }
            )
            continue
        new_frame = new_frame.with_columns(best_series.alias(col))
        per_column.append(
            {
                "column": col,
                "matched_format": best_format,
                "parsed_count": best_parsed,
                "failed_count": max(0, non_null_total - best_parsed),
                "skipped": False,
            }
        )

    summary = {
        "op": "parse_dates",
        "results": per_column,
        "rows_before": frame.height,
        "rows_after": new_frame.height,
    }
    viz: list[dict[str, Any]] = []
    if per_column:
        viz.append({"kind": "parse_dates_summary", "results": per_column})
    return OperationResult(frame=new_frame, summary=summary, visualizations=viz)


__all__ = ["parse_dates"]
