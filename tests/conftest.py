"""Shared pytest fixtures for the Library Management System API tests.

Pytest discovers this file automatically. A test requests a fixture by naming
it as a parameter; test modules never import fixtures directly.

Fixture dependency flow:

    db_session ────────┐
    database_client ───┴─> reset_database -> db_engine -> postgres_container
    memory_client ─────> application lifespan -> fresh InMemoryStore
    api_client ────────> database_client or memory_client (parametrized)

Fixture lifetimes:

    One `uv run pytest` command
    └── one disposable PostgreSQL container and one SQLAlchemy Engine
        └── each test function gets empty tables and its own TestClient or
            Session, so no test depends on another test's data or order

Unit tests request none of the database fixtures, so they never start Docker.

Test configuration never comes from a developer's .env file. Environment
variables take priority over .env in pydantic-settings, so the fixtures below
set every value a test depends on: the classroom tokens, the storage backend,
and a DATABASE_URL that points only at the Testcontainers database.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.community.postgres import PostgresContainer

from app.auth.users import Role
from app.config import Settings, StorageBackend

# Test-only token values. They intentionally differ from .env.example so a
# test can never pass by accident because a developer's .env happens to match.
TEST_TOKENS = {Role.MEMBER: "test-member-token", Role.ADMIN: "test-admin-token"}


@pytest.fixture(scope="session", autouse=True)
def classroom_tokens() -> Generator[None, None, None]:
    """Install the test tokens for every test, including app startup."""
    # monkeypatch is function-scoped, so a session fixture uses the context
    # form directly. Leaving the block restores the original environment.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DEMO_MEMBER_TOKEN", TEST_TOKENS[Role.MEMBER])
        patch.setenv("DEMO_ADMIN_TOKEN", TEST_TOKENS[Role.ADMIN])
        yield


@pytest.fixture
def test_settings() -> Settings:
    """Settings for unit tests that need tokens but no database."""
    return Settings(
        storage_backend=StorageBackend.MEMORY,
        demo_member_token=TEST_TOKENS[Role.MEMBER],
        demo_admin_token=TEST_TOKENS[Role.ADMIN],
    )


@pytest.fixture
def member_headers() -> dict[str, str]:
    """Authorization header for the member request role (read-only)."""
    return {"Authorization": f"Bearer {TEST_TOKENS[Role.MEMBER]}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Authorization header for the administrator request role."""
    return {"Authorization": f"Bearer {TEST_TOKENS[Role.ADMIN]}"}


# POSTGRESQL (TESTCONTAINERS)


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Start one disposable PostgreSQL container for the whole pytest run.

    Testcontainers asks Docker to start postgres:18 on a random free host
    port and waits until it accepts connections. Leaving the `with` block
    stops and removes the container, including all of its data. The local
    library_management database is never touched.
    """
    # driver="psycopg" makes the URL use Psycopg 3, the driver the app uses.
    with PostgresContainer(
        "postgres:18",
        username="postgres",
        password="postgres",
        dbname="library_management_test",
        driver="psycopg",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    """Return the connection URL of the temporary container."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def db_engine(database_url: str) -> Generator[Engine, None, None]:
    """Build the application's own Engine, pointed at the container."""
    from app import models  # noqa: F401  # Register Book and Member tables.
    from app.database.session import create_database

    database = create_database(
        Settings(
            storage_backend=StorageBackend.DATABASE,
            database_url=database_url,
            demo_member_token=TEST_TOKENS[Role.MEMBER],
            demo_admin_token=TEST_TOKENS[Role.ADMIN],
        )
    )
    yield database.engine
    database.engine.dispose()


@pytest.fixture
def reset_database(db_engine: Engine) -> Generator[None, None, None]:
    """Give one test empty members and books tables built from the ORM models."""
    from app.models.base import Base

    # Drop first as well as last, so a crashed earlier run cannot leak rows.
    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)
    yield
    Base.metadata.drop_all(bind=db_engine)


@pytest.fixture
def db_session(reset_database: None, db_engine: Engine) -> Generator[Session, None, None]:
    """Provide a real Session for repository integration tests."""
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
        # A test may deliberately trigger an IntegrityError. Roll back so the
        # connection is clean before reset_database drops the tables.
        session.rollback()


# API CLIENTS
# Each client fixture runs the real FastAPI lifespan, so the same startup
# code that production uses selects the services. The clients start without
# credentials so tests state explicitly which role sends each request.


@pytest.fixture
def database_env(
    reset_database: None,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configure app startup for the empty Testcontainers database."""
    monkeypatch.setenv("STORAGE_BACKEND", StorageBackend.DATABASE.value)
    monkeypatch.setenv("DATABASE_URL", database_url)


@pytest.fixture
def database_client(database_env: None) -> Generator[TestClient, None, None]:
    """TestClient whose lifespan selects the PostgreSQL services."""
    from app.main import app

    # Entering the context runs the lifespan; no server or port is used.
    with TestClient(app) as client:
        yield client


@pytest.fixture
def memory_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """TestClient whose lifespan selects the in-memory services."""
    monkeypatch.setenv("STORAGE_BACKEND", StorageBackend.MEMORY.value)
    # Prove the memory backend needs no database at all.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.main import app

    # Each lifespan builds a new InMemoryStore, so state never leaks.
    with TestClient(app) as client:
        yield client


@pytest.fixture(params=["database", "memory"])
def api_client(request: pytest.FixtureRequest) -> TestClient:
    """Run the requesting test once against each storage backend.

    Business-rule outcomes are part of the public contract, so both backends
    must return the same statuses and bodies for the same requests.
    """
    return request.getfixturevalue(f"{request.param}_client")
