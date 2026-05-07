"""Excel (xlsx) schema inference.

Polars uses the ``fastexcel`` engine under the hood. xlsx files
have *sheets* — for slice B we pick the first sheet by default.
The locator stores the sheet name so a future iteration can let
the user pick.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data.parsers.common import InferredColumn, InferredSchema

_SAMPLE_ROW_COUNT = 5


def list_sheets(path: Path | str) -> list[str]:
    """Return all sheet names in the workbook. The first row is ours
    by default in ``infer_xlsx``."""
    df_map = pl.read_excel(path, sheet_id=0)  # 0 == all sheets, returns dict
    if isinstance(df_map, dict):
        return list(df_map.keys())
    return ["Sheet1"]


def infer_xlsx(path: Path | str, sheet: str | None = None) -> tuple[InferredSchema, str]:
    """Infer the schema of one sheet. Returns the schema *and* the
    sheet name actually read (for the dataset locator)."""
    path_obj = Path(path)
    if sheet is None:
        sheets = list_sheets(path_obj)
        sheet = sheets[0] if sheets else "Sheet1"

    df = pl.read_excel(path_obj, sheet_name=sheet)
    sample_df = df.head(_SAMPLE_ROW_COUNT)

    columns: list[InferredColumn] = []
    for name, dtype in df.schema.items():
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
    return (
        InferredSchema(
            columns=columns,
            row_count_estimate=int(df.height),  # xlsx is small enough to count
            sample_rows=sample_df.to_dicts(),
        ),
        sheet,
    )


__all__ = ["infer_xlsx", "list_sheets"]
