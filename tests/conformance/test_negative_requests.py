"""Explicit negative HTTP tests: invalid input, missing resources, and broken rules.

Each test asserts three things:
1. the specific outcome (status, and which field or rule failed),
2. that /openapi.json documents that status and body shape (assert_conforms),
3. for rejected writes, that stored Library data is unchanged (snapshot).

All requests use an administrator token, so a rejection comes from
validation or a business rule, never from the security dependencies.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.schemas.ids import MAX_ID
from tests.contract import assert_conforms
from tests.helpers import book_payload, create_book, create_member, member_payload, snapshot


def assert_validation_error(response, location: list[Any], error_type: str) -> None:
    """Check FastAPI's documented 422 shape and that it names the bad input."""
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert isinstance(errors, list) and errors
    assert {"loc", "msg", "type"} <= set(errors[0])
    assert any(error["loc"] == location and error["type"] == error_type for error in errors), errors


# REQUEST-BODY VALIDATION (422)


@pytest.mark.parametrize("missing", ["name", "email", "membership_id", "phone"])
def test_create_member_rejects_missing_required_field(
    database_client: TestClient, admin_headers: dict[str, str], missing: str
) -> None:
    body = member_payload()
    body.pop(missing)

    response = database_client.post("/members", json=body, headers=admin_headers)

    assert_validation_error(response, ["body", missing], "missing")
    assert_conforms(database_client, "POST", "/members", response)
    assert database_client.get("/members", headers=admin_headers).json() == []


@pytest.mark.parametrize("missing", ["title", "author", "isbn", "published_year", "member_id"])
def test_create_book_rejects_missing_required_field(
    database_client: TestClient, admin_headers: dict[str, str], missing: str
) -> None:
    member = create_member(database_client, admin_headers)
    body = book_payload(member["id"])
    body.pop(missing)

    response = database_client.post("/books", json=body, headers=admin_headers)

    assert_validation_error(response, ["body", missing], "missing")
    assert_conforms(database_client, "POST", "/books", response)
    assert database_client.get("/books", headers=admin_headers).json() == []


@pytest.mark.parametrize(
    ("path", "body_builder"),
    [("/members", lambda member_id: member_payload()), ("/books", lambda member_id: book_payload(member_id))],
    ids=["member", "book"],
)
@pytest.mark.parametrize("unknown_field", ["id", "borrowed_at"])
def test_create_rejects_unknown_json_fields(
    database_client: TestClient, admin_headers: dict[str, str], path: str, body_builder, unknown_field: str
) -> None:
    """A client may not set the server-generated id or invent new fields."""
    member = create_member(database_client, admin_headers, email="seed@example.com", membership_id="SEED")
    before = snapshot(database_client, admin_headers)

    response = database_client.post(
        path, json={**body_builder(member["id"]), unknown_field: 1}, headers=admin_headers
    )

    assert_validation_error(response, ["body", unknown_field], "extra_forbidden")
    assert_conforms(database_client, "POST", path, response)
    assert snapshot(database_client, admin_headers) == before


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("name", "   ", "string_too_short"),
        ("name", "n" * 121, "string_too_long"),
        ("email", "not-an-email", "value_error"),
        ("membership_id", "M" * 21, "string_too_long"),
        ("phone", "5551234567", "string_pattern_mismatch"),
    ],
)
def test_member_body_rejects_invalid_field_boundaries(
    database_client: TestClient, admin_headers: dict[str, str], field: str, value: str, error_type: str
) -> None:
    response = database_client.post("/members", json=member_payload(**{field: value}), headers=admin_headers)

    assert_validation_error(response, ["body", field], error_type)
    assert_conforms(database_client, "POST", "/members", response)


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("title", "t" * 201, "string_too_long"),
        ("author", "", "string_too_short"),
        ("isbn", "12345", "string_too_short"),
        ("isbn", "123456789012", "value_error"),
        ("published_year", 1449, "greater_than_equal"),
        ("published_year", 9999, "value_error"),
        ("member_id", 0, "greater_than"),
        ("member_id", MAX_ID + 1, "less_than_equal"),
        ("member_id", "one", "int_parsing"),
    ],
)
def test_book_body_rejects_invalid_field_boundaries(
    database_client: TestClient, admin_headers: dict[str, str], field: str, value: Any, error_type: str
) -> None:
    member = create_member(database_client, admin_headers)
    body = {**book_payload(member["id"]), field: value}

    response = database_client.post("/books", json=body, headers=admin_headers)

    assert_validation_error(response, ["body", field], error_type)
    assert_conforms(database_client, "POST", "/books", response)
    assert database_client.get("/books", headers=admin_headers).json() == []


