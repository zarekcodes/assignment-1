"""Shared in-memory state for the alternative service implementations."""

from dataclasses import dataclass, field
from threading import RLock

from app.models.book import Book
from app.models.member import Member


@dataclass
class InMemoryStore:
    """Hold Members and Books for one application-scoped in-memory service pair."""

    members: list[Member] = field(default_factory=list)
    books: list[Book] = field(default_factory=list)
    # FastAPI runs plain def routes in a thread pool. One process-local lock
    # makes compound operations (checks, ID generation, list mutation) atomic.
    # It is reentrant so a locked method can call another locked method.
    lock: RLock = field(default_factory=RLock, repr=False)
