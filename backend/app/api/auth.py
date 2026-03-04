"""Cookie-based auth + role checks."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt

from app.config import get_settings

ALGORITHM = "HS256"
SESSION_COOKIE_NAME = "session"


def verify_login(username: str, password: str) -> bool:
    s = get_settings()
    return username == s.admin_username and password == s.admin_password


def user_role(username: str) -> str:
    s = get_settings()
    if username in s.responder_users_list:
        return "responder"
    return "viewer"


def create_access_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.session_expiry_hours)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


async def get_current_user_optional(
    request: Request,
) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    role = payload.get("role") or user_role(username)
    return {"username": username, "role": role}


async def get_current_user(
    user: dict[str, Any] | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    if get_settings().is_prod and not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user or {"username": "dev", "role": "responder"}


async def require_responder(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user.get("role") != "responder":
        raise HTTPException(status_code=403, detail="Responder role required")
    return user
