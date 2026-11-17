"""HTTP endpoints for the Book resource."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.auth.dependencies import ADMIN_RESPONSES, AUTHENTICATED_RESPONSES, AdminUser, CurrentUser
from app.dependencies import get_book_service
from app.exceptions import BookNotFoundError, IsbnAlreadyExistsError, MemberNotFoundError
from app.models.book import Book
from app.routers.http_errors import book_not_found, isbn_already_exists, member_not_found
from app.schemas.books import BookCreate, BookResponse, BookUpdate
from app.schemas.errors import ErrorResponse
from app.schemas.ids import MAX_ID
from app.services.books import BookService

# Routers validate input, call services, and translate outcomes to HTTP.
# Every route declares CurrentUser (any valid token may read) or AdminUser
# (only an administrator may write). The underscore-prefixed parameters are
# intentionally unused: declaring them makes FastAPI run authentication and
# the role check before the handler, and keeps the services credential-free.
router = APIRouter(prefix="/books", tags=["Books"])

BookId = Annotated[int, Path(gt=0, le=MAX_ID, description="The identifier of the book.")]


@router.get(
    "",
    response_model=list[BookResponse],
    summary="List all books",
    description="Return every book currently stored by the application.",
    responses=AUTHENTICATED_RESPONSES,
)
def list_books(
    _current_user: CurrentUser,
    service: BookService = Depends(get_book_service),
) -> list[Book]:
    """Delegate Book retrieval to the service layer."""
    return service.list_books()


@router.get(
    "/{book_id}",
    response_model=BookResponse,
    summary="Get one book",
    description="Return the book identified by the path parameter.",
    responses={
        **AUTHENTICATED_RESPONSES,
        404: {"model": ErrorResponse, "description": "Book not found"},
    },
)
def get_book(
    book_id: BookId,
    _current_user: CurrentUser,
    service: BookService = Depends(get_book_service),
) -> Book:
    """Return one Book or translate the missing-resource error."""
    try:
        return service.get_book(book_id)
    except BookNotFoundError:
        raise book_not_found() from None


@router.post(
    "",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a book",
    description="Create a book and associate it with the existing member who borrowed it.",
    responses={
        **ADMIN_RESPONSES,
        404: {"model": ErrorResponse, "description": "Related member not found"},
        409: {"model": ErrorResponse, "description": "ISBN already in use"},
    },
)
def create_book(
    data: BookCreate,
    _admin_user: AdminUser,
    service: BookService = Depends(get_book_service),
) -> Book:
    """Create a Book after the service verifies its business rules."""
    try:
        return service.create_book(data)
    except MemberNotFoundError:
        raise member_not_found() from None
    except IsbnAlreadyExistsError:
        raise isbn_already_exists() from None


# Changing member_id reassigns the Book to another Member, which is how staff
# free a Member of Books before deleting them.
@router.put(
    "/{book_id}",
    response_model=BookResponse,
    summary="Replace a book",
    description="Replace all editable fields and verify the related member.",
    responses={
        **ADMIN_RESPONSES,
        404: {"model": ErrorResponse, "description": "Book or related member not found"},
        409: {"model": ErrorResponse, "description": "ISBN already in use"},
    },
)
def replace_book(
    book_id: BookId,
    data: BookUpdate,
    _admin_user: AdminUser,
    service: BookService = Depends(get_book_service),
) -> Book:
    """Replace a Book after checking both related resources."""
    try:
        return service.replace_book(book_id, data)
    except BookNotFoundError:
        raise book_not_found() from None
    except MemberNotFoundError:
        raise member_not_found() from None
    except IsbnAlreadyExistsError:
        raise isbn_already_exists() from None


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a book",
    description="Delete the book identified by the path parameter.",
    responses={
        **ADMIN_RESPONSES,
        404: {"model": ErrorResponse, "description": "Book not found"},
    },
)
def delete_book(
    book_id: BookId,
    _admin_user: AdminUser,
    service: BookService = Depends(get_book_service),
) -> Response:
    """Delete a Book and translate the service outcome into HTTP."""
    try:
        service.delete_book(book_id)
    except BookNotFoundError:
        raise book_not_found() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
