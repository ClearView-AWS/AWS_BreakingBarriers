"""Personal-information check that runs before any post is published.

Two layers:
1. Local rules (always on): emails, phone numbers, street addresses, and a
   child's or staff member's name in the common ways parents write them.
2. Bedrock Guardrails ApplyGuardrail (when BEDROCK_GUARDRAIL_ID is set and
   BEDROCK_ENABLED=1). Create the guardrail with scripts/create_guardrail.sh.

A post is blocked if either layer finds something. The parent is asked to
rephrase. Nothing is ever published on the parent's behalf.
"""

from __future__ import annotations

import os
import re

from runtime_config import AWS_REGION, BEDROCK_ENABLED

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
_ADDRESS = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}"
    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Ct|Court|Way|Pl|Place|Pkwy|Parkway|Cir|Circle|Ter|Terrace)\b\.?"
)
_KIN = r"(?:son|daughter|kid|child|boy|girl|stepson|stepdaughter|twins?|grandson|granddaughter|nephew|niece|little one)"
_NAME = r"([A-Z][a-z]{1,20})"
_NAME_PATTERNS = [
    # "my son Ethan", "my daughter, Maya"
    re.compile(rf"\b[Mm]y\s+(?:\w+\s+)?{_KIN},?\s+{_NAME}\b"),
    # "named Maya", "called Leo"
    re.compile(rf"\b(?:named|called)\s+{_NAME}\b"),
    # "Mr. Lopez", "Coach Daniels", "Principal Grant"
    re.compile(rf"\b(?:Mr|Mrs|Ms|Miss|Dr|Coach|Principal|Teacher|Nurse)\.?\s+{_NAME}\b"),
    # "Ethan is in 6th grade", "Maya is in kindergarten"
    re.compile(rf"\b{_NAME}\s+(?:is|was|will be)\s+(?:in|starting)\s+(?:\d+(?:st|nd|rd|th)|first|second|third|fourth|fifth|sixth|seventh|eighth|kindergarten|pre-?k)\b"),
]
_NOT_NAMES = {
    "The", "This", "That", "Our", "My", "He", "She", "They", "It", "We", "Who", "What",
    "Which", "When", "Where", "Is", "Are", "And", "But", "So", "Any", "Some", "Does",
}


def _local_findings(text: str) -> list[dict]:
    findings: list[dict] = []
    for match in _EMAIL.finditer(text):
        findings.append({"type": "email", "text": match.group(0)})
    for match in _PHONE.finditer(text):
        findings.append({"type": "phone", "text": match.group(0).strip()})
    for match in _ADDRESS.finditer(text):
        findings.append({"type": "address", "text": match.group(0).strip()})
    for pattern in _NAME_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1)
            if name in _NOT_NAMES:
                continue
            findings.append({"type": "name", "text": name})
    seen = set()
    unique = []
    for item in findings:
        key = (item["type"], item["text"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _guardrail_findings(text: str) -> list[dict] | None:
    """Return Guardrails findings, or None when Guardrails is not configured or fails."""
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "").strip()
    if not (BEDROCK_ENABLED and guardrail_id):
        return None
    try:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        response = client.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
            source="INPUT",
            content=[{"text": {"text": text}}],
        )
    except Exception:
        return None
    if response.get("action") != "GUARDRAIL_INTERVENED":
        return []
    found: list[dict] = []
    for assessment in response.get("assessments") or []:
        policy = assessment.get("sensitiveInformationPolicy") or {}
        for entity in policy.get("piiEntities") or []:
            found.append({"type": str(entity.get("type", "pii")).lower(), "text": entity.get("match", "")})
        for regex in policy.get("regexes") or []:
            found.append({"type": regex.get("name", "pattern"), "text": regex.get("match", "")})
    return found or [{"type": "guardrail", "text": ""}]


_MESSAGES = {
    "name": "a name",
    "email": "an email address",
    "phone": "a phone number",
    "address": "a street address",
}


def check_post(text: str) -> dict:
    """{'ok': bool, 'findings': [...], 'message': str, 'checked_by': [...]}"""
    findings = _local_findings(text or "")
    checked_by = ["rules"]
    remote = _guardrail_findings(text or "")
    if remote is not None:
        checked_by.append("bedrock_guardrails")
        findings += [item for item in remote if item not in findings]
    if not findings:
        return {"ok": True, "findings": [], "message": "", "checked_by": checked_by}
    kinds = []
    for item in findings:
        label = _MESSAGES.get(item["type"], "personal information")
        if label not in kinds:
            kinds.append(label)
    message = (
        f"This post includes {' and '.join(kinds)}. "
        "Please rephrase without it so the post can't identify your family or school staff."
    )
    return {"ok": False, "findings": findings, "message": message, "checked_by": checked_by}
