
from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr, Field

from controllers.auth import login_user, signup_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest):
    return signup_user(
        email=str(request.email),
        password=request.password,
    )


@router.post("/login")
def login(request: LoginRequest):
    return login_user(
        email=str(request.email),
        password=request.password,
    )
