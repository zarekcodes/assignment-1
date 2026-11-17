"""Persistence behavior that intentionally differs between storage backends.

"Restarting the API" here means leaving one TestClient context (lifespan
shutdown) and entering a new one (lifespan startup), which is exactly what
stopping and starting Uvicorn does to application state.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import StorageBackend
from tests.helpers import create_book, create_member


def test_database_backend_keeps_data_across_api_restart(
    database_env: None, admin_headers: dict[str, str]
) -> None:
    from app.main import app

    with TestClient(app) as before_restart:
        member = create_member(before_restart, admin_headers)
        book = create_book(before_restart, admin_headers, member["id"])

    with TestClient(app) as after_restart:
        assert after_restart.get("/members", headers=admin_headers).json() == [member]
        assert after_restart.get(f"/members/{member['id']}/books", headers=admin_headers).json() == [book]


def test_memory_backend_starts_empty_after_api_restart(
    monkeypatch: pytest.MonkeyPatch, admin_headers: dict[str, str]
) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", StorageBackend.MEMORY.value)
    from app.main import app

    with TestClient(app) as before_restart:
        create_member(before_restart, admin_headers)

    with TestClient(app) as after_restart:
        assert after_restart.get("/members", headers=admin_headers).json() == []
