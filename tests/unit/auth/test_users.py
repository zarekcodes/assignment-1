"""Unit tests for the token-to-role mapping."""

import pytest

from app.auth.users import AuthenticatedUser, Role, get_token_for_role, get_user_for_token
from app.config import Settings, StorageBackend


@pytest.mark.parametrize("role", list(Role))
def test_each_configured_token_maps_to_its_predefined_role(test_settings: Settings, role: Role) -> None:
    token = get_token_for_role(role, test_settings)

    assert get_user_for_token(token, test_settings) == AuthenticatedUser(username=role.value, role=role)


@pytest.mark.parametrize(
    "token",
    ["", "unknown-token", "test-admin-token ", "TEST-ADMIN-TOKEN", "test-admin"],
    ids=["empty", "unknown", "trailing-space", "wrong-case", "prefix"],
)
def test_tokens_must_match_exactly(test_settings: Settings, token: str) -> None:
    """Near misses are not partial matches: case, prefixes, and spaces count."""
    assert get_user_for_token(token, test_settings) is None


def test_mapping_follows_settings_rather_than_hard_coded_values() -> None:
    """Changing the configured tokens changes which credentials authenticate."""
    settings = Settings(storage_backend=StorageBackend.MEMORY, demo_member_token="m-1", demo_admin_token="a-1")

    assert get_user_for_token("a-1", settings).role is Role.ADMIN
    assert get_user_for_token("test-admin-token", settings) is None
