"""FastAPI dependencies that expose application services to HTTP routes."""

from fastapi import Request

from app.services.books import BookService
from app.services.members import MemberService


def get_member_service(request: Request) -> MemberService:
    """Return the startup-selected Member service."""
    return request.app.state.member_service


def get_book_service(request: Request) -> BookService:
    """Return the startup-selected Book service."""
    return request.app.state.book_service
