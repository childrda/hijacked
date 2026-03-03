"""FastAPI app: routes, CORS, scheduler."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import init_db
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_alerts import router as alerts_router
from app.api.routes_actions import router as actions_router
from app.api.routes_settings import router as settings_router
from app.api.routes_auth import router as auth_router
from app.api.auth import get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_secure()
    init_db()
    if not settings.is_prod:
        app.state.scheduler = start_scheduler()
    yield
    if getattr(app.state, "scheduler", None):
        app.state.scheduler.shutdown(wait=False)


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


@app.post("/api/cron/poll")
def cron_poll(
    _current_user: str = Depends(get_current_user),
):
    """Cloud Scheduler (or cron) trigger: run poll and notify. Call with auth in prod."""
    run_poll_and_notify()
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}


def run_poll_and_notify():
    """Sync job: poll once, then send emails for detections that need it."""
    from app.db.session import SessionLocal
    from app.ingest.poller import poll_once
    from app.services.action_service import should_send_detection_email, send_detection_notification
    from app.db.models import Detection
    from sqlalchemy import select

    db = SessionLocal()
    try:
        try:
            poll_once(db)
        except Exception as e:
            logger.exception("Poll failed: %s", e)
        # Send notifications for OPEN detections that meet threshold and should_send
        try:
            open_detections = db.execute(
                select(Detection).where(Detection.status == "OPEN")
            ).scalars().all()
            for det in open_detections:
                if should_send_detection_email(det):
                    asyncio.run(send_detection_notification(db, det.id, action_taken=False))
        except Exception as e:
            logger.exception("Notify failed: %s", e)
    finally:
        db.close()


def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    settings = get_settings()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_poll_and_notify,
        "interval",
        minutes=max(1, settings.lookback_minutes),
        id="poll_workspace",
    )
    scheduler.start()
    return scheduler


# Optional: start scheduler when running uvicorn directly (local dev)
if __name__ == "__main__":
    import uvicorn
    app.state.scheduler = start_scheduler()
    uvicorn.run(app, host="0.0.0.0", port=8000)
