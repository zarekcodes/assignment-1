"""In-memory Book service implementation."""

from app.exceptions import BookNotFoundError, IsbnAlreadyExistsError, MemberNotFoundError
from app.models.book import Book
from app.schemas.books import BookCreate, BookUpdate
from app.services.in_memory_store import InMemoryStore
from .base import BookService


class InMemoryBookService(BookService):
    """Implement Book use cases with shared in-memory state.

    Data is process-local and is lost when the API stops.
    """

    def __init__(self, store: InMemoryStore):
        self._store = store

    def list_books(self) -> list[Book]:
        with self._store.lock:
            return list(self._store.books)

    def get_book(self, book_id: int) -> Book:
        with self._store.lock:
            for book in self._store.books:
                if book.id == book_id:
                    return book
            raise BookNotFoundError

    def create_book(self, data: BookCreate) -> Book:
        # Validate, generate the ID, and append while holding the lock.
        with self._store.lock:
            self._ensure_member_exists(data.member_id)
            self._ensure_isbn_is_unique(data.isbn)
            book = Book(
                id=max((item.id for item in self._store.books), default=0) + 1,
                **data.model_dump(),
            )
            self._store.books.append(book)
            return book

    def replace_book(self, book_id: int, data: BookUpdate) -> Book:
        with self._store.lock:
            book = self.get_book(book_id)
            self._ensure_member_exists(data.member_id)
            self._ensure_isbn_is_unique(data.isbn, current_id=book_id)
            for field, value in data.model_dump().items():
                setattr(book, field, value)
            return book

    def delete_book(self, book_id: int) -> None:
        with self._store.lock:
            self._store.books.remove(self.get_book(book_id))

    def _ensure_member_exists(self, member_id: int) -> None:
        if not any(member.id == member_id for member in self._store.members):
            raise MemberNotFoundError

    def _ensure_isbn_is_unique(self, isbn: str, current_id: int | None = None) -> None:
        if any(book.isbn == isbn and book.id != current_id for book in self._store.books):
            raise IsbnAlreadyExistsError
