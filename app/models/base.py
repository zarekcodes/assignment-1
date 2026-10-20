"""Shared SQLAlchemy declarative base class."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by every SQLAlchemy ORM model.

    Every model that inherits Base registers its table in Base.metadata, which
    the application uses at startup to create missing tables.
    """
