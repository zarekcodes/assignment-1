"""In-memory Member service implementation."""

from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
    MembershipIdAlreadyExistsError,
)
from app.models.book import Book
from app.models.member import Member
from app.schemas.members import MemberCreate, MemberUpdate
from app.services.in_memory_store import InMemoryStore
from .base import MemberService


class InMemoryMemberService(MemberService):
    """Implement Member use cases with shared in-memory state.

    Data is process-local and is lost when the API stops.
    """

    def __init__(self, store: InMemoryStore):
        self._store = store

    def list_members(self) -> list[Member]:
        with self._store.lock:
            return list(self._store.members)

    def get_member(self, member_id: int) -> Member:
        with self._store.lock:
            for member in self._store.members:
                if member.id == member_id:
                    return member
            raise MemberNotFoundError

    def create_member(self, data: MemberCreate) -> Member:
        # Check uniqueness, generate the ID, and append as one locked operation.
        with self._store.lock:
            self._ensure_unique(data)
            member = Member(
                id=max((item.id for item in self._store.members), default=0) + 1,
                **data.model_dump(),
            )
            self._store.members.append(member)
            return member

    def replace_member(self, member_id: int, data: MemberUpdate) -> Member:
        with self._store.lock:
            member = self.get_member(member_id)
            # Every check finishes before the first field changes, so a
            # rejected request never leaves a half-updated Member.
            self._ensure_unique(data, current_id=member_id)
            for field, value in data.model_dump().items():
                setattr(member, field, value)
            return member

    def delete_member(self, member_id: int) -> None:
        with self._store.lock:
            member = self.get_member(member_id)
            if any(book.member_id == member_id for book in self._store.books):
                raise MemberHasBooksError
            self._store.members.remove(member)

    def list_member_books(self, member_id: int) -> list[Book]:
        with self._store.lock:
            self.get_member(member_id)
            return [book for book in self._store.books if book.member_id == member_id]

    def _ensure_unique(self, data: MemberCreate | MemberUpdate, current_id: int | None = None) -> None:
        """Raise when another Member already uses the email or membership ID."""
        for member in self._store.members:
            if member.id == current_id:
                continue
            if member.email == data.email:
                raise MemberEmailAlreadyExistsError
            if member.membership_id == data.membership_id:
                raise MembershipIdAlreadyExistsError
