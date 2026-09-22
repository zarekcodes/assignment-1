"""HTTP endpoints for the Member resource."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.schemas.books import BookResponse
from app.schemas.members import MemberCreate, MemberResponse, MemberUpdate
from app.storage import books, members

# Every route in this file begins with /members and appears under the
# Members heading in FastAPI's generated API documentation.
router = APIRouter(prefix="/members", tags=["Members"])

# Path(gt=0) validates the ID in the URL the same way Field(gt=0) validates
# IDs in a body: /members/0 or /members/-5 is rejected with 422 before the
# route runs, and the rule is shown in the OpenAPI contract.
MemberId = Annotated[int, Path(gt=0, description="The identifier of the member.")]


def find_member(member_id: int) -> MemberResponse:
    """Find one member or return an HTTP 404 error to the client."""
    for member in members:
        if member.id == member_id:
            return member

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Member not found",
    )


def ensure_member_is_unique(data: MemberCreate | MemberUpdate, current_id: int | None = None) -> None:
    """Return HTTP 409 when another member already uses the email or membership ID."""
    # Pydantic can validate one request body, but it cannot see other stored
    # records, so uniqueness is a business rule checked here. current_id lets
    # a member keep its own values during an update.
    for member in members:
        if member.id == current_id:
            continue
        if member.email == data.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A member with this email already exists",
            )
        if member.membership_id == data.membership_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A member with this membership ID already exists",
            )


# GET /members reads the entire Member collection.
@router.get(
    "",
    response_model=list[MemberResponse],
    summary="List all members",
    description="Return every member currently stored by the application.",
)
def list_members() -> list[MemberResponse]:
    """Return every member currently stored in memory."""
    return members


# The value inside {member_id} is supplied by the URL path.
@router.get(
    "/{member_id}",
    response_model=MemberResponse,
    summary="Get one member",
    description="Return the member identified by the path parameter.",
    responses={404: {"description": "Member not found"}},
)
def get_member(member_id: MemberId) -> MemberResponse:
    """Return the member with the requested ID."""
    return find_member(member_id)


# POST creates a new resource, so a successful request returns HTTP 201.
@router.post(
    "",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a member",
    description="Create a member with a unique email address and membership ID.",
    responses={409: {"description": "Email or membership ID already in use"}},
)
def create_member(data: MemberCreate) -> MemberResponse:
    """Create a member from a validated JSON request body."""
    # FastAPI has already validated the body against MemberCreate; invalid
    # input never reaches this line and receives a 422 response instead.
    ensure_member_is_unique(data)
    next_member_id = max((member.id for member in members), default=0) + 1
    member = MemberResponse(id=next_member_id, **data.model_dump())
    members.append(member)
    return member


# PUT replaces every editable value of the Member identified by the URL.
@router.put(
    "/{member_id}",
    response_model=MemberResponse,
    summary="Replace a member",
    description="Replace all editable fields of an existing member.",
    responses={
        404: {"description": "Member not found"},
        409: {"description": "Email or membership ID already in use"},
    },
)
def replace_member(member_id: MemberId, data: MemberUpdate) -> MemberResponse:
    """Replace the fields of an existing member."""
    member = find_member(member_id)
    ensure_member_is_unique(data, current_id=member_id)
    updated_member = MemberResponse(id=member_id, **data.model_dump())
    members[members.index(member)] = updated_member
    return updated_member


# A successful DELETE has no response body, so it returns HTTP 204.
@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a member",
    description="Delete a member only when they have no borrowed books.",
    responses={
        404: {"description": "Member not found"},
        409: {"description": "Member still has associated books"},
    },
)
def delete_member(member_id: MemberId) -> Response:
    """Remove a member from the in-memory collection."""
    member = find_member(member_id)

    # Deleting the member would leave Books pointing to a Member that no
    # longer exists, so the client must delete or reassign them first.
    if any(book.member_id == member_id for book in books):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete or reassign the member's books before deleting the member",
        )

    members.remove(member)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# This nested URL reads the Books that belong to one Member.
@router.get(
    "/{member_id}/books",
    response_model=list[BookResponse],
    summary="List a member's books",
    description="Return every book borrowed by the requested member.",
    responses={404: {"description": "Member not found"}},
)
def list_member_books(member_id: MemberId) -> list[BookResponse]:
    """Return every book associated with the requested member."""
    # Check the member first so an unknown ID returns 404 instead of an
    # empty list, which would wrongly suggest the member exists.
    find_member(member_id)
    return [book for book in books if book.member_id == member_id]
