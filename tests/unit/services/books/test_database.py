"""Unit tests for DatabaseBookService decisions, using mocked repositories."""

import pytest
from mockito import verify, when

import app.services.books.database as database_module
from app.exceptions import BookNotFoundError, IsbnAlreadyExistsError, MemberNotFoundError
from app.models.book import BOOK_ISBN_UNIQUE, BOOK_MEMBER_FOREIGN_KEY, Book
from app.models.member import Member
from app.schemas.books import BookCreate, BookUpdate
from app.services.books import DatabaseBookService
from tests.fakes import FakeDatabase, integrity_error
from tests.helpers import book_payload, member_payload


@pytest.fixture
def service(fake_database: FakeDatabase) -> DatabaseBookService:
    """Make the service module build the fake repositories.

    The service constructs repositories itself (``MemberRepository(session)``),
    so the module attribute is patched. The fake_database fixture's unstub()
    restores the real classes after the test.
    """
    db = fake_database
    when(database_module).MemberRepository(db.session).thenReturn(db.member_repository)
    when(database_module).BookRepository(db.session).thenReturn(db.book_repository)
    return DatabaseBookService(db.factory)


def stored_book(book_id: int = 1, **overrides) -> Book:
    return Book(id=book_id, **book_payload(member_id=1, **overrides))


@pytest.fixture
def existing_member(fake_database: FakeDatabase) -> Member:
    """Make Member 1 exist from the service's point of view."""
    member = Member(id=1, **member_payload())
    when(fake_database.member_repository).get_by_id(1).thenReturn(member)
    return member


# READS


def test_get_book_translates_missing_row_to_not_found(
    service: DatabaseBookService, fake_database: FakeDatabase
) -> None:
    with pytest.raises(BookNotFoundError):
        service.get_book(999)

    verify(fake_database.factory, times=0).begin()


# CREATE


def test_create_book_checks_member_and_isbn_then_inserts_in_one_transaction(
    service: DatabaseBookService, fake_database: FakeDatabase, existing_member: Member
) -> None:
    book = stored_book()
    when(fake_database.book_repository).create(...).thenReturn(book)

    assert service.create_book(BookCreate(**book_payload(member_id=1))) is book
    verify(fake_database.factory, times=1).begin()
    verify(fake_database.member_repository, times=1).get_by_id(1)
    verify(fake_database.book_repository, times=1).get_by_isbn("9780135957059")
    verify(fake_database.session, times=1).refresh(book)


def test_create_book_rejects_nonexistent_member_without_inserting(
    service: DatabaseBookService, fake_database: FakeDatabase
) -> None:
    with pytest.raises(MemberNotFoundError):
        service.create_book(BookCreate(**book_payload(member_id=999)))

    verify(fake_database.book_repository, times=0).create(...)


def test_create_book_rejects_duplicate_isbn_without_inserting(
    service: DatabaseBookService, fake_database: FakeDatabase, existing_member: Member
) -> None:
    when(fake_database.book_repository).get_by_isbn("9780135957059").thenReturn(stored_book(book_id=8))

    with pytest.raises(IsbnAlreadyExistsError):
        service.create_book(BookCreate(**book_payload(member_id=1)))

    verify(fake_database.book_repository, times=0).create(...)


@pytest.mark.parametrize(
    ("constraint", "error"),
    [(BOOK_ISBN_UNIQUE, IsbnAlreadyExistsError), (BOOK_MEMBER_FOREIGN_KEY, MemberNotFoundError)],
    ids=["isbn-unique", "member-foreign-key"],
)
def test_create_book_translates_constraint_races_to_application_errors(
    service: DatabaseBookService,
    fake_database: FakeDatabase,
    existing_member: Member,
    constraint: str,
    error: type[Exception],
) -> None:
    """A concurrent write can pass the service checks and still be rejected by
    PostgreSQL; the constraint name maps back to the same Library outcome."""
    when(fake_database.book_repository).create(...).thenRaise(integrity_error(constraint))

    with pytest.raises(error):
        service.create_book(BookCreate(**book_payload(member_id=1)))


# REPLACE


def test_replace_book_rejects_missing_book_before_checking_member(
    service: DatabaseBookService, fake_database: FakeDatabase
) -> None:
    with pytest.raises(BookNotFoundError):
        service.replace_book(999, BookUpdate(**book_payload(member_id=1)))

    verify(fake_database.member_repository, times=0).get_by_id(...)
    verify(fake_database.book_repository, times=0).replace(...)


def test_replace_book_rejects_nonexistent_member(service: DatabaseBookService, fake_database: FakeDatabase) -> None:
    when(fake_database.book_repository).get_by_id(1).thenReturn(stored_book())

    with pytest.raises(MemberNotFoundError):
        service.replace_book(1, BookUpdate(**book_payload(member_id=999)))

    verify(fake_database.book_repository, times=0).replace(...)


def test_replace_book_allows_keeping_its_own_isbn(
    service: DatabaseBookService, fake_database: FakeDatabase, existing_member: Member
) -> None:
    book = stored_book()
    when(fake_database.book_repository).get_by_id(1).thenReturn(book)
    when(fake_database.book_repository).get_by_isbn("9780135957059").thenReturn(book)
    when(fake_database.book_repository).replace(book, ...).thenReturn(book)

    assert service.replace_book(1, BookUpdate(**book_payload(member_id=1, title="New Title"))) is book
    verify(fake_database.book_repository, times=1).replace(book, ...)


def test_replace_book_rejects_isbn_of_another_book(
    service: DatabaseBookService, fake_database: FakeDatabase, existing_member: Member
) -> None:
    when(fake_database.book_repository).get_by_id(1).thenReturn(stored_book())
    when(fake_database.book_repository).get_by_isbn("0306406152").thenReturn(stored_book(book_id=2))

    with pytest.raises(IsbnAlreadyExistsError):
        service.replace_book(1, BookUpdate(**book_payload(member_id=1, isbn="0306406152")))

    verify(fake_database.book_repository, times=0).replace(...)


# DELETE


def test_delete_book_deletes_existing_book_in_a_transaction(
    service: DatabaseBookService, fake_database: FakeDatabase
) -> None:
    book = stored_book()
    when(fake_database.book_repository).get_by_id(1).thenReturn(book)

    service.delete_book(1)

    verify(fake_database.factory, times=1).begin()
    verify(fake_database.book_repository, times=1).delete(book)


def test_delete_missing_book_raises_not_found(service: DatabaseBookService, fake_database: FakeDatabase) -> None:
    with pytest.raises(BookNotFoundError):
        service.delete_book(999)

    verify(fake_database.book_repository, times=0).delete(...)
