# Workspace Security Agent – Suspicious Activity Monitor

Full-stack app that ingests Google Workspace audit events, detects suspicious mailbox changes, stores everything for analytics/retraining, and provides a UI to view flagged accounts and run containment (disable user + revoke sessions).

## Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic, APScheduler
- **DB:** PostgreSQL
- **Frontend:** React (Vite), Tailwind CSS
- **Deploy:** Docker Compose (local); Cloud Run + Cloud Scheduler (prod)

## Quick start (local)

1. **Clone and env**

   ```bash
   cd Hijacked
   cp backend/.env.example .env  # or create .env (see Config below)
   ```

2. **Run with Docker**

   ```bash
   docker compose up --build
   ```

   - Postgres: `localhost:5432`
   - Backend API: `http://localhost:8000`
   - Frontend: `http://localhost:5173`

3. **Migrations and seed (first time)**

   ```bash
   docker compose exec backend alembic -c alembic.ini upgrade head
   docker compose exec backend python -m scripts.seed_data
   ```

   Open `http://localhost:5173` to see the dashboard and sample flagged accounts.

## Config (.env)

| Variable | Description |
|----------|-------------|
| `GOOGLE_CREDENTIALS_JSON` | Service account JSON (string or path). Required when `ENABLE_GOOGLE_WORKSPACE=true` and for Google ingest. |
| `GOOGLE_WORKSPACE_ADMIN_USER` | Admin user for domain-wide delegation (e.g. `admin@domain.tld`) |
| `SUPPORT_EMAIL` | Email that receives alerts and test emails |
| `ACTION_FLAG` | `true` = run containment when triggered; `false` = record proposed actions only |
| `ENABLE_GOOGLE_WORKSPACE` | `true/false` toggle for Google containment backend |
| `ENABLE_ACTIVE_DIRECTORY` | `true/false` toggle for Active Directory containment backend |
| `AD_LDAP_URL` | AD LDAP/LDAPS endpoint (required when `ENABLE_ACTIVE_DIRECTORY=true`) |
| `AD_BIND_DN` | AD bind DN for service account (required when `ENABLE_ACTIVE_DIRECTORY=true`) |
| `AD_BIND_PASSWORD` | AD bind password (required when `ENABLE_ACTIVE_DIRECTORY=true`) |
| `AD_BASE_DN` | AD search base DN (required when `ENABLE_ACTIVE_DIRECTORY=true`) |
| `DOMAIN` | Your Workspace domain |
| `LOOKBACK_MINUTES` | Poll window (e.g. 15) |
| `SEVERITY_THRESHOLD` | Min score to treat as alert (e.g. 70) |
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@host:5432/dbname` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_USE_TLS` | SMTP for notifications |
| `APP_ENV` | `dev` or `prod` |
| `SECRET_KEY` | JWT signing key; required to be strong (>=32 chars) in prod |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins (e.g. `https://ui.example.com`) |
| `MASS_SEND_ENABLED` | Enable mass outbound email burst detection logic |
| `MASS_SEND_RECIPIENT_THRESHOLD` | Single-message recipient fanout threshold |
| `MASS_SEND_WINDOW_MINUTES` | Rolling window for burst detection |
| `MASS_SEND_MESSAGE_THRESHOLD` | Message-count threshold in rolling window |
| `MASS_SEND_UNIQUE_RECIPIENT_THRESHOLD` | Unique recipient threshold in rolling window |
| `MASS_SEND_INTERNAL_ONLY_IGNORE` | If true, ignore events where all recipients are internal domain |
| `MASS_SEND_ALLOWLIST_SENDERS` | Comma-separated exempt sender list |
| `MASS_SEND_ALLOWLIST_SUBJECT_KEYWORDS` | Optional comma-separated exempt subject keywords |
| `MASS_SEND_SEVERITY_POINTS_SINGLE` | Points added for single-message fanout rule |
| `MASS_SEND_SEVERITY_POINTS_BURST` | Points added for burst-window rule |
| `UI_BASE_URL` | Base URL for links in emails (e.g. `https://your-ui.example.com`) |

## Google Workspace setup (Domain-Wide Delegation)

1. Create a service account in Google Cloud, enable Domain-Wide Delegation, and note the client ID.
2. In Admin Console: Security → API Controls → Domain-wide delegation → Add the client ID with these scopes:
   - `https://www.googleapis.com/auth/admin.reports.audit.readonly`
   - `https://www.googleapis.com/auth/admin.directory.user`
   - `https://www.googleapis.com/auth/admin.directory.user.security`
3. Put the service account JSON in `GOOGLE_CREDENTIALS_JSON` and set `GOOGLE_WORKSPACE_ADMIN_USER` to a super-admin email.

## Running locally (no Docker)

