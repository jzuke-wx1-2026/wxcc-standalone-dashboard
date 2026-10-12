"""
Organizational Data — entry points, queues, teams, aux codes, and global variables.

Endpoints and field names are injected from api_config.py.

Developer Portal:
https://developer.webex.com/webex-contact-center/docs/api/v1/entry-point
"""

import base64
import re

from config import get_webex_org_id
from api.client import webex_get, wxcc_get, wxcc_org_url, wxcc_put, wxcc_regional_get

MODULE_ID = "module2"
MODULE_NAME = "Organizational Data"

EP_QUEUE_ID_KEY = "queueId"  # provided — not a lab fill-in step

# Flow Store — provided; dashboard resolves flowId → name without a lab step
FLOW_LIST_ENDPOINT = "/flow-store/{org_id}/project/5e5c9ad6d61f870d6d778c1b/flows"
FLOW_ID_KEY = "id"
FLOW_NAME_KEY = "name"

GV_ID_KEY = "id"  # provided — used by dashboard update logic
GV_UPDATE_VALUE_KEY = "defaultValue"  # provided — PUT body field

STEPS = [
    {
        "id": "2.1",
        "label": "Entry Points / Channels",
        "variables": [
            "ENTRY_POINT_LIST_ENDPOINT",
            "EP_NAME_KEY",
            "EP_FLOW_ID_KEY",
            "DIAL_NUMBER_LIST_ENDPOINT",
            "DIAL_NUMBER_DN_KEY",
            "DIAL_NUMBER_EP_ID_KEY",
            "DIAL_NUMBER_LOCATION_KEY",
            "DIAL_NUMBER_REGION_KEY",
            "EP_ACTIVE_KEY",
        ],
    },
    {
        "id": "2.2",
        "label": "Queue Information",
        "variables": [
            "QUEUE_LIST_ENDPOINT",
            "QUEUE_NAME_KEY",
            "QUEUE_ID_KEY",
            "QUEUE_CONTACT_DIRECTION_KEY",
            "QUEUE_TYPE_KEY",
            "QUEUE_ROUTING_TYPE_KEY",
            "QUEUE_STATUS_KEY",
        ],
    },
    {
        "id": "2.3",
        "label": "Team Details",
        "variables": [
            "TEAM_LIST_ENDPOINT",
            "TEAM_NAME_KEY",
            "TEAM_SITE_NAME_KEY",
            "TEAM_TYPE_KEY",
            "TEAM_DN_KEY",
            "TEAM_STATUS_KEY",
        ],
    },
    {
        "id": "2.4",
        "label": "Auxiliary Codes",
        "variables": [
            "AUX_CODE_LIST_ENDPOINT",
            "AUX_CODE_NAME_KEY",
            "AUX_CODE_ID_KEY",
            "AUX_CODE_TYPE_KEY",
            "AUX_CODE_DEFAULT_KEY",
            "AUX_CODE_STATUS_KEY",
        ],
    },
    {
        "id": "2.5",
        "label": "Global Variables",
        "variables": [
            "GLOBAL_VARIABLE_LIST_ENDPOINT",
            "GV_NAME_KEY",
            "GV_VALUE_KEY",
            "GV_TYPE_KEY",
            "GV_STATUS_KEY",
        ],
    },
    {
        "id": "2.6",
        "label": "Update Global Variable",
        "variables": [
            "GV_UPDATE_ENDPOINT",
            "GV_REQUEST_METHOD",
        ],
    },
]


