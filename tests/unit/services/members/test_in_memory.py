"""Unit tests for InMemoryMemberService business rules."""

import pytest

from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
    MembershipIdAlreadyExistsError,
)
from app.models.book import Book
from app.schemas.members import MemberCreate, MemberUpdate
from app.services.in_memory_store import InMemoryStore
from app.services.members import InMemoryMemberService
from tests.helpers import book_payload, member_payload


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def service(store: InMemoryStore) -> InMemoryMemberService:
    return InMemoryMemberService(store)


def test_create_assigns_sequential_ids_and_lists_members(service: InMemoryMemberService) -> None:
    first = service.create_member(MemberCreate(**member_payload()))
    second = service.create_member(MemberCreate(**member_payload(email="b@example.com", membership_id="LIB-2")))

    assert (first.id, second.id) == (1, 2)
    assert service.list_members() == [first, second]
    assert service.get_member(2) is second


def test_get_missing_member_raises_not_found(service: InMemoryMemberService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.get_member(999)


@pytest.mark.parametrize(
    ("duplicate", "error"),
    [
        ({"email": "ada@example.com", "membership_id": "LIB-9"}, MemberEmailAlreadyExistsError),
        ({"email": "other@example.com", "membership_id": "LIB-0001"}, MembershipIdAlreadyExistsError),
    ],
    ids=["email", "membership-id"],
)
def test_create_rejects_duplicate_unique_values(
    service: InMemoryMemberService, duplicate: dict[str, str], error: type[Exception]
) -> None:
    service.create_member(MemberCreate(**member_payload()))

    with pytest.raises(error):
        service.create_member(MemberCreate(**member_payload(**duplicate)))

    assert len(service.list_members()) == 1


def test_replace_updates_every_field_and_may_keep_own_unique_values(service: InMemoryMemberService) -> None:
    member = service.create_member(MemberCreate(**member_payload()))

    # Same email and membership ID as before: not a conflict with itself.
    updated = service.replace_member(member.id, MemberUpdate(**member_payload(name="Ada King")))

    assert updated is member
    assert updated.name == "Ada King"


def test_replace_rejects_another_members_email_without_changing_anything(
    service: InMemoryMemberService,
) -> None:
    service.create_member(MemberCreate(**member_payload()))
    second = service.create_member(MemberCreate(**member_payload(email="b@example.com", membership_id="LIB-2")))

    with pytest.raises(MemberEmailAlreadyExistsError):
        service.replace_member(second.id, MemberUpdate(**member_payload(name="Changed", membership_id="LIB-2")))

    assert second.name == "Ada Lovelace"
    assert second.email == "b@example.com"


def test_replace_missing_member_raises_not_found(service: InMemoryMemberService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.replace_member(999, MemberUpdate(**member_payload()))


def test_delete_is_blocked_while_member_has_books(store: InMemoryStore, service: InMemoryMemberService) -> None:
    member = service.create_member(MemberCreate(**member_payload()))
    store.books.append(Book(id=1, **book_payload(member_id=member.id)))

    with pytest.raises(MemberHasBooksError):
        service.delete_member(member.id)

    assert service.get_member(member.id) is member


def test_delete_removes_member_without_books(service: InMemoryMemberService) -> None:
    member = service.create_member(MemberCreate(**member_payload()))

    service.delete_member(member.id)

    assert service.list_members() == []


def test_delete_missing_member_raises_not_found(service: InMemoryMemberService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.delete_member(999)


def test_list_member_books_returns_only_that_members_books(
    store: InMemoryStore, service: InMemoryMemberService
) -> None:
    ada = service.create_member(MemberCreate(**member_payload()))
    grace = service.create_member(MemberCreate(**member_payload(email="g@example.com", membership_id="LIB-2")))
    adas_book = Book(id=1, **book_payload(member_id=ada.id))
    store.books.extend([adas_book, Book(id=2, **book_payload(member_id=grace.id, isbn="0306406152"))])

    assert service.list_member_books(ada.id) == [adas_book]


def test_list_member_books_requires_existing_member(service: InMemoryMemberService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.list_member_books(999)
