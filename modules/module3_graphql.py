"""
GraphQL reports — CSR, CAR, ASR, AAR, and real-time agent states.

Field names are injected from api_config.py.

Developer Portal:
https://developer.webex.com/webex-contact-center/docs/getting-started-with-search-api
"""

import time

from api.client import wxcc_graphql
from lab_data_dictionary import graphql_leaf

MODULE_ID = "module3"
MODULE_NAME = "GraphQL Reports"

def _gql_field(key: str) -> str:
    """Resolve a lab answer (full dictionary path or leaf) to a GraphQL field name."""
    return graphql_leaf(key)

RT_TIME_WINDOW_MS = 7 * 24 * 60 * 60 * 1000  # 7 days — session startTime must fall in window
ACTIVITIES_LOOKBACK_MS = 23 * 60 * 60 * 1000  # REST Activities API max span is 24 hours
REPORT_LOOKBACK_DAYS = 30  # CSR / CAR / ASR / AAR — past 30 days including today

# GraphQL Search API query roots and response keys (hardcoded — not lab steps)
_SEARCH_TASK_QUERY = "taskDetails"
_SEARCH_AGENT_QUERY = "agentSession"
_SEARCH_TASKS_ARRAY_KEY = "tasks"
_SEARCH_AGENT_SESSIONS_ARRAY_KEY = "agentSessions"

# Detail-view field keys (provided — not fill-in steps)
CSR_ANI_KEY = "origin"
CSR_DNIS_KEY = "destination"
CSR_DURATION_KEY = "totalDuration"
CSR_START_TIME_KEY = "createdTime"
CSR_END_TIME_KEY = "endedTime"
ASR_SESSION_ID_KEY = "agentSessionId"
ASR_LOGIN_KEY = "userLoginId"
ASR_LOGIN_TIME_KEY = "startTime"
ASR_LOGOUT_TIME_KEY = "endTime"

STEPS = [
    {
        "id": "3.1",
        "label": "CSR Report Query",
        "variables": ["CSR_RECORD_TYPE", "CSR_TASK_ID_KEY", "CSR_CHANNEL_TYPE_KEY", "CSR_TERMINATION_TYPE_KEY", "CSR_CALL_DIRECTION_KEY"],
    },
    {
        "id": "3.2",
        "label": "CAR Report Query",
        "variables": ["CAR_RECORD_TYPE", "CAR_ACTIVITY_NAME_KEY", "CAR_QUEUE_NAME_KEY"],
    },
    {
        "id": "3.3",
        "label": "ASR Report Query",
        "variables": ["ASR_RECORD_TYPE", "ASR_AGENT_ID_KEY", "ASR_AGENT_NAME_KEY", "ASR_TEAM_NAME_KEY"],
    },
    {
        "id": "3.4",
        "label": "AAR Report Query",
        "variables": ["AAR_RECORD_TYPE", "AAR_ACTIVITY_TYPE_KEY", "AAR_DURATION_KEY"],
    },
    {
        "id": "3.5",
        "label": "Real-Time Agent States",
        "variables": ["RT_AGENT_STATE_KEY", "RT_AGENT_ID_KEY"],
    },
]





def _time_range_ms(window_ms: int):

    now_ms = int(time.time() * 1000)

    return now_ms - window_ms, now_ms





def _report_time_range():
    """All historical report queries — past 30 days through now."""
    now_ms = int(time.time() * 1000)
    return now_ms - (REPORT_LOOKBACK_DAYS * 24 * 60 * 60 * 1000), now_ms


def _historical_time_range():
    return _report_time_range()


def _granular_time_range():
    return _report_time_range()





def _run_graphql(query: str, start: int, end: int, extra_variables: dict | None = None) -> dict:
    variables = {"from": start, "to": end}
    if extra_variables:
        variables.update(extra_variables)
    return wxcc_graphql(query, variables)





def _task_root(result: dict) -> dict:

    from progress import is_filled



    query_type = _SEARCH_TASK_QUERY

    return result.get("data", {}).get(query_type, {})





def _agent_root(result: dict) -> dict:

    from progress import is_filled



    query_type = _SEARCH_AGENT_QUERY

    return result.get("data", {}).get(query_type, {})