def test_replace_with_invalid_body_leaves_member_unchanged(
    database_client: TestClient, admin_headers: dict[str, str]
) -> None:
    member = create_member(database_client, admin_headers)

    response = database_client.put(
        f"/members/{member['id']}", json=member_payload(phone="not-a-phone"), headers=admin_headers
    )

    assert_validation_error(response, ["body", "phone"], "string_pattern_mismatch")
    assert_conforms(database_client, "PUT", "/members/{member_id}", response)
    assert database_client.get(f"/members/{member['id']}", headers=admin_headers).json() == member


# PATH-PARAMETER VALIDATION (422)


@pytest.mark.parametrize(
    ("method", "template", "url", "param"),
    [
        ("GET", "/members/{member_id}", "/members/abc", "member_id"),
        ("GET", "/members/{member_id}/books", "/members/1.5/books", "member_id"),
        ("DELETE", "/members/{member_id}", "/members/abc", "member_id"),
        ("GET", "/books/{book_id}", "/books/abc", "book_id"),
        ("DELETE", "/books/{book_id}", "/books/abc", "book_id"),
    ],
)
def test_non_integer_path_id_is_rejected(
    database_client: TestClient, admin_headers: dict[str, str], method: str, template: str, url: str, param: str
) -> None:
    response = database_client.request(method, url, headers=admin_headers)

    assert_validation_error(response, ["path", param], "int_parsing")
    assert_conforms(database_client, method, template, response)


@pytest.mark.parametrize(
    ("value", "error_type"),
    [(0, "greater_than"), (-1, "greater_than"), (MAX_ID + 1, "less_than_equal")],
    ids=["zero", "negative", "above-postgres-integer"],
)
def test_out_of_range_path_id_is_rejected(
    api_client: TestClient, admin_headers: dict[str, str], value: int, error_type: str
) -> None:
    """IDs PostgreSQL could never store get 422 on both backends, instead of a
    database "integer out of range" error (500) on one and 404 on the other."""
    response = api_client.get(f"/members/{value}", headers=admin_headers)

    assert_validation_error(response, ["path", "member_id"], error_type)


# MISSING RESOURCES (404)


@pytest.mark.parametrize(
    ("method", "template", "body", "detail"),
    [
        ("GET", "/members/{member_id}", None, "Member not found"),
        ("PUT", "/members/{member_id}", member_payload(email="x@example.com", membership_id="X"), "Member not found"),
        ("DELETE", "/members/{member_id}", None, "Member not found"),
        ("GET", "/members/{member_id}/books", None, "Member not found"),
        ("GET", "/books/{book_id}", None, "Book not found"),
        ("PUT", "/books/{book_id}", "valid-book", "Book not found"),
        ("DELETE", "/books/{book_id}", None, "Book not found"),
    ],
)
def test_missing_member_or_book_returns_404_without_changes(
    api_client: TestClient,
    admin_headers: dict[str, str],
    method: str,
    template: str,
    body: Any,
    detail: str,
) -> None:
    member = create_member(api_client, admin_headers)
    create_book(api_client, admin_headers, member["id"])
    before = snapshot(api_client, admin_headers)
    if body == "valid-book":
        body = book_payload(member["id"], isbn="0306406152")

    response = api_client.request(
        method, template.format(member_id=999999, book_id=999999), json=body, headers=admin_headers
    )

    assert response.status_code == 404
    assert response.json() == {"detail": detail}
    assert_conforms(api_client, method, template, response)
    assert snapshot(api_client, admin_headers) == before


