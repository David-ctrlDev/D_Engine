"""``normalize_text`` — fix common text-quality issues column-by-column.

The agent reaches for this whenever a column mixes "España" / "españa" /
"ESPAÑA", or has stray leading/trailing spaces, or non-ASCII variants
("á" vs "a") that block downstream group-bys.

Args
----

``columns: list[str]`` (required)
``case: "lower" | "upper" | "title" | "preserve"`` (default ``"title"``)
    Casing to apply. ``"preserve"`` keeps the original casing and only
    fixes whitespace / accents.
``strip: bool`` (default ``True``)
    Strip leading/trailing whitespace.
``collapse_spaces: bool`` (default ``True``)
    Collapse multiple internal spaces into one.
``remove_accents: bool`` (default ``False``)
    Strip diacritics ("á" → "a"). Off by default — Spanish content often
    needs accents preserved.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import polars as pl

from app.transforms.types import OperationError, OperationResult


def _strip_accents(s: str) -> str:
    if s is None:
        return s
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_text(frame: pl.DataFrame, args: dict[str, Any]) -> OperationResult:
    cols = args.get("columns")
    if not isinstance(cols, list) or not cols:
        raise OperationError("normalize_text necesita al menos una columna en 'columns'.")
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise OperationError(f"Estas columnas no existen: {', '.join(missing)}.")

    case = args.get("case", "title")
    if case not in ("lower", "upper", "title", "preserve"):
        raise OperationError("'case' debe ser 'lower', 'upper', 'title' o 'preserve'.")
    strip = bool(args.get("strip", True))
    collapse_spaces = bool(args.get("collapse_spaces", True))
    remove_accents = bool(args.get("remove_accents", False))

    rows_before = frame.height
    per_column: list[dict[str, Any]] = []
    new_frame = frame

    for col in cols:
        if frame[col].dtype != pl.Utf8:
            # Silently skip — the agent sometimes asks for non-text
            # columns; better to no-op than fail the whole call.
            continue
        before_unique = int(frame[col].n_unique())
        series = pl.col(col)
        if strip:
            series = series.str.strip_chars()
        if collapse_spaces:
            series = series.str.replace_all(r"\s+", " ")
        if case == "lower":
            series = series.str.to_lowercase()
        elif case == "upper":
            series = series.str.to_uppercase()
        elif case == "title":
            series = series.str.to_titlecase()
        new_frame = new_frame.with_columns(series.alias(col))
        if remove_accents:
            # Polars doesn't have a built-in unaccent; map in Python.
            new_frame = new_frame.with_columns(
                pl.col(col)
                .map_elements(
                    lambda v: _strip_accents(v) if isinstance(v, str) else v,
                    return_dtype=pl.Utf8,
                )
                .alias(col)
            )
        after_unique = int(new_frame[col].n_unique())
        per_column.append(
            {
                "column": col,
                "case": case,
                "strip": strip,
                "collapse_spaces": collapse_spaces,
                "remove_accents": remove_accents,
                "distinct_before": before_unique,
                "distinct_after": after_unique,
                "collapsed_variants": max(0, before_unique - after_unique),
            }
        )

    summary = {
        "op": "normalize_text",
        "applied": per_column,
        "rows_before": rows_before,
        "rows_after": new_frame.height,
    }
    viz: list[dict[str, Any]] = []
    if per_column:
        viz.append(
            {
                "kind": "normalize_text_summary",
                "applied": per_column,
            }
        )
    return OperationResult(frame=new_frame, summary=summary, visualizations=viz)


__all__ = ["normalize_text"]
