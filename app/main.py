"""FastAPI application for the Library Management System API."""

from fastapi import FastAPI

from app.routers.books import router as books_router
from app.routers.members import router as members_router

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

# Uvicorn loads this object (app.main:app). Its metadata becomes the header
# of the generated OpenAPI document.
app = FastAPI(
    title="Library Management System API",
    description=(
        "Manage library Members and the Books they borrow. Each Book belongs to "
        "exactly one existing Member, and a Member may borrow many Books. Data is "
        "stored in memory and resets when the server restarts."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
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
