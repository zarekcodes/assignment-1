"""Unit tests for the typed application settings."""

import pytest
from pydantic import ValidationError

from app.config import Settings, StorageBackend


def test_database_backend_requires_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        Settings(storage_backend=StorageBackend.DATABASE, database_url=None)


def test_memory_backend_does_not_need_database_url() -> None:
    assert Settings(storage_backend=StorageBackend.MEMORY, database_url=None).database_url is None


@pytest.mark.parametrize("missing", ["DEMO_MEMBER_TOKEN", "DEMO_ADMIN_TOKEN"])
def test_role_tokens_are_required(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    """There is no token default in source code; startup fails without one."""
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError):
        # _env_file=None ignores a developer's .env so only the test env counts.
        Settings(_env_file=None, storage_backend=StorageBackend.MEMORY)


def test_empty_role_token_is_rejected() -> None:
    """An empty token would let an empty credential authenticate."""
    with pytest.raises(ValidationError):
        Settings(storage_backend=StorageBackend.MEMORY, demo_member_token="")


def test_role_tokens_must_differ() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        Settings(storage_backend=StorageBackend.MEMORY, demo_member_token="same", demo_admin_token="same")


def test_tokens_are_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_ADMIN_TOKEN", "from-environment")

    assert Settings(storage_backend=StorageBackend.MEMORY).demo_admin_token == "from-environment"
