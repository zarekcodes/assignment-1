"""HTTP endpoints for the Member resource."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.auth.dependencies import ADMIN_RESPONSES, AUTHENTICATED_RESPONSES, AdminUser, CurrentUser
from app.dependencies import get_member_service
from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
    MembershipIdAlreadyExistsError,
)
from app.models.book import Book
from app.models.member import Member
from app.routers.http_errors import (
    member_email_already_exists,
    member_has_books,
    member_not_found,
    membership_id_already_exists,
)
from app.schemas.books import BookResponse
from app.schemas.errors import ErrorResponse
from app.schemas.ids import MAX_ID
from app.schemas.members import MemberCreate, MemberResponse, MemberUpdate
from app.services.members import MemberService

# Routers validate input, call services, and translate outcomes to HTTP.
# Reads require CurrentUser and writes require AdminUser; see books.py.
router = APIRouter(prefix="/members", tags=["Members"])

# Reusable path parameter type: non-positive IDs are rejected with 422 before
# the route runs, and the rule appears in the OpenAPI contract.
MemberId = Annotated[int, Path(gt=0, le=MAX_ID, description="The identifier of the member.")]


@router.get(
    "",
    response_model=list[MemberResponse],
    summary="List all members",
    description="Return every member currently stored by the application.",
    responses=AUTHENTICATED_RESPONSES,
)
def list_members(
    _current_user: CurrentUser,
    service: MemberService = Depends(get_member_service),
) -> list[Member]:
    """Delegate Member retrieval to the service layer."""
    return service.list_members()


@router.get(
    "/{member_id}",
    response_model=MemberResponse,
    summary="Get one member",
    description="Return the member identified by the path parameter.",
    responses={
        **AUTHENTICATED_RESPONSES,
        404: {"model": ErrorResponse, "description": "Member not found"},
    },
)
def get_member(
    member_id: MemberId,
    _current_user: CurrentUser,
    service: MemberService = Depends(get_member_service),
) -> Member:
    """Return one Member or translate the missing-resource error."""
    try:
        return service.get_member(member_id)
    except MemberNotFoundError:
        raise member_not_found() from None


@router.post(
    "",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a member",
    description="Create a member with a unique email address and membership ID.",
    responses={
        **ADMIN_RESPONSES,
        409: {"model": ErrorResponse, "description": "Email or membership ID already in use"},
    },
)
def create_member(
    data: MemberCreate,
    _admin_user: AdminUser,
    service: MemberService = Depends(get_member_service),
) -> Member:
    """Pass validated input to the business and persistence layers."""
    try:
        return service.create_member(data)
    except MemberEmailAlreadyExistsError:
        raise member_email_already_exists() from None
    except MembershipIdAlreadyExistsError:
        raise membership_id_already_exists() from None


# PUT replaces every editable field, so the body must be complete.
@router.put(
    "/{member_id}",
    response_model=MemberResponse,
    summary="Replace a member",
    description="Replace all editable fields of an existing member.",
    responses={
        **ADMIN_RESPONSES,
        404: {"model": ErrorResponse, "description": "Member not found"},
        409: {"model": ErrorResponse, "description": "Email or membership ID already in use"},
    },
)
def replace_member(
    member_id: MemberId,
    data: MemberUpdate,
    _admin_user: AdminUser,
    service: MemberService = Depends(get_member_service),
) -> Member:
    """Replace one Member through the service layer."""
    try:
        return service.replace_member(member_id, data)
    except MemberNotFoundError:
        raise member_not_found() from None
    except MemberEmailAlreadyExistsError:
        raise member_email_already_exists() from None
    except MembershipIdAlreadyExistsError:
        raise membership_id_already_exists() from None


@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a member",
    description="Delete a member only when they have no borrowed books.",
    responses={
        **ADMIN_RESPONSES,
        404: {"model": ErrorResponse, "description": "Member not found"},
        409: {"model": ErrorResponse, "description": "Member still has associated books"},
    },
)
def delete_member(
    member_id: MemberId,
    _admin_user: AdminUser,
    service: MemberService = Depends(get_member_service),
) -> Response:
    """Translate Member deletion outcomes into HTTP responses."""
    try:
        service.delete_member(member_id)
    except MemberNotFoundError:
        raise member_not_found() from None
    except MemberHasBooksError:
        raise member_has_books() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# This nested URL reads the Books associated with one Member.
@router.get(
    "/{member_id}/books",
    response_model=list[BookResponse],
    summary="List a member's books",
    description="Return every book borrowed by the requested member.",
    responses={
        **AUTHENTICATED_RESPONSES,
        404: {"model": ErrorResponse, "description": "Member not found"},
    },
)
def list_member_books(
    member_id: MemberId,
    _current_user: CurrentUser,
    service: MemberService = Depends(get_member_service),
) -> list[Book]:
    """Return related Books after the service verifies the Member."""
    try:
        return service.list_member_books(member_id)
    except MemberNotFoundError:
        raise member_not_found() from None
