"""Domain errors for the data layer.

Mirrors the auth layer's pattern: each error subclasses a single
``DataError`` so the router can map them to HTTP statuses in one
``except`` block. Keeping the mapping out of the service means the
service stays HTTP-agnostic and is easy to call from background
workers later.
"""

from __future__ import annotations


class DataError(Exception):
    """Root for all data-domain failures."""


class DuplicateNameError(DataError):
    """A source or dataset with that name already exists in the tenant."""


class InvalidFileError(DataError):
    """The upload couldn't be parsed (corrupt, wrong format, empty)."""


class UnsupportedSourceKindError(DataError):
    """The route was hit with a kind we haven't wired up yet."""


class DatasetNotFoundError(DataError):
    """Dataset doesn't exist or is invisible to the caller (RLS)."""


__all__ = [
    "DataError",
    "DatasetNotFoundError",
    "DuplicateNameError",
    "InvalidFileError",
    "UnsupportedSourceKindError",
]
