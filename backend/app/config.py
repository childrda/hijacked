"""Application configuration from environment."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "dev"
    secret_key: str = "dev-secret-change-in-prod"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = "postgresql+psycopg2://workspace_agent:workspace_agent_secret@localhost:5432/workspace_security"

    # Google Workspace
    google_credentials_json: str = ""
    google_workspace_admin_user: str = "admin@domain.tld"
    domain: str = "yourdomain.tld"

    # Security / containment
    support_email: str = "support@domain.tld"
    action_flag: bool = False
    action_cooldown_minutes: int = 30
    suspension_rate_limit_max: int = 5      # max DISABLE_ACCOUNT successes in the window; circuit breaker trips above this
    suspension_rate_limit_minutes: int = 60  # rolling window for suspension rate limit
    protected_emails: str = ""               # comma-separated emails that must never be suspended (e.g. admin@mycorp.com)
    protected_domains: str = ""               # comma-separated domain suffixes (e.g. mycorp.com) whose users are never suspended
    enable_google_workspace: bool = True   # when True and action_flag=True, suspend/sign-out/revoke in Google
    enable_active_directory: bool = False  # when True and action_flag=True, disable user in AD (requires AD_* config)
    admin_username: str = "admin"
    admin_password: str = ""
    responder_users: str = "admin"
    session_expiry_hours: int = 8

    # Active Directory (used only when enable_active_directory is True)
    ad_ldap_url: str = ""  # e.g. ldap://dc.example.com or ldaps://dc.example.com
    ad_bind_dn: str = ""   # e.g. CN=svc-workspace-agent,OU=Service Accounts,DC=example,DC=com
    ad_bind_password: str = ""
    ad_base_dn: str = ""   # e.g. DC=example,DC=com (search base for users)
    severity_threshold: int = 70
    lookback_minutes: int = 15

    # Mass outbound detection (phishing indicator)
    mass_send_enabled: bool = True
    mass_send_recipient_threshold: int = 50
    mass_send_window_minutes: int = 10
    mass_send_message_threshold: int = 20
    mass_send_unique_recipient_threshold: int = 80
    mass_send_internal_only_ignore: bool = True
    mass_send_allowlist_senders: str = ""
    mass_send_allowlist_subject_keywords: str = ""
    mass_send_severity_points_single: int = 70
    mass_send_severity_points_burst: int = 60

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_use_tls: bool = True

    # UI base URL for links in emails
    ui_base_url: str = "http://localhost:5173"

    # Cron auth
    cron_auth_mode: str = "apikey"  # apikey | oidc
    cron_api_key: str = ""
    cron_oidc_audience: str = ""

    # Polling controls
    poll_enabled: bool = False
    poll_interval_seconds: int = 300
    poll_jitter_seconds: int = 15
    poll_lock_ttl_seconds: int = 600
    poll_max_runtime_seconds: int = 240
    poll_mode: str = "scheduler"  # scheduler | internal

    # Gmail mailbox filter inspection (state inspection, separate from audit log polling)
    gmail_filter_inspection_enabled: bool = False
    filter_scan_enabled: bool = False
    filter_scan_interval_seconds: int = 3600   # default 60 min
    filter_scan_user_scope: str = ""           # comma-separated user emails, or leave empty to derive from domain
    filter_risk_keywords: str = "security,alert,password,admin,phishing,login,verification,account"
    filter_approval_required: bool = True
    filter_external_forwarding_only: bool = False  # if True, only flag filters that forward externally
    filter_risky_actions: str = "delete,mark_read,archive,forward_external"  # comma-separated

    @property
    def filter_risk_keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.filter_risk_keywords.split(",") if k.strip()]

    @property
    def filter_scan_user_scope_list(self) -> list[str]:
        return [e.strip().lower() for e in self.filter_scan_user_scope.split(",") if e.strip()]

    @field_validator("google_credentials_json", mode="before")
    @classmethod
    def load_google_creds(cls, v: Any) -> str:
        if not v:
            return "{}"
        if isinstance(v, str) and v.strip().startswith("{"):
            return v
        path = Path(v) if isinstance(v, str) else None
        if path and path.exists():
            return path.read_text(encoding="utf-8")
        return v or "{}"

    def get_google_credentials(self) -> dict[str, Any]:
        raw = self.google_credentials_json or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() == "prod"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mass_send_allowlist_senders_list(self) -> list[str]:
        return [s.strip().lower() for s in self.mass_send_allowlist_senders.split(",") if s.strip()]

    @property
    def mass_send_allowlist_subject_keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.mass_send_allowlist_subject_keywords.split(",") if k.strip()]

    @property
    def responder_users_list(self) -> list[str]:
        return [u.strip() for u in self.responder_users.split(",") if u.strip()]

    @property
    def protected_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.protected_emails.split(",") if e.strip()]

    @property
    def protected_domains_list(self) -> list[str]:
        return [d.strip().lower() for d in self.protected_domains.split(",") if d.strip()]

    def ensure_secure(self) -> None:
        if not (self.admin_password or "").strip():
            raise ValueError("ADMIN_PASSWORD must be set to a non-empty value in all environments.")
        if self.secret_key == "dev-secret-change-in-prod" or len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be set to a strong value (>=32 chars) in all environments.")
        if self.is_prod:
            if not self.cors_origin_list:
                raise ValueError("In production, CORS_ORIGINS must include at least one explicit origin.")
            if self.action_flag:
                # In prod we allow containment only explicitly; dry-run remains safe default.
                pass
            if self.poll_mode not in {"scheduler", "internal"}:
                raise ValueError("POLL_MODE must be scheduler or internal")
            if self.cron_auth_mode not in {"apikey", "oidc"}:
                raise ValueError("CRON_AUTH_MODE must be apikey or oidc")

    @property
    def poll_enabled_effective(self) -> bool:
        if "POLL_ENABLED" in os.environ:
            return self.poll_enabled
        return not self.is_prod


def get_settings() -> Settings:
    return Settings()
