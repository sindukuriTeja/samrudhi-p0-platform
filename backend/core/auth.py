"""JWT-based authentication for the human control room.

Agents do NOT use JWT — they are identified by canonical_id and governed by
the authority guard. JWT is only for human users (website → backend).
"""
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from config.settings import get_settings

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def _hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# Demo human users (replace with real auth in production)
# Passwords hashed at import time.
_DEMO_PLAIN = "demo1234"
DEMO_USERS = {
    "vikram": {"username": "vikram", "role": "founder", "password_hash": _hash_pw(_DEMO_PLAIN)},
    "divya": {"username": "divya", "role": "client_experience_lead", "password_hash": _hash_pw(_DEMO_PLAIN)},
    "satya_human": {"username": "satya_human", "role": "assurance_lead", "password_hash": _hash_pw(_DEMO_PLAIN)},
    # An authorised contact at the demo client: may sign off that client's content at Gate 2 only.
    "client_demo": {"username": "client_demo", "role": "client_approver", "client_id": "DEMO-HEALTHCARE-01",
                    "password_hash": _hash_pw(_DEMO_PLAIN)},
}


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def authenticate_user(username: str, password: str) -> dict | None:
    user = DEMO_USERS.get(username)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {"username": user["username"], "role": user["role"]}


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = DEMO_USERS.get(username)
    if user is None:
        raise credentials_exception
    out = {"username": user["username"], "role": user["role"]}
    if user.get("client_id"):
        out["client_id"] = user["client_id"]      # a client contact acts only for their own client
    return out


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory: restrict an endpoint to specific human roles."""
    async def role_checker(
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user['role']} not allowed",
            )
        return user
    return role_checker
