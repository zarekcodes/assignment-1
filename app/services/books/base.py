"""Abstract Book service contract."""

from abc import ABC, abstractmethod

from app.models.book import Book
from app.schemas.books import BookCreate, BookUpdate


class BookService(ABC):
    """Define Book use-case operations shared by all implementations."""

    @abstractmethod
    def list_books(self) -> list[Book]:
        """Return every Book."""

    @abstractmethod
    def get_book(self, book_id: int) -> Book:
        """Return one Book or raise BookNotFoundError."""

    @abstractmethod
    def create_book(self, data: BookCreate) -> Book:
        """Create a Book borrowed by an existing Member with a unique ISBN."""

    @abstractmethod
    def replace_book(self, book_id: int, data: BookUpdate) -> Book:
        """Replace one Book after verifying its Member and ISBN."""

    @abstractmethod
    def delete_book(self, book_id: int) -> None:
        """Delete a Book."""