def _normalize_list(data, data_key=None):
    from progress import is_filled

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if data_key and is_filled(data_key) and isinstance(data.get(data_key), list):
            return data[data_key]
        for key in ("data", "items", "records", "teams"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _fetch_flow_name_lookup():
    """Build a map of flowId -> flow display name (uses built-in Flow Store constants)."""
    try:
        data = wxcc_regional_get(
            FLOW_LIST_ENDPOINT.format(org_id="{org_id}"),
            params={"size": 100},
        )
        items = _normalize_list(data)
        lookup = {}
        for item in items:
            flow_id = item.get(FLOW_ID_KEY)
            flow_name = item.get(FLOW_NAME_KEY)
            if flow_id and flow_name:
                lookup[flow_id] = flow_name
        return lookup
    except Exception:
        return {}


def _fetch_dial_numbers_by_entry_point():
    """Build a map of entryPointId -> DN, Webex Calling location, and media region."""
    from progress import is_filled

    if not all(
        is_filled(v)
        for v in (DIAL_NUMBER_LIST_ENDPOINT, DIAL_NUMBER_DN_KEY, DIAL_NUMBER_EP_ID_KEY)
    ):
        return {}

    try:
        url = wxcc_org_url(DIAL_NUMBER_LIST_ENDPOINT.format(org_id="{org_id}"))
        data = wxcc_get(url)
        items = _normalize_list(data)
        dial_map: dict[str, dict] = {}
        location_key = DIAL_NUMBER_LOCATION_KEY if is_filled(DIAL_NUMBER_LOCATION_KEY) else "location"
        region_key = DIAL_NUMBER_REGION_KEY if is_filled(DIAL_NUMBER_REGION_KEY) else "regionId"

        for mapping in items:
            ep_id = mapping.get(DIAL_NUMBER_EP_ID_KEY)
            dn = mapping.get(DIAL_NUMBER_DN_KEY)
            if not ep_id:
                continue

            entry = dial_map.setdefault(
                ep_id,
                {"dns": [], "locations": [], "regions": []},
            )
            if dn:
                entry["dns"].append(str(dn))

            location = mapping.get(location_key)
            if location and location not in entry["locations"]:
                entry["locations"].append(str(location))

            region = mapping.get(region_key)
            if region and region not in entry["regions"]:
                entry["regions"].append(str(region))

        return dial_map
    except Exception:
        return {}


def _join_unique(values: list[str]) -> str | None:
    cleaned = [value for value in values if value]
    return ", ".join(cleaned) if cleaned else None


def _item_value(item: dict, key: str | None, fallback: str | None = None):
    from progress import is_filled

    if key and is_filled(key) and item.get(key) not in (None, ""):
        return item.get(key)
    if fallback and item.get(fallback) not in (None, ""):
        return item.get(fallback)
    return None


def _format_active_status(value) -> str | None:
    if isinstance(value, bool):
        return "Active" if value else "Inactive"
    if value is None:
        return None
    return "Active" if str(value).lower() in ("true", "1", "yes") else "Inactive"


def _format_default_flag(value) -> str | None:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return None
    return "Yes" if str(value).lower() in ("true", "1", "yes") else "No"


def _format_skills_based_routing(routing_type) -> str | None:
    if routing_type is None:
        return None
    return "Yes" if str(routing_type).upper() == "SKILL_BASED" else "No"


def _location_id_suffix(location_id: str) -> str | None:
    """Extract the UUID suffix from a Webex location id for dial-number matching."""
    try:
        pad = "=" * (-len(location_id) % 4)
        decoded = base64.urlsafe_b64decode(location_id + pad).decode()
        if "/" in decoded:
            return decoded.rsplit("/", 1)[-1].lower()
    except Exception:
        pass

    match = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        location_id,
        re.I,
    )
    return match.group(0).lower() if match else None


def _fetch_webex_location_lookup() -> dict[str, str]:
    """Build a map of dial-number location id -> Webex Calling location name."""
    try:
        data = webex_get("/locations")
        items = data.get("items", data if isinstance(data, list) else [])
        lookup: dict[str, str] = {}
        for item in items:
            location_id = item.get("id")
            name = item.get("name")
            if not location_id or not name:
                continue
            lookup[str(location_id)] = name
            suffix = _location_id_suffix(str(location_id))
            if suffix:
                lookup[suffix] = name
        return lookup
    except Exception:
        return {}


def _fetch_telephony_region_lookup() -> dict[str, str]:
    """Build a map of regionId -> media region display name."""
    org_id = get_webex_org_id()
    if not org_id:
        return {}

    try:
        data = wxcc_regional_get("/global/telephony-region", params={"orgId": org_id})
        items = data if isinstance(data, list) else _normalize_list(data)
        lookup: dict[str, str] = {}
        for item in items:
            region_id = item.get("id")
            region_name = item.get("region") or item.get("name")
            if region_id and region_name:
                lookup[str(region_id)] = str(region_name)
        return lookup
    except Exception:
        return {}


def _resolve_lookup_values(values: list[str], lookup: dict[str, str]) -> list[str]:
    """Replace known IDs with display names; leave unresolved values as-is."""
    resolved: list[str] = []
    for value in values:
        if not value:
            continue
        key = str(value)
        name = lookup.get(key) or lookup.get(key.lower())
        resolved.append(name if name else key)
    return resolved


