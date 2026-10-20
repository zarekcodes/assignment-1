"""Database operations for Member records."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.schemas.members import MemberCreate, MemberUpdate


class MemberRepository:
    """Read and write Member rows with a SQLAlchemy Session."""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[Member]:
        statement = select(Member).order_by(Member.id)
        return list(self.session.scalars(statement))

    def get_by_id(self, member_id: int) -> Member | None:
        return self.session.get(Member, member_id)

    def get_by_email(self, email: str) -> Member | None:
        statement = select(Member).where(Member.email == email)
        return self.session.scalars(statement).first()

    def get_by_membership_id(self, membership_id: str) -> Member | None:
        statement = select(Member).where(Member.membership_id == membership_id)
        return self.session.scalars(statement).first()

    def create(self, data: MemberCreate) -> Member:
        member = Member(**data.model_dump())
        self.session.add(member)
        # Flush sends the INSERT inside the current transaction, which makes
        # the database-generated ID available before the service commits.
        self.session.flush()
        return member

    def replace(self, member: Member, data: MemberUpdate) -> Member:
        for field, value in data.model_dump().items():
            setattr(member, field, value)
        self.session.flush()
        return member

    def delete(self, member: Member) -> None:
        self.session.delete(member)
        self.session.flush()
