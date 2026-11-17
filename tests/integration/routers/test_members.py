"""API workflow tests for Members, run once per storage backend.

`api_client` is parametrized in conftest.py, so each test appears twice in
the report: [database] uses PostgreSQL through Testcontainers and [memory]
uses the in-memory services. Same requests, same expected responses.
"""

from fastapi.testclient import TestClient

from tests.helpers import create_book, create_member, member_payload


def test_create_returns_201_with_generated_id_and_normalized_email(
    api_client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = api_client.post(
        "/members",
        json=member_payload(name="  Ada Lovelace  ", email="ADA@Example.com"),
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {**member_payload(), "id": body["id"]}
    assert body["id"] > 0


def test_list_and_get_return_created_members(
    api_client: TestClient, admin_headers: dict[str, str], member_headers: dict[str, str]
) -> None:
    ada = create_member(api_client, admin_headers)
    grace = create_member(api_client, admin_headers, name="Grace Hopper", email="g@example.com", membership_id="LIB-2")

    # Reads are allowed for the member role, not only the administrator.
    assert api_client.get("/members", headers=member_headers).json() == [ada, grace]
    response = api_client.get(f"/members/{grace['id']}", headers=member_headers)
    assert response.status_code == 200
    assert response.json() == grace


def test_replace_updates_member_and_later_reads_see_it(
    api_client: TestClient, admin_headers: dict[str, str]
) -> None:
    member = create_member(api_client, admin_headers)
    replacement = member_payload(name="Ada King", phone="972-555-0100")

    response = api_client.put(f"/members/{member['id']}", json=replacement, headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {**replacement, "id": member["id"]}
    assert api_client.get(f"/members/{member['id']}", headers=admin_headers).json() == response.json()


def test_delete_returns_204_and_removes_member(api_client: TestClient, admin_headers: dict[str, str]) -> None:
    member = create_member(api_client, admin_headers)

    response = api_client.delete(f"/members/{member['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert response.content == b""
    assert api_client.get(f"/members/{member['id']}", headers=admin_headers).status_code == 404


def test_member_books_lists_only_that_members_books(
    api_client: TestClient, admin_headers: dict[str, str], member_headers: dict[str, str]
) -> None:
    ada = create_member(api_client, admin_headers)
    grace = create_member(api_client, admin_headers, email="g@example.com", membership_id="LIB-2")
    first = create_book(api_client, admin_headers, ada["id"])
    create_book(api_client, admin_headers, grace["id"], isbn="0306406152")
    second = create_book(api_client, admin_headers, ada["id"], isbn="080442957X")

    response = api_client.get(f"/members/{ada['id']}/books", headers=member_headers)

    assert response.status_code == 200
    assert response.json() == [first, second]


def test_member_books_is_empty_for_member_without_books(
    api_client: TestClient, admin_headers: dict[str, str]
) -> None:
    member = create_member(api_client, admin_headers)

    assert api_client.get(f"/members/{member['id']}/books", headers=admin_headers).json() == []


def test_member_can_be_deleted_after_books_are_reassigned(
    api_client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Business rule 7: delete or reassign a Member's Books, then delete them."""
    ada = create_member(api_client, admin_headers)
    grace = create_member(api_client, admin_headers, email="g@example.com", membership_id="LIB-2")
    book = create_book(api_client, admin_headers, ada["id"])

    assert api_client.delete(f"/members/{ada['id']}", headers=admin_headers).status_code == 409

    moved = {key: value for key, value in book.items() if key != "id"} | {"member_id": grace["id"]}
    assert api_client.put(f"/books/{book['id']}", json=moved, headers=admin_headers).status_code == 200
    assert api_client.delete(f"/members/{ada['id']}", headers=admin_headers).status_code == 204
    assert api_client.get(f"/members/{grace['id']}/books", headers=admin_headers).json() == [
        {**book, "member_id": grace["id"]}
    ]
