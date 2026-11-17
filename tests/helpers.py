"""Request bodies and API helpers shared by the test modules.

Each builder returns a fresh dict, so a test can change one field without
affecting another test. Keyword overrides keep each test focused on the one
value it is about.
"""

from typing import Any

from fastapi.testclient import TestClient


def member_payload(**overrides: Any) -> dict[str, Any]:
    """Return a valid Member request body."""
    return {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "membership_id": "LIB-0001",
        "phone": "555-123-4567",
        **overrides,
    }


def book_payload(member_id: int, **overrides: Any) -> dict[str, Any]:
    """Return a valid Book request body borrowed by member_id."""
    return {
        "title": "The Pragmatic Programmer",
        "author": "David Thomas",
        "isbn": "9780135957059",
        "published_year": 2019,
        "member_id": member_id,
        **overrides,
    }


def create_member(client: TestClient, admin_headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    """Create a Member through the public API and return its response body."""
    response = client.post("/members", json=member_payload(**overrides), headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def create_book(
    client: TestClient,
    admin_headers: dict[str, str],
    member_id: int,
    **overrides: Any,
) -> dict[str, Any]:
    """Create a Book through the public API and return its response body."""
    response = client.post("/books", json=book_payload(member_id, **overrides), headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def snapshot(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """Capture every Member and Book so a test can prove nothing changed."""
    return {
        "members": client.get("/members", headers=headers).json(),
        "books": client.get("/books", headers=headers).json(),
    }
