"""Validate the access token and organization ID entered in the UI.

Credentials are kept in process memory for this run only and are never
written into source files or to disk.
"""

from __future__ import annotations

import re

import requests

from config import get_webex_api_base_url, get_wxcc_org_base_url, org_id_from_token
from lab_credentials import get_stored_token, save_org_id, save_token

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def _normalize_token(raw: str) -> str:
    token = (raw or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token.strip('"').strip("'")


def _probe_wxcc_users(token: str, org_id: str) -> tuple[bool, str]:
    base = get_wxcc_org_base_url().rstrip("/")
    url = f"{base}/{org_id}/v2/user"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return False, f"Could not reach WxCC API: {exc}"

    if response.status_code == 401:
        return False, "Token rejected (401). Copy a fresh admin bearer token from developer.webex.com."
    if response.status_code == 403:
        return False, (
            "Access denied (403). Use a Webex Contact Center admin account with "
            "Contact Center configuration scopes (cjp:config, cjp:config_read, cjp:config_write)."
        )
    if response.status_code >= 400:
        body = (response.text or "")[:200].strip()
        return False, f"WxCC API returned {response.status_code}. {body}"
    return True, "Connected to your organization."


def _org_from_people_me(token: str) -> str | None:
    url = get_webex_api_base_url().rstrip("/") + "/people/me"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    except requests.RequestException:
        return None
    if response.status_code >= 400:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    org_id = str(data.get("orgId") or "").strip()
    return org_id if _UUID_RE.match(org_id) else None


def save_connection(token_raw: str, org_id_raw: str, keep_existing_token: bool = False) -> dict:
    """Validate token + org ID, probe List Users, then store locally. Never returns the token."""
    errors: list[str] = []
    token = _normalize_token(token_raw)
    if (not token or token == "your_bearer_token_here") and keep_existing_token:
        token = get_stored_token()
    org_id = (org_id_raw or "").strip()

    if not token or token == "your_bearer_token_here":
        errors.append("Paste an admin profile bearer token from developer.webex.com (token string only).")
    elif len(token) < 20:
        errors.append("This token looks too short. Copy the full bearer token from your Developer Portal profile.")

    if not org_id or org_id == "your_org_id_here":
        errors.append("Paste your organization ID from the Developer Portal profile menu.")
    elif not _UUID_RE.match(org_id):
        errors.append("Organization ID must be a UUID (for example 5e5c9ad6-d61f-870d-6d77-8fc1b…).")

    if errors:
        return {"valid": False, "message": " ".join(errors)}

    token_org = org_id_from_token(token) or _org_from_people_me(token)
    if token_org and token_org.lower() != org_id.lower():
        return {
            "valid": False,
            "message": (
                f"This org ID does not match the organization on your token ({token_org}). "
                "Copy the org ID shown with your profile bearer token."
            ),
        }

    ok, message = _probe_wxcc_users(token, org_id)
    if not ok:
        return {"valid": False, "message": message}

    save_token(token, auth_method="bearer")
    save_org_id(org_id)
    return {"valid": True, "message": message, "org_id": org_id}
