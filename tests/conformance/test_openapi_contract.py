"""Conformance tests for the published OpenAPI contract.

These start where an API consumer starts: /openapi.json. They check that the
document is valid OpenAPI, that it publishes the operations, schemas, and
statuses the Library API is designed around, and (with Schemathesis) that
generated requests receive responses matching that document.
"""

from typing import Any

import pytest
import schemathesis
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from tests.contract import assert_conforms, openapi_document
from tests.helpers import create_book, create_member, member_payload

# DOCUMENT VALIDITY


def test_generated_openapi_document_is_valid(database_client: TestClient) -> None:
    """openapi-spec-validator raises if FastAPI produced an invalid document."""
    validate(openapi_document(database_client))


# OPERATIONS AND STATUSES
# Every designed operation with its success status and the error statuses a
# client must be prepared for. 401/403 are covered in the security contract.

EXPECTED_OPERATIONS = {
    ("get", "/"): {"200"},
    ("get", "/health"): {"200"},
    ("get", "/members"): {"200"},
    ("post", "/members"): {"201", "409", "422"},
    ("get", "/members/{member_id}"): {"200", "404", "422"},
    ("put", "/members/{member_id}"): {"200", "404", "409", "422"},
    ("delete", "/members/{member_id}"): {"204", "404", "409", "422"},
    ("get", "/members/{member_id}/books"): {"200", "404", "422"},
    ("get", "/books"): {"200"},
    ("post", "/books"): {"201", "404", "409", "422"},
    ("get", "/books/{book_id}"): {"200", "404", "422"},
    ("put", "/books/{book_id}"): {"200", "404", "409", "422"},
    ("delete", "/books/{book_id}"): {"204", "404", "422"},
}


def test_document_publishes_exactly_the_designed_operations(database_client: TestClient) -> None:
    paths = openapi_document(database_client)["paths"]

    published = {(method, path) for path, operations in paths.items() for method in operations}

    assert published == set(EXPECTED_OPERATIONS)


@pytest.mark.parametrize(("method", "path"), list(EXPECTED_OPERATIONS))
def test_operation_documents_success_and_error_statuses(database_client: TestClient, method: str, path: str) -> None:
    responses = openapi_document(database_client)["paths"][path][method]["responses"]

    assert EXPECTED_OPERATIONS[(method, path)] <= set(responses)


# REQUEST AND RESPONSE SCHEMAS

REF = "#/components/schemas/{}".format
BODY_SCHEMAS = {
    ("post", "/members"): ("MemberCreate", "201", REF("MemberResponse")),
    ("put", "/members/{member_id}"): ("MemberUpdate", "200", REF("MemberResponse")),
    ("post", "/books"): ("BookCreate", "201", REF("BookResponse")),
    ("put", "/books/{book_id}"): ("BookUpdate", "200", REF("BookResponse")),
}


@pytest.mark.parametrize(("method", "path"), list(BODY_SCHEMAS))
def test_write_operations_reference_request_and_response_schemas(
    database_client: TestClient, method: str, path: str
) -> None:
    operation = openapi_document(database_client)["paths"][path][method]
    request_schema, status, response_ref = BODY_SCHEMAS[(method, path)]

    assert operation["requestBody"]["required"] is True
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {"$ref": REF(request_schema)}
    assert operation["responses"][status]["content"]["application/json"]["schema"] == {"$ref": response_ref}
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": REF("HTTPValidationError")
    }


