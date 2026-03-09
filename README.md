# WASP – Workspace Account Security Patrol

![WASP logo](assets/wasp-logo.png)

Full-stack app that ingests Google Workspace audit events, detects suspicious mailbox changes, stores everything for analytics/retraining, and provides a UI to view flagged accounts and run containment (disable user + revoke sessions).

## Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic
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

   To build without using cache (e.g. after dependency or lockfile changes):

   ```bash
   docker compose build --no-cache
   docker compose up
   ```

   To build only the frontend (e.g. after pulling UI changes like the Status dropdown):

   ```bash
   docker compose build frontend --no-cache
   docker compose up -d
   ```

   If you see **"network mode bridge2 not supported by buildkit"**, use the legacy builder for that build:

   ```bash
   DOCKER_BUILDKIT=0 docker compose build frontend --no-cache
   docker compose up -d
   ```

   After `git pull`, run `docker compose up -d --build` (or rebuild the `frontend` service) so the browser gets the new JavaScript; otherwise you may still see the old UI.

   A **root `.dockerignore`** (and `frontend/.dockerignore`) excludes `node_modules`, `dist`, `.env`, etc. from the build context so host artifacts never get copied in and builds stay reproducible across machines.

   - Postgres: `localhost:5432`
   - Backend API: `http://localhost:8000`
   - Frontend (nginx): `http://localhost` (port 80; proxies `/api`, `/docs`, `/openapi.json` to backend)

3. **Migrations and seed (first time)**

   ```bash
   docker compose exec backend alembic -c alembic.ini upgrade head
   docker compose exec backend python -m scripts.seed_data
   ```

   Open `http://localhost` to see the dashboard and sample flagged accounts.

## Config (.env)

**Docker:** The backend reads `.env` from the **project root** (same directory as `docker-compose.yml`). If you use `backend/.env`, copy the variables you need into a root `.env` or set them in `docker-compose.yml`. After changing `RESPONDER_USERS` or other auth settings, restart the backend and **log out and log in again** so your session gets the new role.

| Variable | Description |
|----------|-------------|
| `GOOGLE_CREDENTIALS_JSON` | Service account JSON (string or path). Required when `ENABLE_GOOGLE_WORKSPACE=true` and for Google ingest. |
| `GOOGLE_WORKSPACE_ADMIN_USER` | Admin user for domain-wide delegation (e.g. `admin@domain.tld`) |
| `SUPPORT_EMAIL` | Email that receives alerts and test emails |
| `ACTION_FLAG` | When `true`, allows the *app* to take containment automatically (e.g. without admin intervention). Manual "Disable account" by a responder always runs containment regardless of this flag. |
| `ACTION_COOLDOWN_MINUTES` | Prevent repeated disable actions on same account within cooldown window |
| `SUSPENSION_RATE_LIMIT_MAX` | Max DISABLE_ACCOUNT successes in the window; circuit breaker trips above this (default 5) |
| `SUSPENSION_RATE_LIMIT_MINUTES` | Rolling window for suspension rate limit (default 60) |
| `PROTECTED_EMAILS` | Comma-separated emails that must never be suspended (e.g. `admin@mycorp.com`) |
| `PROTECTED_DOMAINS` | Comma-separated domain suffixes (e.g. `mycorp.com`) whose users are never suspended |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Internal login credentials used by `/api/auth/login` |
| `RESPONDER_USERS` | Comma-separated usernames with responder privileges |
| `SESSION_EXPIRY_HOURS` | Session cookie JWT lifetime in hours (default 8) |
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
| `CRON_AUTH_MODE` | `apikey` or `oidc` for `/api/cron/poll` authentication |
| `CRON_API_KEY` | Required when `CRON_AUTH_MODE=apikey` (sent in `X-CRON-KEY`) |
| `CRON_OIDC_AUDIENCE` | Optional explicit audience for OIDC token validation |
| `POLL_MODE` | `scheduler` (recommended prod) or `internal` |
| `POLL_ENABLED` | Poll loop switch; defaults safe for prod detect-only behavior |
| `POLL_INTERVAL_SECONDS` | Internal loop interval |
| `POLL_JITTER_SECONDS` | Random jitter for internal loop |
| `POLL_LOCK_TTL_SECONDS` | Poll lock TTL to prevent overlapping runs |
| `POLL_MAX_RUNTIME_SECONDS` | Runtime guardrail for one poll pass |
| `GMAIL_FILTER_INSPECTION_ENABLED` | Enable Gmail mailbox filter inspection (separate from audit log polling) |
| `FILTER_SCAN_ENABLED` | Run filter scan when cron/poll runs (requires FILTER_SCAN_USER_SCOPE) |
| `FILTER_SCAN_INTERVAL_SECONDS` | How often to run filter scan (default 3600 = 60 min) |
| `FILTER_SCAN_USER_SCOPE` | Comma-separated user emails to inspect (e.g. `user1@domain.com,user2@domain.com`) |
| `FILTER_RISK_KEYWORDS` | Comma-separated keywords in criteria that make a filter risky (e.g. security, password) |
| `FILTER_EXTERNAL_FORWARDING_ONLY` | If true, only flag filters that forward externally |
| `UI_BASE_URL` | Base URL for links in emails (e.g. `https://your-ui.example.com`) |

