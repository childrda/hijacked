"""Admin SDK Directory API for user suspend, sign-out, token revoke."""
from __future__ import annotations

import logging
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.google.auth import get_credentials, SCOPES_DIRECTORY

logger = logging.getLogger(__name__)


def _get_directory_service():
    creds = get_credentials(SCOPES_DIRECTORY)
    return build("admin", "directory_v1", credentials=creds, cache_discovery=False)


def get_user(domain: str, user_key: str) -> dict[str, Any] | None:
    """Get user by email (user_key). Returns None if not found."""
    try:
        service = _get_directory_service()
        return service.users().get(userKey=user_key).execute()
    except HttpError as e:
        if e.resp.status == 404:
            return None
        raise


def suspend_user(user_key: str) -> dict[str, Any]:
    """Set user suspended=true. Returns updated user or error dict."""
    logger.info("Google API: suspend_user(%s)", user_key)
    service = _get_directory_service()
    try:
        out = service.users().update(
            userKey=user_key,
            body={"suspended": True},
        ).execute()
        logger.info("Google API: suspend_user(%s) -> 200 OK (suspended=True)", user_key)
        return out
    except HttpError as e:
        status = getattr(e.resp, "status", None)
        err_msg = str(e)
        logger.warning("Google API: suspend_user(%s) -> %s %s", user_key, status, err_msg[:200])
        return {"error": err_msg, "status": status}


def sign_out_user(user_key: str) -> dict[str, Any]:
    """Force sign-out (invalidate sessions)."""
    logger.info("Google API: signOut(%s)", user_key)
    service = _get_directory_service()
    try:
        service.users().signOut(userKey=user_key).execute()
        logger.info("Google API: signOut(%s) -> OK", user_key)
        return {"success": True}
    except HttpError as e:
        status = getattr(e.resp, "status", None)
        logger.warning("Google API: signOut(%s) -> %s %s", user_key, status, str(e)[:200])
        return {"error": str(e), "status": status}


def list_tokens(user_key: str) -> list[dict[str, Any]]:
    """List OAuth tokens for user (best-effort)."""
    service = _get_directory_service()
    try:
        result = service.tokens().list(userKey=user_key).execute()
        return result.get("items") or []
    except HttpError:
        return []


def revoke_token(user_key: str, client_id: str) -> dict[str, Any]:
    """Revoke a single token by client_id."""
    service = _get_directory_service()
    try:
        service.tokens().delete(userKey=user_key, clientId=client_id).execute()
        return {"success": True, "clientId": client_id}
    except HttpError as e:
        return {"error": str(e), "clientId": client_id, "status": getattr(e.resp, "status", None)}


def revoke_all_tokens(user_key: str) -> dict[str, Any]:
    """List and delete all tokens for user (best-effort)."""
    tokens = list_tokens(user_key)
    logger.info("Google API: revoke_all_tokens(%s) -> %d token(s)", user_key, len(tokens))
    results = []
    for t in tokens:
        cid = t.get("clientId")
        if cid:
            results.append(revoke_token(user_key, cid))
    n = len([r for r in results if r.get("success")])
    logger.info("Google API: revoke_all_tokens(%s) -> %d revoked", user_key, n)
    return {"tokens_revoked": n, "results": results}
