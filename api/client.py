import requests

from config import (
    get_webex_api_base_url,
    get_webex_bearer_token,
    get_webex_org_id,
    get_wxcc_org_base_url,
    get_wxcc_search_base_url,
)
from lab_paths import resolve_org_path_segment, resolve_regional_path_segment


def get_headers():
    return {
        "Authorization": f"Bearer {get_webex_bearer_token()}",
        "Content-Type": "application/json",
    }


def wxcc_get(path: str, params: dict | None = None):
    """GET request to WxCC Organization API."""
    org_id = get_webex_org_id()
    if path.startswith("http"):
        url = path
    else:
        suffix = resolve_org_path_segment(path, org_id)
        url = f"{get_wxcc_org_base_url().rstrip('/')}{suffix}"
    response = requests.get(url, headers=get_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def wxcc_regional_base_url() -> str:
    """Regional WxCC API base URL (without the /organization prefix)."""
    base = get_wxcc_org_base_url().rstrip("/")
    if base.endswith("/organization"):
        return base[: -len("/organization")]
    return base


def wxcc_org_url(relative_path: str, **path_vars) -> str:
    """Build a full WxCC organization API URL from a portal path or template."""
    org_id = get_webex_org_id()
    if relative_path.startswith("http"):
        return relative_path
    suffix = resolve_org_path_segment(relative_path, org_id, **path_vars)
    return f"{get_wxcc_org_base_url().rstrip('/')}{suffix}"


def wxcc_regional_url(relative_path: str, **path_vars) -> str:
    """Build a full WxCC regional API URL (e.g. flow-store, project flows)."""
    org_id = get_webex_org_id()
    if relative_path.startswith("http"):
        return relative_path
    path = resolve_regional_path_segment(relative_path, org_id, **path_vars)
    return f"{wxcc_regional_base_url()}{path}"


def wxcc_regional_get(relative_path: str, params: dict | None = None, **path_vars):
    """GET request to a WxCC regional API path (outside /organization)."""
    url = wxcc_regional_url(relative_path, **path_vars)
    response = requests.get(url, headers=get_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def wxcc_agents_get(relative_path: str, params: dict | None = None):
    """GET request to WxCC Agents API (/v1/agents/...)."""
    path = relative_path if relative_path.startswith("/") else f"/{relative_path}"
    url = f"{wxcc_regional_base_url()}{path}"
    response = requests.get(url, headers=get_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def wxcc_put(path: str, body: dict, params: dict | None = None):
    """PUT request to WxCC Organization API."""
    org_id = get_webex_org_id()
    if path.startswith("http"):
        url = path
    else:
        suffix = resolve_org_path_segment(path, org_id)
        url = f"{get_wxcc_org_base_url().rstrip('/')}{suffix}"
    response = requests.put(url, headers=get_headers(), json=body, params=params, timeout=30)
    response.raise_for_status()
    if response.content:
        return response.json()
    return {"status": response.status_code}


def wxcc_graphql(query: str, variables: dict | None = None):
    """POST GraphQL query to WxCC Search API."""
    org_id = get_webex_org_id()
    url = f"{get_wxcc_search_base_url()}?orgId={org_id}"
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = requests.post(url, headers=get_headers(), json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("errors") and not data.get("data"):
        first = data["errors"][0] if data["errors"] else {}
        message = first.get("message") or "GraphQL query failed"
        raise RuntimeError(message)
    return data


def webex_get(path: str, params: dict | None = None):
    """GET request to Webex Platform API."""
    url = f"{get_webex_api_base_url()}{path}"
    response = requests.get(url, headers=get_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()
