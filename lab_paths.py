"""Normalize Developer Portal paths (paste-as-seen) for verify and API calls."""

from __future__ import annotations

import re
from urllib.parse import urlparse

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_VERSION_PREFIX_RE = re.compile(r"^v\d+$", re.I)


def _strip_url(path: str) -> str:
    text = (path or "").strip()
    if "://" in text:
        text = urlparse(text).path or text
    return text


_ORG_PREFIX_RE = re.compile(
    r"^/organization/(?:"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|\{org_id\}|\{orgId\}|\{orgid\})"
    r"(?=/|$)",
    re.I,
)
_ORG_PLACEHOLDER_RE = re.compile(r"^/\{orgId\}|^/\{orgid\}", re.I)


def normalize_portal_org_prefix(path: str) -> str:
    """Portal pastes like /organization/<uuid|orgId>/… → /{org_id}/… templates."""
    p = _strip_url(path)
    p = _ORG_PREFIX_RE.sub("/{org_id}", p)
    p = _ORG_PLACEHOLDER_RE.sub("/{org_id}", p)
    return p


def strip_version_prefix(path: str) -> str:
    """Drop leading /v1, /v2, … when the answer key omits the API version segment."""
    p = _strip_url(path)
    parts = [seg for seg in p.split("/") if seg]
    while parts and _VERSION_PREFIX_RE.match(parts[0]):
        parts = parts[1:]
    return "/" + "/".join(parts) if parts else "/"


def canonical_path(path: str, template: str = "") -> str:
    """Canonical form for comparing portal pastes to answer-key templates."""
    p = strip_version_prefix(normalize_portal_org_prefix(path))
    parts = [seg for seg in p.split("/") if seg]
    if not template:
        return "/" + "/".join(parts)

    template_parts = [seg for seg in strip_version_prefix(template).split("/") if seg]
    if len(parts) != len(template_parts):
        return p

    canonical: list[str] = []
    for submitted_seg, template_seg in zip(parts, template_parts):
        if template_seg.startswith("{") and template_seg.endswith("}"):
            canonical.append(template_seg)
        else:
            canonical.append(submitted_seg)
    return "/" + "/".join(canonical)


def paths_equivalent(submitted: str, expected: str) -> bool:
    if not expected:
        return bool(submitted.strip())
    return canonical_path(submitted, expected).lower() == canonical_path(expected, expected).lower()


def normalize_endpoint_for_storage(submitted: str, expected: str) -> str:
    """After validation, store the concise template form used by lab modules."""
    if paths_equivalent(submitted, expected):
        return expected
    return strip_version_prefix(submitted.strip())


def format_endpoint_template(path: str, **path_vars: str) -> str:
    """Resolve {location_id} / {locationId} placeholders for Webex Calling paths."""
    normalized = strip_version_prefix(path.strip())
    normalized = re.sub(r"\{locationId\}", "{location_id}", normalized, flags=re.I)
    return normalized.format(**path_vars)


def resolve_org_path_segment(path: str, org_id: str, **path_vars: str) -> str:
    """
    Turn a lab endpoint answer (portal paste or template) into the path suffix
    appended to WXCC_ORG_BASE_URL (…/organization).
    """
    raw = _strip_url(path)
    portal_match = re.match(
        r"^/organization/(?:"
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        r"|\{org_id\}|\{orgId\}|\{orgid\})(/.*)?$",
        raw,
        flags=re.I,
    )
    if portal_match:
        suffix = portal_match.group(1) or ""
        if "{" in suffix:
            suffix = suffix.format(org_id=org_id, orgId=org_id, orgid=org_id, **path_vars)
        return f"/{org_id}{suffix}"

    resolved = raw
    if "{org_id}" in resolved or "{orgId}" in resolved or "{orgid}" in resolved or "{" in resolved:
        resolved = resolved.format(org_id=org_id, orgId=org_id, orgid=org_id, **path_vars)
    elif resolved.startswith(f"/{org_id}"):
        pass
    elif re.match(r"^/[0-9a-f-]{36}/", resolved, re.I):
        pass
    elif resolved.startswith("/") and not resolved.startswith(f"/{org_id}"):
        resolved = f"/{org_id}{resolved}"
    return resolved


def resolve_regional_path_segment(path: str, org_id: str, **path_vars: str) -> str:
    """Resolve flow-store and other regional paths (portal paste or template)."""
    raw = _strip_url(path)
    if "{org_id}" in raw or "{" in raw:
        return raw.format(org_id=org_id, **path_vars)
    return re.sub(
        r"/flow-store/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        f"/flow-store/{org_id}",
        raw,
        count=1,
        flags=re.I,
    )