def _tasks_from_result(result: dict) -> list:

    from progress import is_filled



    tasks_key = _SEARCH_TASKS_ARRAY_KEY

    return _task_root(result).get(tasks_key, [])





def _agent_sessions_from_result(result: dict) -> list:

    from progress import is_filled



    agents_key = _SEARCH_AGENT_SESSIONS_ARRAY_KEY

    return _agent_root(result).get(agents_key, [])





def fetch_csr_report():

    from progress import is_filled



    if not is_filled(CSR_RECORD_TYPE):

        return []



    query_type = _SEARCH_TASK_QUERY

    tasks_key = _SEARCH_TASKS_ARRAY_KEY

    fields = [_gql_field(k) for k in [CSR_TASK_ID_KEY, CSR_CHANNEL_TYPE_KEY, CSR_TERMINATION_TYPE_KEY, CSR_CALL_DIRECTION_KEY] if is_filled(k)]

    field_str = "\n        ".join(fields or ["id"])

    query = f"""

    query($from: Long!, $to: Long!) {{

      {query_type}(from: $from, to: $to) {{

        {tasks_key} {{

          {field_str}

        }}

      }}

    }}

    """

    start, end = _historical_time_range()

    result = _run_graphql(query, start, end)

    id_key = _gql_field(CSR_TASK_ID_KEY) if is_filled(CSR_TASK_ID_KEY) else "id"
    channel_key = _gql_field(CSR_CHANNEL_TYPE_KEY) if is_filled(CSR_CHANNEL_TYPE_KEY) else "channelType"
    term_key = _gql_field(CSR_TERMINATION_TYPE_KEY) if is_filled(CSR_TERMINATION_TYPE_KEY) else "terminationType"
    dir_key = _gql_field(CSR_CALL_DIRECTION_KEY) if is_filled(CSR_CALL_DIRECTION_KEY) else "direction"

    records = []
    for task in _tasks_from_result(result):
        records.append(
            {
                "id": task.get(id_key) or task.get("id"),
                "channelType": task.get(channel_key) or task.get("channelType"),
                "terminationType": task.get(term_key) or task.get("terminationType"),
                "direction": task.get(dir_key) or task.get("direction") or task.get("contactDirection"),
                "_raw": task,
            }
        )
    return records





def fetch_car_report():

    from progress import is_filled



    if not is_filled(CAR_RECORD_TYPE):

        return []



    query_type = _SEARCH_TASK_QUERY

    tasks_key = _SEARCH_TASKS_ARRAY_KEY

    activity_fields = [_gql_field(k) for k in [CAR_ACTIVITY_NAME_KEY, CAR_QUEUE_NAME_KEY] if is_filled(k)]

    activity_field_str = "\n            ".join(activity_fields or ["id"])

    query = f"""

    query($from: Long!, $to: Long!) {{

      {query_type}(from: $from, to: $to) {{

        {tasks_key} {{

          id

          activities {{

            nodes {{

              {activity_field_str}

            }}

          }}

        }}

      }}

    }}

    """

    start, end = _granular_time_range()

    result = _run_graphql(query, start, end)

    records = []

    for task in _tasks_from_result(result):

        for node in task.get("activities", {}).get("nodes", []):

            records.append(

                {

                    "activityName": node.get(_gql_field(CAR_ACTIVITY_NAME_KEY)) if is_filled(CAR_ACTIVITY_NAME_KEY) else None,

                    "queueName": node.get(_gql_field(CAR_QUEUE_NAME_KEY)) if is_filled(CAR_QUEUE_NAME_KEY) else None,

                    "taskId": task.get("id"),

                    "_raw": node,

                }

            )

    return records





