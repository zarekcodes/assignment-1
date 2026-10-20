"""FastAPI application for the Library Management System API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  # Register ORM models before create_all().
from app.config import Settings, StorageBackend
from app.database.session import create_database
from app.models.base import Base
from app.routers.books import router as books_router
from app.routers.members import router as members_router
from app.services.books import DatabaseBookService, InMemoryBookService
from app.services.in_memory_store import InMemoryStore
from app.services.members import DatabaseMemberService, InMemoryMemberService

# Tag descriptions group related operations and explain each resource in
# Swagger UI and ReDoc.
tags_metadata = [
    {
        "name": "General",
        "description": "Basic application information and health checks.",
    },
    {
        "name": "Members",
        "description": "Create and manage library members and view the books they have borrowed.",
    },
    {
        "name": "Books",
        "description": "Create and manage books, each borrowed by exactly one member.",
    },
]


# Settings are loaded and validated once here, and the selected service
# implementations are stored on application state. Routers only ever see the
# MemberService and BookService contracts through app/dependencies.py.
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize application-scoped infrastructure at startup."""
    settings = Settings()
    application.state.settings = settings
    database = None

    if settings.storage_backend is StorageBackend.MEMORY:
        # Both services share one store so Book rules can see Members.
        store = InMemoryStore()
        application.state.member_service = InMemoryMemberService(store)
        application.state.book_service = InMemoryBookService(store)
    elif settings.storage_backend is StorageBackend.DATABASE:
        database = create_database(settings)
        # Creates missing tables only; it never alters or drops existing ones.
        # Schema changes will be handled by migrations in a later module.
        Base.metadata.create_all(bind=database.engine)
        application.state.member_service = DatabaseMemberService(database.session_factory)
        application.state.book_service = DatabaseBookService(database.session_factory)

    yield

    # Close pooled connections cleanly when the server shuts down.
    if database is not None:
        database.engine.dispose()


# Uvicorn loads this object (app.main:app). Its metadata becomes the header
# of the generated OpenAPI document.
app = FastAPI(
    title="Library Management System API",
    description=(
        "Manage library Members and the Books they borrow. Each Book belongs to "
        "exactly one existing Member, and a Member may borrow many Books. Data is "
        "stored in PostgreSQL by default, or in process memory when the in-memory "
        "storage backend is selected."
    ),
    version="0.2.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.include_router(members_router)
app.include_router(books_router)


@app.get("/", tags=["General"], summary="Introduce the API")
def read_root() -> dict[str, str]:
    """Return a short introduction to the API."""
    return {"message": "Library Management System API"}


# The health endpoint gives clients a simple way to confirm the API is running.
@app.get(
    "/health",
    tags=["General"],
    summary="Check API health",
    description="Confirm that the API process is running.",
)
def health_check() -> dict[str, str]:
    """Confirm that the API process is running."""
    return {"status": "healthy"}
