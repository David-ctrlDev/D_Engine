"""Local file storage for uploaded datasets.

This module is the only place in the app that writes to disk. The
:class:`LocalFileStorage` API is intentionally narrow so we can swap
the backing store (S3, Azure Blob, GCS) without touching callers.

Layout on disk
--------------

::

    {root}/
        {tenant_id}/
            {dataset_uuid}_{safe_filename}

We never let the original filename influence the on-disk path beyond
its sanitised tail — the leading UUID guarantees uniqueness and the
sanitisation strips everything but ``[A-Za-z0-9._-]`` so a malicious
upload can't escape the tenant directory or collide with other rows.

Streaming I/O
-------------

Files can be much larger than RAM, so we hash and write in 1 MiB
chunks. The hash is computed during the write — there is no second
pass to read the file back.

Errors
------

* :class:`StorageError` — any failure rolling up to a single type so
  callers can branch with a single ``except``.
* The ``size_bytes`` returned by :meth:`save` is the *actual* number
  of bytes written; the caller is expected to enforce a maximum size
  (the FastAPI router uses ``settings.file_upload_max_bytes``).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class StorageError(Exception):
    """Any disk-side failure during save / read."""


class FileTooLargeError(StorageError):
    """Raised when an upload exceeds the configured byte cap."""


@dataclass(frozen=True, slots=True)
class StoredFile:
    """The result of a successful :meth:`LocalFileStorage.save` call."""

    path: str
    sha256: str
    size_bytes: int
    original_filename: str


def _sanitise_filename(name: str) -> str:
    """Strip everything but ``[A-Za-z0-9._-]``.

    Empty input or input that sanitises down to nothing falls back to
    ``upload`` so we always have a non-empty tail. We also forbid
    leading dots to avoid ``..`` or ``.hidden`` payloads.
    """
    cleaned = _SAFE_NAME_RE.sub("_", name).lstrip(".")
    return cleaned or "upload"


class LocalFileStorage:
    """Filesystem-backed implementation. Tenant-scoped paths.

    Construction is cheap; reuse a single instance for the app's
    lifetime. The root directory is created lazily on first ``save``.
    """

    def __init__(self, root: str | Path, *, max_bytes: int) -> None:
        self._root = Path(root).resolve()
        self._max_bytes = max_bytes

    # ------------------------------------------------------------------
    # Path helpers — kept private. Callers never get a raw Path back.
    # ------------------------------------------------------------------

    def _tenant_dir(self, tenant_id: uuid.UUID) -> Path:
        return self._root / str(tenant_id)

    def _resolve_safe(self, path: str) -> Path:
        """Resolve a stored relative path back to an absolute Path,
        rejecting anything that escapes the storage root."""
        candidate = (self._root / path).resolve()
        # Path.is_relative_to lands cleanly even on Windows.
        if not candidate.is_relative_to(self._root):
            raise StorageError(f"path escapes storage root: {path!r}")
        return candidate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        *,
        tenant_id: uuid.UUID,
        original_filename: str,
        stream: BinaryIO,
    ) -> StoredFile:
        """Persist ``stream`` to disk. Raises :class:`FileTooLargeError`
        if the upload exceeds ``max_bytes``."""
        tenant_dir = self._tenant_dir(tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)

        safe_tail = _sanitise_filename(original_filename)
        relative = f"{tenant_id}/{uuid.uuid4()}_{safe_tail}"
        target = self._resolve_safe(relative)

        sha = hashlib.sha256()
        size = 0
        try:
            with target.open("wb") as out:
                while True:
                    chunk = stream.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self._max_bytes:
                        # Drop the partial file so we don't leak quota.
                        out.close()
                        target.unlink(missing_ok=True)
                        raise FileTooLargeError(f"upload exceeds {self._max_bytes} bytes")
                    sha.update(chunk)
                    out.write(chunk)
        except OSError as e:  # pragma: no cover — disk full, permission, etc.
            target.unlink(missing_ok=True)
            raise StorageError(f"failed to write upload: {e}") from e

        return StoredFile(
            path=relative,
            sha256=sha.hexdigest(),
            size_bytes=size,
            original_filename=original_filename,
        )

    def open_read(self, path: str) -> BinaryIO:
        """Open a stored file for reading. Path is the relative form
        returned by :meth:`save`. Raises :class:`StorageError` if the
        path escapes the storage root or doesn't exist."""
        target = self._resolve_safe(path)
        if not target.is_file():
            raise StorageError(f"stored file not found: {path!r}")
        return target.open("rb")

    def absolute_path(self, path: str) -> Path:
        """Resolve to an absolute path on disk. Same safety check as
        :meth:`open_read`. Useful for libraries (polars) that take a
        path string instead of a file object."""
        return self._resolve_safe(path)

    def delete(self, path: str) -> None:
        """Best-effort removal. Missing files are not an error — RLS
        sometimes lets a row delete succeed before the storage call,
        and re-deleting the same path during cleanup is fine."""
        target = self._resolve_safe(path)
        target.unlink(missing_ok=True)


__all__ = [
    "FileTooLargeError",
    "LocalFileStorage",
    "StorageError",
    "StoredFile",
]