def fetch_asr_report():

    from progress import is_filled



    if not is_filled(ASR_RECORD_TYPE):

        return []



    query_type = _SEARCH_AGENT_QUERY

    agents_key = _SEARCH_AGENT_SESSIONS_ARRAY_KEY

    fields = [_gql_field(k) for k in [ASR_AGENT_ID_KEY, ASR_AGENT_NAME_KEY, ASR_TEAM_NAME_KEY] if is_filled(k)]
    for extra in (ASR_LOGIN_TIME_KEY, ASR_LOGOUT_TIME_KEY):
        leaf = _gql_field(extra)
        if leaf not in fields:
            fields.append(leaf)

    field_str = "\n        ".join(fields or ["agentId"])

    query = f"""

    query($from: Long!, $to: Long!) {{

      {query_type}(from: $from, to: $to) {{

        {agents_key} {{

          {field_str}

        }}

      }}

    }}

    """

    start, end = _historical_time_range()

    result = _run_graphql(query, start, end)

    login_key = _gql_field(ASR_LOGIN_TIME_KEY)
    logout_key = _gql_field(ASR_LOGOUT_TIME_KEY)
    records = []
    for session in _agent_sessions_from_result(result):
        record = dict(session)
        record["startTime"] = session.get(login_key) or session.get("startTime")
        record["endTime"] = session.get(logout_key) or session.get("endTime")
        records.append(record)
    return records





def fetch_aar_report():

    from progress import is_filled



    if not is_filled(AAR_RECORD_TYPE):

        return []



    query_type = _SEARCH_AGENT_QUERY

    agents_key = _SEARCH_AGENT_SESSIONS_ARRAY_KEY

    activity_fields = [_gql_field(k) for k in [AAR_ACTIVITY_TYPE_KEY, AAR_DURATION_KEY] if is_filled(k)]

    activity_field_str = "\n              ".join(activity_fields or ["id"])

    query = f"""

    query($from: Long!, $to: Long!) {{

      {query_type}(from: $from, to: $to) {{

        {agents_key} {{

          agentId

          channelInfo {{

            channelType

            activities {{

              nodes {{

                {activity_field_str}

              }}

            }}

          }}

        }}

      }}

    }}

    """

    start, end = _granular_time_range()

    result = _run_graphql(query, start, end)

    records = []

    for session in _agent_sessions_from_result(result):

        for channel in session.get("channelInfo", []):

            for node in channel.get("activities", {}).get("nodes", []):

                records.append(

                    {

                        "activityType": node.get(_gql_field(AAR_ACTIVITY_TYPE_KEY)) if is_filled(AAR_ACTIVITY_TYPE_KEY) else None,

                        "duration": node.get(_gql_field(AAR_DURATION_KEY)) if is_filled(AAR_DURATION_KEY) else None,

                        "agentId": session.get("agentId"),

                        "channelType": channel.get("channelType"),

                        "_raw": node,

                    }

                )

    return records





def _format_timestamp_ms(value) -> str | None:
    if value in (None, "", 0, -1):
        return None
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OSError):
        return str(value)


def fetch_csr_details():
    """CSR records for the customer detail drill-down (Interaction ID, ANI, DNIS, duration)."""
    from progress import is_filled

    if not is_filled(CSR_RECORD_TYPE):
        return []

    query_type = _SEARCH_TASK_QUERY
    tasks_key = _SEARCH_TASKS_ARRAY_KEY
    id_key = _gql_field(CSR_TASK_ID_KEY) if is_filled(CSR_TASK_ID_KEY) else "id"
    query = f"""
    query($from: Long!, $to: Long!) {{
      {query_type}(from: $from, to: $to, pagination: {{ cursor: "0" }}) {{
        {tasks_key} {{
          {id_key}
          {CSR_ANI_KEY}
          {CSR_DNIS_KEY}
          {CSR_DURATION_KEY}
          {CSR_START_TIME_KEY}
          {CSR_END_TIME_KEY}
        }}
      }}
    }}
    """
    start, end = _report_time_range()
    result = _run_graphql(query, start, end)
    rows = []
    for task in _tasks_from_result(result):
        task_id = task.get(id_key) or task.get("id")
        rows.append(
            {
                "interaction_id": task_id,
                "start_time": _format_timestamp_ms(task.get(CSR_START_TIME_KEY)),
                "end_time": _format_timestamp_ms(task.get(CSR_END_TIME_KEY)),
                "ani": task.get(CSR_ANI_KEY),
                "dnis": task.get(CSR_DNIS_KEY),
                "duration": _format_duration_ms(task.get(CSR_DURATION_KEY)),
                "_sort_start": _activity_start_ms(task, CSR_START_TIME_KEY),
                "_raw": task,
            }
        )
    return _sort_by_start_ms(rows)


