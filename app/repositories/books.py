"""Database operations for Book records."""

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.book import Book
from app.schemas.books import BookCreate, BookUpdate


class BookRepository:
    """Read and write Book rows with a SQLAlchemy Session."""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[Book]:
        statement = select(Book).order_by(Book.id)
        return list(self.session.scalars(statement))

    def list_by_member(self, member_id: int) -> list[Book]:
        statement = select(Book).where(Book.member_id == member_id).order_by(Book.id)
        return list(self.session.scalars(statement))

    def get_by_id(self, book_id: int) -> Book | None:
        return self.session.get(Book, book_id)

    def get_by_isbn(self, isbn: str) -> Book | None:
        statement = select(Book).where(Book.isbn == isbn)
        return self.session.scalars(statement).first()

    def exists_for_member(self, member_id: int) -> bool:
        # EXISTS stops at the first matching row instead of loading every Book.
        statement = select(exists().where(Book.member_id == member_id))
        return bool(self.session.scalar(statement))

    def create(self, data: BookCreate) -> Book:
        book = Book(**data.model_dump())
        self.session.add(book)
        # Flush sends the INSERT and makes the generated ID available.
        self.session.flush()
        return book

    def replace(self, book: Book, data: BookUpdate) -> Book:
        for field, value in data.model_dump().items():
            setattr(book, field, value)
        self.session.flush()
        return book

    def delete(self, book: Book) -> None:
        self.session.delete(book)
        self.session.flush()
