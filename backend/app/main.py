"""FastAPI app: routes, auth, polling orchestration."""
from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select

from app.config import get_settings
from app.db.session import init_db, SessionLocal
from app.db.models import Detection, PollLock
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_alerts import router as alerts_router
from app.api.routes_actions import router as actions_router
from app.api.routes_settings import router as settings_router
from app.api.routes_auth import router as auth_router
from app.api.auth import get_current_user_optional
from app.google.auth import get_credentials, SCOPES_REPORTS
from app.services.audit_service import log_audit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_secure()
    init_db()
    app.state.internal_poll_task = None
    if settings.poll_mode == "internal" and settings.poll_enabled_effective:
        app.state.internal_poll_task = asyncio.create_task(internal_poll_loop())
    yield
    task = getattr(app.state, "internal_poll_task", None)
    if task:
        task.cancel()


app = FastAPI(
    title="Workspace Security Agent",
    description="Suspicious Activity Monitor",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(alerts_router)
app.include_router(actions_router)
app.include_router(settings_router)
app.include_router(auth_router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["x-request-id"] = request_id
    return response


@app.post("/api/cron/poll")
async def cron_poll(
    request: Request,
    force: bool = Query(False),
    x_cron_key: str | None = Header(None),
    session_user: dict | None = Depends(get_current_user_optional),
):
    if force:
        if not session_user or session_user.get("role") != "responder":
            raise HTTPException(status_code=403, detail="force=true requires responder session")
    else:
        await _authorize_cron(request, x_cron_key)
    ok = await run_poll_and_notify(force=force, actor="cron")
    db = SessionLocal()
    try:
        log_audit(
            db,
            actor=(session_user or {}).get("username", "cron"),
            action="CRON_POLL",
            payload_summary={"force": force},
            result="success" if ok else "fail",
        )
    finally:
        db.close()
    if not ok:
        raise HTTPException(status_code=429, detail="poll_lock_not_acquired")
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/health")
def health():
    return healthz()


@app.get("/readyz")
def readyz():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    s = get_settings()
    if s.enable_google_workspace:
        try:
            get_credentials(SCOPES_REPORTS)
        except Exception as e:
            return JSONResponse(status_code=503, content={"status": "not_ready", "error": f"google_auth:{e}"})
    return {"status": "ready"}


async def run_poll_and_notify(*, force: bool = False, actor: str = "system") -> bool:
    """Single poll pass with lock + max-runtime guardrails."""
    acquired = _acquire_poll_lock(actor)
    if not acquired:
        return False
    try:
        await asyncio.wait_for(asyncio.to_thread(_run_poll_and_notify_sync), timeout=get_settings().poll_max_runtime_seconds)
    except asyncio.TimeoutError:
        logger.exception("Poll runtime exceeded max runtime")
    finally:
        _release_poll_lock(actor)
    return True


def _run_poll_and_notify_sync():
    """Sync job body: poll once, then send emails for detections that need it."""
    from app.ingest.poller import poll_once
    from app.services.action_service import should_send_detection_email, send_detection_notification

    db = SessionLocal()
    try:
        try:
            poll_once(db)
        except Exception as e:
            logger.exception("Poll failed: %s", e)
        # Send notifications for active detections that meet threshold and should_send
        try:
            open_detections = db.execute(
                select(Detection).where(Detection.status.in_(["NEW", "TRIAGE"]))
            ).scalars().all()
            for det in open_detections:
                if should_send_detection_email(det):
                    asyncio.run(send_detection_notification(db, det.id, action_taken=False))
        except Exception as e:
            logger.exception("Notify failed: %s", e)
    finally:
        db.close()


def _acquire_poll_lock(owner: str) -> bool:
    now = datetime.now(timezone.utc)
    settings = get_settings()
    db = SessionLocal()
    try:
        lock = db.query(PollLock).filter(PollLock.name == "poll").first()
        lock_until = lock.locked_until if lock else None
        if lock_until and lock_until.tzinfo is None:
            lock_until = lock_until.replace(tzinfo=timezone.utc)
        if lock and lock_until and lock_until > now:
            return False
        until = now + timedelta(seconds=settings.poll_lock_ttl_seconds)
        if lock:
            lock.locked_until = until
            lock.owner = owner
        else:
            db.add(PollLock(name="poll", locked_until=until, owner=owner))
        db.commit()
        return True
    finally:
        db.close()


def _release_poll_lock(owner: str) -> None:
    db = SessionLocal()
    try:
        lock = db.query(PollLock).filter(PollLock.name == "poll").first()
        if lock and lock.owner == owner:
            lock.locked_until = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


async def internal_poll_loop():
    while True:
        s = get_settings()
        interval = max(1, int(getattr(s, "poll_interval_seconds", 300) or 1))
        jitter_window = max(0, int(getattr(s, "poll_jitter_seconds", 0) or 0))
        jitter = random.randint(-jitter_window, jitter_window) if jitter_window > 0 else 0
        sleep_for = max(1, interval + jitter)
        await asyncio.sleep(sleep_for)
        await run_poll_and_notify(actor=f"internal-{uuid.uuid4()}")


async def _authorize_cron(request: Request, x_cron_key: str | None) -> None:
    s = get_settings()
    mode = s.cron_auth_mode.lower()
    if mode == "apikey":
        if not s.cron_api_key or x_cron_key != s.cron_api_key:
            raise HTTPException(status_code=401, detail="Invalid cron API key")
        return
    if mode == "oidc":
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = auth.split(" ", 1)[1]
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            audience = s.cron_oidc_audience or str(request.url).split("?")[0]
            info = id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)
            issuer = info.get("iss")
            if issuer not in {"https://accounts.google.com", "accounts.google.com"}:
                raise ValueError("invalid issuer")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid OIDC token: {e}") from e
        return
    raise HTTPException(status_code=401, detail="Unsupported cron auth mode")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
