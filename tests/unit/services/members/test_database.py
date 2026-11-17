"""Unit tests for DatabaseMemberService decisions, using mocked repositories."""

import pytest
from mockito import verify, when

import app.services.members.database as database_module
from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
    MembershipIdAlreadyExistsError,
)
from app.models.book import BOOK_MEMBER_FOREIGN_KEY
from app.models.member import MEMBER_EMAIL_UNIQUE, Member
from app.schemas.members import MemberCreate, MemberUpdate
from app.services.members import DatabaseMemberService
from tests.helpers import member_payload
from tests.fakes import FakeDatabase, integrity_error


@pytest.fixture
def service(fake_database: FakeDatabase) -> DatabaseMemberService:
    """Make the service module build the fake repositories.

    The service constructs repositories itself (``MemberRepository(session)``),
    so the module attribute is patched. The fake_database fixture's unstub()
    restores the real classes after the test.
    """
    db = fake_database
    when(database_module).MemberRepository(db.session).thenReturn(db.member_repository)
    when(database_module).BookRepository(db.session).thenReturn(db.book_repository)
    return DatabaseMemberService(db.factory)


def stored_member(member_id: int = 1, **overrides: str) -> Member:
    return Member(id=member_id, **member_payload(**overrides))


# READS


def test_get_member_returns_repository_result_using_a_read_session(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    member = stored_member()
    when(fake_database.member_repository).get_by_id(1).thenReturn(member)

    assert service.get_member(1) is member
    verify(fake_database.factory, times=1).__call__()
    verify(fake_database.factory, times=0).begin()


def test_get_member_translates_missing_row_to_not_found(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    when(fake_database.member_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(MemberNotFoundError):
        service.get_member(999)


def test_list_member_books_checks_member_before_querying_books(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    with pytest.raises(MemberNotFoundError):
        service.list_member_books(999)

    verify(fake_database.book_repository, times=0).list_by_member(...)


# CREATE AND REPLACE


def test_create_member_inserts_inside_one_transaction(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    member = stored_member()
    when(fake_database.member_repository).create(...).thenReturn(member)

    assert service.create_member(MemberCreate(**member_payload())) is member
    verify(fake_database.factory, times=1).begin()
    verify(fake_database.member_repository, times=1).create(...)
    verify(fake_database.session, times=1).refresh(member)


def test_create_member_rejects_duplicate_email_without_inserting(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    when(fake_database.member_repository).get_by_email("ada@example.com").thenReturn(stored_member(5))

    with pytest.raises(MemberEmailAlreadyExistsError):
        service.create_member(MemberCreate(**member_payload()))

    verify(fake_database.member_repository, times=0).create(...)


def test_create_member_rejects_duplicate_membership_id_without_inserting(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    when(fake_database.member_repository).get_by_membership_id("LIB-0001").thenReturn(stored_member(5))

    with pytest.raises(MembershipIdAlreadyExistsError):
        service.create_member(MemberCreate(**member_payload()))

    verify(fake_database.member_repository, times=0).create(...)


def test_replace_member_allows_member_to_keep_its_own_email(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    member = stored_member()
    when(fake_database.member_repository).get_by_id(1).thenReturn(member)
    when(fake_database.member_repository).get_by_email("ada@example.com").thenReturn(member)
    when(fake_database.member_repository).replace(member, ...).thenReturn(member)

    assert service.replace_member(1, MemberUpdate(**member_payload(name="Ada King"))) is member
    verify(fake_database.member_repository, times=1).replace(member, ...)


def test_replace_missing_member_raises_before_uniqueness_checks(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    with pytest.raises(MemberNotFoundError):
        service.replace_member(999, MemberUpdate(**member_payload()))

    verify(fake_database.member_repository, times=0).get_by_email(...)
    verify(fake_database.member_repository, times=0).replace(...)


def test_unique_constraint_race_is_translated_to_application_error(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    """If a concurrent request inserts the same email after the service's
    check, PostgreSQL's constraint fires; the client still gets a clean 409."""
    when(fake_database.member_repository).create(...).thenRaise(integrity_error(MEMBER_EMAIL_UNIQUE))

    with pytest.raises(MemberEmailAlreadyExistsError):
        service.create_member(MemberCreate(**member_payload()))


# DELETE


def test_delete_member_is_blocked_while_books_exist(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    when(fake_database.member_repository).get_by_id(1).thenReturn(stored_member())
    when(fake_database.book_repository).exists_for_member(1).thenReturn(True)

    with pytest.raises(MemberHasBooksError):
        service.delete_member(1)

    verify(fake_database.member_repository, times=0).delete(...)


def test_delete_member_without_books_deletes_in_a_transaction(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    member = stored_member()
    when(fake_database.member_repository).get_by_id(1).thenReturn(member)
    when(fake_database.book_repository).exists_for_member(1).thenReturn(False)

    service.delete_member(1)

    verify(fake_database.factory, times=1).begin()
    verify(fake_database.member_repository, times=1).delete(member)


def test_delete_member_translates_foreign_key_race_to_has_books(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    """A Book added between the EXISTS check and DELETE trips the RESTRICT FK."""
    member = stored_member()
    when(fake_database.member_repository).get_by_id(1).thenReturn(member)
    when(fake_database.book_repository).exists_for_member(1).thenReturn(False)
    when(fake_database.member_repository).delete(member).thenRaise(integrity_error(BOOK_MEMBER_FOREIGN_KEY))

    with pytest.raises(MemberHasBooksError):
        service.delete_member(1)


def test_delete_missing_member_raises_not_found(
    service: DatabaseMemberService, fake_database: FakeDatabase
) -> None:
    with pytest.raises(MemberNotFoundError):
        service.delete_member(999)

    verify(fake_database.book_repository, times=0).exists_for_member(...)
