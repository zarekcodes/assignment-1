"""SQLAlchemy model for the books table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.member import Member

BOOK_ISBN_UNIQUE = "uq_books_isbn"
BOOK_MEMBER_FOREIGN_KEY = "fk_books_member_id_members"


class Book(Base):
    """Map Book objects to rows in the books table."""

    __tablename__ = "books"
    __table_args__ = (UniqueConstraint("isbn", name=BOOK_ISBN_UNIQUE),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    # The schema normalizes ISBNs to 10 or 13 characters before storage.
    isbn: Mapped[str] = mapped_column(String(13), nullable=False)
    published_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # RESTRICT makes PostgreSQL itself refuse to delete a Member who still has
    # Books, backing up the service-layer check with a database guarantee.
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", name=BOOK_MEMBER_FOREIGN_KEY, ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    member: Mapped[Member] = relationship(back_populates="books")
