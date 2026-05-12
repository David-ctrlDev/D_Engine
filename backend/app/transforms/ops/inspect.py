"""Read-only inspections.

The agent calls these to *see* the data before proposing a mutation
to the user. They never write anything; they return a summary + a
viz spec the chat can render.

* :func:`inspect_column` — value distribution: histogram for numeric
  columns, top-N value counts for categorical/text, null pct.
* :func:`preview_duplicates` — find rows that would collapse if a
  given column (or columns) were used as a dedupe key.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from app.transforms.types import OperationError, OperationResult

# Caps so the agent (and the chat) never receive megabytes of stats.
_HISTOGRAM_BINS = 20
_TOP_N = 10
_PREVIEW_GROUPS = 8


def inspect_column(frame: pl.DataFrame, args: dict[str, Any]) -> OperationResult:
    """Return summary stats + a viz spec for one column."""
    name = args.get("column")
    if not isinstance(name, str) or name not in frame.columns:
        raise OperationError(f"La columna '{name}' no existe en el dataset.")
    series = frame[name]
    total = frame.height
    null_count = series.null_count()
    null_pct = (null_count / total) if total else 0.0

    summary: dict[str, Any] = {
        "op": "inspect_column",
        "column": name,
        "dtype": str(series.dtype),
        "total_rows": total,
        "null_count": int(null_count),
        "null_pct": float(null_pct),
    }
    visualizations: list[dict[str, Any]] = []

    if series.dtype.is_numeric():
        non_null = series.drop_nulls()
        if non_null.len() > 0:
            stats = {
                "min": float(non_null.min()) if non_null.len() else None,  # type: ignore[arg-type]
                "max": float(non_null.max()) if non_null.len() else None,  # type: ignore[arg-type]
                "mean": float(non_null.mean()) if non_null.len() else None,  # type: ignore[arg-type]
                "median": float(non_null.median()) if non_null.len() else None,  # type: ignore[arg-type]
            }
            summary["stats"] = stats
            # Build a fixed-width histogram. We deliberately bin
            # client-side-friendly: a list of {label, count} the chart
            # can render without doing any math itself.
            try:
                hist = non_null.hist(bin_count=_HISTOGRAM_BINS)
                bins = []
                # Polars hist() returns a DataFrame with breakpoint + count
                # columns. Schema varies a bit by version, so we hunt for
                # the count column tolerantly.
                count_col = "count" if "count" in hist.columns else hist.columns[-1]
                edge_col = next(
                    (c for c in hist.columns if "break" in c or "edge" in c),
                    hist.columns[0],
                )
                for row in hist.iter_rows(named=True):
                    bins.append(
                        {
                            "label": f"≤ {row[edge_col]:.2f}"
                            if isinstance(row[edge_col], int | float)
                            else str(row[edge_col]),
                            "count": int(row[count_col]),
                        }
                    )
                visualizations.append(
                    {
                        "kind": "histogram",
                        "column": name,
                        "bins": bins,
                    }
                )
            except Exception:  # noqa: S110 - polars version skew; never fail the call
                # Fall back to no histogram rather than failing the call.
                pass
    else:
        # Categorical / text: top-N value counts + a "rest" bucket.
        counts = series.drop_nulls().value_counts(sort=True).head(_TOP_N)
        # value_counts returns columns [name, "count"] in current polars
        items = []
        for row in counts.iter_rows(named=True):
            items.append(
                {
                    "value": str(row[name]) if row[name] is not None else "(vacío)",
                    "count": int(row["count"]),
                }
            )
        summary["top_values"] = items
        summary["distinct_count"] = int(series.n_unique())
        visualizations.append(
            {
                "kind": "value_counts",
                "column": name,
                "items": items,
            }
        )

    if null_pct > 0:
        visualizations.append(
            {
                "kind": "null_pct",
                "column": name,
                "null_count": int(null_count),
                "total": total,
                "null_pct": float(null_pct),
            }
        )

    return OperationResult(frame=None, summary=summary, visualizations=visualizations)


def preview_duplicates(frame: pl.DataFrame, args: dict[str, Any]) -> OperationResult:
    """Find duplicate groups by ``columns`` without removing anything.

    Returns up to :data:`_PREVIEW_GROUPS` example groups + the total
    number of duplicate rows that would be removed if the user
    accepted a dedupe with the same args.
    """
    cols = args.get("columns")
    if not isinstance(cols, list) or not cols:
        raise OperationError("preview_duplicates necesita al menos una columna.")
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise OperationError(f"Estas columnas no existen en el dataset: {', '.join(missing)}.")

    # Count occurrences per key tuple; keep only the duplicates.
    grouped = (
        frame.group_by(cols)
        .agg(pl.len().alias("__count__"))
        .filter(pl.col("__count__") > 1)
        .sort("__count__", descending=True)
    )
    duplicate_groups = int(grouped.height)
    total_duplicates = int((grouped["__count__"] - 1).sum()) if duplicate_groups else 0

    example_groups: list[dict[str, Any]] = []
    for row in grouped.head(_PREVIEW_GROUPS).iter_rows(named=True):
        example_groups.append(
            {
                "key": {c: (str(row[c]) if row[c] is not None else None) for c in cols},
                "count": int(row["__count__"]),
            }
        )

    summary = {
        "op": "preview_duplicates",
        "columns": cols,
        "total_rows": frame.height,
        "duplicate_groups": duplicate_groups,
        "total_duplicates": total_duplicates,
        "example_groups": example_groups,
    }
    visualizations: list[dict[str, Any]] = []
    if duplicate_groups > 0:
        visualizations.append(
            {
                "kind": "duplicate_preview",
                "columns": cols,
                "duplicate_groups": duplicate_groups,
                "total_duplicates": total_duplicates,
                "example_groups": example_groups,
            }
        )
    return OperationResult(frame=None, summary=summary, visualizations=visualizations)


__all__ = ["inspect_column", "preview_duplicates"]
