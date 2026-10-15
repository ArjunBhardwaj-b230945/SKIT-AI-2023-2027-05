
import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_change_me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))

# Temporary in-memory storage. Data resets whenever the server restarts.
users = []
next_user_id = 1


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email_format(email: str) -> bool:
    email = normalize_email(email)
    return (
        "@" in email
        and "." in email.rsplit("@", 1)[-1]
        and " " not in email
    )


def validate_password(password: str) -> None:
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least 6 characters",
        )


def validate_user_data(email: str, password: str) -> None:
    if not is_valid_email_format(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address",
        )
    validate_password(password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def find_user_by_email(email: str):
    normalized = normalize_email(email)
    return next(
        (user for user in users if user["email"] == normalized),
        None,
    )


def find_user_by_id(user_id: int):
    return next(
        (user for user in users if user["id"] == user_id),
        None,
    )


def serialize_user(user: dict) -> dict:
    """Return public user fields without exposing the password hash."""
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"],
    }


def create_user(email: str, password: str, role: str = "user") -> dict:
    global next_user_id

    validate_user_data(email, password)
    email = normalize_email(email)

    if find_user_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    if role not in {"user", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    user = {
        "id": next_user_id,
        "email": email,
        "password": hash_password(password),
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    users.append(user)
    next_user_id += 1
    return serialize_user(user)


def signup_user(email: str, password: str) -> dict:
    # Public signup never accepts a role from the client.
    return create_user(email=email, password=password, role="user")


def create_access_token(user: dict) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRES_MINUTES),
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def login_user(email: str, password: str) -> dict:
    user = find_user_by_email(email)

    if not user or not verify_password(password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


def get_user_profile(user_id: int) -> dict:
    user = find_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return serialize_user(user)


def get_all_users() -> list:
    return [serialize_user(user) for user in users]


def update_user(user_id: int, email: str | None = None) -> dict:
    user = find_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if email is not None:
        if not is_valid_email_format(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email address",
            )

        normalized = normalize_email(email)
        existing = find_user_by_email(normalized)

        if existing and existing["id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

        user["email"] = normalized

    return serialize_user(user)


def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
) -> dict:
    user = find_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not verify_password(current_password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    validate_password(new_password)
    user["password"] = hash_password(new_password)

    return {"message": "Password updated successfully"}


def delete_user(user_id: int) -> dict:
    user = find_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    users.remove(user)
    return {"message": "User deleted successfully"}