def fetch_entry_points():
    from progress import is_filled

    if not is_filled(ENTRY_POINT_LIST_ENDPOINT):
        return []

    url = wxcc_org_url(ENTRY_POINT_LIST_ENDPOINT.format(org_id="{org_id}"))
    data = wxcc_get(url)
    items = _normalize_list(data)
    dial_map = _fetch_dial_numbers_by_entry_point()
    flow_names = _fetch_flow_name_lookup()
    location_names = _fetch_webex_location_lookup()
    region_names = _fetch_telephony_region_lookup()

    results = []
    for item in items:
        ep_id = item.get("id")
        dial_info = dial_map.get(ep_id, {})
        mapped_dns = dial_info.get("dns", [])
        # Telephony DNs come from dial-number mappings; other channels may use assetId
        channel_address = ", ".join(mapped_dns) if mapped_dns else item.get("assetId") or ""
        flow_id = item.get(EP_FLOW_ID_KEY) if is_filled(EP_FLOW_ID_KEY) else None
        flow_name = flow_names.get(flow_id) if flow_id else None
        calling_locations = _resolve_lookup_values(dial_info.get("locations", []), location_names)
        media_regions = _resolve_lookup_values(dial_info.get("regions", []), region_names)

        results.append(
            {
                "name": item.get(EP_NAME_KEY, "") if is_filled(EP_NAME_KEY) else "",
                "dn": channel_address or None,
                "calling_location": _join_unique(calling_locations),
                "media_region": _join_unique(media_regions),
                "channel_type": item.get("channelType"),
                "entry_point_type": item.get("entryPointType"),
                "flow_name": flow_name or flow_id,
                "queue_id": item.get(EP_QUEUE_ID_KEY) if is_filled(EP_QUEUE_ID_KEY) else None,
                "status": _format_active_status(
                    _item_value(item, EP_ACTIVE_KEY if is_filled(EP_ACTIVE_KEY) else None, "active")
                ),
                "_raw": item,
            }
        )
    return results


def fetch_queues():
    from progress import is_filled

    if not is_filled(QUEUE_LIST_ENDPOINT):
        return []

    url = wxcc_org_url(QUEUE_LIST_ENDPOINT.format(org_id="{org_id}"))
    data = wxcc_get(url)
    items = _normalize_list(data)

    return [
        {
            "id": item.get(QUEUE_ID_KEY) if is_filled(QUEUE_ID_KEY) else item.get("id"),
            "name": item.get(QUEUE_NAME_KEY, "") if is_filled(QUEUE_NAME_KEY) else "",
            "contact_direction": _item_value(
                item, QUEUE_CONTACT_DIRECTION_KEY if is_filled(QUEUE_CONTACT_DIRECTION_KEY) else None, "queueType"
            ),
            "type": _item_value(item, QUEUE_TYPE_KEY if is_filled(QUEUE_TYPE_KEY) else None, "channelType"),
            "skills_based_routing": _format_skills_based_routing(
                _item_value(
                    item,
                    QUEUE_ROUTING_TYPE_KEY if is_filled(QUEUE_ROUTING_TYPE_KEY) else None,
                    "queueRoutingType",
                )
            ),
            "status": _format_active_status(
                _item_value(item, QUEUE_STATUS_KEY if is_filled(QUEUE_STATUS_KEY) else None, "active")
            ),
            "_raw": item,
        }
        for item in items
    ]


GV_TYPE_ALIASES = {
    "DATETIME": "DATE_TIME",
    "DATE": "DATE_TIME",
    "DOUBLE": "DECIMAL",
    "FLOAT": "DECIMAL",
    "NUMBER": "DECIMAL",
    "BOOL": "BOOLEAN",
    "INT": "INTEGER",
}


def _normalize_gv_type(value) -> str:
    raw = str(value or "").strip()
    key = raw.upper().replace(" ", "_").replace("-", "_")
    return GV_TYPE_ALIASES.get(key, key or raw)


def _as_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _unwrap_cad_variable(data):
    if not isinstance(data, dict):
        return None
    inner = data.get("data")
    if isinstance(inner, dict) and any(key in inner for key in ("variableType", "name", "id", "defaultValue")):
        return inner
    return data


