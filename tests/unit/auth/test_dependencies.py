"""Unit tests for the authentication and authorization dependencies.

The dependency functions are plain Python, so these tests call them directly
with the objects FastAPI would normally inject. No app, HTTP, or database.
"""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user, require_admin
from app.auth.users import AuthenticatedUser, Role, get_token_for_role
from app.config import Settings


def bearer(token: str, scheme: str = "Bearer") -> HTTPAuthorizationCredentials:
    """Build the object FastAPI's HTTPBearer yields for an Authorization header."""
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


# AUTHENTICATION: who is calling?


@pytest.mark.parametrize("role", list(Role))
def test_valid_token_authenticates_its_role(test_settings: Settings, role: Role) -> None:
    user = get_current_user(bearer(get_token_for_role(role, test_settings)), test_settings)

    assert user.role is role


@pytest.mark.parametrize(
    "credentials",
    [None, bearer("unknown-token"), bearer("test-admin-token", scheme="Basic")],
    ids=["missing", "unknown-token", "non-bearer-scheme"],
)
def test_missing_or_invalid_credentials_raise_401_with_bearer_challenge(
    test_settings: Settings, credentials: HTTPAuthorizationCredentials | None
) -> None:
    with pytest.raises(HTTPException) as error:
        get_current_user(credentials, test_settings)

    assert error.value.status_code == 401
    assert error.value.detail == "Missing or invalid Bearer token"
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


# AUTHORIZATION: may this caller do this?


def test_admin_passes_the_admin_requirement() -> None:
    admin = AuthenticatedUser(username="admin", role=Role.ADMIN)

    assert require_admin(admin) is admin


def test_member_is_forbidden_from_admin_operations() -> None:
    member = AuthenticatedUser(username="member", role=Role.MEMBER)

    with pytest.raises(HTTPException) as error:
        require_admin(member)

    assert error.value.status_code == 403
    assert error.value.detail == "Administrator role required"
