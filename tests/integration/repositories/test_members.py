"""PostgreSQL integration tests for MemberRepository and the members table.

These use the real ORM mappings against the disposable Testcontainers
database, so they verify what mocks cannot: generated IDs, SQL queries, and
the constraints PostgreSQL itself enforces.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.errors import violated_constraint
from app.models.member import MEMBER_EMAIL_UNIQUE, MEMBER_MEMBERSHIP_ID_UNIQUE, Member
from app.repositories.members import MemberRepository
from app.schemas.members import MemberCreate, MemberUpdate
from tests.helpers import member_payload


def add_member(session: Session, **overrides: str) -> Member:
    """Insert and commit one Member through the repository."""
    member = MemberRepository(session).create(MemberCreate(**member_payload(**overrides)))
    session.commit()
    return member


def test_create_generates_increasing_ids(db_session: Session) -> None:
    first = add_member(db_session)
    second = add_member(db_session, email="b@example.com", membership_id="LIB-2")

    assert first.id > 0
    assert second.id > first.id


def test_list_all_returns_members_in_id_order(db_session: Session) -> None:
    first = add_member(db_session)
    second = add_member(db_session, email="b@example.com", membership_id="LIB-2")

    assert [member.id for member in MemberRepository(db_session).list_all()] == [first.id, second.id]


def test_lookups_find_stored_member_or_return_none(db_session: Session) -> None:
    member = add_member(db_session)
    repository = MemberRepository(db_session)

    assert repository.get_by_id(member.id) is member
    assert repository.get_by_email("ada@example.com") is member
    assert repository.get_by_membership_id("LIB-0001") is member
    assert repository.get_by_id(999) is None
    assert repository.get_by_email("nobody@example.com") is None
    assert repository.get_by_membership_id("LIB-404") is None


def test_replace_persists_new_values(db_session: Session) -> None:
    member = add_member(db_session)

    MemberRepository(db_session).replace(member, MemberUpdate(**member_payload(name="Ada King")))
    db_session.commit()
    db_session.expire_all()  # Force the next read to come from PostgreSQL.

    assert MemberRepository(db_session).get_by_id(member.id).name == "Ada King"


def test_delete_removes_row(db_session: Session) -> None:
    member = add_member(db_session)

    MemberRepository(db_session).delete(member)
    db_session.commit()

    assert MemberRepository(db_session).get_by_id(member.id) is None


@pytest.mark.parametrize(
    ("duplicate", "constraint"),
    [
        ({"membership_id": "LIB-2"}, MEMBER_EMAIL_UNIQUE),
        ({"email": "b@example.com"}, MEMBER_MEMBERSHIP_ID_UNIQUE),
    ],
    ids=["email", "membership-id"],
)
def test_database_enforces_member_unique_constraints(
    db_session: Session, duplicate: dict[str, str], constraint: str
) -> None:
    """The repository has no uniqueness check; PostgreSQL rejects the row by
    the constraint name that app/database/errors.py translates."""
    add_member(db_session)

    with pytest.raises(IntegrityError) as error:
        MemberRepository(db_session).create(MemberCreate(**member_payload(**duplicate)))

    assert violated_constraint(error.value) == constraint
