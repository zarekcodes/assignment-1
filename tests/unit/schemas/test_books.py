"""Unit tests for the Book Pydantic schemas and every declared rule."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.models.book import Book
from app.schemas.books import EARLIEST_PUBLISHED_YEAR, BookCreate, BookResponse, BookUpdate
from app.schemas.ids import MAX_ID
from tests.helpers import book_payload

REQUEST_SCHEMAS = [BookCreate, BookUpdate]


@pytest.fixture(params=REQUEST_SCHEMAS, ids=lambda schema: schema.__name__)
def schema(request: pytest.FixtureRequest) -> type[BookCreate] | type[BookUpdate]:
    return request.param


# REQUIRED AND UNKNOWN FIELDS


@pytest.mark.parametrize("missing_field", ["title", "author", "isbn", "published_year", "member_id"])
def test_book_request_requires_each_field(schema, missing_field: str) -> None:
    data = book_payload(member_id=1)
    data.pop(missing_field)

    with pytest.raises(ValidationError) as error:
        schema(**data)

    assert error.value.errors()[0]["type"] == "missing"
    assert error.value.errors()[0]["loc"] == (missing_field,)


@pytest.mark.parametrize("unknown_field", ["id", "genre"])
def test_book_request_rejects_unknown_fields(schema, unknown_field: str) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**book_payload(member_id=1, **{unknown_field: 1}))

    assert error.value.errors()[0]["type"] == "extra_forbidden"


# TITLE AND AUTHOR


@pytest.mark.parametrize(
    ("field", "value"),
    [("title", "   "), ("title", "t" * 201), ("author", "   "), ("author", "a" * 121)],
    ids=["blank-title", "title-too-long", "blank-author", "author-too-long"],
)
def test_book_request_rejects_out_of_range_lengths(schema, field: str, value: str) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**book_payload(member_id=1, **{field: value}))

    assert error.value.errors()[0]["loc"] == (field,)


def test_book_request_trims_and_accepts_inclusive_length_limits(schema) -> None:
    book = schema(**book_payload(member_id=1, title=f"  {'t' * 200}  ", author=f" {'a' * 120} "))

    assert book.title == "t" * 200
    assert book.author == "a" * 120


# ISBN


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("978-0-13-595705-9", "9780135957059"),
        ("978 0 13 595705 9", "9780135957059"),
        ("0-306-40615-2", "0306406152"),
        ("080442957x", "080442957X"),  # A lowercase check digit is normalized.
    ],
)
def test_book_request_normalizes_valid_isbn(schema, raw: str, stored: str) -> None:
    assert schema(**book_payload(member_id=1, isbn=raw)).isbn == stored


@pytest.mark.parametrize(
    "isbn",
    ["123456789", "12345678901", "978013595705X", "X123456789", "97801359570590", "abcdefghij"],
    ids=["9-digits", "11-digits", "isbn13-with-x", "x-not-last", "14-digits", "letters"],
)
def test_book_request_rejects_invalid_isbn_shape(schema, isbn: str) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**book_payload(member_id=1, isbn=isbn))

    assert error.value.errors()[0]["loc"] == ("isbn",)


# PUBLISHED YEAR: 1450 through the current year, inclusive


def test_book_request_accepts_published_year_boundaries(schema) -> None:
    current_year = date.today().year

    assert schema(**book_payload(member_id=1, published_year=EARLIEST_PUBLISHED_YEAR)).published_year == 1450
    assert schema(**book_payload(member_id=1, published_year=current_year)).published_year == current_year


@pytest.mark.parametrize(
    "year",
    [EARLIEST_PUBLISHED_YEAR - 1, date.today().year + 1],
    ids=["before-1450", "next-year"],
)
def test_book_request_rejects_published_year_outside_range(schema, year: int) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**book_payload(member_id=1, published_year=year))

    assert error.value.errors()[0]["loc"] == ("published_year",)


# MEMBER REFERENCE


@pytest.mark.parametrize("member_id", [0, -1, MAX_ID + 1])
def test_book_request_requires_positive_member_id(schema, member_id: int) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**book_payload(member_id=member_id))

    assert error.value.errors()[0]["loc"] == ("member_id",)


def test_book_request_accepts_largest_database_id(schema) -> None:
    """MAX_ID is the PostgreSQL INTEGER maximum; anything larger cannot exist."""
    assert schema(**book_payload(member_id=MAX_ID)).member_id == MAX_ID


# RESPONSE SCHEMA


def test_book_response_reads_an_orm_book() -> None:
    source = Book(id=3, **book_payload(member_id=1))

    assert BookResponse.model_validate(source).model_dump() == {"id": 3, **book_payload(member_id=1)}
