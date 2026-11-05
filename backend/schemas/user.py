from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base schema for user data."""
    email: EmailStr = Field(..., description="Unique email address for user login")


class UserCreate(UserBase):
    """Schema for user account registration."""
    password: str = Field(
        ...,
        min_length=6,
        description="User password, minimum 6 characters",
    )


class UserLogin(UserBase):
    """Schema for user authentication request."""
    password: str = Field(..., description="User password for credential verification")


class UserUpdate(BaseModel):
    """Schema for updating user profile information."""
    email: EmailStr | None = Field(
        default=None,
        description="Updated email address",
    )


class UserPasswordChange(BaseModel):
    """Schema for changing user password with verification."""
    current_password: str = Field(..., description="Current user password")
    new_password: str = Field(
        ...,
        min_length=6,
        description="New replacement password, minimum 6 characters",
    )


class UserResponse(UserBase):
    """Serialized schema for user output without sensitive information."""
    id: int
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Schema for paginated or batch user listing."""
    total: int
    users: list[UserResponse]


class Token(BaseModel):
    """Schema for JWT access token response."""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Schema for decoded JWT access token claims."""
    sub: str | None = None
    exp: int | None = None
