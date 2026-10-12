"""Webex Contact Center report field allow-lists (CSR/CAR/ASR/AAR data dictionaries)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DICTIONARY_PATH = ROOT / "data" / "report_data_dictionary.json"

DICTIONARY_URLS = {
    "CSR": "https://github.com/WebexSamples/webex-contact-center-api-samples/blob/main/reporting-samples/graphql-sample/DataDictionary/CSR.md",
    "CAR": "https://github.com/WebexSamples/webex-contact-center-api-samples/blob/main/reporting-samples/graphql-sample/DataDictionary/CAR.md",
    "ASR": "https://github.com/WebexSamples/webex-contact-center-api-samples/blob/main/reporting-samples/graphql-sample/DataDictionary/ASR.md",
    "AAR": "https://github.com/WebexSamples/webex-contact-center-api-samples/blob/main/reporting-samples/graphql-sample/DataDictionary/AAR.md",
}

# Lab variable → data dictionary report type
FIELD_VAR_REPORT: dict[str, str] = {
    "CSR_TASK_ID_KEY": "CSR",
    "CSR_CHANNEL_TYPE_KEY": "CSR",
    "CSR_TERMINATION_TYPE_KEY": "CSR",
    "CSR_CALL_DIRECTION_KEY": "CSR",
    "CAR_ACTIVITY_NAME_KEY": "CAR",
    "CAR_QUEUE_NAME_KEY": "CAR",
    "ASR_AGENT_ID_KEY": "ASR",
    "ASR_AGENT_NAME_KEY": "ASR",
    "ASR_TEAM_NAME_KEY": "ASR",
    "AAR_ACTIVITY_TYPE_KEY": "AAR",
    "AAR_DURATION_KEY": "AAR",
    "RT_AGENT_STATE_KEY": "ASR",
    "RT_AGENT_ID_KEY": "ASR",
}

RECORD_TYPE_VARS = {
    "CSR_RECORD_TYPE",
    "CAR_RECORD_TYPE",
    "ASR_RECORD_TYPE",
    "AAR_RECORD_TYPE",
}


@lru_cache(maxsize=1)
def load_report_fields() -> dict[str, list[str]]:
    if not DICTIONARY_PATH.is_file():
        return {}
    data = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    return {report: list(fields) for report, fields in data.items()}


def graphql_leaf(field_path: str) -> str:
    """Last segment of a dotted data-dictionary field path for GraphQL selection."""
    text = (field_path or "").strip()
    if not text:
        return text
    return text.split(".")[-1]


def field_in_dictionary(report_type: str, submitted: str) -> bool:
    """True if submitted is a full dictionary path or a unique partial suffix match."""
    text = (submitted or "").strip()
    if not text or not report_type:
        return False

    fields = load_report_fields().get(report_type.upper(), [])
    if text in fields:
        return True

    matches = [field for field in fields if field == text or field.endswith(f".{text}")]
    return len(matches) >= 1


def dictionary_hint(report_type: str) -> str:
    url = DICTIONARY_URLS.get(report_type.upper(), "")
    label = report_type.upper()
    if url:
        return f"Pick a field from the {label} Data Dictionary — full path or leaf name (see {url})."
    return f"Pick a field name from the {label} Data Dictionary (full path or leaf name)."