## Gmail mailbox filter inspection

WASP can inspect Gmail filters (state inspection) via the Gmail API, because admin/audit logs do not reliably expose user-created filter events. This is **separate** from audit log polling.

- **Enable:** Set `GMAIL_FILTER_INSPECTION_ENABLED=true` and `FILTER_SCAN_ENABLED=true`. Add `https://www.googleapis.com/auth/gmail.settings.basic` to your service account’s Domain-Wide Delegation scopes.
- **Users:** Set `FILTER_SCAN_USER_SCOPE` to a comma-separated list of user emails to scan (e.g. high-risk or pilot users).
- **Frequency:** The filter scan runs when the poll runs (cron or internal loop), but only if at least `FILTER_SCAN_INTERVAL_SECONDS` (default 3600 = 60 min) have passed since the last scan.
- **Risky filters:** A filter is considered risky if it deletes, archives, or marks messages read; forwards externally; or targets security-related criteria (subject/from/query matching `FILTER_RISK_KEYWORDS`). Risk is rule-based and configurable.
- **Fingerprinting:** Each filter is normalized and hashed (fingerprint). Trust is by fingerprint, not Gmail filter ID: if a user changes the filter, the fingerprint changes and it must be reviewed again.
- **UI:** **Mailbox Filters** in the sidebar lists filters, risk, status (new / approved / ignored / blocked / removed). Responders can approve, ignore, or block; rescan triggers an immediate scan for a user. Alerts are generated only for new risky filters, or when an approved/benign filter changes into something risky.

## Google Workspace setup (Domain-Wide Delegation)

1. Create a service account in Google Cloud, enable Domain-Wide Delegation, and note the client ID.
2. In Admin Console: Security → API Controls → Domain-wide delegation → Add the client ID with these scopes:
   - `https://www.googleapis.com/auth/admin.reports.audit.readonly`
   - `https://www.googleapis.com/auth/admin.directory.user`
   - `https://www.googleapis.com/auth/admin.directory.user.security`
   - `https://www.googleapis.com/auth/gmail.settings.basic` (only if using Gmail mailbox filter inspection)
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

  The app uses relative `/api`; in production nginx proxies `/api` to the backend (no build-time API URL).

## Deploying backend (Cloud Run + Scheduler)

1. Build and push the backend image; deploy to Cloud Run with `DATABASE_URL` (Cloud SQL or other), env vars above, and no public unauthenticated access.
2. Create a Cloud Scheduler job that calls `POST https://your-run-url/api/cron/poll` with auth (OIDC or API key). Suggested frequency: every 15 minutes (or match `LOOKBACK_MINUTES`).

Example frequencies:
- 1 min: `* * * * *`
- 2 min: `*/2 * * * *`
- 5 min: `*/5 * * * *`
- 10 min: `*/10 * * * *`

Example (API key mode):

```bash
gcloud scheduler jobs create http hijacked-poll \
  --schedule "*/5 * * * *" \
  --http-method POST \
  --uri "https://YOUR_RUN_URL/api/cron/poll" \
  --headers "X-CRON-KEY=YOUR_CRON_KEY"
```

Example (OIDC mode):

```bash
gcloud scheduler jobs create http hijacked-poll \
  --schedule "*/5 * * * *" \
  --http-method POST \
  --uri "https://YOUR_RUN_URL/api/cron/poll" \
  --oidc-service-account-email "scheduler-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --oidc-token-audience "https://YOUR_RUN_URL/api/cron/poll"
```

## Safety: ACTION_FLAG and backend toggles

- **`ACTION_FLAG=false` (default):** Containment is **not** executed. The app records a **proposed** action and shows it in the UI and in the email. Use this until you have validated rules and workflows.
- **`ACTION_FLAG=true`:** Disable Account (single or bulk) runs only the backends you enable via config (no code changes):
  - **`ENABLE_ACTIVE_DIRECTORY=true`** (default: false): Disable the user in AD via LDAP (`userAccountControl` + ACCOUNTDISABLE). Requires `AD_LDAP_URL`, `AD_BIND_DN`, `AD_BIND_PASSWORD`, `AD_BASE_DN`. Use when Google is synced from AD so replication won’t re-enable the user.
  - **`ENABLE_GOOGLE_WORKSPACE=true`** (default: true): Suspend the user (Directory API `users.update` with `suspended=true`), force sign-out (`users.signOut`), and revoke tokens (`tokens.list` + `tokens.delete`).

