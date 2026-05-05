"""Declarative base + a single shared metadata.

A predictable ``naming_convention`` is critical: it makes Alembic's
auto-generated migrations deterministic across machines and lets us reference
constraints by name when toggling RLS or dropping indexes.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Project-wide ORM base. All models inherit from this class."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
