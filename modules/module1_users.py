"""
Users — Contact Center user list, profiles, skills, teams, and channel types.

Endpoints and field names are injected from api_config.py.

Developer Portal:
https://developer.webex.com/webex-contact-center/docs/api/v1/users
"""

from api.client import wxcc_get, wxcc_org_url

MODULE_ID = "module1"
MODULE_NAME = "Users"

STEPS = [
    {
        "id": "1.1",
        "label": "List Users API",
        "variables": ["USERS_LIST_ENDPOINT"],
    },
    {
        "id": "1.2",
        "label": "Name & Email Fields",
        "variables": ["USER_FIRST_NAME_KEY", "USER_LAST_NAME_KEY", "USER_EMAIL_KEY"],
    },
    {
        "id": "1.3",
        "label": "Profile Information",
        "variables": [
            "AGENT_PROFILE_ID_KEY",
            "MULTIMEDIA_PROFILE_ID_KEY",
            "USER_PROFILE_ID_KEY",
            "AGENT_PROFILE_LIST_ENDPOINT",
            "AGENT_PROFILE_NAME_KEY",
            "USER_PROFILE_LIST_ENDPOINT",
            "USER_PROFILE_NAME_KEY",
            "MULTIMEDIA_PROFILE_LIST_ENDPOINT",
            "MULTIMEDIA_PROFILE_NAME_KEY",
        ],
    },
    {
        "id": "1.4",
        "label": "Contact Channel Types",
        "variables": [
            "CHANNEL_TELEPHONY_KEY",
            "CHANNEL_CHAT_KEY",
            "CHANNEL_EMAIL_KEY",
            "CHANNEL_SOCIAL_KEY",
        ],
    },
    {
        "id": "1.5",
        "label": "Skill Information",
        "variables": ["SKILL_PROFILE_LIST_ENDPOINT", "SKILL_PROFILE_ID_KEY", "SKILL_NAME_KEY"],
    },
    {
        "id": "1.6",
        "label": "Team Information",
        "variables": ["TEAM_LIST_ENDPOINT", "TEAM_IDS_KEY", "TEAM_NAME_KEY"],
    },
]