def _activity_start_ms(node: dict, *keys: str) -> int:
    for key in keys:
        value = node.get(key)
        if value in (None, "", 0, -1):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _sort_by_start_ms(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda row: row.get("_sort_start", 0))


def _entry_point_name(task: dict) -> str | None:
    entry_point = task.get("lastEntryPoint") or {}
    if isinstance(entry_point, dict):
        return entry_point.get("name")
    return None


def get_report_query(
    report_id: str,
    *,
    task_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Return the full GraphQL query and variables used for a report type."""
    from api.client import wxcc_regional_base_url
    from config import get_webex_org_id, get_wxcc_search_base_url
    from progress import is_filled

    labels = {
        "csr": "CSR — Customer Session Records",
        "car": "CAR — Customer Activity Records",
        "asr": "ASR — Agent Session Records",
        "aar": "AAR — Agent Activity Records",
        "rt": "Real-Time Agent States",
        "csr-details": "CSR Details — Customer Session Details",
        "car-events": "CAR Events — Customer Activity (single interaction)",
        "asr-details": "ASR Details — Agent Session Details",
        "aar-events": "AAR Events — Agent Activity (single session)",
    }
    if report_id not in labels:
        raise ValueError(f"Unknown report type: {report_id}")

    query_type_task = _SEARCH_TASK_QUERY
    tasks_key = _SEARCH_TASKS_ARRAY_KEY
    query_type_agent = _SEARCH_AGENT_QUERY
    agents_key = _SEARCH_AGENT_SESSIONS_ARRAY_KEY

    if report_id == "csr-details":
        id_key = _gql_field(CSR_TASK_ID_KEY) if is_filled(CSR_TASK_ID_KEY) else "id"
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!) {{
  {query_type_task}(from: $from, to: $to, pagination: {{ cursor: "0" }}) {{
    {tasks_key} {{
      {id_key}
      {CSR_ANI_KEY}
      {CSR_DNIS_KEY}
      {CSR_DURATION_KEY}
      {CSR_START_TIME_KEY}
      {CSR_END_TIME_KEY}
    }}
  }}
}}"""
        variables = {"from": start, "to": end}
    elif report_id == "car-events":
        queue_fields = [_gql_field(k) for k in [CAR_QUEUE_NAME_KEY] if is_filled(k)]
        queue_field_str = "\n          ".join(queue_fields or ["queueName"])
        task_id_value = task_id or "<interaction_id>"
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!, $taskId: String!) {{
  {query_type_task}(
    from: $from,
    to: $to,
    filter: {{ id: {{ equals: $taskId }} }},
    pagination: {{ cursor: "0" }}
  ) {{
    {tasks_key} {{
      id
      lastEntryPoint {{
        name
      }}
      activities {{
        nodes {{
          eventName
          {queue_field_str}
          duration
          createdTime
          endedTime
        }}
      }}
    }}
  }}
}}"""
        variables = {"from": start, "to": end, "taskId": task_id_value}
    elif report_id == "asr-details":
        name_key = _gql_field(ASR_AGENT_NAME_KEY) if is_filled(ASR_AGENT_NAME_KEY) else "agentName"
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!) {{
  {query_type_agent}(from: $from, to: $to, pagination: {{ cursor: "0" }}) {{
    {agents_key} {{
      {ASR_SESSION_ID_KEY}
      {ASR_LOGIN_KEY}
      {ASR_LOGIN_TIME_KEY}
      {ASR_LOGOUT_TIME_KEY}
      {name_key}
    }}
  }}
}}"""
        variables = {"from": start, "to": end}
    elif report_id == "aar-events":
        activity_fields = [_gql_field(k) for k in [AAR_ACTIVITY_TYPE_KEY, AAR_DURATION_KEY] if is_filled(k)]
        activity_field_str = "\n            ".join(activity_fields or ["state", "duration"])
        session_id_value = session_id or "<agent_session_id>"
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!, $sessionId: String!) {{
  {query_type_agent}(
    from: $from,
    to: $to,
    filter: {{ agentSessionId: {{ equals: $sessionId }} }},
    pagination: {{ cursor: "0" }}
  ) {{
    {agents_key} {{
      agentSessionId
      channelInfo {{
        channelType
        activities {{
          nodes {{
            {activity_field_str}
            startTime
            endTime
          }}
        }}
      }}
    }}
  }}
}}"""
        variables = {"from": start, "to": end, "sessionId": session_id_value}
    elif report_id == "csr":
        fields = [_gql_field(k) for k in [CSR_TASK_ID_KEY, CSR_CHANNEL_TYPE_KEY, CSR_TERMINATION_TYPE_KEY, CSR_CALL_DIRECTION_KEY] if is_filled(k)]
        field_str = "\n      ".join(fields or ["id"])
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!) {{
  {query_type_task}(from: $from, to: $to) {{
    {tasks_key} {{
      {field_str}
    }}
  }}
}}"""
        variables = {"from": start, "to": end}
    elif report_id == "car":
        activity_fields = [_gql_field(k) for k in [CAR_ACTIVITY_NAME_KEY, CAR_QUEUE_NAME_KEY] if is_filled(k)]
        activity_field_str = "\n          ".join(activity_fields or ["activityName", "queueName"])
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!) {{
  {query_type_task}(from: $from, to: $to) {{
    {tasks_key} {{
      id
      activities {{
        nodes {{
          {activity_field_str}
        }}
      }}
    }}
  }}
}}"""
        variables = {"from": start, "to": end}
    elif report_id == "asr":
        fields = [_gql_field(k) for k in [ASR_AGENT_ID_KEY, ASR_AGENT_NAME_KEY, ASR_TEAM_NAME_KEY] if is_filled(k)]
        for extra in (ASR_LOGIN_TIME_KEY, ASR_LOGOUT_TIME_KEY):
            leaf = _gql_field(extra)
            if leaf not in fields:
                fields.append(leaf)
        field_str = "\n      ".join(fields or ["agentId"])
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!) {{
  {query_type_agent}(from: $from, to: $to) {{
    {agents_key} {{
      {field_str}
    }}
  }}
}}"""
        variables = {"from": start, "to": end}
    elif report_id == "aar":
        activity_fields = [_gql_field(k) for k in [AAR_ACTIVITY_TYPE_KEY, AAR_DURATION_KEY] if is_filled(k)]
        activity_field_str = "\n            ".join(activity_fields or ["state", "duration"])
        start, end = _report_time_range()
        query = f"""query($from: Long!, $to: Long!) {{
  {query_type_agent}(from: $from, to: $to) {{
    {agents_key} {{
      agentId
      channelInfo {{
        channelType
        activities {{
          nodes {{
            {activity_field_str}
          }}
        }}
      }}
    }}
  }}
}}"""
        variables = {"from": start, "to": end}
    else:  # rt
        start, end = _time_range_ms(RT_TIME_WINDOW_MS)
        query = f"""query($from: Long!, $to: Long!) {{
  {query_type_agent}(from: $from, to: $to, filter: {{ isActive: {{ equals: true }} }}) {{
    {agents_key} {{
      agentId
      agentName
      isActive
      startTime
      channelInfo {{
        channelType
        activities {{
          nodes {{
            state
            duration
            startTime
            taskId
            idleCode {{
              name
            }}
          }}
        }}
      }}
    }}
  }}
}}"""
        variables = {"from": start, "to": end}

    payload = {
        "report_id": report_id,
        "label": labels[report_id],
        "query": query.strip(),
        "variables": variables,
        "endpoint": f"POST {get_wxcc_search_base_url()}?orgId={get_webex_org_id()}",
        "method": "POST",
    }
    if report_id == "rt":
        payload["rest"] = {
            "method": "GET",
            "path": "/v1/agents/activities",
            "endpoint": f"GET {wxcc_regional_base_url()}/v1/agents/activities",
            "params": {
                "from": "<now - 23h>",
                "to": "<now>",
                "channelTypes": "telephony",
                "pageSize": 1000,
                "orgId": get_webex_org_id(),
                "agentIds": "<logged-in agent IDs from GraphQL>",
            },
            "how": (
                "GraphQL Search lists logged-in agent sessions for the configured org. "
                "GET /v1/agents/activities then supplies the current telephony state, idle code, "
                "duration, and interaction ID used in the live table."
            ),
        }
    return payload


