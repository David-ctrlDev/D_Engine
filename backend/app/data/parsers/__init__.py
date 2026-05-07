"""File parsers (csv, parquet, xlsx) wrapped behind a small interface.

Each parser is a free function ``infer_schema(path) -> InferredSchema``
plus an optional sample reader. The service layer picks the parser by
:class:`app.data.models.DataSourceKind`. Keeping each format in its
own module means polars-specific quirks (xlsx engines, parquet types)
don't leak.
"""
