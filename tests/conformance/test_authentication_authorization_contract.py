"""Conformance tests for the published security contract.

Swagger UI and generated clients learn how to authenticate only from
/openapi.json, so the document must declare the Bearer scheme, mark every
protected operation, leave public operations open, and describe the 401 and
403 outcomes that the dependencies actually produce.
"""

import pytest
from fastapi.testclient import TestClient

from tests.contract import assert_conforms, openapi_document

PUBLIC_OPERATIONS = [("get", "/"), ("get", "/health")]
READ_OPERATIONS = [
    ("get", "/members"),
    ("get", "/members/{member_id}"),
    ("get", "/members/{member_id}/books"),
    ("get", "/books"),
    ("get", "/books/{book_id}"),
]
WRITE_OPERATIONS = [
    ("post", "/members"),
    ("put", "/members/{member_id}"),
    ("delete", "/members/{member_id}"),
    ("post", "/books"),
    ("put", "/books/{book_id}"),
    ("delete", "/books/{book_id}"),
]


def operation(client: TestClient, method: str, path: str) -> dict:
    return openapi_document(client)["paths"][path][method]


def test_document_declares_http_bearer_scheme(database_client: TestClient) -> None:
    schemes = openapi_document(database_client)["components"]["securitySchemes"]

    assert schemes == {
        "BearerAuthentication": {
            "type": "http",
            "scheme": "bearer",
            "description": "Use the classroom member or administrator token from .env.",
        }
    }


@pytest.mark.parametrize(("method", "path"), PUBLIC_OPERATIONS)
def test_public_operations_have_no_security_requirement(database_client: TestClient, method: str, path: str) -> None:
    documented = operation(database_client, method, path)

    assert "security" not in documented
    assert not {"401", "403"} & set(documented["responses"])


@pytest.mark.parametrize(("method", "path"), READ_OPERATIONS + WRITE_OPERATIONS)
def test_protected_operations_require_bearer_and_document_401_challenge(
    database_client: TestClient, method: str, path: str
) -> None:
    documented = operation(database_client, method, path)

    assert documented["security"] == [{"BearerAuthentication": []}]
    unauthorized = documented["responses"]["401"]
    assert "WWW-Authenticate" in unauthorized["headers"]
    assert unauthorized["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}


@pytest.mark.parametrize(("method", "path"), READ_OPERATIONS)
def test_reads_do_not_document_403(database_client: TestClient, method: str, path: str) -> None:
    """Both roles may read, so no role can be forbidden from a read."""
    assert "403" not in operation(database_client, method, path)["responses"]


@pytest.mark.parametrize(("method", "path"), WRITE_OPERATIONS)
def test_writes_document_403_for_non_administrators(database_client: TestClient, method: str, path: str) -> None:
    forbidden = operation(database_client, method, path)["responses"]["403"]

    assert forbidden["description"] == "Administrator role required"
    assert forbidden["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}


def test_actual_401_and_403_responses_match_the_document(
    database_client: TestClient, member_headers: dict[str, str]
) -> None:
    unauthorized = database_client.get("/members")
    forbidden = database_client.delete("/members/1", headers=member_headers)

    assert unauthorized.status_code == 401
    assert_conforms(database_client, "GET", "/members", unauthorized)
    assert forbidden.status_code == 403
    assert_conforms(database_client, "DELETE", "/members/{member_id}", forbidden)
