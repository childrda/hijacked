"""Simple admin auth for dev; pluggable JWT/SSO later."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.db.models import AdminUser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
bearer = HTTPBearer(auto_error=False)

SECRET_KEY = get_settings().secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def get_admin_user(db: Session, username: str) -> AdminUser | None:
    return db.execute(select(AdminUser).where(AdminUser.username == username)).scalars().first()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


async def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> str | None:
    """Return username if valid token; else None. For prod, require auth."""
    if not creds or not creds.credentials:
        if get_settings().is_prod:
            raise HTTPException(status_code=401, detail="Authentication required")
        return None
    payload = decode_token(creds.credentials)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    if not get_admin_user(db, username):
        return None
    return username


async def get_current_user(
    username: str | None = Depends(get_current_user_optional),
) -> str:
    """Require auth in prod; in dev allow anonymous."""
    if get_settings().is_prod and not username:
        raise HTTPException(status_code=401, detail="Authentication required")
    return username or "dev"
