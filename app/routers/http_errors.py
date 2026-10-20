"""Translate application outcomes into HTTP responses for API routes."""

from fastapi import HTTPException, status


def member_not_found() -> HTTPException:
    """Return the HTTP 404 response for a missing Member.

    This mapping belongs in the router package because HTTPException is a
    FastAPI transport concern, not a Library business rule.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Member not found",
    )


def book_not_found() -> HTTPException:
    """Return the HTTP 404 response for a missing Book."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Book not found",
    )


def member_has_books() -> HTTPException:
    """Return the HTTP 409 response for a Member who still has Books."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Delete or reassign the member's books before deleting the member",
    )


def member_email_already_exists() -> HTTPException:
    """Return the HTTP 409 response for a duplicate Member email address."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A member with this email already exists",
    )


def membership_id_already_exists() -> HTTPException:
    """Return the HTTP 409 response for a duplicate membership ID."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A member with this membership ID already exists",
    )


def isbn_already_exists() -> HTTPException:
    """Return the HTTP 409 response for a duplicate ISBN."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A book with this ISBN already exists",
    )
