"""Relational-database Member service implementation."""

from sqlalchemy.orm import Session, sessionmaker

from app.database.errors import translate_integrity_errors
from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
    MembershipIdAlreadyExistsError,
)
from app.models.book import BOOK_MEMBER_FOREIGN_KEY, Book
from app.models.member import MEMBER_EMAIL_UNIQUE, MEMBER_MEMBERSHIP_ID_UNIQUE, Member
from app.repositories.books import BookRepository
from app.repositories.members import MemberRepository
from app.schemas.members import MemberCreate, MemberUpdate
from .base import MemberService

# From a Member write's point of view, a foreign-key violation can only mean
# that Books still reference the Member being deleted.
_CONSTRAINT_ERRORS = {
    MEMBER_EMAIL_UNIQUE: MemberEmailAlreadyExistsError,
    MEMBER_MEMBERSHIP_ID_UNIQUE: MembershipIdAlreadyExistsError,
    BOOK_MEMBER_FOREIGN_KEY: MemberHasBooksError,
}


class DatabaseMemberService(MemberService):
    """Implement Member use cases with PostgreSQL persistence.

    The service applies Library rules and owns each transaction boundary.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        # Share the factory; each operation creates and closes its own Session.
        self._session_factory = session_factory

    def list_members(self) -> list[Member]:
        with self._session_factory() as session:
            return MemberRepository(session).list_all()

    def get_member(self, member_id: int) -> Member:
        with self._session_factory() as session:
            member = MemberRepository(session).get_by_id(member_id)
            if member is None:
                raise MemberNotFoundError
            return member

    def create_member(self, data: MemberCreate) -> Member:
        # begin() commits when the block finishes and rolls back if an
        # exception escapes, so the checks and INSERT succeed or fail together.
        with translate_integrity_errors(_CONSTRAINT_ERRORS), self._session_factory.begin() as session:
            repository = MemberRepository(session)
            _ensure_unique(repository, data)
            member = repository.create(data)
            session.refresh(member)
            return member

    def replace_member(self, member_id: int, data: MemberUpdate) -> Member:
        with translate_integrity_errors(_CONSTRAINT_ERRORS), self._session_factory.begin() as session:
            repository = MemberRepository(session)
            member = repository.get_by_id(member_id)
            if member is None:
                raise MemberNotFoundError
            _ensure_unique(repository, data, current_id=member_id)
            updated_member = repository.replace(member, data)
            session.refresh(updated_member)
            return updated_member

    def delete_member(self, member_id: int) -> None:
        # The related-Books check and the DELETE share one transaction.
        with translate_integrity_errors(_CONSTRAINT_ERRORS), self._session_factory.begin() as session:
            repository = MemberRepository(session)
            member = repository.get_by_id(member_id)
            if member is None:
                raise MemberNotFoundError
            if BookRepository(session).exists_for_member(member_id):
                raise MemberHasBooksError
            repository.delete(member)

    def list_member_books(self, member_id: int) -> list[Book]:
        with self._session_factory() as session:
            if MemberRepository(session).get_by_id(member_id) is None:
                raise MemberNotFoundError
            return BookRepository(session).list_by_member(member_id)


def _ensure_unique(
    repository: MemberRepository,
    data: MemberCreate | MemberUpdate,
    current_id: int | None = None,
) -> None:
    """Raise when another Member already uses the email or membership ID.

    current_id lets a Member keep its own values during a replacement.
    """
    existing = repository.get_by_email(data.email)
    if existing is not None and existing.id != current_id:
        raise MemberEmailAlreadyExistsError
    existing = repository.get_by_membership_id(data.membership_id)
    if existing is not None and existing.id != current_id:
        raise MembershipIdAlreadyExistsError
