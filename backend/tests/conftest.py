"""Pytest fixtures and env for WASP backend tests."""
from __future__ import annotations

import os

# Ensure secure config so app startup (ensure_secure) passes in all test runs.
if "ADMIN_PASSWORD" not in os.environ or not (os.environ.get("ADMIN_PASSWORD") or "").strip():
    os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
if "SECRET_KEY" not in os.environ or os.environ.get("SECRET_KEY", "").strip() == "" or len(os.environ.get("SECRET_KEY", "")) < 32:
    os.environ.setdefault("SECRET_KEY", "x" * 40)