@pytest.mark.parametrize(
    ("path", "item_schema"),
    [("/members", "MemberResponse"), ("/books", "BookResponse"), ("/members/{member_id}/books", "BookResponse")],
)
def test_collection_reads_return_arrays_of_response_schema(
    database_client: TestClient, path: str, item_schema: str
) -> None:
    schema = openapi_document(database_client)["paths"][path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    assert schema["type"] == "array"
    assert schema["items"] == {"$ref": REF(item_schema)}


@pytest.mark.parametrize(
    ("schema_name", "fields"),
    [
        ("MemberCreate", {"name", "email", "membership_id", "phone"}),
        ("MemberUpdate", {"name", "email", "membership_id", "phone"}),
        ("BookCreate", {"title", "author", "isbn", "published_year", "member_id"}),
        ("BookUpdate", {"title", "author", "isbn", "published_year", "member_id"}),
    ],
)
def test_request_schemas_require_every_field_and_forbid_extras(
    database_client: TestClient, schema_name: str, fields: set[str]
) -> None:
    schema = openapi_document(database_client)["components"]["schemas"][schema_name]

    assert set(schema["properties"]) == fields
    assert set(schema["required"]) == fields
    assert schema["additionalProperties"] is False


def test_response_schemas_add_the_server_generated_id(database_client: TestClient) -> None:
    schemas = openapi_document(database_client)["components"]["schemas"]

    for resource in ("Member", "Book"):
        response_fields = set(schemas[f"{resource}Response"]["properties"])
        assert response_fields == set(schemas[f"{resource}Create"]["properties"]) | {"id"}
        assert "id" in schemas[f"{resource}Response"]["required"]


def test_schemas_publish_the_validation_rules_clients_must_follow(database_client: TestClient) -> None:
    schemas = openapi_document(database_client)["components"]["schemas"]
    member = schemas["MemberCreate"]["properties"]
    book = schemas["BookCreate"]["properties"]

    assert (member["name"]["minLength"], member["name"]["maxLength"]) == (1, 120)
    assert member["email"]["format"] == "email"
    assert member["phone"]["pattern"] == r"^\d{3}-\d{3}-\d{4}$"
    assert (book["title"]["minLength"], book["title"]["maxLength"]) == (1, 200)
    assert (book["author"]["minLength"], book["author"]["maxLength"]) == (1, 120)
    assert book["published_year"]["minimum"] == 1450
    assert book["member_id"]["exclusiveMinimum"] == 0


# TARGETED RESPONSES AGREE WITH THE DOCUMENT


def test_successful_workflow_responses_match_their_documented_operations(
    database_client: TestClient, admin_headers: dict[str, str]
) -> None:
    client = database_client
    created = client.post("/members", json=member_payload(), headers=admin_headers)
    assert_conforms(client, "POST", "/members", created)
    member_id = created.json()["id"]
    book = create_book(client, admin_headers, member_id)

    checks = [
        ("GET", "/members", client.get("/members", headers=admin_headers)),
        ("GET", "/members/{member_id}", client.get(f"/members/{member_id}", headers=admin_headers)),
        ("GET", "/members/{member_id}/books", client.get(f"/members/{member_id}/books", headers=admin_headers)),
        ("GET", "/books/{book_id}", client.get(f"/books/{book['id']}", headers=admin_headers)),
        ("DELETE", "/books/{book_id}", client.delete(f"/books/{book['id']}", headers=admin_headers)),
        ("DELETE", "/members/{member_id}", client.delete(f"/members/{member_id}", headers=admin_headers)),
    ]
    for method, path, response in checks:
        assert response.is_success
        assert_conforms(client, method, path, response)


def test_conflict_response_matches_its_documented_operation(
    database_client: TestClient, admin_headers: dict[str, str]
) -> None:
    member = create_member(database_client, admin_headers)
    create_book(database_client, admin_headers, member["id"])

    response = database_client.delete(f"/members/{member['id']}", headers=admin_headers)

    assert response.status_code == 409
    assert_conforms(database_client, "DELETE", "/members/{member_id}", response)


# SCHEMA-DRIVEN TESTING WITH SCHEMATHESIS


@pytest.fixture
def openapi_schema(database_client: TestClient) -> Any:
    """Load the contract from the running app after the test database is ready."""
    from app.main import app

    return schemathesis.openapi.from_asgi("/openapi.json", app)


# from_fixture defers loading until a test runs, so Testcontainers and the
# environment are configured first. Only safe, read-only GET operations are
# selected: generated writes would need hand-built valid relationships and
# would mostly exercise 422 paths already covered by explicit tests.
schema = schemathesis.pytest.from_fixture("openapi_schema").include(method="GET")


@schema.parametrize()
def test_generated_reads_conform_to_openapi(
    case: Any,
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Schemathesis generates path IDs (valid, zero, negative, huge) and checks
    each response's status, headers, and body against /openapi.json."""
    case.call_and_validate(
        session=database_client,
        headers=admin_headers,
        # Known framework limitation, not a Library API design choice: Starlette
        # registers each method as its own route, so a 405 for OPTIONS
        # /books/1 lists only the first matching route (Allow: GET) instead of
        # every documented method (GET, PUT, DELETE). Every other default check
        # (status codes, response schemas, headers, content type) still runs.
        excluded_checks=[schemathesis.checks.allow_header_conformance],
    )
