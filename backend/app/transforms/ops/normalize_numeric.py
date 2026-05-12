"""``normalize_numeric`` — coerce text-shaped numbers into real numerics.

Handles the everyday business-data cases:

* ``"1,234.56"`` (US thousands) → ``1234.56``
* ``"1.234,56"`` (EU thousands) → ``1234.56``
* ``"$ 1,200"`` → ``1200`` (strips a leading currency symbol)
* ``"45%"``     → ``45`` (strips a trailing percent sign; agent decides
  whether to divide by 100 — defaults to leaving the integer alone)

Args
----

``columns: list[str]`` (required)
``decimal: "auto" | "." | ","`` (default ``"auto"``)
    Auto-detection picks the rarer character as the decimal mark per
    column. Override when you know the locale.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl

from app.transforms.types import OperationError, OperationResult

# Strip everything that isn't a digit, decimal mark, or sign. The
# decision of which of ``,`` and ``.`` is the decimal is made per-column
# *before* this strip — see ``_detect_decimal``.
_NON_NUMERIC_RE = re.compile(r"[^0-9eE+\-.,]")


def _detect_decimal(values: list[str]) -> str:
    """Pick the rarer of ``,`` and ``.`` per column.

    Reasoning: in "1,234.56" the comma is the thousands separator
    (frequent) and the dot is the decimal (rare). Inverting works for
    EU-style "1.234,56".
    """
    commas = sum(v.count(",") for v in values)
    dots = sum(v.count(".") for v in values)
    if commas == 0:
        return "."
    if dots == 0:
        return ","
    return "." if dots <= commas else ","


def _coerce(value: str, decimal: str) -> float | None:
    s = _NON_NUMERIC_RE.sub("", value)
    if not s:
        return None
    # ``decimal == ","`` (EU-style "1.234,56"): drop the dots (thousands)
    # then promote the comma to a decimal point. Otherwise the US-style
    # path just removes thousands-commas and leaves the dot as decimal.
    s = (
        s.replace(".", "").replace(",", ".")
        if decimal == ","
        else s.replace(",", "")
    )
    try:
        return float(s)
    except ValueError:
        return None


def normalize_numeric(frame: pl.DataFrame, args: dict[str, Any]) -> OperationResult:
    cols = args.get("columns")
    if not isinstance(cols, list) or not cols:
        raise OperationError("normalize_numeric necesita al menos una columna en 'columns'.")
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise OperationError(f"Estas columnas no existen: {', '.join(missing)}.")

    decimal_arg = args.get("decimal", "auto")
    if decimal_arg not in ("auto", ".", ","):
        raise OperationError("'decimal' debe ser 'auto', '.' o ','.")

    per_column: list[dict[str, Any]] = []
    new_frame = frame
    for col in cols:
        series = frame[col]
        if series.dtype.is_numeric():
            per_column.append(
                {
                    "column": col,
                    "skipped": True,
                    "reason": "ya numérica",
                    "converted_count": 0,
                    "failed_count": 0,
                }
            )
            continue
        if series.dtype != pl.Utf8:
            per_column.append(
                {
                    "column": col,
                    "skipped": True,
                    "reason": f"tipo no soportado ({series.dtype})",
                    "converted_count": 0,
                    "failed_count": 0,
                }
            )
            continue
        raw = [v for v in series.to_list() if isinstance(v, str)]
        if not raw:
            per_column.append(
                {
                    "column": col,
                    "skipped": True,
                    "reason": "sin valores",
                    "converted_count": 0,
                    "failed_count": 0,
                }
            )
            continue
        decimal = _detect_decimal(raw) if decimal_arg == "auto" else decimal_arg
        coerced = [
            (_coerce(v, decimal) if isinstance(v, str) else None)
            for v in series.to_list()
        ]
        raw_list = series.to_list()
        converted = sum(
            1
            for v, raw in zip(coerced, raw_list, strict=True)
            if v is not None and raw is not None
        )
        failed = sum(
            1
            for v, raw in zip(coerced, raw_list, strict=True)
            if v is None and isinstance(raw, str)
        )
        new_frame = new_frame.with_columns(
            pl.Series(name=col, values=coerced, dtype=pl.Float64)
        )
        per_column.append(
            {
                "column": col,
                "decimal": decimal,
                "converted_count": converted,
                "failed_count": failed,
                "skipped": False,
            }
        )

    summary = {
        "op": "normalize_numeric",
        "results": per_column,
        "rows_before": frame.height,
        "rows_after": new_frame.height,
    }
    viz: list[dict[str, Any]] = []
    if per_column:
        viz.append({"kind": "normalize_numeric_summary", "results": per_column})
    return OperationResult(frame=new_frame, summary=summary, visualizations=viz)


__all__ = ["normalize_numeric"]