def _wxcc_http_error_message(exc: Exception) -> str:
    resp = getattr(exc, "response", None)
    if resp is None:
        return str(exc)
    try:
        payload = resp.json()
    except Exception:
        text = (getattr(resp, "text", None) or "").strip()
        return f"{resp.status_code} {text[:400] or resp.reason}"

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        messages = error.get("message")
        if isinstance(messages, list):
            parts = []
            for item in messages:
                if isinstance(item, dict):
                    parts.append(item.get("description") or item.get("message") or str(item))
                else:
                    parts.append(str(item))
            if parts:
                return "; ".join(parts)
        if isinstance(messages, str) and messages.strip():
            return messages
        if error.get("description"):
            return str(error["description"])
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return f"{resp.status_code} {resp.reason}"


def _validate_gv_default_value(var_type: str, value) -> str:
    text = "" if value is None else str(value).strip()
    if var_type == "BOOLEAN":
        if text.lower() not in ("true", "false"):
            raise ValueError("Boolean default value must be true or false.")
        return text.lower()
    if var_type == "INTEGER":
        if not re.fullmatch(r"-?\d+", text):
            raise ValueError("Integer default value must be a whole number.")
        return text
    if var_type == "DECIMAL":
        if not re.fullmatch(r"-?\d+(\.\d+)?", text):
            raise ValueError("Decimal default value must be a number.")
        return text
    if var_type == "DATE_TIME":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?", text):
            raise ValueError("Date Time default value must be YYYY-MM-DD or YYYY-MM-DDThh:mm.")
        return text
    if len(text) > 256:
        raise ValueError("String default value cannot exceed 256 characters.")
    return text


def _gv_default_value_field(var_type: str) -> dict:
    if var_type == "BOOLEAN":
        return {
            "key": "defaultValue",
            "label": "Default value",
            "input": "boolean-value",
            "required": True,
            "hint": "Boolean variables only accept true or false.",
        }
    if var_type == "INTEGER":
        return {
            "key": "defaultValue",
            "label": "Default value",
            "input": "integer",
            "required": True,
            "hint": "Whole number only.",
        }
    if var_type == "DECIMAL":
        return {
            "key": "defaultValue",
            "label": "Default value",
            "input": "decimal",
            "required": True,
            "hint": "Number, with or without a decimal.",
        }
    if var_type == "DATE_TIME":
        return {
            "key": "defaultValue",
            "label": "Default value",
            "input": "datetime",
            "required": True,
            "hint": "Tenant timezone. Use YYYY-MM-DD or YYYY-MM-DDThh:mm.",
        }
    return {
        "key": "defaultValue",
        "label": "Default value",
        "input": "text",
        "required": True,
        "maxLength": 256,
        "hint": "Up to 256 characters.",
    }


def global_variable_edit_form(raw: dict) -> dict:
    """Writable Update-by-ID fields for this variableType. Name and type stay read-only."""
    var_type = _normalize_gv_type(raw.get("variableType"))
    values = {
        "defaultValue": raw.get("defaultValue"),
        "description": raw.get("description") or "",
        "desktopLabel": raw.get("desktopLabel") or "",
        "active": _as_bool(raw.get("active"), True),
        "reportable": _as_bool(raw.get("reportable"), False),
        "sensitive": _as_bool(raw.get("sensitive"), False),
        "agentViewable": _as_bool(raw.get("agentViewable"), False),
        "agentEditable": _as_bool(raw.get("agentEditable"), False),
    }
    fields = [
        _gv_default_value_field(var_type),
        {
            "key": "description",
            "label": "Description",
            "input": "textarea",
            "required": False,
            "maxLength": 256,
        },
        {
            "key": "desktopLabel",
            "label": "Desktop label",
            "input": "text",
            "required": False,
            "maxLength": 50,
            "dependsOn": "agentViewable",
            "hint": "Label shown on Agent Desktop when the variable is viewable.",
        },
        {"key": "active", "label": "Active", "input": "boolean", "required": True},
        {
            "key": "reportable",
            "label": "Reportable",
            "input": "boolean",
            "required": True,
            "hint": "At most 100 global variables can be reportable at a time.",
        },
        {"key": "sensitive", "label": "Sensitive", "input": "boolean", "required": False},
        {"key": "agentViewable", "label": "Agent viewable", "input": "boolean", "required": True},
        {
            "key": "agentEditable",
            "label": "Agent editable",
            "input": "boolean",
            "required": True,
            "dependsOn": "agentViewable",
            "hint": "Agents can edit this value on Desktop only when it is also viewable.",
        },
    ]
    return {
        "id": raw.get("id"),
        "name": raw.get("name") or "",
        "variableType": var_type or raw.get("variableType") or "",
        "systemDefault": _as_bool(raw.get("systemDefault"), False),
        "version": raw.get("version"),
        "values": values,
        "fields": fields,
    }


