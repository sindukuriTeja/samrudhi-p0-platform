"""Auth routes — human login for the control room."""
from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Form
from pydantic import BaseModel

from backend.core.auth import authenticate_user, create_access_token
from config.settings import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=Token)
async def login(
    username: str | None = Form(default=None),
    password: str | None = Form(default=None),
    json_login: LoginRequest | None = None,
) -> Token:
    """Login with username/password. Returns JWT.

    Accepts either form-encoded (OAuth2 standard) or JSON body.
    """
    if json_login is not None:
        username = json_login.username
        password = json_login.password
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username and password required",
        )
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return Token(access_token=access_token, role=user["role"])
