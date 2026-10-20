"""SQLAlchemy model for the members table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.book import Book

# Constraint names are fixed so services can recognize which rule PostgreSQL
# rejected and report it as the matching application error.
MEMBER_EMAIL_UNIQUE = "uq_members_email"
MEMBER_MEMBERSHIP_ID_UNIQUE = "uq_members_membership_id"


class Member(Base):
    """Map Member objects to rows in the members table."""

    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("email", name=MEMBER_EMAIL_UNIQUE),
        UniqueConstraint("membership_id", name=MEMBER_MEMBERSHIP_ID_UNIQUE),
    )

    # PostgreSQL generates the primary key with an identity column.
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # 320 characters is the maximum length of an email address.
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    membership_id: Mapped[str] = mapped_column(String(20), nullable=False)
    phone: Mapped[str] = mapped_column(String(12), nullable=False)

    # The foreign key lives on Book, the "many" side of the relationship.
    # By default, deleting a Member through the ORM would first set each
    # Book's member_id to NULL. passive_deletes="all" turns that off so the
    # database's RESTRICT foreign key rejects the delete instead.
    books: Mapped[list[Book]] = relationship(back_populates="member", passive_deletes="all")
