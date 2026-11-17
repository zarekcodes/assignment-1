"""Check an HTTP response against the operation published in /openapi.json.

Explicit tests assert specific outcomes ("this returns 409"). This helper adds
a second assertion: the API's own contract documents that status for that
operation, and the body matches the documented schema. If a route starts
returning an undocumented status or shape, the test fails even though the
behavior assertion still passes.
"""

from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from jsonschema import Draft202012Validator


def openapi_document(client: TestClient) -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def assert_conforms(client: TestClient, method: str, path_template: str, response: Response) -> None:
    """Assert the status is documented for this operation and the body fits its schema.

    path_template is the OpenAPI path key, such as "/members/{member_id}".
    """
    document = openapi_document(client)
    operation = document["paths"][path_template][method.lower()]
    status = str(response.status_code)
    assert status in operation["responses"], (
        f"{method} {path_template} returned {status}, which /openapi.json does not document"
    )

    content = operation["responses"][status].get("content")
    if content is None:
        # A documented body-less response, such as 204 No Content.
        assert response.content == b""
        return

    schema = content["application/json"]["schema"]
    # A "#/components/..." reference resolves against the root of the schema
    # being validated, so the document's components travel with it.
    Draft202012Validator({**schema, "components": document["components"]}).validate(response.json())