def fetch_car_for_task(task_id: str):
    """CAR activity nodes for a single customer interaction."""
    from progress import is_filled

    if not is_filled(CAR_RECORD_TYPE) or not task_id:
        return {"entry_point": None, "records": []}

    query_type = _SEARCH_TASK_QUERY
    tasks_key = _SEARCH_TASKS_ARRAY_KEY
    queue_fields = [_gql_field(k) for k in [CAR_QUEUE_NAME_KEY] if is_filled(k)]
    queue_field_str = "\n              ".join(queue_fields or ["queueName"])
    query = f"""
    query($from: Long!, $to: Long!, $taskId: String!) {{
      {query_type}(
        from: $from,
        to: $to,
        filter: {{ id: {{ equals: $taskId }} }},
        pagination: {{ cursor: "0" }}
      ) {{
        {tasks_key} {{
          id
          lastEntryPoint {{
            name
          }}
          activities {{
            nodes {{
              eventName
              {queue_field_str}
              duration
              createdTime
              endedTime
            }}
          }}
        }}
      }}
    }}
    """
    start, end = _report_time_range()
    result = _run_graphql(query, start, end, extra_variables={"taskId": task_id})
    entry_point = None
    records = []
    for task in _tasks_from_result(result):
        entry_point = _entry_point_name(task) or entry_point
        for node in task.get("activities", {}).get("nodes", []):
            queue_name = node.get(_gql_field(CAR_QUEUE_NAME_KEY)) if is_filled(CAR_QUEUE_NAME_KEY) else node.get("queueName")
            records.append(
                {
                    "event_name": node.get("eventName"),
                    "entry_point": entry_point,
                    "queue_name": queue_name,
                    "start_time": _format_timestamp_ms(node.get("createdTime")),
                    "end_time": _format_timestamp_ms(node.get("endedTime")),
                    "duration": _format_duration_ms(node.get("duration")),
                    "_sort_start": _activity_start_ms(node, "createdTime"),
                    "_raw": node,
                }
            )
    return {"entry_point": entry_point, "records": _sort_by_start_ms(records)}


