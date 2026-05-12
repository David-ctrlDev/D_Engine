"""Operation dispatcher + base types.

Operations are pure functions over a polars DataFrame plus an args
dict. They return an :class:`OperationResult` with the new frame, a
result-summary dict, and a list of viz specs. The summary + visuals
flow back into the chat so the user sees what happened.

Adding a new operation
----------------------

1. Write a function in :mod:`app.transforms.ops` that takes
   ``(frame: pl.DataFrame, args: dict)`` and returns an
   ``OperationResult``.
2. Register it in :data:`_REGISTRY` below.
3. Add a tool definition in :mod:`app.agent.tools` so the LLM can
   propose it.

That's it — the migration doesn't need to change, because ``op`` and
``args`` are stored as strings + JSONB.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import polars as pl

from app.transforms.ops import dedupe as _dedupe_op
from app.transforms.ops import inspect as _inspect_op
from app.transforms.types import (
    OperationError,
    OperationResult,
    UnknownOperationError,
)

_OpFn = Callable[[pl.DataFrame, dict[str, Any]], OperationResult]


# Read-only inspections — never write to the working copy.
_INSPECT_REGISTRY: dict[str, _OpFn] = {
    "inspect_column": cast("_OpFn", _inspect_op.inspect_column),
    "preview_duplicates": cast("_OpFn", _inspect_op.preview_duplicates),
}

# Mutating operations — produce a new snapshot.
_MUTATE_REGISTRY: dict[str, _OpFn] = {
    "dedupe": cast("_OpFn", _dedupe_op.dedupe),
}


def is_mutating(op: str) -> bool:
    return op in _MUTATE_REGISTRY


def apply_operation(op: str, args: dict[str, Any], *, frame: pl.DataFrame) -> OperationResult:
    """Look up the op and execute it. Raises :class:`OperationError`
    on bad args / missing columns; :class:`UnknownOperationError` if
    the name isn't registered."""
    fn = _MUTATE_REGISTRY.get(op) or _INSPECT_REGISTRY.get(op)
    if fn is None:
        raise UnknownOperationError(op)
    return fn(frame, args)


__all__ = [
    "OperationError",
    "OperationResult",
    "UnknownOperationError",
    "apply_operation",
    "is_mutating",
]
