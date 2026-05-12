"""``fillna`` — handle null / missing values column-by-column.

Args
----

``columns: list[str]`` (optional)
    Columns to process. Omit for "all columns with nulls".
``strategy: "median" | "mean" | "mode" | "constant" | "drop_row"`` (default ``"auto"``)
    How to fill. ``"auto"`` picks median for numerics, mode for
    categoricals/text — the data-scientist default for "just clean it".
``constant: str | float | int | null``
    Required when ``strategy="constant"``. Used as the literal fill value.
``min_pct_to_drop: float`` (default ``0.5``)
    When ``strategy="drop_row"``, a row is dropped only if at least this
    fraction of its columns are null. Conservative by default.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from app.transforms.types import OperationError, OperationResult


def _auto_strategy_for(series: pl.Series) -> str:
    return "median" if series.dtype.is_numeric() else "mode"


def _fill_value(series: pl.Series, strategy: str, constant: Any) -> Any:
    non_null = series.drop_nulls()
    if non_null.len() == 0:
        return constant if strategy == "constant" else None
    if strategy == "median":
        if not series.dtype.is_numeric():
            return non_null.mode().first()
        return non_null.median()
    if strategy == "mean":
        if not series.dtype.is_numeric():
            return non_null.mode().first()
        return float(non_null.mean())  # type: ignore[arg-type]
    if strategy == "mode":
        return non_null.mode().first()
    if strategy == "constant":
        return constant
    raise OperationError(f"Estrategia desconocida: {strategy}")


def fillna(frame: pl.DataFrame, args: dict[str, Any]) -> OperationResult:
    requested_cols = args.get("columns")
    strategy = args.get("strategy", "auto")
    constant = args.get("constant")
    min_pct_to_drop = float(args.get("min_pct_to_drop", 0.5))

    if requested_cols is not None and (
        not isinstance(requested_cols, list) or not requested_cols
    ):
        raise OperationError(
            "'columns' debe ser una lista de nombres (o se omite para auto-detectar)."
        )

    # Auto-detect columns with nulls when the agent doesn't pass any.
    if requested_cols is None:
        cols = [c for c in frame.columns if frame[c].null_count() > 0]
    else:
        missing = [c for c in requested_cols if c not in frame.columns]
        if missing:
            raise OperationError(
                f"Estas columnas no existen: {', '.join(missing)}."
            )
        cols = list(requested_cols)

    if not cols:
        return OperationResult(
            frame=frame,
            summary={
                "op": "fillna",
                "strategy": strategy,
                "filled": [],
                "rows_before": frame.height,
                "rows_after": frame.height,
            },
            visualizations=[],
        )

    rows_before = frame.height

    if strategy == "drop_row":
        # Compute null density per row and drop the very-empty ones.
        null_mask = frame.select(
            [pl.col(c).is_null().alias(c) for c in cols]
        )
        null_count_per_row = null_mask.select(pl.sum_horizontal(pl.all())).to_series()
        threshold = max(1, round(min_pct_to_drop * len(cols)))
        keep_mask = null_count_per_row < threshold
        new_frame = frame.filter(keep_mask)
        drop_summary = {
            "op": "fillna",
            "strategy": "drop_row",
            "columns_considered": cols,
            "min_pct_to_drop": min_pct_to_drop,
            "rows_before": rows_before,
            "rows_after": new_frame.height,
            "removed": rows_before - new_frame.height,
        }
        drop_viz: list[dict[str, Any]] = [
            {
                "kind": "before_after",
                "label": "Filas",
                "before": rows_before,
                "after": new_frame.height,
                "delta_label": f"-{rows_before - new_frame.height}"
                if rows_before > new_frame.height
                else "0",
                "tone": "warning"
                if (rows_before - new_frame.height) / max(rows_before, 1) > 0.1
                else "positive",
            }
        ]
        return OperationResult(frame=new_frame, summary=drop_summary, visualizations=drop_viz)

    # Per-column fill — auto picks median for numeric, mode for text.
    per_column: list[dict[str, Any]] = []
    new_frame = frame
    for col in cols:
        series = frame[col]
        nulls = series.null_count()
        if nulls == 0:
            continue
        effective_strategy = (
            _auto_strategy_for(series) if strategy == "auto" else strategy
        )
        value = _fill_value(series, effective_strategy, constant)
        if value is None:
            # Column was all-null; skip.
            continue
        new_frame = new_frame.with_columns(pl.col(col).fill_null(value).alias(col))
        per_column.append(
            {
                "column": col,
                "strategy": effective_strategy,
                "value": str(value),
                "filled_count": int(nulls),
            }
        )

    total_filled = sum(int(c["filled_count"]) for c in per_column)
    summary = {
        "op": "fillna",
        "strategy": strategy,
        "filled": per_column,
        "total_filled": total_filled,
        "rows_before": rows_before,
        "rows_after": new_frame.height,
    }
    # One stacked-summary viz so the chat shows what got filled per column.
    viz: list[dict[str, Any]] = []
    if per_column:
        viz.append(
            {
                "kind": "fillna_summary",
                "filled": per_column,
                "total_filled": total_filled,
            }
        )
    return OperationResult(frame=new_frame, summary=summary, visualizations=viz)


__all__ = ["fillna"]