def fetch_asr_details():
    """ASR records for the agent detail drill-down."""
    from progress import is_filled

    if not is_filled(ASR_RECORD_TYPE):
        return []

    query_type = _SEARCH_AGENT_QUERY
    agents_key = _SEARCH_AGENT_SESSIONS_ARRAY_KEY
    name_key = _gql_field(ASR_AGENT_NAME_KEY) if is_filled(ASR_AGENT_NAME_KEY) else "agentName"
    query = f"""
    query($from: Long!, $to: Long!) {{
      {query_type}(from: $from, to: $to, pagination: {{ cursor: "0" }}) {{
        {agents_key} {{
          {ASR_SESSION_ID_KEY}
          {ASR_LOGIN_KEY}
          {ASR_LOGIN_TIME_KEY}
          {ASR_LOGOUT_TIME_KEY}
          {name_key}
        }}
      }}
    }}
    """
    start, end = _report_time_range()
    result = _run_graphql(query, start, end)
    rows = []
    for session in _agent_sessions_from_result(result):
        rows.append(
            {
                "agent_session_id": session.get(ASR_SESSION_ID_KEY),
                "agent_name": session.get(name_key, ""),
                "agent_login": session.get(ASR_LOGIN_KEY),
                "login_time": _format_timestamp_ms(session.get(ASR_LOGIN_TIME_KEY)),
                "logout_time": _format_timestamp_ms(session.get(ASR_LOGOUT_TIME_KEY)),
                "_sort_start": _activity_start_ms(session, ASR_LOGIN_TIME_KEY),
                "_raw": session,
            }
        )
    return _sort_by_start_ms(rows)