def _summarize_global_variable(item: dict, variable_id: str | None = None) -> dict:
    from progress import is_filled

    raw = _unwrap_cad_variable(item) or item
    return {
        "id": _item_value(raw, GV_ID_KEY if is_filled(GV_ID_KEY) else None, "id") or variable_id,
        "name": raw.get(GV_NAME_KEY, "") if is_filled(GV_NAME_KEY) else raw.get("name") or "",
        "value": raw.get(GV_VALUE_KEY) if is_filled(GV_VALUE_KEY) else raw.get("defaultValue"),
        "type": _normalize_gv_type(
            _item_value(raw, GV_TYPE_KEY if is_filled(GV_TYPE_KEY) else None, "variableType")
        ),
        "status": _format_active_status(
            _item_value(raw, GV_STATUS_KEY if is_filled(GV_STATUS_KEY) else None, "active")
        ),
        "_raw": raw,
    }


def fetch_global_variables():
    from progress import is_filled

    if not is_filled(GLOBAL_VARIABLE_LIST_ENDPOINT):
        return []

    url = wxcc_org_url(GLOBAL_VARIABLE_LIST_ENDPOINT.format(org_id="{org_id}"))
    data = wxcc_get(url, params={"page": 0, "pageSize": 100})
    items = _normalize_list(data)
    return [_summarize_global_variable(item) for item in items]


def _global_variable_url(variable_id: str) -> str:
    from progress import is_filled

    if not is_filled(GV_UPDATE_ENDPOINT):
        raise ValueError("GV_UPDATE_ENDPOINT is not configured")
    return wxcc_org_url(GV_UPDATE_ENDPOINT, variable_id=variable_id)


def fetch_global_variable(variable_id: str):
    """Retrieve a single global variable by ID (full object for update)."""
    from progress import is_filled
    from requests import HTTPError

    if not variable_id or not is_filled(GV_UPDATE_ENDPOINT):
        return None

    url = _global_variable_url(variable_id)
    try:
        return _unwrap_cad_variable(wxcc_get(url))
    except HTTPError as exc:
        raise ValueError(_wxcc_http_error_message(exc)) from exc


def get_global_variable_edit_form(variable_id: str) -> dict:
    current = fetch_global_variable(variable_id)
    if not isinstance(current, dict):
        raise ValueError(f"Global variable {variable_id} not found")
    form = global_variable_edit_form(current)
    return {"global_variable": _summarize_global_variable(current, variable_id), "form": form}


def _build_gv_put_body(current: dict, updates: dict) -> dict:
    var_type = _normalize_gv_type(current.get("variableType"))
    merged = dict(current)
    for key, value in (updates or {}).items():
        if key == "value":
            merged["defaultValue"] = value
        elif key in {
            "defaultValue",
            "description",
            "desktopLabel",
            "active",
            "reportable",
            "sensitive",
            "agentViewable",
            "agentEditable",
        }:
            merged[key] = value

    agent_viewable = _as_bool(merged.get("agentViewable"), False)
    agent_editable = _as_bool(merged.get("agentEditable"), False) if agent_viewable else False
    default_value = _validate_gv_default_value(
        var_type,
        merged.get(GV_UPDATE_VALUE_KEY, merged.get("defaultValue")),
    )

    body = {
        "id": current.get("id"),
        "name": current.get("name"),
        "variableType": current.get("variableType") or var_type,
        "defaultValue": default_value,
        "active": _as_bool(merged.get("active"), True),
        "reportable": _as_bool(merged.get("reportable"), False),
        "agentViewable": agent_viewable,
        "agentEditable": agent_editable,
        "sensitive": _as_bool(merged.get("sensitive"), False),
    }
    description = merged.get("description")
    if description not in (None, ""):
        body["description"] = str(description)[:256]
    desktop_label = merged.get("desktopLabel")
    if agent_viewable and desktop_label not in (None, ""):
        body["desktopLabel"] = str(desktop_label)[:50]
    if current.get("version") is not None:
        body["version"] = current.get("version")
    if not body.get("id"):
        raise ValueError("Update payload is missing the variable ID.")
    if not body.get("name"):
        raise ValueError("Update payload is missing the variable name.")
    if not body.get("variableType"):
        raise ValueError("Update payload is missing variableType.")
    return body


