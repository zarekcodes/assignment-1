"""Test doubles shared by the database-service unit tests."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from sqlalchemy.exc import IntegrityError


@dataclass
class FakeDatabase:
    """The mocks a database-service test arranges and verifies."""

    factory: Any
    session: Any
    member_repository: Any
    book_repository: Any


def integrity_error(constraint_name: str) -> IntegrityError:
    """Build the IntegrityError SQLAlchemy raises when PostgreSQL rejects a write.

    app/database/errors.py reads ``error.orig.diag.constraint_name``, so the
    fake driver error exposes only that attribute.
    """
    driver_error = Exception("constraint violation")
    driver_error.diag = SimpleNamespace(constraint_name=constraint_name)  # type: ignore[attr-defined]
    return IntegrityError("INSERT ...", {}, driver_error)
