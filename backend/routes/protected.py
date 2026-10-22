
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from controllers.auth import (
    change_password,
    delete_user,
    get_all_users,
    get_user_profile,
    update_user,
)
from database import get_db
from middleware.auth import (
    get_current_admin,
    get_current_user,
    require_self_or_admin,
)

router = APIRouter(tags=["User Management"])


class UpdateUserRequest(BaseModel):
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.get("/auth/me")
def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_profile(db, current_user["id"])


@router.get("/auth/users")
def list_users(
    _: dict = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return get_all_users(db)


@router.get("/auth/users/{user_id}")
def get_user(
    user_id: int,
    _: dict = Depends(require_self_or_admin),
    db: Session = Depends(get_db),
):
    return get_user_profile(db, user_id)


@router.put("/auth/users/{user_id}")
def edit_user(
    user_id: int,
    request: UpdateUserRequest,
    _: dict = Depends(require_self_or_admin),
    db: Session = Depends(get_db),
):
    return update_user(
        db=db,
        user_id=user_id,
        email=str(request.email) if request.email is not None else None,
    )


@router.put("/auth/users/{user_id}/password")
def edit_password(
    user_id: int,
    request: ChangePasswordRequest,
    _: dict = Depends(require_self_or_admin),
    db: Session = Depends(get_db),
):
    return change_password(
        db=db,
        user_id=user_id,
        current_password=request.current_password,
        new_password=request.new_password,
    )


@router.delete("/auth/users/{user_id}")
def remove_user(
    user_id: int,
    _: dict = Depends(require_self_or_admin),
    db: Session = Depends(get_db),
):
    return delete_user(db, user_id)
