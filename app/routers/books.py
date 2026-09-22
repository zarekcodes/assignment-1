"""HTTP endpoints for the Book resource."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.routers.members import find_member
from app.schemas.books import BookCreate, BookResponse, BookUpdate
from app.storage import books

# Books use the same collection and item URL pattern as Members.
router = APIRouter(prefix="/books", tags=["Books"])

BookId = Annotated[int, Path(gt=0, description="The identifier of the book.")]


def find_book(book_id: int) -> BookResponse:
    """Find one book or return an HTTP 404 error to the client."""
    for book in books:
        if book.id == book_id:
            return book

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Book not found",
    )


def ensure_isbn_is_unique(isbn: str, current_id: int | None = None) -> None:
    """Return HTTP 409 when another book already uses the ISBN."""
    # The schema normalizes ISBNs before this check, so formatting
    # differences such as hyphens cannot bypass uniqueness.
    if any(book.isbn == isbn and book.id != current_id for book in books):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A book with this ISBN already exists",
        )


# GET /books reads the entire Book collection.
@router.get(
    "",
    response_model=list[BookResponse],
    summary="List all books",
    description="Return every book currently stored by the application.",
)
def list_books() -> list[BookResponse]:
    """Return every book currently stored in memory."""
    return books


# GET /books/{book_id} reads one Book identified by its path parameter.
@router.get(
    "/{book_id}",
    response_model=BookResponse,
    summary="Get one book",
    description="Return the book identified by the path parameter.",
    responses={404: {"description": "Book not found"}},
)
def get_book(book_id: BookId) -> BookResponse:
    """Return the book with the requested ID."""
    return find_book(book_id)


# A Book can be created only when its related Member exists.
@router.post(
    "",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a book",
    description="Create a book and associate it with the existing member who borrowed it.",
    responses={
        404: {"description": "Related member not found"},
        409: {"description": "ISBN already in use"},
    },
)
def create_book(data: BookCreate) -> BookResponse:
    """Create a book associated with an existing member."""
    # Pydantic confirmed member_id is a positive integer; this check confirms
    # that a Member with that ID actually exists.
    find_member(data.member_id)
    ensure_isbn_is_unique(data.isbn)
    next_book_id = max((book.id for book in books), default=0) + 1
    book = BookResponse(id=next_book_id, **data.model_dump())
    books.append(book)
    return book


# PUT replaces all editable Book values, including its Member relationship,
# which is how a Book is reassigned to a different Member.
@router.put(
    "/{book_id}",
    response_model=BookResponse,
    summary="Replace a book",
    description="Replace all editable fields and verify the related member.",
    responses={
        404: {"description": "Book or related member not found"},
        409: {"description": "ISBN already in use"},
    },
)
def replace_book(book_id: BookId, data: BookUpdate) -> BookResponse:
    """Replace an existing book after checking its related member."""
    book = find_book(book_id)
    find_member(data.member_id)
    ensure_isbn_is_unique(data.isbn, current_id=book_id)
    updated_book = BookResponse(id=book_id, **data.model_dump())
    books[books.index(book)] = updated_book
    return updated_book


# A successful DELETE removes the Book and returns no response body.
@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a book",
    description="Delete the book identified by the path parameter.",
    responses={404: {"description": "Book not found"}},
)
def delete_book(book_id: BookId) -> Response:
    """Remove a book from the in-memory collection."""
    book = find_book(book_id)
    books.remove(book)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
