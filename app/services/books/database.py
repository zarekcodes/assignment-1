"""Relational-database Book service implementation."""

from sqlalchemy.orm import Session, sessionmaker

from app.database.errors import translate_integrity_errors
from app.exceptions import BookNotFoundError, IsbnAlreadyExistsError, MemberNotFoundError
from app.models.book import BOOK_ISBN_UNIQUE, BOOK_MEMBER_FOREIGN_KEY, Book
from app.repositories.books import BookRepository
from app.repositories.members import MemberRepository
from app.schemas.books import BookCreate, BookUpdate
from .base import BookService

# From a Book write's point of view, a foreign-key violation means the
# referenced Member was deleted after the service checked that it existed.
_CONSTRAINT_ERRORS = {
    BOOK_ISBN_UNIQUE: IsbnAlreadyExistsError,
    BOOK_MEMBER_FOREIGN_KEY: MemberNotFoundError,
}


class DatabaseBookService(BookService):
    """Implement Book use cases with PostgreSQL persistence.

    The service applies Library rules and owns each transaction boundary.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        # Share the factory; each operation creates and closes its own Session.
        self._session_factory = session_factory

    def list_books(self) -> list[Book]:
        with self._session_factory() as session:
            return BookRepository(session).list_all()

    def get_book(self, book_id: int) -> Book:
        with self._session_factory() as session:
            book = BookRepository(session).get_by_id(book_id)
            if book is None:
                raise BookNotFoundError
            return book

    def create_book(self, data: BookCreate) -> Book:
        # Verifying the parent Member and inserting the child Book are one
        # atomic use case: any failure rolls the whole transaction back.
        with translate_integrity_errors(_CONSTRAINT_ERRORS), self._session_factory.begin() as session:
            if MemberRepository(session).get_by_id(data.member_id) is None:
                raise MemberNotFoundError
            repository = BookRepository(session)
            if repository.get_by_isbn(data.isbn) is not None:
                raise IsbnAlreadyExistsError
            book = repository.create(data)
            session.refresh(book)
            return book

    def replace_book(self, book_id: int, data: BookUpdate) -> Book:
        with translate_integrity_errors(_CONSTRAINT_ERRORS), self._session_factory.begin() as session:
            repository = BookRepository(session)
            book = repository.get_by_id(book_id)
            if book is None:
                raise BookNotFoundError
            if MemberRepository(session).get_by_id(data.member_id) is None:
                raise MemberNotFoundError
            existing = repository.get_by_isbn(data.isbn)
            if existing is not None and existing.id != book_id:
                raise IsbnAlreadyExistsError
            updated_book = repository.replace(book, data)
            session.refresh(updated_book)
            return updated_book

    def delete_book(self, book_id: int) -> None:
        with self._session_factory.begin() as session:
            repository = BookRepository(session)
            book = repository.get_by_id(book_id)
            if book is None:
                raise BookNotFoundError
            repository.delete(book)
