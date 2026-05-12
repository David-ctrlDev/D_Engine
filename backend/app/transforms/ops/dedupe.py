"""``dedupe`` — remove duplicate rows by one or more columns.

Args
----

``columns: list[str]`` (required)
    The columns to consider when deciding two rows are "the same".
``keep: "first" | "last"`` (default ``"first"``)
    Which row of each duplicate group to keep. ``"first"`` matches what
    most users expect when they say "elimina duplicados".
``normalize_text: bool`` (default ``False``)
    If true, applies a simple normalisation (lower + strip) before
    comparing — useful for emails like ``Juan@correo.com`` vs
    ``juan@correo.com``. The original casing stays in the kept row.

The op returns the deduped frame plus a summary the chat renders as
"antes: N filas → ahora: M filas (eliminé K duplicados)".
"""

from __future__ import annotations

from typing import Any

import polars as pl

from app.transforms.types import OperationError, OperationResult


def dedupe(frame: pl.DataFrame, args: dict[str, Any]) -> OperationResult:
    cols = args.get("columns")
    if not isinstance(cols, list) or not cols:
        raise OperationError("dedupe necesita al menos una columna en 'columns'.")
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise OperationError(f"Estas columnas no existen en el dataset: {', '.join(missing)}.")
    keep = args.get("keep", "first")
    if keep not in ("first", "last"):
        raise OperationError("'keep' debe ser 'first' o 'last'.")
    normalize_text = bool(args.get("normalize_text", False))

    rows_before = frame.height

    if normalize_text:
        # Create transient normalised columns just for the dedupe key,
        # then drop them. The original column values are preserved
        # exactly in whatever row survives.
        sentinel_cols: list[str] = []
        f = frame
        for col in cols:
            sentinel = f"__norm_{col}__"
            if f.schema[col] == pl.Utf8:
                f = f.with_columns(pl.col(col).str.strip_chars().str.to_lowercase().alias(sentinel))
            else:
                f = f.with_columns(pl.col(col).alias(sentinel))
            sentinel_cols.append(sentinel)
        f = f.unique(subset=sentinel_cols, keep=keep, maintain_order=True)
        new_frame = f.drop(sentinel_cols)
    else:
        new_frame = frame.unique(subset=cols, keep=keep, maintain_order=True)

    rows_after = new_frame.height
    removed = rows_before - rows_after

    summary = {
        "op": "dedupe",
        "columns": cols,
        "keep": keep,
        "normalize_text": normalize_text,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "removed": removed,
    }
    # A before/after bar comparison + a "what got removed" note —
    # both rendered inline in the chat.
    visualizations = [
        {
            "kind": "before_after",
            "label": "Filas",
            "before": rows_before,
            "after": rows_after,
            "delta_label": f"-{removed}" if removed else "0",
            "tone": "positive" if removed > 0 else "neutral",
        }
    ]
    return OperationResult(frame=new_frame, summary=summary, visualizations=visualizations)


__all__ = ["dedupe"]
