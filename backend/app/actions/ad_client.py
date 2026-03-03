"""Active Directory LDAP client: disable user account so replication won't re-enable in Google."""
from __future__ import annotations

from typing import Any

from app.config import get_settings

# userAccountControl: ACCOUNTDISABLE = 2
UAC_ACCOUNTDISABLE = 2


def _ad_configured() -> bool:
    """True if AD integration is enabled and LDAP settings are set."""
    s = get_settings()
    return bool(s.enable_active_directory and s.ad_ldap_url and s.ad_bind_dn and s.ad_base_dn)


def disable_user_in_ad(target_email: str) -> dict[str, Any]:
    """
    Find user in AD by mail or userPrincipalName and set userAccountControl to disable.
    Returns {"success": True} or {"error": "...", "status": ...}.
    """
    if not _ad_configured():
        return {"skipped": True, "reason": "AD not configured"}

    try:
        from ldap3 import Connection, Server, ALL, SUBTREE
        from ldap3.utils.conv import escape_filter_chars
        from ldap3.core.exceptions import LDAPException
    except ImportError:
        return {"error": "ldap3 not installed", "skipped": True}

    settings = get_settings()
    server = Server(settings.ad_ldap_url, get_info=ALL)
    try:
        conn = Connection(
            server,
            user=settings.ad_bind_dn,
            password=settings.ad_bind_password,
            auto_bind=True,
        )
    except LDAPException as e:
        return {"error": str(e), "status": "bind_failed"}

    try:
        # Search by mail or userPrincipalName (both often match email)
        safe_email = escape_filter_chars(target_email)
        safe_sam = escape_filter_chars(target_email.split("@")[0])
        search_filter = (
            f"(|(mail={safe_email})(userPrincipalName={safe_email})(sAMAccountName={safe_sam}))"
        )
        conn.search(
            search_base=settings.ad_base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["distinguishedName", "userAccountControl"],
        )
        if not conn.entries:
            return {"error": f"User not found: {target_email}", "status": 404}
        entry = conn.entries[0]
        dn = str(entry.entry_dn)
        current_uac = int(entry.userAccountControl.value) if entry.userAccountControl else 0
        if current_uac & UAC_ACCOUNTDISABLE:
            return {"success": True, "already_disabled": True}
        new_uac = current_uac | UAC_ACCOUNTDISABLE
        from ldap3 import MODIFY_REPLACE
        ok = conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [new_uac])]})
        if not ok:
            return {"error": str(conn.result), "status": "modify_failed"}
        return {"success": True}
    except LDAPException as e:
        return {"error": str(e), "status": "ldap_error"}
    finally:
        conn.unbind()


def ad_disable_available() -> bool:
    """True if AD is enabled and configured; we should attempt AD disable when action_flag is True."""
    return _ad_configured()
