"""Unit tests for InMemoryBookService business rules."""

import pytest

from app.exceptions import BookNotFoundError, IsbnAlreadyExistsError, MemberNotFoundError
from app.models.member import Member
from app.schemas.books import BookCreate, BookUpdate
from app.services.books import InMemoryBookService
from app.services.in_memory_store import InMemoryStore
from tests.helpers import book_payload, member_payload


@pytest.fixture
def store() -> InMemoryStore:
    """A store that already holds Members 1 and 2 for Books to reference."""
    return InMemoryStore(
        members=[
            Member(id=1, **member_payload()),
            Member(id=2, **member_payload(email="g@example.com", membership_id="LIB-2")),
        ]
    )


@pytest.fixture
def service(store: InMemoryStore) -> InMemoryBookService:
    return InMemoryBookService(store)


def test_create_list_and_get_book(service: InMemoryBookService) -> None:
    book = service.create_book(BookCreate(**book_payload(member_id=1)))

    assert book.id == 1
    assert service.list_books() == [book]
    assert service.get_book(book.id) is book


def test_get_missing_book_raises_not_found(service: InMemoryBookService) -> None:
    with pytest.raises(BookNotFoundError):
        service.get_book(999)


def test_create_rejects_nonexistent_member(service: InMemoryBookService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.create_book(BookCreate(**book_payload(member_id=999)))

    assert service.list_books() == []


def test_create_rejects_duplicate_isbn(service: InMemoryBookService) -> None:
    service.create_book(BookCreate(**book_payload(member_id=1)))

    # The same ISBN written with hyphens normalizes to the stored value.
    with pytest.raises(IsbnAlreadyExistsError):
        service.create_book(BookCreate(**book_payload(member_id=2, isbn="978-0-13-595705-9")))

    assert len(service.list_books()) == 1


def test_replace_reassigns_book_to_another_member(service: InMemoryBookService) -> None:
    book = service.create_book(BookCreate(**book_payload(member_id=1)))

    updated = service.replace_book(book.id, BookUpdate(**book_payload(member_id=2, title="Refactoring")))

    assert updated is book
    assert (updated.member_id, updated.title) == (2, "Refactoring")


@pytest.mark.parametrize(
    ("book_id", "member_id", "error"),
    [(999, 1, BookNotFoundError), (1, 999, MemberNotFoundError)],
    ids=["missing-book", "missing-member"],
)
def test_replace_rejects_missing_book_or_member_without_changes(
    service: InMemoryBookService, book_id: int, member_id: int, error: type[Exception]
) -> None:
    book = service.create_book(BookCreate(**book_payload(member_id=1)))

    with pytest.raises(error):
        service.replace_book(book_id, BookUpdate(**book_payload(member_id=member_id, title="Changed")))

    assert book.title == "The Pragmatic Programmer"
    assert book.member_id == 1


def test_replace_rejects_isbn_owned_by_another_book(service: InMemoryBookService) -> None:
    service.create_book(BookCreate(**book_payload(member_id=1)))
    second = service.create_book(BookCreate(**book_payload(member_id=1, isbn="0306406152")))

    with pytest.raises(IsbnAlreadyExistsError):
        service.replace_book(second.id, BookUpdate(**book_payload(member_id=1)))

    assert second.isbn == "0306406152"


def test_delete_removes_book(service: InMemoryBookService) -> None:
    book = service.create_book(BookCreate(**book_payload(member_id=1)))

    service.delete_book(book.id)

    assert service.list_books() == []


def test_delete_missing_book_raises_not_found(service: InMemoryBookService) -> None:
    with pytest.raises(BookNotFoundError):
        service.delete_book(999)
