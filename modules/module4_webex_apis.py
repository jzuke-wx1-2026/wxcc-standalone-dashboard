"""
Webex Control Hub & Webex Calling APIs — people, locations, and PSTN data.

Endpoints and field names are injected from api_config.py.

Developer Portal:
  - People: https://developer.webex.com/docs/api/v1/people
  - Locations: https://developer.webex.com/calling/docs/api/v1/locations
  - PSTN: https://developer.webex.com/calling/docs/api/v1/pstn
"""

from concurrent.futures import ThreadPoolExecutor

from api.client import webex_get
from config import FILL_IN_PLACEHOLDER
from lab_paths import format_endpoint_template
from lab_store import get_answer

MODULE_ID = "module4"
MODULE_NAME = "Control Hub & Webex Calling"

# Hardcoded lookup / nested keys (not lab steps)
_ROLE_ID_KEY = "id"
_ROLE_NAME_KEY = "name"
_LICENSE_ID_KEY = "id"
_LICENSE_NAME_KEY = "name"
_LOCATION_COUNTRY_KEY = "country"
_PSTN_TYPE_KEY = "pstnConnectionType"
_PSTN_CARRIER_NAME_KEY = "displayName"
_LOCATION_ADDRESS_LINE1_KEY = "address1"
_LOCATION_CITY_KEY = "city"
_LOCATION_STATE_KEY = "state"
_LOCATION_POSTAL_CODE_KEY = "postalCode"
_LOCATION_PHONE_LOCATION_ID_KEY = "id"
_LOCATION_DETAIL_PATH = "/locations/{location_id}"

STEPS = [
    {
        "id": "4.1",
        "label": "Control Hub User Info",
        "variables": [
            "WEBEX_PEOPLE_ENDPOINT",
            "PEOPLE_EMAIL_KEY",
            "PEOPLE_DISPLAY_NAME_KEY",
            "PEOPLE_STATUS_KEY",
            "PEOPLE_ROLES_KEY",
            "PEOPLE_LICENSES_KEY",
            "WEBEX_ROLES_ENDPOINT",
            "WEBEX_LICENSES_ENDPOINT",
        ],
    },
    {
        "id": "4.2",
        "label": "Webex Calling Locations",
        "variables": [
            "WEBEX_LOCATION_ENDPOINT",
            "LOCATION_NAME_KEY",
            "LOCATION_ID_KEY",
            "LOCATION_ADDRESS_KEY",
            "WEBEX_PHONE_NUMBERS_ENDPOINT",
            "PHONE_NUMBER_KEY",
        ],
    },
    {
        "id": "4.3",
        "label": "PSTN / Carrier / Trunk",
        "variables": ["PSTN_CONNECTION_ENDPOINT"],
    },
]


def _normalize_webex_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", [])
    return []