def fetch_aar_for_session(agent_session_id: str):
    """AAR activity nodes for a single agent session."""
    from progress import is_filled

    if not is_filled(AAR_RECORD_TYPE) or not agent_session_id:
        return []

    query_type = _SEARCH_AGENT_QUERY
    agents_key = _SEARCH_AGENT_SESSIONS_ARRAY_KEY
    activity_fields = [_gql_field(k) for k in [AAR_ACTIVITY_TYPE_KEY, AAR_DURATION_KEY] if is_filled(k)]
    activity_field_str = "\n                ".join(activity_fields or ["state", "duration"])
    query = f"""
    query($from: Long!, $to: Long!, $sessionId: String!) {{
      {query_type}(
        from: $from,
        to: $to,
        filter: {{ agentSessionId: {{ equals: $sessionId }} }},
        pagination: {{ cursor: "0" }}
      ) {{
        {agents_key} {{
          agentSessionId
          channelInfo {{
            channelType
            activities {{
              nodes {{
                {activity_field_str}
                startTime
                endTime
              }}
            }}
          }}
        }}
      }}
    }}
    """
    start, end = _report_time_range()
    result = _run_graphql(query, start, end, extra_variables={"sessionId": agent_session_id})
    records = []
    for session in _agent_sessions_from_result(result):
        for channel in session.get("channelInfo", []):
            channel_type = channel.get("channelType")
            if str(channel_type or "").lower() != "telephony":
                continue
            for node in channel.get("activities", {}).get("nodes", []):
                state_key = _gql_field(AAR_ACTIVITY_TYPE_KEY) if is_filled(AAR_ACTIVITY_TYPE_KEY) else "state"
                duration_key = _gql_field(AAR_DURATION_KEY) if is_filled(AAR_DURATION_KEY) else "duration"
                records.append(
                    {
                        "state": node.get(state_key),
                        "start_time": _format_timestamp_ms(node.get("startTime")),
                        "end_time": _format_timestamp_ms(node.get("endTime")),
                        "duration": _format_duration_ms(node.get(duration_key)),
                        "_sort_start": _activity_start_ms(node, "startTime"),
                        "_raw": node,
                    }
                )
    return _sort_by_start_ms(records)


_CHANNEL_PRIORITY = ("telephony", "chat", "email", "social")
_CALL_STATES = frozenset({"connected", "hold", "wrapup", "ringing", "engaged"})