def _normalize_list(data, data_key=None):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if data_key and isinstance(data.get(data_key), list):
            return data[data_key]
        for key in ("data", "items", "records", "teams", "users", "content"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = _normalize_list(value)
                if nested:
                    return nested
    return []


def _value_at(record: dict, key):
    if not key or not isinstance(record, dict):
        return None
    if key in record:
        return record[key]
    if isinstance(key, str) and "." in key:
        current = record
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current
    return None


def _wxcc_paged_list(list_endpoint, page_size=100):
    """Fetch every page of a WxCC list API. pageSize=1000 is rejected by some resources."""
    from progress import is_filled

    if not is_filled(list_endpoint):
        return []

    url = wxcc_org_url(list_endpoint)
    items = []
    for page in range(0, 50):
        try:
            data = wxcc_get(url, params={"page": page, "pageSize": page_size})
        except Exception:
            if page == 0:
                try:
                    data = wxcc_get(url)
                except Exception:
                    return []
            else:
                break
        batch = _normalize_list(data)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < page_size:
            break
    return items


def _team_id_from_value(item):
    if item is None or item is False:
        return ""
    if isinstance(item, dict):
        value = item.get("id") or item.get("teamId") or item.get("sid") or item.get("teamSID")
        return str(value) if value else ""
    text = str(item).strip()
    return text if text and text not in ("None", "null") else ""


def _parse_team_ids(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [tid for tid in (_team_id_from_value(item) for item in raw_value) if tid]
    if isinstance(raw_value, dict):
        tid = _team_id_from_value(raw_value)
        return [tid] if tid else []
    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value.startswith("["):
            import json

            try:
                parsed = json.loads(raw_value)
                return _parse_team_ids(parsed)
            except json.JSONDecodeError:
                pass
        if "," in raw_value or ";" in raw_value:
            parts = [part.strip() for part in raw_value.replace(";", ",").split(",") if part.strip()]
            return [tid for tid in (_team_id_from_value(part) for part in parts) if tid]
        tid = _team_id_from_value(raw_value)
        return [tid] if tid else []
    return []


def _team_names_from_user(user: dict, team_ids: list, team_lookup: dict, team_id_key: str = "") -> str:
    names: list[str] = []
    source_keys = [team_id_key] if team_id_key else []
    source_keys.extend(
        ("teams", "team", "teamIds", "teamids", "associatedTeamIds", "teamName", "teamNames")
    )
    for key in dict.fromkeys(k for k in source_keys if k):
        raw = _value_at(user, key)
        if raw is None:
            continue
        entries = raw if isinstance(raw, list) else [raw]
        for entry in entries:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("teamName") or entry.get("displayName")
                if name:
                    names.append(str(name))
            elif isinstance(entry, str) and key in ("teamName", "teamNames") and entry.strip():
                names.append(entry.strip())
    if names:
        return ", ".join(dict.fromkeys(names))
    looked_up = [_lookup_name(tid, team_lookup) for tid in team_ids]
    return ", ".join(name for name in looked_up if name)


def _collect_user_team_ids(user: dict, team_id_key: str = "") -> list:
    ids: list[str] = []
    keys = [team_id_key] if team_id_key else []
    keys.extend(("teamIds", "teamids", "teams", "teamId", "teamSID", "teamSids", "associatedTeamIds"))
    for key in dict.fromkeys(k for k in keys if k):
        ids.extend(_parse_team_ids(_value_at(user, key)))
    return list(dict.fromkeys(ids))


def _add_name(bucket: dict, key, name: str) -> None:
    if not key or not name:
        return
    text = str(key)
    names = bucket.setdefault(text, [])
    if name not in names:
        names.append(name)
    lower = text.lower()
    if lower != text:
        names_lower = bucket.setdefault(lower, [])
        if name not in names_lower:
            names_lower.append(name)


def _index_team_list() -> tuple[dict, dict]:
    """Map team IDs → names and user IDs → team names.

    List Users v2 does not include teamIds. Each team record carries userIds,
    so membership is joined from the team list.
    """
    from progress import is_filled

    if not is_filled(TEAM_LIST_ENDPOINT):
        return {}, {}

    lookup: dict = {}
    by_user: dict = {}
    name_keys = _name_keys(TEAM_NAME_KEY, "name", "teamName", "displayName")
    for item in _wxcc_paged_list(TEAM_LIST_ENDPOINT):
        if not isinstance(item, dict):
            continue
        name = ""
        for key in name_keys:
            if item.get(key):
                name = str(item[key]).strip()
                break
        if not name:
            continue
        for candidate in (item.get("id"), item.get("teamId"), item.get("sid"), item.get("teamSID"), item.get("dbId")):
            if not candidate:
                continue
            text = str(candidate)
            lookup[text] = name
            lookup[text.lower()] = name
        user_ids_key = TEAM_IDS_KEY if is_filled(TEAM_IDS_KEY) else "userIds"
        raw_ids = item.get(user_ids_key)
        if raw_ids is None:
            raw_ids = item.get("userIds") or item.get("users") or item.get("members")
        for uid in _parse_team_ids(raw_ids):
            _add_name(by_user, uid, name)
    return lookup, by_user


def _names_for_user(user: dict, teams_by_user: dict) -> str:
    for candidate in (user.get("id"), user.get("ciUserId"), user.get("broadCloudUserId")):
        if not candidate:
            continue
        text = str(candidate)
        names = teams_by_user.get(text) or teams_by_user.get(text.lower())
        if names:
            return ", ".join(names)
    return ""


def _enrich_team_lookup(lookup: dict, team_ids: list) -> dict:
    """Fill gaps with Module 2's team list, then GET-by-id for a few remaining IDs."""
    from progress import is_filled

    missing = [tid for tid in team_ids if tid and not _lookup_name(tid, lookup)]
    if not missing:
        return lookup

    try:
        from lab_context import inject_answers
        from modules import module2_org_data as module2

        inject_answers(module2)
        for team in module2.fetch_teams() or []:
            name = team.get("name")
            raw = team.get("_raw") if isinstance(team.get("_raw"), dict) else {}
            if not name:
                continue
            for candidate in (raw.get("id"), raw.get("sid"), raw.get("teamId"), raw.get("teamSID")):
                if not candidate:
                    continue
                text = str(candidate)
                lookup[text] = name
                lookup[text.lower()] = name
    except Exception:
        pass

    missing = [tid for tid in team_ids if tid and not _lookup_name(tid, lookup)]
    if not missing or not is_filled(TEAM_LIST_ENDPOINT):
        return lookup

    base = str(TEAM_LIST_ENDPOINT).rstrip("/")
    for tid in missing[:20]:
        try:
            data = wxcc_get(wxcc_org_url(f"{base}/{tid}"))
            item = data if isinstance(data, dict) else {}
            if isinstance(item.get("data"), dict):
                item = item["data"]
            name = item.get("name") or item.get("teamName") or item.get("displayName")
            if not name:
                continue
            lookup[str(tid)] = name
            lookup[str(tid).lower()] = name
            if item.get("id"):
                lookup[str(item["id"])] = name
        except Exception:
            continue
    return lookup


def _lookup_name(record_id, lookup):
    if not record_id:
        return ""
    text = str(record_id)
    return lookup.get(text) or lookup.get(text.lower()) or ""


def _name_keys(primary_key: str, *fallbacks: str) -> tuple[str, ...]:
    from progress import is_filled

    keys: list[str] = []
    if is_filled(primary_key):
        keys.append(primary_key)
    keys.extend(fallbacks)
    return tuple(dict.fromkeys(keys))


def _fetch_name_lookup(list_endpoint, name_keys=("name",), id_key="id"):
    from progress import is_filled

    if not is_filled(list_endpoint):
        return {}

    try:
        items = _wxcc_paged_list(list_endpoint)
        lookup = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            name = ""
            for key in name_keys:
                if item.get(key):
                    name = item[key]
                    break
            if not name:
                continue
            for candidate in (
                item.get(id_key),
                item.get("id"),
                item.get("teamId"),
                item.get("sid"),
                item.get("teamSID"),
                item.get("profileId"),
                item.get("dbId"),
            ):
                if not candidate:
                    continue
                text = str(candidate)
                lookup[text] = name
                lookup[text.lower()] = name
        return lookup
    except Exception:
        return {}


def _channel_capacity(profile: dict, field_key: str, fallback: str) -> int:
    from progress import is_filled

    key = field_key if is_filled(field_key) else fallback
    value = profile.get(key)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_channel_types(profile: dict) -> str:
    from progress import is_filled

    if not any(
        is_filled(v)
        for v in (CHANNEL_TELEPHONY_KEY, CHANNEL_CHAT_KEY, CHANNEL_EMAIL_KEY, CHANNEL_SOCIAL_KEY)
    ):
        return ""

    labels = []
    for field_key, label in (
        (CHANNEL_TELEPHONY_KEY, "telephony"),
        (CHANNEL_CHAT_KEY, "chat"),
        (CHANNEL_EMAIL_KEY, "email"),
        (CHANNEL_SOCIAL_KEY, "social"),
    ):
        if _channel_capacity(profile, field_key, label) > 0:
            labels.append(label)
    return ", ".join(labels)


def _fetch_channel_type_lookup() -> dict[str, str]:
    from progress import is_filled

    if not is_filled(MULTIMEDIA_PROFILE_LIST_ENDPOINT):
        return {}

    try:
        lookup: dict[str, str] = {}
        for item in _wxcc_paged_list(MULTIMEDIA_PROFILE_LIST_ENDPOINT):
            profile_id = item.get("id") or item.get("profileId") or item.get("sid")
            if not profile_id:
                continue
            channel_types = _format_channel_types(item)
            if channel_types:
                text = str(profile_id)
                lookup[text] = channel_types
                lookup[text.lower()] = channel_types
        return lookup
    except Exception:
        return {}


def _get_profile_lookups():
    from progress import is_filled

    lookups = {}
    if is_filled(AGENT_PROFILE_LIST_ENDPOINT):
        lookups["agent"] = _fetch_name_lookup(
            AGENT_PROFILE_LIST_ENDPOINT,
            _name_keys(AGENT_PROFILE_NAME_KEY, "name", "profileName"),
        )
    if is_filled(USER_PROFILE_LIST_ENDPOINT):
        lookups["user"] = _fetch_name_lookup(
            USER_PROFILE_LIST_ENDPOINT,
            _name_keys(USER_PROFILE_NAME_KEY, "name"),
        )
    if is_filled(MULTIMEDIA_PROFILE_LIST_ENDPOINT):
        lookups["multimedia"] = _fetch_name_lookup(
            MULTIMEDIA_PROFILE_LIST_ENDPOINT,
            _name_keys(MULTIMEDIA_PROFILE_NAME_KEY, "name"),
        )
    if is_filled(SKILL_PROFILE_LIST_ENDPOINT):
        skill_id_key = SKILL_PROFILE_ID_KEY if is_filled(SKILL_PROFILE_ID_KEY) else "id"
        lookups["skill"] = _fetch_name_lookup(
            SKILL_PROFILE_LIST_ENDPOINT,
            _name_keys(SKILL_NAME_KEY, "name"),
            id_key=skill_id_key,
        )
    team_lookup, teams_by_user = _index_team_list()
    lookups["team"] = team_lookup
    lookups["team_by_user"] = teams_by_user
    return lookups


def fetch_users():
    """Fetch and normalize user list for the dashboard."""
    from progress import is_filled

    if not is_filled(USERS_LIST_ENDPOINT):
        return []

    url = wxcc_org_url(USERS_LIST_ENDPOINT)
    users_raw = _wxcc_paged_list(USERS_LIST_ENDPOINT)
    if not users_raw:
        data = wxcc_get(url)
        users_raw = _normalize_list(data)

    lookups = _get_profile_lookups()
    agent_lookup = lookups.get("agent", {})
    user_lookup = lookups.get("user", {})
    multimedia_lookup = lookups.get("multimedia", {})
    skill_lookup = lookups.get("skill", {})
    team_lookup = lookups.get("team", {})
    teams_by_user = lookups.get("team_by_user", {})
    channel_type_lookup = _fetch_channel_type_lookup()

    pending_team_ids: list[str] = []
    parsed_users = []
    for user in users_raw:
        user_id = user.get("id")
        first_name = user.get(USER_FIRST_NAME_KEY, "") if is_filled(USER_FIRST_NAME_KEY) else user.get("firstName", "")
        last_name = user.get(USER_LAST_NAME_KEY, "") if is_filled(USER_LAST_NAME_KEY) else user.get("lastName", "")
        email = user.get(USER_EMAIL_KEY, "") if is_filled(USER_EMAIL_KEY) else user.get("email", "")
        display_name = user.get("displayName") or f"{first_name} {last_name}".strip() or email or user_id

        agent_profile_id = user.get(AGENT_PROFILE_ID_KEY) if is_filled(AGENT_PROFILE_ID_KEY) else None
        multimedia_profile_id = user.get(MULTIMEDIA_PROFILE_ID_KEY) if is_filled(MULTIMEDIA_PROFILE_ID_KEY) else None
        user_profile_id = user.get(USER_PROFILE_ID_KEY) if is_filled(USER_PROFILE_ID_KEY) else None
        skill_profile_id = user.get("skillProfileId")
        team_ids = _collect_user_team_ids(user, "")
        pending_team_ids.extend(team_ids)
        parsed_users.append(
            {
                "user": user,
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "display_name": display_name,
                "agent_profile_id": agent_profile_id,
                "multimedia_profile_id": multimedia_profile_id,
                "user_profile_id": user_profile_id,
                "skill_profile_id": skill_profile_id,
                "team_id_key": "",
                "team_ids": team_ids,
            }
        )

    team_lookup = _enrich_team_lookup(team_lookup, list(dict.fromkeys(pending_team_ids)))

    users = []
    for parsed in parsed_users:
        user = parsed["user"]
        team_ids = parsed["team_ids"]
        team_names = _names_for_user(user, teams_by_user) or _team_names_from_user(
            user, team_ids, team_lookup, parsed["team_id_key"]
        )
        agent_profile_id = parsed["agent_profile_id"]
        multimedia_profile_id = parsed["multimedia_profile_id"]
        user_profile_id = parsed["user_profile_id"]
        skill_profile_id = parsed["skill_profile_id"]
        users.append(
            {
                "id": parsed["user_id"],
                "display_name": parsed["display_name"],
                "first_name": parsed["first_name"],
                "last_name": parsed["last_name"],
                "email": parsed["email"],
                "agent_profile_id": agent_profile_id,
                "agent_profile_name": _lookup_name(agent_profile_id, agent_lookup) if agent_profile_id else "",
                "multimedia_profile_id": multimedia_profile_id,
                "multimedia_profile_name": _lookup_name(multimedia_profile_id, multimedia_lookup) if multimedia_profile_id else "",
                "user_profile_id": user_profile_id,
                "user_profile_name": _lookup_name(user_profile_id, user_lookup) if user_profile_id else "",
                "skill_profile_id": skill_profile_id,
                "skill_profile_name": _lookup_name(skill_profile_id, skill_lookup) if skill_profile_id else "",
                "team_ids": team_ids,
                "team_names": team_names,
                "channel_types": _lookup_name(multimedia_profile_id, channel_type_lookup) if multimedia_profile_id else "",
                "_raw": user,
            }
        )
    return users
