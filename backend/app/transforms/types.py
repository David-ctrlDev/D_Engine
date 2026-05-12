"""Shared types for the transformation engine.

Lives outside :mod:`dispatcher` and :mod:`ops` so both can import it
without a cycle. The dispatcher imports ops modules at top-level (to
register them), and each op imports ``OperationError`` /
``OperationResult`` for its return type — that's the cycle we sidestep.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl


class OperationError(Exception):
    """A transform op failed (bad args, column missing, etc.).

    The caller — agent service — maps this to a chat message back to
    the LLM ("the operation you proposed didn't work because…") so
    the agent can either retry with different args or apologize.
    """


class UnknownOperationError(OperationError):
    """The op name isn't in the registry."""


@dataclass(frozen=True, slots=True)
class OperationResult:
    """What an op returns.

    * ``frame`` — the post-op DataFrame (or ``None`` for read-only
      inspections that don't mutate the working copy).
    * ``summary`` — a JSON-serialisable dict the chat renders as a
      "what happened" card (e.g. ``{"removed_rows": 3, "kept": 1244}``).
    * ``visualizations`` — typed viz specs the chat renders inline
      (histograms, before/after bars, value-count pies).
    """

    frame: pl.DataFrame | None
    summary: dict[str, Any]
    visualizations: list[dict[str, Any]]


__all__ = ["OperationError", "OperationResult", "UnknownOperationError"]
