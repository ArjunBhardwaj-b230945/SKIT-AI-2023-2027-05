from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from controllers.auth import (
    JWT_ALGORITHM,
    JWT_SECRET,
    find_user_by_id,
)


# ============================================================
# Authentication Configuration
# ============================================================

# Extract Bearer tokens from the Authorization header.
# auto_error=False allows us to return our own consistent
# error response when the header is missing.
bearer_scheme = HTTPBearer(
    auto_error=False
)


# ============================================================
# Authentication Error Responses
# ============================================================

def authentication_error(
    message: str = "Authentication required"
):
    """
    Create a standardized authentication exception.
    """

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )


def permission_error(
    message: str = "You do not have permission"
):
    """
    Create a standardized authorization exception.
    """

    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message
    )


# ============================================================
# Token Validation
# ============================================================

def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    The JWT library verifies the signature and expiration
    claim when decoding the token.
    """

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

        subject = payload.get("sub")

        if not subject:
            raise authentication_error(
                "Token subject is missing"
            )

        return payload

    except JWTError:
        raise authentication_error(
            "Invalid or expired access token"
        )


# ============================================================
# Current User Identification
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    )
):
    """
    Resolve the authenticated user from the Bearer token.

    The token identifies a user, but the user is also looked
    up in current storage so deleted accounts cannot continue
    accessing protected endpoints with old tokens.
    """

    if credentials is None:
        raise authentication_error()

    if credentials.scheme.lower() != "bearer":
        raise authentication_error(
            "Unsupported authentication scheme"
        )

    payload = decode_access_token(
        credentials.credentials
    )

    subject = payload.get("sub")

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise authentication_error(
            "Invalid token subject"
        )

    user = find_user_by_id(
        user_id
    )

    if user is None:
        raise authentication_error(
            "User associated with token was not found"
        )

    return user


# ============================================================
# Role-Based Authorization
# ============================================================

def require_role(required_role: str):
    """
    Build a reusable dependency for role-based access checks.

    Example:
        Depends(require_role("admin"))
    """

    def role_checker(
        current_user: dict = Depends(
            get_current_user
        )
    ):
        if current_user["role"] != required_role:
            raise permission_error(
                "Insufficient permissions"
            )

        return current_user

    return role_checker


# ============================================================
# Administrator Dependency
# ============================================================

def get_current_admin(
    current_user: dict = Depends(
        require_role("admin")
    )
):
    """
    Return the current user only if they are an administrator.
    """

    return current_user


# ============================================================
# Resource Ownership
# ============================================================

def require_self_or_admin(
    requested_user_id: int,
    current_user: dict
) -> None:
    """
    Allow access when the requester owns the resource
    or has administrator privileges.
    """

    is_owner = (
        current_user["id"] == requested_user_id
    )

    is_admin = (
        current_user["role"] == "admin"
    )

    if not (is_owner or is_admin):
        raise permission_error(
            "You can access only your own account"
        )