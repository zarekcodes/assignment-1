"""Response schema for the application's own error outcomes."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Describe the body FastAPI sends for an HTTPException.

    Routers raise HTTPException(detail="..."), which FastAPI serializes as
    {"detail": "..."}. Declaring that shape on every 401, 403, 404, and 409
    response lets clients and contract tests rely on it. 422 responses use
    FastAPI's built-in HTTPValidationError schema instead.
    """

    detail: str = Field(description="A short, client-safe explanation.", examples=["Member not found"])
