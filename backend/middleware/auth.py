
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from controllers.auth import (
    JWT_ALGORITHM,
    JWT_SECRET,
    find_user_by_id,
    serialize_user,
)

bearer_scheme = HTTPBearer(auto_error=False)


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def permission_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to perform this action",
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        subject = payload.get("sub")

        if subject is None:
            raise authentication_error()

        return payload

    except JWTError:
        raise authentication_error()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise authentication_error()

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise authentication_error()

    user = find_user_by_id(user_id)

    # Also invalidates access after the user's account is deleted.
    if user is None:
        raise authentication_error()

    return serialize_user(user)


def require_role(required_role: str):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] != required_role:
            raise permission_error()
        return current_user

    return role_checker


def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "admin":
        raise permission_error()
    return current_user


def require_self_or_admin(
    user_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["id"] != user_id and current_user["role"] != "admin":
        raise permission_error()

    return current_user
