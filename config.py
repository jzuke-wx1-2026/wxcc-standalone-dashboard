import os
import re

from dotenv import load_dotenv

FILL_IN_PLACEHOLDER = "___FILL_IN___"

_ORG_SUFFIX_RE = re.compile(
    r"_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.I,
)


def reload_env() -> None:
    """Re-read .env so token/org changes apply without restarting Flask."""
    load_dotenv(override=True)


def _normalize_token(raw: str) -> str:
    token = (raw or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token.strip('"').strip("'")


def get_webex_bearer_token() -> str:
    try:
        from lab_credentials import get_stored_token

        stored = _normalize_token(get_stored_token())
        if stored and stored != "your_bearer_token_here":
            return stored
    except ImportError:
        pass
    reload_env()
    return _normalize_token(os.getenv("WEBEX_BEARER_TOKEN", ""))


def get_webex_org_id() -> str:
    try:
        from lab_credentials import get_stored_org_id

        stored = get_stored_org_id().strip()
        if stored and stored != "your_org_id_here":
            return stored
    except ImportError:
        pass
    reload_env()
    return os.getenv("WEBEX_ORG_ID", "").strip()


def org_id_from_token(token: str | None = None) -> str | None:
    """Extract org UUID from Webex token suffix (_<org-id>), if present."""
    raw = token if token is not None else get_webex_bearer_token()
    match = _ORG_SUFFIX_RE.search(raw)
    return match.group(1) if match else None


def get_wxcc_org_base_url() -> str:
    reload_env()
    return os.getenv("WXCC_ORG_BASE_URL", "https://api.wxcc-us1.cisco.com/organization")


def get_wxcc_search_base_url() -> str:
    reload_env()
    return os.getenv("WXCC_SEARCH_BASE_URL", "https://api.wxcc-us1.cisco.com/search")


def get_webex_api_base_url() -> str:
    reload_env()
    return os.getenv("WEBEX_API_BASE_URL", "https://webexapis.com/v1")


def get_org_config_status() -> dict:
    """Non-secret snapshot of active credentials for debugging."""
    try:
        from lab_credentials import is_fully_configured

        dashboard_credentials = is_fully_configured()
    except ImportError:
        dashboard_credentials = False

    org_id = get_webex_org_id()
    token = get_webex_bearer_token()
    token_org = org_id_from_token(token)
    mismatch = bool(
        org_id
        and org_id != "your_org_id_here"
        and token_org
        and org_id.lower() != token_org.lower()
    )
    token_configured = bool(token and token != "your_bearer_token_here")
    org_configured = bool(org_id and org_id != "your_org_id_here")
    return {
        "org_id": org_id,
        "token_org_id": token_org,
        "org_id_mismatch": mismatch,
        "token_configured": token_configured,
        "org_configured": org_configured,
        # Connected only when token/org were saved in the dashboard Connect panel.
        # .env can still power API calls, but it must not keep the Connected state after Disconnect.
        "setup_complete": dashboard_credentials and not mismatch,
        "credential_source": "dashboard" if dashboard_credentials else ("env" if token_configured else "none"),
        "wxcc_org_base_url": get_wxcc_org_base_url(),
        "auth_method": _auth_method_for_status(dashboard_credentials, token_configured),
    }


def _auth_method_for_status(dashboard_credentials: bool, token_configured: bool) -> str:
    try:
        from lab_credentials import get_auth_method

        method = get_auth_method()
        if method:
            return method
    except ImportError:
        pass
    if dashboard_credentials or token_configured:
        return "bearer"
    return ""
