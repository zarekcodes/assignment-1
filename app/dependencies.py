"""FastAPI dependencies that expose application services to HTTP routes."""

from fastapi import Request

from app.config import Settings
from app.services.books import BookService
from app.services.members import MemberService


def get_settings(request: Request) -> Settings:
    """Return the validated settings created once during application startup."""
    return request.app.state.settings


def get_member_service(request: Request) -> MemberService:
    """Return the startup-selected Member service."""
    return request.app.state.member_service


def get_book_service(request: Request) -> BookService:
    """Return the startup-selected Book service."""
    return request.app.state.book_service
