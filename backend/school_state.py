"""Which state a school is in, for rules that differ by state."""

from __future__ import annotations


def school_state(school: dict) -> str:
    """Best-effort state code. WA OSPI rows are tagged even when OpenSearch omits `state`."""
    raw = str(school.get("state") or "").strip().upper()
    if raw:
        return raw
    school_id = str(school.get("id") or "")
    if school_id.startswith("School wa-") or school_id.startswith("wa-"):
        return "WA"
    if isinstance((school.get("osp") or {}).get("wa_report_card"), dict):
        return "WA"
    if str(school.get("_source") or "").startswith("wa"):
        return "WA"
    return ""
