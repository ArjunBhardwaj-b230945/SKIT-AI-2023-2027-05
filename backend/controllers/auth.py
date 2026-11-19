
import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be configured in .env")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_password(password: str) -> None:
    if len(password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters",
        )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def find_user_by_email(db: Session, email: str):
    statement = select(User).where(
        User.email == normalize_email(email)
    )
    return db.scalar(statement)


def find_user_by_id(db: Session, user_id: int):
    return db.get(User, user_id)


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }


def create_user(
    db: Session,
    email: str,
    password: str,
    role: str = "user",
) -> dict:
    email = normalize_email(email)
    validate_password(password)

    if find_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    if role not in {"user", "admin"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid role",
        )

    user = User(
        email=email,
        password=hash_password(password),
        role=role,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        # A unique constraint also protects against concurrent signups.
        if find_user_by_email(db, email):
            raise HTTPException(
                status_code=409,
                detail="Email is already registered",
            )
        raise

    return serialize_user(user)


def signup_user(db: Session, email: str, password: str) -> dict:
    # Never let public signup assign an administrative role.
    return create_user(db, email, password, role="user")


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRES_MINUTES),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def login_user(db: Session, email: str, password: str) -> dict:
    user = find_user_by_email(db, email)

    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


def get_user_profile(db: Session, user_id: int) -> dict:
    user = find_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return serialize_user(user)


def get_all_users(db: Session) -> list[dict]:
    statement = select(User).order_by(User.id)
    return [serialize_user(user) for user in db.scalars(statement).all()]


def update_user(
    db: Session,
    user_id: int,
    email: str | None = None,
) -> dict:
    user = find_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if email is not None:
        email = normalize_email(email)
        existing = find_user_by_email(db, email)

        if existing and existing.id != user_id:
            raise HTTPException(
                status_code=409,
                detail="Email is already registered",
            )

        user.email = email

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return serialize_user(user)


def change_password(
    db: Session,
    user_id: int,
    current_password: str,
    new_password: str,
) -> dict:
    user = find_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(current_password, user.password):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    validate_password(new_password)
    user.password = hash_password(new_password)

    db.commit()

    return {"message": "Password updated successfully"}


def delete_user(db: Session, user_id: int) -> dict:
    user = find_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}