You can enable one, both, or neither. All actions are stored in the `actions` table with result and details (including AD and Google steps, or “skipped” with reason when a backend is disabled).

## Blast Radius Mitigation

To limit damage if WASP is compromised or a rule misfires, use the following deployment practices and config.

### Rate limiting (circuit breaker)

- **`SUSPENSION_RATE_LIMIT_MAX`** (default 5) and **`SUSPENSION_RATE_LIMIT_MINUTES`** (default 60): If the number of successful DISABLE_ACCOUNT actions in the last N minutes exceeds the max, WASP returns **503** and does not suspend any more accounts until the window clears. A critical audit event `SUSPENSION_RATE_LIMIT_TRIPPED` is logged. This prevents a compromised app or a bad rule from shutting down the entire org.

### Protected list (do-not-suspend)

- **`PROTECTED_EMAILS`**: Comma-separated exact emails (e.g. `admin@mycorp.com`) that must never be suspended. Containment skips them and records result `SKIPPED`.
- **`PROTECTED_DOMAINS`**: Comma-separated domain suffixes (e.g. `mycorp.com`). Any user whose email domain matches is skipped. Use for admin or critical OUs.

### Google Workspace protections

Domain-wide delegation for `https://www.googleapis.com/auth/admin.directory.user` allows suspending any user, including Super Admins. To reduce blast radius:

- **Do not** grant the service account the ability to suspend Super Admins. Prefer assigning a **custom admin role** to the service account (or the user used for `GOOGLE_WORKSPACE_ADMIN_USER`) that only allows managing users in **specific non-admin Organizational Units (OUs)**. Avoid granting full domain-wide delegation over all users; scope the role to OUs that contain standard users only, and explicitly exclude Super Admin and other privileged OUs.

### Active Directory protections

The `AD_BIND_DN` service account can disable users via LDAP. To reduce blast radius:

- Grant **"Write userAccountControl"** (or the minimum right needed to set `ACCOUNTDISABLE`) only over **specific OUs** (e.g. `OU=Standard Users`). Explicitly **deny** permissions over `OU=Domain Admins`, service account OUs, and other high-privilege OUs so that even if WASP is compromised, it cannot disable those accounts.

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
- `GET /api/alerts/{id}` – alert detail + timeline + audit trail
- `POST /api/alerts/{id}/dismiss` – dismiss one
- `POST /api/alerts/bulk-dismiss` – body `{ "alert_ids": [1,2,...] }`
- `POST /api/alerts/{id}/status` – set status (`NEW|TRIAGE|CONTAINED|FALSE_POSITIVE|CLOSED`)
- `POST /api/alerts/{id}/assign` – assign responder
- `POST /api/alerts/{id}/notes` – add/update notes
- `POST /api/actions/disable-account` – body `{ "alert_ids": [...], "reason": "..." }`
- `POST /api/settings/test-email` – send test email to SUPPORT_EMAIL
- `POST /api/cron/poll` – trigger poll + notify (for Cloud Scheduler)
- `GET /healthz`, `GET /readyz`

## Operations

- **Safe defaults:** keep `ACTION_FLAG=false` in production until playbooks are validated.
- **Least privilege:** only usernames in `RESPONDER_USERS` can run containment and status transitions.
- **Login from new location:** each successful login records the client IP (from the request, or `X-Forwarded-For` when behind a proxy). If the user has never logged in from that IP before, an extra audit event `AUTH_LOGIN_NEW_LOCATION` is written so you can monitor or alert on first-time locations.
- **Secret rotation:** rotate `ADMIN_PASSWORD`, `CRON_API_KEY`, `SECRET_KEY`, SMTP credentials on a schedule; restart service after rotation.
- **Poll mode:**
  - `POLL_MODE=scheduler` (recommended): no internal loop; use Cloud Scheduler cadence.
  - `POLL_MODE=internal`: backend runs poll loop with `POLL_INTERVAL_SECONDS +/- POLL_JITTER_SECONDS`.
- **Incident flow runbook:** `NEW -> TRIAGE -> CONTAINED (if needed) -> CLOSED` or `FALSE_POSITIVE`; record notes and assignment on each step.

## Email alerts

- The app sends an email to `SUPPORT_EMAIL` when a **new** detection is OPEN and score ≥ `SEVERITY_THRESHOLD`.
- Re-email only if: risk level increases, score increases by ≥ 20 since last notify, or ≥ 12 hours since last notify.
- Email is sent **after** any containment actions so the body reflects “Action Taken” or “Proposed Action”.
- Subject: `[{RISK}] WASP Alert: {user_email} (Score {score})`.
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
