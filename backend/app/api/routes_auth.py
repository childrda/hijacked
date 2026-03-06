"""Login/logout using HttpOnly session cookie."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.auth import (
    verify_login,
    user_role,
    create_access_token,
    get_current_user,
    SESSION_COOKIE_NAME,
)
from app.config import get_settings
from app.db.models import AuditLog
from app.db.session import get_db
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str


def _safe_actor(username: str, max_len: int = 64) -> str:
    """Truncate username for audit logs to avoid logging accidentally pasted passwords."""
    return (username or "")[:max_len]


def _client_ip(request: Request) -> str:
    """Client IP for logging; respects X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or ""
    return ""


def _is_new_login_location(db: Session, actor: str, client_ip: str) -> bool:
    """True if this actor has never had a successful login from this IP before."""
    if not client_ip:
        return False
    try:
        rows = (
            db.query(AuditLog)
            .filter(
                AuditLog.actor == actor,
                AuditLog.action == "AUTH_LOGIN",
                AuditLog.result == "success",
            )
            .all()
        )
        for row in rows:
            if (row.payload_summary or {}).get("client_ip") == client_ip:
                return False
        return True
    except OperationalError:
        return True  # e.g. audit_log missing in old DB; treat as new location


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        if not verify_login(body.username, body.password):
            log_audit(db, actor=_safe_actor(body.username), action="AUTH_LOGIN", result="fail", error="invalid_credentials")
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except HTTPException:
        raise
    except Exception:
        log_audit(db, actor=_safe_actor(body.username), action="AUTH_LOGIN", result="fail", error="login_error")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    actor = _safe_actor(body.username)
    client_ip = _client_ip(request)
    new_location = _is_new_login_location(db, actor, client_ip)

    role = user_role(body.username)
    token = create_access_token(data={"sub": body.username, "role": role})
    s = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(hours=s.session_expiry_hours)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=s.is_prod,
        samesite="strict",
        expires=expires,
        path="/",
    )
    log_audit(
        db,
        actor=actor,
        action="AUTH_LOGIN",
        result="success",
        payload_summary={"role": role, "client_ip": client_ip, "new_location": new_location},
    )
    if new_location and client_ip:
        log_audit(
            db,
            actor=actor,
            action="AUTH_LOGIN_NEW_LOCATION",
            result="success",
            payload_summary={"client_ip": client_ip},
        )
    return LoginResponse(username=body.username, role=role)


@router.post("/logout")
def logout(response: Response, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    log_audit(db, actor=user.get("username", "unknown"), action="AUTH_LOGOUT", result="success")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"username": user.get("username"), "role": user.get("role")}