# BROKEN RELATIONSHIP (404)


def test_create_book_for_nonexistent_member_returns_404(api_client: TestClient, admin_headers: dict[str, str]) -> None:
    response = api_client.post("/books", json=book_payload(999999), headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Member not found"}
    assert_conforms(api_client, "POST", "/books", response)
    assert api_client.get("/books", headers=admin_headers).json() == []


def test_reassign_book_to_nonexistent_member_returns_404_and_keeps_owner(
    api_client: TestClient, admin_headers: dict[str, str]
) -> None:
    member = create_member(api_client, admin_headers)
    book = create_book(api_client, admin_headers, member["id"])

    response = api_client.put(f"/books/{book['id']}", json=book_payload(999999), headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Member not found"}
    assert_conforms(api_client, "PUT", "/books/{book_id}", response)
    assert api_client.get(f"/books/{book['id']}", headers=admin_headers).json() == book


# DUPLICATE UNIQUE VALUES (409)


@pytest.mark.parametrize(
    ("overrides", "detail"),
    [
        ({"email": "ADA@example.com", "membership_id": "LIB-9"}, "A member with this email already exists"),
        ({"email": "other@example.com", "membership_id": "LIB-0001"}, "A member with this membership ID already exists"),
    ],
    ids=["email-any-case", "membership-id"],
)
def test_duplicate_member_values_return_409_without_changes(
    api_client: TestClient, admin_headers: dict[str, str], overrides: dict[str, str], detail: str
) -> None:
    create_member(api_client, admin_headers)
    second = create_member(api_client, admin_headers, email="second@example.com", membership_id="LIB-2")
    before = snapshot(api_client, admin_headers)

    created = api_client.post("/members", json=member_payload(**overrides), headers=admin_headers)
    replaced = api_client.put(f"/members/{second['id']}", json=member_payload(**overrides), headers=admin_headers)

    for method, template, response in [
        ("POST", "/members", created),
        ("PUT", "/members/{member_id}", replaced),
    ]:
        assert response.status_code == 409
        assert response.json() == {"detail": detail}
        assert_conforms(api_client, method, template, response)
    assert snapshot(api_client, admin_headers) == before


def test_duplicate_isbn_returns_409_without_changes(api_client: TestClient, admin_headers: dict[str, str]) -> None:
    member = create_member(api_client, admin_headers)
    create_book(api_client, admin_headers, member["id"])
    second = create_book(api_client, admin_headers, member["id"], isbn="0306406152")
    before = snapshot(api_client, admin_headers)
    # The same ISBN with hyphens normalizes to the stored value.
    duplicate = book_payload(member["id"], isbn="978-0-13-595705-9")

    created = api_client.post("/books", json=duplicate, headers=admin_headers)
    replaced = api_client.put(f"/books/{second['id']}", json=duplicate, headers=admin_headers)

    for method, template, response in [("POST", "/books", created), ("PUT", "/books/{book_id}", replaced)]:
        assert response.status_code == 409
        assert response.json() == {"detail": "A book with this ISBN already exists"}
        assert_conforms(api_client, method, template, response)
    assert snapshot(api_client, admin_headers) == before


# BLOCKED DELETION (409)


def test_deleting_member_with_books_returns_409_and_keeps_member_and_books(
    api_client: TestClient, admin_headers: dict[str, str]
) -> None:
    member = create_member(api_client, admin_headers)
    book = create_book(api_client, admin_headers, member["id"])
    before = snapshot(api_client, admin_headers)

    response = api_client.delete(f"/members/{member['id']}", headers=admin_headers)

    assert response.status_code == 409
    assert response.json() == {"detail": "Delete or reassign the member's books before deleting the member"}
    assert_conforms(api_client, "DELETE", "/members/{member_id}", response)
    assert snapshot(api_client, admin_headers) == before
    assert api_client.get(f"/members/{member['id']}/books", headers=admin_headers).json() == [book]
