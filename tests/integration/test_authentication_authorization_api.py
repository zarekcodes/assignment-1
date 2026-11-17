"""HTTP tests for authentication (401) and role-based authorization (403).

Security belongs at the HTTP boundary, so it is tested through TestClient:
real headers in, real status codes and challenge headers out.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import book_payload, create_book, create_member, member_payload, snapshot

READ_OPERATIONS = [
    ("GET", "/members"),
    ("GET", "/members/{member_id}"),
    ("GET", "/members/{member_id}/books"),
    ("GET", "/books"),
    ("GET", "/books/{book_id}"),
]
WRITE_OPERATIONS = [
    ("POST", "/members"),
    ("PUT", "/members/{member_id}"),
    ("DELETE", "/members/{member_id}"),
    ("POST", "/books"),
    ("PUT", "/books/{book_id}"),
    ("DELETE", "/books/{book_id}"),
]
PROTECTED_OPERATIONS = READ_OPERATIONS + WRITE_OPERATIONS


@pytest.fixture
def library(database_client: TestClient, admin_headers: dict[str, str]) -> dict[str, Any]:
    """Seed one Member with one Book so every path ID refers to real data."""
    member = create_member(database_client, admin_headers)
    book = create_book(database_client, admin_headers, member["id"])
    return {"member": member, "book": book}


def send(
    client: TestClient, method: str, path: str, library: dict[str, Any], headers: dict[str, str] | None = None
):
    """Send a valid request for one operation, filling path IDs from seed data.

    Bodies are valid and would succeed for an admin, so a 401 or 403 proves
    the security dependency (not validation or a business rule) refused it.
    """
    url = path.format(member_id=library["member"]["id"], book_id=library["book"]["id"])
    body = None
    if method in {"POST", "PUT"}:
        if path.startswith("/members"):
            body = member_payload(email="new@example.com", membership_id="LIB-NEW")
        else:
            body = book_payload(library["member"]["id"], isbn="0306406152")
    return client.request(method, url, json=body, headers=headers)


# PUBLIC ENDPOINTS


@pytest.mark.parametrize("path", ["/", "/health", "/docs", "/redoc", "/openapi.json"])
def test_root_health_and_documentation_are_public(database_client: TestClient, path: str) -> None:
    assert database_client.get(path).status_code == 200


# 401: MISSING, MALFORMED, OR UNKNOWN TOKEN


@pytest.mark.parametrize(("method", "path"), PROTECTED_OPERATIONS)
def test_every_protected_operation_requires_a_token(
    database_client: TestClient, library: dict[str, Any], method: str, path: str
) -> None:
    response = send(database_client, method, path, library)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid Bearer token"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-real-token",
        "Bearer",  # Scheme without a token.
        "test-admin-token",  # Token without a scheme.
        "Basic test-admin-token",
        "Token test-admin-token",
        "Bearer test-admin-token extra",
    ],
    ids=["unknown-token", "empty-bearer", "no-scheme", "basic-scheme", "token-scheme", "extra-segment"],
)
def test_malformed_or_unknown_authorization_receives_401(
    database_client: TestClient, library: dict[str, Any], authorization: str
) -> None:
    response = send(database_client, "GET", "/members", library, headers={"Authorization": authorization})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_bearer_scheme_name_is_case_insensitive(database_client: TestClient) -> None:
    """RFC 7235 auth schemes are case-insensitive; the token itself is not."""
    response = database_client.get("/members", headers={"Authorization": "bearer test-member-token"})

    assert response.status_code == 200


# ROLE CHECKS


@pytest.mark.parametrize("role_headers", ["member_headers", "admin_headers"])
@pytest.mark.parametrize(("method", "path"), READ_OPERATIONS)
def test_both_roles_may_read(
    database_client: TestClient,
    library: dict[str, Any],
    request: pytest.FixtureRequest,
    role_headers: str,
    method: str,
    path: str,
) -> None:
    headers = request.getfixturevalue(role_headers)

    assert send(database_client, method, path, library, headers).status_code == 200


@pytest.mark.parametrize(("method", "path"), WRITE_OPERATIONS)
def test_member_role_is_forbidden_from_every_write(
    database_client: TestClient,
    library: dict[str, Any],
    member_headers: dict[str, str],
    method: str,
    path: str,
) -> None:
    response = send(database_client, method, path, library, member_headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator role required"}


def test_role_check_runs_before_body_validation(database_client: TestClient, member_headers: dict[str, str]) -> None:
    """A member learns nothing about the write contract: 403, not 422."""
    response = database_client.post("/members", json={"unexpected": True}, headers=member_headers)

    assert response.status_code == 403


# DENIED REQUESTS DO NOT CHANGE DATA


@pytest.mark.parametrize("caller", ["anonymous", "unknown", "member"])
def test_denied_writes_leave_library_data_unchanged(
    database_client: TestClient,
    library: dict[str, Any],
    admin_headers: dict[str, str],
    member_headers: dict[str, str],
    caller: str,
) -> None:
    headers = {
        "anonymous": None,
        "unknown": {"Authorization": "Bearer not-a-real-token"},
        "member": member_headers,
    }[caller]
    before = snapshot(database_client, admin_headers)

    for method, path in WRITE_OPERATIONS:
        assert send(database_client, method, path, library, headers).status_code in {401, 403}

    assert snapshot(database_client, admin_headers) == before


# ADMINISTRATOR WRITES


@pytest.mark.parametrize(("method", "path"), WRITE_OPERATIONS)
def test_administrator_may_perform_every_write(
    database_client: TestClient,
    library: dict[str, Any],
    admin_headers: dict[str, str],
    method: str,
    path: str,
) -> None:
    if path == "/members/{member_id}" and method == "DELETE":
        # The seeded Member has a Book; remove it so the delete is allowed.
        database_client.delete(f"/books/{library['book']['id']}", headers=admin_headers)

    response = send(database_client, method, path, library, admin_headers)

    assert response.status_code == {"POST": 201, "PUT": 200, "DELETE": 204}[method]