def _format_duration_ms(ms: int | None) -> str:
    if ms is None or ms < 0:
        return "—"
    total_sec = ms // 1000
    hours, rem = divmod(total_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _current_channel_node(channel: dict) -> dict | None:
    nodes = channel.get("activities", {}).get("nodes", [])
    for node in reversed(nodes):
        if node.get("duration") == -1:
            return node
    return nodes[-1] if nodes else None


def _preferred_channel(session: dict) -> dict | None:
    channels = session.get("channelInfo", [])
    by_type = {ch.get("channelType"): ch for ch in channels if ch.get("channelType")}
    for ch_type in _CHANNEL_PRIORITY:
        ch = by_type.get(ch_type)
        if ch:
            return ch
    return channels[0] if channels else None


def _details_from_activity(activity: dict) -> dict:
    now_ms = int(time.time() * 1000)
    state = activity.get("currentState") or "unknown"
    state_key = state.lower()
    start = activity.get("startTime") or 0
    end = activity.get("endTime")
    if activity.get("active") and (end is None or end == -1):
        duration_ms = max(0, now_ms - start) if start else None
    elif end and end > 0 and start:
        duration_ms = end - start
    else:
        duration_ms = None

    idle_code_name = activity.get("idleCodeName") or ""
    if state_key != "idle":
        idle_code_name = ""

    task_id = activity.get("taskId") or ""
    if state_key not in _CALL_STATES and not (activity.get("active") and task_id):
        task_id = ""

    return {
        "state": state,
        "idle_code_name": idle_code_name or "—",
        "state_duration": _format_duration_ms(duration_ms),
        "interaction_id": task_id or "—",
    }


def _details_from_session(session: dict) -> dict:
    channel = _preferred_channel(session)
    if not channel:
        return {
            "state": "unknown",
            "idle_code_name": "—",
            "state_duration": "—",
            "interaction_id": "—",
        }

    node = _current_channel_node(channel)
    if not node:
        return {
            "state": "unknown",
            "idle_code_name": "—",
            "state_duration": "—",
            "interaction_id": "—",
        }

    state = node.get("state") or "unknown"
    state_key = state.lower()
    start = node.get("startTime") or 0
    duration = node.get("duration")
    if duration == -1 and start:
        duration_ms = max(0, int(time.time() * 1000) - start)
    elif isinstance(duration, int) and duration > 0:
        duration_ms = duration
    else:
        duration_ms = None

    idle_code_name = ""
    if state_key == "idle":
        idle_code_name = (node.get("idleCode") or {}).get("name") or node.get("idleCodeName") or ""

    task_id = node.get("taskId") or ""
    if state_key not in _CALL_STATES:
        task_id = ""

    return {
        "state": state,
        "idle_code_name": idle_code_name or "—",
        "state_duration": _format_duration_ms(duration_ms),
        "interaction_id": task_id or "—",
    }


def _fetch_latest_activities(agent_ids: list[str]) -> dict[str, dict]:
    """Latest active telephony activity per agent via Get Agent Activities REST API."""

    from config import get_webex_org_id
    from api.client import wxcc_agents_get

    if not agent_ids:
        return {}

    end = int(time.time() * 1000)
    start = end - ACTIVITIES_LOOKBACK_MS
    params = {
        "from": start,
        "to": end,
        "channelTypes": "telephony",
        "pageSize": 1000,
        "orgId": get_webex_org_id(),
    }
    if len(agent_ids) <= 100:
        params["agentIds"] = ",".join(agent_ids)

    try:
        result = wxcc_agents_get("/v1/agents/activities", params)
    except Exception:
        return {}

    latest_active: dict[str, dict] = {}
    for activity in result.get("data", []):
        if not activity.get("active"):
            continue
        if activity.get("channelType") != "telephony":
            continue
        agent_id = activity.get("agentId")
        if not agent_id:
            continue
        existing = latest_active.get(agent_id)
        if not existing or activity.get("startTime", 0) >= existing.get("startTime", 0):
            latest_active[agent_id] = activity

    return latest_active





def fetch_rt_agents():

    """Real-time agent states for the Module 3 dashboard."""

    from progress import is_filled



    if not is_filled(RT_AGENT_STATE_KEY):

        return []



    query_type = _SEARCH_AGENT_QUERY

    agents_key = _SEARCH_AGENT_SESSIONS_ARRAY_KEY

    query = f"""

    query($from: Long!, $to: Long!) {{

      {query_type}(from: $from, to: $to, filter: {{ isActive: {{ equals: true }} }}) {{

        {agents_key} {{

          agentId

          agentName

          isActive

          startTime

          channelInfo {{

            channelType

            activities {{

              nodes {{

                state

                duration

                startTime

                taskId

                idleCode {{

                  name

                }}

              }}

            }}

          }}

        }}

      }}

    }}

    """

    start, end = _time_range_ms(RT_TIME_WINDOW_MS)

    result = _run_graphql(query, start, end)

    records = _agent_sessions_from_result(result)



    # One row per agent — keep the newest active session if duplicates exist

    latest_by_agent = {}

    for record in records:

        agent_id = record.get(_gql_field(RT_AGENT_ID_KEY) if is_filled(RT_AGENT_ID_KEY) else "agentId")

        if not agent_id:

            continue

        existing = latest_by_agent.get(agent_id)

        if not existing or record.get("startTime", 0) >= existing.get("startTime", 0):

            latest_by_agent[agent_id] = record



    latest_activities = _fetch_latest_activities(list(latest_by_agent.keys()))



    agents = []
    for session in latest_by_agent.values():
        agent_id = session.get(_gql_field(RT_AGENT_ID_KEY) if is_filled(RT_AGENT_ID_KEY) else "agentId")
        activity = latest_activities.get(agent_id)
        details = _details_from_activity(activity) if activity else _details_from_session(session)
        agents.append(
            {
                "agent_id": agent_id,
                "name": session.get("agentName", ""),
                "state": details["state"],
                "idle_code_name": details["idle_code_name"],
                "state_duration": details["state_duration"],
                "interaction_id": details["interaction_id"],
                "_raw": session,
            }
        )

    return agents


