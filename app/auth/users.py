"""Predefined classroom identities and the token-to-role mapping.

This is intentionally not a user store. Two configured Bearer tokens map to two
fixed request identities so the authentication and authorization flow stays
easy to inspect. A request *role* named "member" is unrelated to the Library
Member records stored by the API: it describes who is calling, not what data
exists.
"""

import secrets
from dataclasses import dataclass
from enum import StrEnum

from app.config import Settings


class Role(StrEnum):
    """Request roles supported by the Library permission policy."""

    MEMBER = "member"
    ADMIN = "admin"


@dataclass(frozen=True)
class AuthenticatedUser:
    """The identity and role established by a valid Bearer token."""

    username: str
    role: Role


def get_token_for_role(role: Role, settings: Settings) -> str:
    """Return the configured classroom token for one role."""
    if role is Role.ADMIN:
        return settings.demo_admin_token
    return settings.demo_member_token


def get_user_for_token(token: str, settings: Settings) -> AuthenticatedUser | None:
    """Map a presented token to its predefined identity, or None if unknown."""
    for role in (Role.ADMIN, Role.MEMBER):
        # compare_digest takes the same time whether the first or last
        # character differs, so response timing cannot leak a token prefix.
        if secrets.compare_digest(token.encode(), get_token_for_role(role, settings).encode()):
            return AuthenticatedUser(username=role.value, role=role)
    return None
