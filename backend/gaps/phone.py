"""Phone a school with every open question parents have for it. One call answers them all.

Amazon Connect places the call; backend/voice/lex_turn.py runs the conversation and writes
the transcript to the state table under pk=CALLS. This module starts the call, reads the
transcript back, and applies answers only after code checks them.

Calls go only to VOICE_VERIFIED_TO, so a real school cannot be reached by mistake.
Without VOICE_ENABLED=1 the call is not placed and the question goes by email instead.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone

from catalog import needs
from runtime_config import AWS_REGION

from gaps.inbox import reply_to_question

TERMINAL = {"completed", "ended", "no_answer", "declined", "failed", "off"}
# Needs whose answer is a clock time. Only these change a card; other answers are kept as replies.
TIME_NEEDS = {"after_care", "extended_day", "before_care"}


def enabled() -> bool:
    keys = ("VOICE_INSTANCE_ID", "VOICE_FLOW_ID", "VOICE_SOURCE", "VOICE_VERIFIED_TO")
    return os.environ.get("VOICE_ENABLED", "").lower() in {"1", "true", "yes"} and all(os.environ.get(k) for k in keys)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def opening(school_name: str, count: int) -> str:
    many = "a few quick questions" if count > 1 else "one quick question"
    return (
        "Hi, this is an automated AI assistant calling on behalf of families who use GreatSchools. "
        f"I have {many} about {school_name}. Is it okay if I transcribe this call?"
    )


def start_call(state: dict, school: dict) -> dict:
    """Call the school about every open inbox question for it."""
    items = [i for i in state.get("inbox") or [] if i["school_id"] == school["id"] and i["status"] == "open"]
    questions = [{"id": i["need"], "question": i["question"]} for i in items]
    call = {
        "id": f"call-{uuid.uuid4().hex[:10]}",
        "school_id": school["id"],
        "school_name": school["name"],
        "question_ids": [i["id"] for i in items],
        "questions": questions,
        "parent_count": len({sid for i in items for sid in i["session_ids"]}),
        "opening": opening(school["name"], len(questions)),
        "status": "dialing",
        "created": _now(),
        "transcript": [],
        "answers": [],
        "applied": False,
    }
    if not questions:
        call["status"] = "failed"
        call["error"] = "no open questions for this school"
    elif not enabled():
        call["status"] = "off"
    else:
        try:
            import boto3

            client = boto3.client("connect", region_name=AWS_REGION)
            response = client.start_outbound_voice_contact(
                InstanceId=os.environ["VOICE_INSTANCE_ID"],
                ContactFlowId=os.environ["VOICE_FLOW_ID"],
                SourcePhoneNumber=os.environ["VOICE_SOURCE"],
                DestinationPhoneNumber=os.environ["VOICE_VERIFIED_TO"],
                Attributes={
                    "call_id": call["id"],
                    "school_name": school["name"],
                    "questions": json.dumps(questions),
                    "opening": call["opening"],
                },
            )
            call["contact_id"] = response["ContactId"]
        except Exception as exc:
            call["status"] = "failed"
            call["error"] = str(exc)[:300]
    state.setdefault("calls", {})[call["id"]] = call
    return call


def refresh_call(state: dict, call_id: str) -> dict | None:
    """Read the transcript the Lambda wrote, notice a hang-up, and apply answers once the call ends."""
    call = (state.get("calls") or {}).get(call_id)
    if not call or call["status"] in TERMINAL:
        return call
    record = _read_record(call_id)
    disconnected = _disconnected(call.get("contact_id"))
    if record:
        call["transcript"] = record.get("transcript") or []
        call["status"] = record.get("status") or "in_call"
        if record.get("consent") is False:
            call["status"] = "declined"
        call["raw_answers"] = record.get("answers") or {}
    if disconnected and call["status"] not in TERMINAL:
        call["status"] = "ended" if call["transcript"] else "no_answer"
    if call["status"] == "declined":
        # They said no to a transcript: keep that they declined, not what was said.
        call["transcript"] = []
        call.pop("raw_answers", None)
    if call["status"] in TERMINAL and not call["applied"]:
        _apply(state, call)
    return call


def _apply(state: dict, call: dict) -> None:
    raw = call.pop("raw_answers", None) or {}
    by_need = {i["need"]: i for i in state.get("inbox") or [] if i["id"] in call["question_ids"]}
    for need_id, item in by_need.items():
        answer = raw.get(need_id)
        if not isinstance(answer, dict):
            continue
        quote = str(answer.get("quote") or "").strip()
        if not quote or not _heard(quote, call["transcript"]):
            continue  # the model can't cite words nobody said
        value = check_value(need_id, answer.get("value"))
        reply_to_question(state, item["id"], f'By phone: "{quote}"', value)
        call["answers"].append(
            {"need": need_id, "label": needs().get(need_id, {}).get("label", need_id), "quote": quote, "value": value}
        )
    call["applied"] = True


def check_value(need_id: str, value) -> str | None:
    """The model's reading is untrusted. Keep a value only when code can parse it."""
    if need_id in TIME_NEEDS:
        return parse_time(str(value or ""), evening=need_id != "before_care")
    return None


def parse_time(text: str, evening: bool = True) -> str | None:
    """"6 PM", "6:30pm", "18:00". A bare "until 6" at the end of a school day means the evening."""
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])?\.?\s*m?\b", text.lower())
    if not match:
        return None
    hour, minute, half = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if half == "p" and hour < 12:
        hour += 12
    if half == "a" and hour == 12:
        hour = 0
    if not half and evening and 1 <= hour <= 9 and "morning" not in text.lower():
        hour += 12
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _heard(quote: str, transcript: list[dict]) -> bool:
    said = " ".join(line["text"] for line in transcript if line.get("who") == "school").lower()
    words = re.findall(r"[a-z0-9]+", quote.lower())
    return bool(words) and sum(word in said for word in words) >= max(1, int(len(words) * 0.6))


def _read_record(call_id: str) -> dict | None:
    # The Lambda writes transcripts to the app's table. VOICE_TABLE points a local API at it
    # without moving the rest of the local state into DynamoDB.
    table = os.environ.get("VOICE_TABLE") or os.environ.get("GS_DYNAMODB_TABLE")
    if not table:
        return None
    try:
        import boto3

        item = boto3.resource("dynamodb", region_name=AWS_REGION).Table(table).get_item(
            Key={"pk": "CALLS", "sk": call_id}
        ).get("Item")
        return json.loads(item["data_json"]) if item else None
    except Exception:
        return None


def _disconnected(contact_id: str | None) -> bool:
    if not contact_id:
        return False
    try:
        import boto3

        contact = boto3.client("connect", region_name=AWS_REGION).describe_contact(
            InstanceId=os.environ["VOICE_INSTANCE_ID"], ContactId=contact_id
        )["Contact"]
        return bool(contact.get("DisconnectTimestamp"))
    except Exception:
        return False


def public(call: dict) -> dict:
    """What the browser sees: never the destination number."""
    keys = ("id", "school_id", "school_name", "questions", "parent_count", "status", "transcript", "answers", "error")
    return {key: call.get(key) for key in keys}
