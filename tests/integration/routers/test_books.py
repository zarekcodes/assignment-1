"""API workflow tests for Books, run once per storage backend."""

from fastapi.testclient import TestClient

from tests.helpers import book_payload, create_book, create_member


def test_create_returns_201_with_normalized_isbn(api_client: TestClient, admin_headers: dict[str, str]) -> None:
    member = create_member(api_client, admin_headers)

    response = api_client.post(
        "/books",
        json=book_payload(member["id"], isbn="978-0-13-595705-9", title="  Spaced Title  "),
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        **book_payload(member["id"], title="Spaced Title"),
        "isbn": "9780135957059",
        "id": body["id"],
    }


def test_list_and_get_return_created_books(
    api_client: TestClient, admin_headers: dict[str, str], member_headers: dict[str, str]
) -> None:
    member = create_member(api_client, admin_headers)
    first = create_book(api_client, admin_headers, member["id"])
    second = create_book(api_client, admin_headers, member["id"], isbn="0306406152")

    assert api_client.get("/books", headers=member_headers).json() == [first, second]
    response = api_client.get(f"/books/{second['id']}", headers=member_headers)
    assert response.status_code == 200
    assert response.json() == second


def test_replace_updates_book_and_can_reassign_member(api_client: TestClient, admin_headers: dict[str, str]) -> None:
    ada = create_member(api_client, admin_headers)
    grace = create_member(api_client, admin_headers, email="g@example.com", membership_id="LIB-2")
    book = create_book(api_client, admin_headers, ada["id"])
    replacement = book_payload(grace["id"], title="Refactoring", author="Martin Fowler", published_year=2018)

    response = api_client.put(f"/books/{book['id']}", json=replacement, headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {**replacement, "id": book["id"]}
    assert api_client.get(f"/members/{ada['id']}/books", headers=admin_headers).json() == []
    assert api_client.get(f"/members/{grace['id']}/books", headers=admin_headers).json() == [response.json()]


def test_replace_may_keep_the_books_own_isbn(api_client: TestClient, admin_headers: dict[str, str]) -> None:
    member = create_member(api_client, admin_headers)
    book = create_book(api_client, admin_headers, member["id"])

    response = api_client.put(
        f"/books/{book['id']}", json=book_payload(member["id"], title="Second Edition"), headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["isbn"] == book["isbn"]


def test_delete_returns_204_and_removes_book(api_client: TestClient, admin_headers: dict[str, str]) -> None:
    member = create_member(api_client, admin_headers)
    book = create_book(api_client, admin_headers, member["id"])

    response = api_client.delete(f"/books/{book['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert response.content == b""
    assert api_client.get("/books", headers=admin_headers).json() == []
    assert api_client.get(f"/members/{member['id']}/books", headers=admin_headers).json() == []
