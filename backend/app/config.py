"""Application configuration from environment."""
from __future__ import annotations

import json
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
    enable_google_workspace: bool = True   # when True and action_flag=True, suspend/sign-out/revoke in Google
    enable_active_directory: bool = False  # when True and action_flag=True, disable user in AD (requires AD_* config)

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

    def ensure_secure(self) -> None:
        if self.is_prod:
            if self.secret_key == "dev-secret-change-in-prod" or len(self.secret_key) < 32:
                raise ValueError("In production, SECRET_KEY must be set to a strong value (>=32 chars).")
            if not self.cors_origin_list:
                raise ValueError("In production, CORS_ORIGINS must include at least one explicit origin.")


def get_settings() -> Settings:
    return Settings()
