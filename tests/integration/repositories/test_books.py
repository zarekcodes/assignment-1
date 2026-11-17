"""PostgreSQL integration tests for BookRepository and the Member-to-Book foreign key."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.errors import violated_constraint
from app.models.book import BOOK_ISBN_UNIQUE, BOOK_MEMBER_FOREIGN_KEY, Book
from app.models.member import Member
from app.repositories.books import BookRepository
from app.repositories.members import MemberRepository
from app.schemas.books import BookCreate, BookUpdate
from app.schemas.members import MemberCreate
from tests.helpers import book_payload, member_payload


def add_member(session: Session, **overrides: str) -> Member:
    member = MemberRepository(session).create(MemberCreate(**member_payload(**overrides)))
    session.commit()
    return member


def add_book(session: Session, member_id: int, **overrides) -> Book:
    book = BookRepository(session).create(BookCreate(**book_payload(member_id=member_id, **overrides)))
    session.commit()
    return book


@pytest.fixture
def member(db_session: Session) -> Member:
    return add_member(db_session)


def test_create_generates_id_and_stores_normalized_isbn(db_session: Session, member: Member) -> None:
    book = add_book(db_session, member.id, isbn="978-0-13-595705-9")
    db_session.expire_all()

    stored = BookRepository(db_session).get_by_id(book.id)
    assert book.id > 0
    assert stored.isbn == "9780135957059"
    assert stored.member_id == member.id


def test_lookups_find_stored_book_or_return_none(db_session: Session, member: Member) -> None:
    book = add_book(db_session, member.id)
    repository = BookRepository(db_session)

    assert repository.get_by_id(book.id) is book
    assert repository.get_by_isbn("9780135957059") is book
    assert repository.get_by_id(999) is None
    assert repository.get_by_isbn("0306406152") is None


def test_list_by_member_returns_only_that_members_books(db_session: Session, member: Member) -> None:
    other = add_member(db_session, email="g@example.com", membership_id="LIB-2")
    first = add_book(db_session, member.id)
    add_book(db_session, other.id, isbn="0306406152")
    third = add_book(db_session, member.id, isbn="080442957X")

    repository = BookRepository(db_session)
    assert [book.id for book in repository.list_by_member(member.id)] == [first.id, third.id]
    assert len(repository.list_all()) == 3


def test_exists_for_member_reflects_related_rows(db_session: Session, member: Member) -> None:
    repository = BookRepository(db_session)
    assert repository.exists_for_member(member.id) is False

    add_book(db_session, member.id)

    assert repository.exists_for_member(member.id) is True


def test_replace_can_reassign_book_to_another_member(db_session: Session, member: Member) -> None:
    other = add_member(db_session, email="g@example.com", membership_id="LIB-2")
    book = add_book(db_session, member.id)

    BookRepository(db_session).replace(book, BookUpdate(**book_payload(member_id=other.id, title="Moved")))
    db_session.commit()
    db_session.expire_all()

    stored = BookRepository(db_session).get_by_id(book.id)
    assert (stored.member_id, stored.title) == (other.id, "Moved")


def test_delete_removes_row(db_session: Session, member: Member) -> None:
    book = add_book(db_session, member.id)

    BookRepository(db_session).delete(book)
    db_session.commit()

    assert BookRepository(db_session).get_by_id(book.id) is None


# DATABASE CONSTRAINTS


def test_database_enforces_unique_isbn(db_session: Session, member: Member) -> None:
    add_book(db_session, member.id)

    with pytest.raises(IntegrityError) as error:
        BookRepository(db_session).create(BookCreate(**book_payload(member_id=member.id)))

    assert violated_constraint(error.value) == BOOK_ISBN_UNIQUE


def test_foreign_key_rejects_book_for_nonexistent_member(db_session: Session) -> None:
    with pytest.raises(IntegrityError) as error:
        BookRepository(db_session).create(BookCreate(**book_payload(member_id=999)))

    assert violated_constraint(error.value) == BOOK_MEMBER_FOREIGN_KEY


def test_foreign_key_restricts_deleting_member_with_books(db_session: Session, member: Member) -> None:
    """ON DELETE RESTRICT plus passive_deletes="all" means PostgreSQL, not the
    ORM, refuses the delete, and the Book keeps its member_id."""
    book = add_book(db_session, member.id)

    with pytest.raises(IntegrityError) as error:
        MemberRepository(db_session).delete(member)

    assert violated_constraint(error.value) == BOOK_MEMBER_FOREIGN_KEY
    db_session.rollback()
    assert BookRepository(db_session).get_by_id(book.id).member_id == member.id
