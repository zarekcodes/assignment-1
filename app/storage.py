"""Temporary in-memory storage shared by the API routers."""

from app.schemas.books import BookResponse
from app.schemas.members import MemberResponse

# These lists reset whenever the application restarts. Assignment 2 replaces
# them with SQLAlchemy and a relational database.
members: list[MemberResponse] = [
    MemberResponse(
        id=1,
        name="Ada Lovelace",
        email="ada@example.com",
        membership_id="LIB-0001",
        phone="555-123-4567",
    )
]

books: list[BookResponse] = [
    BookResponse(
        id=1,
        title="The Pragmatic Programmer",
        author="David Thomas",
        isbn="9780135957059",
        published_year=2019,
        member_id=1,
    )
]
