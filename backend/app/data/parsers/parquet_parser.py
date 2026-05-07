"""Parquet schema inference. Same shape as ``csv_parser.infer_csv``.

Parquet is self-describing — types come from the file footer, no
heuristic — so the inference path is much shorter than CSV's.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data.parsers.common import InferredColumn, InferredSchema

_SAMPLE_ROW_COUNT = 5


def infer_parquet(path: Path | str) -> InferredSchema:
    path_obj = Path(path)
    schema = pl.scan_parquet(path_obj).collect_schema()
    sample_df = pl.read_parquet(path_obj, n_rows=_SAMPLE_ROW_COUNT)

    columns: list[InferredColumn] = []
    for name, dtype in schema.items():
        col = sample_df.get_column(name) if name in sample_df.columns else None
        sample_values = (
            [str(v) if v is not None else "" for v in col.to_list()] if col is not None else []
        )
        columns.append(
            InferredColumn(
                name=name,
                dtype=str(dtype),
                nullable=bool(col.null_count()) if col is not None else True,
                sample_values=sample_values,
            )
        )
    return InferredSchema(
        columns=columns,
        row_count_estimate=None,
        sample_rows=sample_df.to_dicts(),
    )


__all__ = ["infer_parquet"]