- **Postgres:** run PostgreSQL 15, create DB and user, set `DATABASE_URL`.
- **Backend:**

  ```bash
  cd backend
  pip install -r requirements.txt
  pip install -e .
  alembic -c alembic.ini upgrade head
  python -m scripts.seed_data
  uvicorn app.main:app --reload --port 8000
  ```

  Optional: start scheduler in process (dev) or call `POST /api/cron/poll` on a schedule.

- **Frontend:**

  ```bash
  cd frontend
  npm install
  npm run dev
  ```

  Set `VITE_API_URL=http://localhost:8000` if the API is on another host.

## Deploying backend (Cloud Run + Scheduler)

1. Build and push the backend image; deploy to Cloud Run with `DATABASE_URL` (Cloud SQL or other), env vars above, and no public unauthenticated access.
2. Create a Cloud Scheduler job that calls `POST https://your-run-url/api/cron/poll` with auth (OIDC or API key). Suggested frequency: every 15 minutes (or match `LOOKBACK_MINUTES`).

## Safety: ACTION_FLAG and backend toggles

- **`ACTION_FLAG=false` (default):** Containment is **not** executed. The app records a **proposed** action and shows it in the UI and in the email. Use this until you have validated rules and workflows.
- **`ACTION_FLAG=true`:** Disable Account (single or bulk) runs only the backends you enable via config (no code changes):
  - **`ENABLE_ACTIVE_DIRECTORY=true`** (default: false): Disable the user in AD via LDAP (`userAccountControl` + ACCOUNTDISABLE). Requires `AD_LDAP_URL`, `AD_BIND_DN`, `AD_BIND_PASSWORD`, `AD_BASE_DN`. Use when Google is synced from AD so replication won’t re-enable the user.
  - **`ENABLE_GOOGLE_WORKSPACE=true`** (default: true): Suspend the user (Directory API `users.update` with `suspended=true`), force sign-out (`users.signOut`), and revoke tokens (`tokens.list` + `tokens.delete`).

You can enable one, both, or neither. All actions are stored in the `actions` table with result and details (including AD and Google steps, or “skipped” with reason when a backend is disabled).

## Mass Outbound Email Burst Detection

- Enable with `MASS_SEND_ENABLED=true`.
- Single-message fanout rule triggers when one sent message reaches `MASS_SEND_RECIPIENT_THRESHOLD`.
- Burst rule triggers in `MASS_SEND_WINDOW_MINUTES` when either:
  - `messages_sent >= MASS_SEND_MESSAGE_THRESHOLD`, or
  - `unique_recipients >= MASS_SEND_UNIQUE_RECIPIENT_THRESHOLD`.
- Optional noise reduction:
  - `MASS_SEND_INTERNAL_ONLY_IGNORE=true` ignores internal-only recipient sets.
  - `MASS_SEND_ALLOWLIST_SENDERS` exempts known bulk senders.
  - `MASS_SEND_ALLOWLIST_SUBJECT_KEYWORDS` exempts known bulk subjects.
- Correlation adds extra score when mass-send occurs near mailbox tampering events.
- UI event labels:
  - `Mass Outbound Email (Single Message)`
  - `Mass Outbound Email (Burst)`

## API overview

- `GET /api/dashboard/metrics?window=24h` – critical count, recent events, trend, agent status
- `GET /api/alerts?status=OPEN&window=24h&search=` – flagged accounts
- `POST /api/alerts/{id}/dismiss` – dismiss one
- `POST /api/alerts/bulk-dismiss` – body `{ "alert_ids": [1,2,...] }`
- `POST /api/actions/disable-account` – body `{ "alert_ids": [...], "reason": "..." }`
- `POST /api/settings/test-email` – send test email to SUPPORT_EMAIL
- `POST /api/cron/poll` – trigger poll + notify (for Cloud Scheduler)

## Email alerts

- The app sends an email to `SUPPORT_EMAIL` when a **new** detection is OPEN and score ≥ `SEVERITY_THRESHOLD`.
- Re-email only if: risk level increases, score increases by ≥ 20 since last notify, or ≥ 12 hours since last notify.
- Email is sent **after** any containment actions so the body reflects “Action Taken” or “Proposed Action”.
- Subject: `[{RISK}] Workspace Security Alert: {user_email} (Score {score})`.
- If sending fails, a row is stored in `actions` with `action_type=EMAIL_NOTIFY`, `result=FAILED`, and `notified_at` stays null so the next run can retry.

## Tests

```bash
cd backend
pip install -r requirements.txt pytest
pytest tests/ -v
```

## Project layout

- `backend/` – FastAPI app, ingest, detect, actions, notifier, API routes
- `frontend/` – React (Vite) + Tailwind, dashboard and flagged table
- `docker-compose.yml` – Postgres, backend, frontend
