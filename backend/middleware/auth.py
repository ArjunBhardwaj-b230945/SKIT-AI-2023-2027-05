
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from controllers.auth import (
    JWT_ALGORITHM,
    JWT_SECRET,
    find_user_by_id,
    serialize_user,
)
from database import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def authentication_error():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def permission_error():
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

        if not payload.get("sub"):
            raise authentication_error()

        return payload
    except JWTError:
        raise authentication_error()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    if credentials is None:
        raise authentication_error()

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise authentication_error()

    user = find_user_by_id(db, user_id)

    if user is None:
        raise authentication_error()

    return serialize_user(user)


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