def _first_value(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def _fetch_webex_name_lookup(list_endpoint, id_key, name_key):
    from progress import is_filled

    if not all(is_filled(v) for v in (list_endpoint, id_key, name_key)):
        return {}

    try:
        data = webex_get(list_endpoint)
        lookup = {}
        for item in _normalize_webex_list(data):
            record_id = item.get(id_key)
            record_name = item.get(name_key)
            if record_id and record_name:
                lookup[record_id] = record_name
        return lookup
    except Exception:
        return {}


def _resolve_names(record_ids, lookup: dict[str, str]) -> str | None:
    if not record_ids:
        return None
    names = [lookup.get(record_id, record_id) for record_id in record_ids if record_id]
    return ", ".join(names) if names else None


def fetch_webex_people():
    from progress import is_filled

    if not is_filled(WEBEX_PEOPLE_ENDPOINT):
        return []

    data = webex_get(WEBEX_PEOPLE_ENDPOINT)
    items = _normalize_webex_list(data)
    role_lookup = _fetch_webex_name_lookup(WEBEX_ROLES_ENDPOINT, _ROLE_ID_KEY, _ROLE_NAME_KEY)
    license_lookup = _fetch_webex_name_lookup(
        WEBEX_LICENSES_ENDPOINT, _LICENSE_ID_KEY, _LICENSE_NAME_KEY
    )

    results = []
    for item in items:
        role_ids = item.get(PEOPLE_ROLES_KEY) if is_filled(PEOPLE_ROLES_KEY) else item.get("roles", [])
        license_ids = (
            item.get(PEOPLE_LICENSES_KEY) if is_filled(PEOPLE_LICENSES_KEY) else item.get("licenses", [])
        )
        email_value = item.get(PEOPLE_EMAIL_KEY) if is_filled(PEOPLE_EMAIL_KEY) else item.get("emails")

        results.append(
            {
                "email": _first_value(email_value),
                "display_name": item.get(PEOPLE_DISPLAY_NAME_KEY, "") if is_filled(PEOPLE_DISPLAY_NAME_KEY) else "",
                "role_name": _resolve_names(role_ids, role_lookup),
                "license_names": _resolve_names(license_ids, license_lookup),
                "status": item.get(PEOPLE_STATUS_KEY) if is_filled(PEOPLE_STATUS_KEY) else None,
                "_raw": item,
            }
        )
    return results


def _location_address(item: dict) -> dict:
    from progress import is_filled

    address_key = LOCATION_ADDRESS_KEY if is_filled(LOCATION_ADDRESS_KEY) else "address"
    address = item.get(address_key) or {}
    return address if isinstance(address, dict) else {}


def _format_location_address(address: dict) -> str | None:
    if not address:
        return None

    parts = [
        address.get(_LOCATION_ADDRESS_LINE1_KEY),
        address.get(_LOCATION_CITY_KEY),
        address.get(_LOCATION_STATE_KEY),
        address.get(_LOCATION_POSTAL_CODE_KEY),
        address.get(_LOCATION_COUNTRY_KEY),
    ]
    cleaned = [str(part) for part in parts if part]
    return ", ".join(cleaned) if cleaned else None


def _phone_numbers_endpoint() -> str | None:
    from progress import is_filled

    endpoint = get_answer("WEBEX_PHONE_NUMBERS_ENDPOINT", FILL_IN_PLACEHOLDER)
    return endpoint if is_filled(endpoint) else None


def _phone_number_key() -> str:
    from progress import is_filled

    key = get_answer("PHONE_NUMBER_KEY", FILL_IN_PLACEHOLDER)
    return key if is_filled(key) else "phoneNumber"


def _fetch_provisioned_number_counts() -> dict[str, int]:
    endpoint = _phone_numbers_endpoint()
    if not endpoint:
        return {}

    try:
        data = webex_get(endpoint)
        phone_key = _phone_number_key()
        counts: dict[str, int] = {}
        for item in data.get("phoneNumbers", _normalize_webex_list(data)):
            if not item.get(phone_key):
                continue
            location = item.get("location") or {}
            location_id = location.get(_LOCATION_PHONE_LOCATION_ID_KEY)
            if location_id:
                counts[location_id] = counts.get(location_id, 0) + 1
        return counts
    except Exception:
        return {}


def fetch_locations():
    from progress import is_filled

    if not is_filled(WEBEX_LOCATION_ENDPOINT):
        return []

    data = webex_get(WEBEX_LOCATION_ENDPOINT)
    items = data.get("items", data if isinstance(data, list) else [])
    number_counts = _fetch_provisioned_number_counts()

    return [
        {
            "id": item.get(LOCATION_ID_KEY) if is_filled(LOCATION_ID_KEY) else item.get("id"),
            "name": item.get(LOCATION_NAME_KEY, "") if is_filled(LOCATION_NAME_KEY) else "",
            "country": _location_address(item).get(_LOCATION_COUNTRY_KEY),
            "provisioned_numbers": number_counts.get(
                item.get(LOCATION_ID_KEY) if is_filled(LOCATION_ID_KEY) else item.get("id"),
                0,
            ),
            "address": _format_location_address(_location_address(item)),
            "_raw": item,
        }
        for item in items
    ]


def _normalize_phone_number(number: str) -> str:
    cleaned = str(number).strip()
    if cleaned and not cleaned.startswith("+") and cleaned.replace("-", "").isdigit():
        digits = cleaned.replace("-", "").replace(" ", "")
        if digits:
            cleaned = f"+{digits}"
    return cleaned


def _format_connection_carrier(pstn_data: dict) -> str | None:
    carrier = pstn_data.get(_PSTN_CARRIER_NAME_KEY)
    connection = pstn_data.get(_PSTN_TYPE_KEY)
    if carrier and connection:
        return f"{carrier} ({connection})"
    return carrier or connection


def fetch_pstn_connection(location_id: str):
    from lab_api_cache import cached

    return cached(f"webex:pstn:{location_id}", lambda: _fetch_pstn_connection_uncached(location_id))


def _fetch_pstn_connection_uncached(location_id: str):
    from progress import is_filled

    if not is_filled(PSTN_CONNECTION_ENDPOINT):
        return {}

    path = format_endpoint_template(PSTN_CONNECTION_ENDPOINT, location_id=location_id)
    data = webex_get(path)

    return {
        "connection_carrier": _format_connection_carrier(data),
        "pstn_type": data.get(_PSTN_TYPE_KEY),
        "carrier_name": data.get(_PSTN_CARRIER_NAME_KEY),
        "_raw": data,
    }


def _fetch_location_country(location_id: str, cache: dict[str, str | None]) -> str | None:
    from progress import is_filled

    if location_id in cache:
        return cache[location_id]

    try:
        path = format_endpoint_template(_LOCATION_DETAIL_PATH, location_id=location_id)
        data = webex_get(path)
        address = data.get(LOCATION_ADDRESS_KEY if is_filled(LOCATION_ADDRESS_KEY) else "address") or {}
        country = address.get(_LOCATION_COUNTRY_KEY) if isinstance(address, dict) else None
        cache[location_id] = country
        return country
    except Exception:
        cache[location_id] = None
        return None


def _fetch_phone_number_lookup() -> dict[str, dict]:
    endpoint = _phone_numbers_endpoint()
    if not endpoint:
        return {}

    try:
        data = webex_get(endpoint)
        phone_key = _phone_number_key()
        lookup = {}
        for item in data.get("phoneNumbers", _normalize_webex_list(data)):
            number = item.get(phone_key)
            if number:
                lookup[_normalize_phone_number(number)] = item
        return lookup
    except Exception:
        return {}


def fetch_ep_pstn_numbers():
    """PSTN details for telephony numbers mapped to Module 2 entry points."""
    from progress import is_filled

    if not is_filled(PSTN_CONNECTION_ENDPOINT) or not _phone_numbers_endpoint():
        return []

    from lab_api_cache import cached
    from lab_context import inject_answers
    from modules import module2_org_data as module2

    inject_answers(module2)
    entry_payload = cached("org:entry_points", lambda: {"entry_points": module2.fetch_entry_points()})
    entry_points = entry_payload.get("entry_points") or []
    phone_lookup = _fetch_phone_number_lookup()

    pending: list[dict] = []
    seen_numbers: set[str] = set()
    location_ids: list[str] = []

    for entry_point in entry_points:
        dn_value = entry_point.get("dn")
        if not dn_value:
            continue

        for raw_number in str(dn_value).split(","):
            number = _normalize_phone_number(raw_number)
            if not number or number in seen_numbers:
                continue
            seen_numbers.add(number)

            phone = phone_lookup.get(number)
            if not phone:
                continue

            location = phone.get("location") or {}
            location_id = location.get("id")
            if location_id:
                location_ids.append(location_id)
            pending.append(
                {
                    "entry_point": entry_point,
                    "phone": phone,
                    "number": number,
                    "location_id": location_id,
                    "location_name": location.get("name") or entry_point.get("calling_location"),
                }
            )

    unique_ids = list(dict.fromkeys(location_ids))
    pstn_by_id: dict[str, dict] = {}
    country_by_id: dict[str, str | None] = {}

    def _pstn(location_id: str) -> tuple[str, dict]:
        try:
            return location_id, fetch_pstn_connection(location_id)
        except Exception:
            return location_id, {}

    def _country(location_id: str) -> tuple[str, str | None]:
        return location_id, _fetch_location_country(location_id, {})

    if unique_ids:
        with ThreadPoolExecutor(max_workers=8) as pool:
            pstn_futs = [pool.submit(_pstn, lid) for lid in unique_ids]
            country_futs = [pool.submit(_country, lid) for lid in unique_ids]
            for fut in pstn_futs:
                location_id, payload = fut.result()
                pstn_by_id[location_id] = payload
            for fut in country_futs:
                location_id, country = fut.result()
                country_by_id[location_id] = country

    rows = []
    for item in pending:
        location_id = item["location_id"]
        pstn = pstn_by_id.get(location_id) or {}
        rows.append(
            {
                "entry_point": item["entry_point"].get("name"),
                "number": item["number"],
                "location_name": item["location_name"],
                "connection_carrier": pstn.get("connection_carrier"),
                "country": country_by_id.get(location_id),
                "_raw": {"entry_point": item["entry_point"], "phone": item["phone"]},
            }
        )
    return rows