def update_global_variable(variable_id: str, updates: dict | None = None):
    """PUT the Update-by-ID payload using writable CadVariableDTO fields for this type."""
    from progress import is_filled
    from requests import HTTPError

    if not is_filled(GV_UPDATE_ENDPOINT):
        raise ValueError("Complete step 2.6 before updating global variables")

    current = fetch_global_variable(variable_id)
    if not isinstance(current, dict):
        raise ValueError(f"Global variable {variable_id} not found")
    if _as_bool(current.get("systemDefault"), False):
        raise ValueError("System default variables cannot be updated from the dashboard.")

    if not current.get("id"):
        current = {**current, "id": variable_id}
    body = _build_gv_put_body(current, updates or {})
    url = _global_variable_url(variable_id)
    try:
        updated = wxcc_put(url, body)
    except HTTPError as exc:
        raise ValueError(_wxcc_http_error_message(exc)) from exc

    raw = _unwrap_cad_variable(updated) or updated
    return _summarize_global_variable(raw, variable_id)


def fetch_aux_codes():
    from progress import is_filled

    if not is_filled(AUX_CODE_LIST_ENDPOINT):
        return []

    url = wxcc_org_url(AUX_CODE_LIST_ENDPOINT.format(org_id="{org_id}"))
    data = wxcc_get(url)
    items = data if isinstance(data, list) else data.get("data", [])

    return [
        {
            "id": item.get(AUX_CODE_ID_KEY) if is_filled(AUX_CODE_ID_KEY) else item.get("id"),
            "name": item.get(AUX_CODE_NAME_KEY, "") if is_filled(AUX_CODE_NAME_KEY) else "",
            "code_type": _item_value(
                item, AUX_CODE_TYPE_KEY if is_filled(AUX_CODE_TYPE_KEY) else None, "workTypeCode"
            ),
            "default": _format_default_flag(
                _item_value(item, AUX_CODE_DEFAULT_KEY if is_filled(AUX_CODE_DEFAULT_KEY) else None, "defaultCode")
            ),
            "status": _format_active_status(
                _item_value(item, AUX_CODE_STATUS_KEY if is_filled(AUX_CODE_STATUS_KEY) else None, "active")
            ),
            "_raw": item,
        }
        for item in items
    ]


def _team_dn(item: dict) -> str | None:
    """Return dialed number for capacity-based teams when configured."""
    from progress import is_filled

    team_type = item.get(TEAM_TYPE_KEY) if is_filled(TEAM_TYPE_KEY) else item.get("teamType")
    if team_type != "CAPACITY":
        return None

    dn_key = TEAM_DN_KEY if is_filled(TEAM_DN_KEY) else "dialedNumber"
    dn = item.get(dn_key)
    if not dn or str(dn).strip() in ("", "0"):
        return None
    return str(dn)


def fetch_teams():
    from progress import is_filled

    if not is_filled(TEAM_LIST_ENDPOINT):
        return []

    url = wxcc_org_url(TEAM_LIST_ENDPOINT.format(org_id="{org_id}"))
    data = wxcc_get(url, params={"page": 0, "pageSize": 100})
    items = _normalize_list(data)

    results = []
    for item in items:
        results.append(
            {
                "name": _item_value(item, TEAM_NAME_KEY if is_filled(TEAM_NAME_KEY) else None, "name")
                or item.get("teamName")
                or item.get("displayName")
                or "",
                "site": item.get(TEAM_SITE_NAME_KEY) if is_filled(TEAM_SITE_NAME_KEY) else item.get("siteName"),
                "type": item.get(TEAM_TYPE_KEY) if is_filled(TEAM_TYPE_KEY) else item.get("teamType"),
                "dn": _team_dn(item),
                "status": _item_value(item, TEAM_STATUS_KEY if is_filled(TEAM_STATUS_KEY) else None, "teamStatus"),
                "_raw": item,
            }
        )
    return results
