"""FastAPI dependencies that authenticate Bearer tokens and enforce roles.

Security decisions live here, at the HTTP boundary. Routes declare
``CurrentUser`` (any valid token) or ``AdminUser`` (administrator only), and
the Book and Member services never see credentials or roles.
"""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.users import AuthenticatedUser, Role, get_user_for_token
from app.config import Settings
from app.dependencies import get_settings
from app.schemas.errors import ErrorResponse

# HTTPBearer reads "Authorization: Bearer <token>" and publishes the HTTP
# Bearer security scheme in OpenAPI, which adds Swagger UI's Authorize button.
# auto_error=False returns None for a missing or non-Bearer header instead of
# FastAPI's default error, so get_current_user produces one consistent 401.
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuthentication",
    description="Use the classroom member or administrator token from .env.",
)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
AppSettings = Annotated[Settings, Depends(get_settings)]

UNAUTHORIZED_DETAIL = "Missing or invalid Bearer token"
FORBIDDEN_DETAIL = "Administrator role required"

# Routers reuse these so the OpenAPI document describes exactly the security
# outcomes that the dependencies below produce at runtime.
UNAUTHORIZED_RESPONSE: dict[str, Any] = {
    "model": ErrorResponse,
    "description": UNAUTHORIZED_DETAIL,
    "headers": {
        "WWW-Authenticate": {
            "description": "The authentication scheme the client must use (Bearer).",
            "schema": {"type": "string"},
        }
    },
}
FORBIDDEN_RESPONSE: dict[str, Any] = {"model": ErrorResponse, "description": FORBIDDEN_DETAIL}
AUTHENTICATED_RESPONSES: dict[int | str, dict[str, Any]] = {401: UNAUTHORIZED_RESPONSE}
ADMIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: UNAUTHORIZED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
}


def unauthenticated() -> HTTPException:
    """Build the 401 response with the Bearer challenge required by RFC 6750."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=UNAUTHORIZED_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(credentials: BearerCredentials, settings: AppSettings) -> AuthenticatedUser:
    """Authenticate the request's Bearer token and return its identity.

    Missing headers, other schemes such as Basic, and unknown tokens all
    receive the same 401 so a client cannot probe which part was wrong.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthenticated()
    user = get_user_for_token(credentials.credentials, settings)
    if user is None:
        raise unauthenticated()
    return user


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_admin(current_user: CurrentUser) -> AuthenticatedUser:
    """Allow only an authenticated administrator to continue.

    Authentication (who are you?) has already succeeded, so a member gets 403
    rather than 401: the server knows who is calling and refuses that role.
    """
    if current_user.role is not Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_DETAIL)
    return current_user


AdminUser = Annotated[AuthenticatedUser, Depends(require_admin)]
