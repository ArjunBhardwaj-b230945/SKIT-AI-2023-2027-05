from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, EmailStr

from controllers.auth import (
    signup_user,
    login_user,
    get_user_profile,
    get_all_users,
    update_user,
    delete_user,
    serialize_user,
)

from middleware.auth import (
    get_current_user,
    get_current_admin,
    require_self_or_admin,
)


# ============================================================
# Router Configuration
# ============================================================

router = APIRouter(
    prefix="/auth",
    tags=["User Management"]
)


# ============================================================
# Request Models
# ============================================================

class SignupRequest(BaseModel):
    """
    Data required for public user registration.
    """

    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """
    Data required for user login.
    """

    email: EmailStr
    password: str


class UpdateUserRequest(BaseModel):
    """
    Fields that a user can update through the public API.

    Role changes are intentionally excluded from this model.
    """

    email: EmailStr | None = None


# ============================================================
# Registration
# ============================================================

@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED
)
def signup(data: SignupRequest):
    """
    Register a standard user.

    Public requests cannot choose their own role.
    """

    return signup_user(
        email=data.email,
        password=data.password,
        role="user"
    )


# ============================================================
# Login
# ============================================================

@router.post(
    "/login",
    status_code=status.HTTP_200_OK
)
def login(data: LoginRequest):
    """
    Authenticate a user and issue an access token.
    """

    return login_user(
        email=data.email,
        password=data.password
    )


# ============================================================
# Current User Profile
# ============================================================

@router.get(
    "/me",
    status_code=status.HTTP_200_OK
)
def get_my_profile(
    current_user: dict = Depends(
        get_current_user
    )
):
    """
    Return the profile of the authenticated user.

    The client does not supply a user ID, so it cannot
    request another user's profile through this endpoint.
    """

    return {
        "success": True,
        "user": serialize_user(
            current_user
        )
    }


# ============================================================
# List Users - Administrator Only
# ============================================================

@router.get(
    "/users",
    status_code=status.HTTP_200_OK
)
def get_users(
    current_admin: dict = Depends(
        get_current_admin
    )
):
    """
    List registered users.

    Access is restricted to administrators.
    """

    return get_all_users()


# ============================================================
# Retrieve User By ID
# ============================================================

@router.get(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK
)
def get_profile(
    user_id: int,
    current_user: dict = Depends(
        get_current_user
    )
):
    """
    Retrieve a user profile when the requester is the
    account owner or an administrator.
    """

    require_self_or_admin(
        requested_user_id=user_id,
        current_user=current_user
    )

    return get_user_profile(
        user_id
    )


# ============================================================
# Update User
# ============================================================

@router.put(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK
)
def update_profile(
    user_id: int,
    data: UpdateUserRequest,
    current_user: dict = Depends(
        get_current_user
    )
):
    """
    Update the email of the account owner.

    Administrators may also update a user's email.
    Role changes are not exposed through this endpoint.
    """

    require_self_or_admin(
        requested_user_id=user_id,
        current_user=current_user
    )

    if data.email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one update field is required"
        )

    return update_user(
        user_id=user_id,
        email=data.email
    )


# ============================================================
# Delete User
# ============================================================

@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK
)
def delete_profile(
    user_id: int,
    current_user: dict = Depends(
        get_current_user
    )
):
    """
    Delete an account when the requester is its owner
    or an administrator.
    """

    require_self_or_admin(
        requested_user_id=user_id,
        current_user=current_user
    )

    return delete_user(
        user_id
    )