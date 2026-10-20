"""PostgreSQL engine and operation-scoped SQLAlchemy session factory."""

from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


@dataclass(frozen=True)
class DatabaseInfrastructure:
    """Database engine and session factory created from validated settings."""

    engine: Engine
    session_factory: sessionmaker[Session]


def create_database(settings: Settings) -> DatabaseInfrastructure:
    """Create the engine and session factory for one application instance."""
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required to create database infrastructure")

    # The engine owns the connection pool and is created once per application.
    # Sessions borrow a pooled connection only while database work runs.
    engine = create_engine(settings.database_url, echo=settings.database_echo_sql)

    # Services share this factory, but each service operation opens its own
    # Session, so no Session is ever shared between concurrent requests.
    # expire_on_commit=False keeps loaded values readable after the Session
    # closes, which FastAPI needs when it serializes the returned ORM object.
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    return DatabaseInfrastructure(engine=engine, session_factory=session_factory)
