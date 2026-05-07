"""CSV schema inference.

We use ``polars.scan_csv`` for the type detection pass — it streams
the file rather than materialising it — and ``read_csv`` with
``n_rows`` for the sample. Polars' inference is good enough for the
heuristic we need today; we revisit if users start seeing wrong types
on real files.

Sample rows are converted to plain Python (lists of dicts) because
the result is going straight into a JSON HTTP response.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data.parsers.common import InferredColumn, InferredSchema

# How many rows polars looks at to guess each column's type. Higher is
# more accurate on heterogeneous files; lower is faster. 10 000 hits a
# reasonable point for the kinds of files non-technical users upload.
_INFER_SCHEMA_LENGTH = 10_000

# Sample rows we hand back to the UI in the create response. Kept small
# on purpose — the dataset detail endpoint can return more.
_SAMPLE_ROW_COUNT = 5


def infer_csv(path: Path | str) -> InferredSchema:
    """Read the head of a CSV and infer its schema.

    Raises ``polars.exceptions.ComputeError`` (or one of its
    subclasses) on malformed files; the caller maps that to a 422.
    """
    path_obj = Path(path)

    # Pass 1 — schema only. ``collect_schema`` evaluates the lazy
    # frame's schema without materialising rows.
    lazy = pl.scan_csv(path_obj, infer_schema_length=_INFER_SCHEMA_LENGTH)
    schema = lazy.collect_schema()

    # Pass 2 — N rows for the sample. ``read_csv`` is eager but capped
    # at ``n_rows``, so memory is bounded.
    sample_df = pl.read_csv(
        path_obj,
        n_rows=_SAMPLE_ROW_COUNT,
        infer_schema_length=_INFER_SCHEMA_LENGTH,
    )

    columns: list[InferredColumn] = []
    for name, dtype in schema.items():
        col_series = sample_df.get_column(name) if name in sample_df.columns else None
        sample_values = (
            [str(v) if v is not None else "" for v in col_series.to_list()]
            if col_series is not None
            else []
        )
        nullable = bool(col_series.null_count()) if col_series is not None else True
        columns.append(
            InferredColumn(
                name=name,
                dtype=str(dtype),
                nullable=nullable,
                sample_values=sample_values,
            )
        )

    # We don't pay for a full row-count scan here — it's an estimate,
    # the profiler will compute the exact figure later. ``None`` keeps
    # the UI honest about what it knows.
    sample_rows = sample_df.to_dicts()

    return InferredSchema(
        columns=columns,
        row_count_estimate=None,
        sample_rows=sample_rows,
    )


__all__ = ["infer_csv"]
