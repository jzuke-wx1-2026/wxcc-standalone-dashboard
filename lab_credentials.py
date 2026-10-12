"""Keep the access token and org ID in process memory for this run only.

Nothing is written to disk. Any leftover data/credentials.json from earlier
versions is deleted on import and again when the process exits.
"""

from __future__ import annotations

import atexit
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREDENTIALS_PATH = ROOT / "data" / "credentials.json"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)

_SESSION: dict[str, str] = {}


def _delete_leftover_file() -> None:
    try:
        if CREDENTIALS_PATH.is_file():
            CREDENTIALS_PATH.unlink()
    except OSError:
        pass


def _session() -> dict[str, str]:
    return _SESSION


def get_stored_token() -> str:
    return str(_session().get("token") or "").strip()


def get_stored_org_id() -> str:
    return str(_session().get("org_id") or "").strip()


def has_token() -> bool:
    token = get_stored_token()
    return bool(token and token != "your_bearer_token_here")


def has_org_id() -> bool:
    org_id = get_stored_org_id()
    return bool(org_id and org_id != "your_org_id_here" and _UUID_RE.match(org_id))


def is_fully_configured() -> bool:
    return has_token() and has_org_id()


def save_token(token: str, auth_method: str | None = None) -> None:
    _SESSION["token"] = token.strip()
    if auth_method:
        _SESSION["auth_method"] = str(auth_method).strip()


def save_org_id(org_id: str) -> None:
    _SESSION["org_id"] = org_id.strip()


def get_auth_method() -> str:
    method = str(_session().get("auth_method") or "").strip().lower()
    if method in ("bearer", "integration"):
        return method
    return "bearer" if has_token() else ""


def get_integration_client_id() -> str:
    return str(_session().get("integration_client_id") or "").strip()


def save_integration_client_id(client_id: str) -> None:
    value = (client_id or "").strip()
    if value:
        _SESSION["integration_client_id"] = value
    else:
        _SESSION.pop("integration_client_id", None)


def get_suggested_org_id() -> str:
    return str(_session().get("suggested_org_id") or "").strip()


def save_suggested_org_id(org_id: str) -> None:
    value = (org_id or "").strip()
    if value:
        _SESSION["suggested_org_id"] = value
    else:
        _SESSION.pop("suggested_org_id", None)


def clear_credentials() -> None:
    _SESSION.clear()
    _delete_leftover_file()


_delete_leftover_file()
atexit.register(clear_credentials)
