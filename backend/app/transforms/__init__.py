"""Dataset transformation engine.

The agent's tool-use endpoints land here. Each operation is a pure
function over a polars ``LazyFrame`` plus its args, returning a new
LazyFrame and a result-summary dict the chat can render.

For the first slice we ship two surfaces:

* :func:`preview_duplicates` — read-only inspection. The agent calls
  it to "see" what would happen before proposing a dedupe to the user.
* :func:`dedupe` — the actual mutating operation.

More operations land in :mod:`app.transforms.ops` as their own
modules; the dispatcher in :mod:`.dispatcher` routes by op name.
"""

from app.transforms.dispatcher import (
    OperationError,
    OperationResult,
    UnknownOperationError,
    apply_operation,
)
from app.transforms.models import DatasetOperation, DatasetWorkingCopy

__all__ = [
    "DatasetOperation",
    "DatasetWorkingCopy",
    "OperationError",
    "OperationResult",
    "UnknownOperationError",
    "apply_operation",
]
