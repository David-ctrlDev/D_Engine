"""FastAPI dependencies specific to the data domain.

We expose the :class:`LocalFileStorage` instance as a dependency so
tests can override it with a tmp_path-backed fixture without touching
the real ``var/uploads`` tree.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import settings
from app.data.storage import LocalFileStorage


@lru_cache(maxsize=1)
def _storage_singleton() -> LocalFileStorage:
    return LocalFileStorage(
        settings.file_storage_root,
        max_bytes=settings.file_upload_max_bytes,
    )


def get_storage() -> LocalFileStorage:
    return _storage_singleton()


StorageDep = Annotated[LocalFileStorage, Depends(get_storage)]


__all__ = ["StorageDep", "get_storage"]
