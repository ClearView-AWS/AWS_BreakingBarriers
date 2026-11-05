"""Phone a school with every open question parents have for it. One call answers them all.

Amazon Connect places the call; backend/voice/lex_turn.py runs the conversation and writes
the transcript to the state table under pk=CALLS. This module starts the call, reads the
transcript back, and applies answers only after code checks them.

Hackathon demo: every outbound call goes to DEMO_VOICE_TO (+1 206-535-0596). School
profile phone numbers are never dialed. Without VOICE_ENABLED=1 the call is not placed
and the question goes by email instead. Guardrails in config/calls.yaml (per-school
spacing, office hours, question cap, daily cap, do-not-call) also block a dial and fall
back to email with a reason.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from catalog import call_limits, needs
from runtime_config import AWS_REGION, TODAY

from gaps.inbox import reply_to_question

TERMINAL = {"completed", "ended", "no_answer", "declined", "failed", "off", "blocked"}
# Needs whose answer is a clock time. Only these change a card; other answers are kept as replies.
TIME_NEEDS = {"after_care", "extended_day", "before_care"}
_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

# Only number the demo may dial. Never read a school office line from the corpus.
DEMO_VOICE_TO = "+12065350596"


def destination_number() -> str:
    """E.164 handset for every demo call. Ignores school phones and env overrides."""
    return DEMO_VOICE_TO


def enabled() -> bool:
    # Destination is fixed in code; Connect still needs instance, flow, and caller ID.
    keys = ("VOICE_INSTANCE_ID", "VOICE_FLOW_ID", "VOICE_SOURCE")
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
    """Dial the demo handset about open inbox questions for this school.

    Destination is always DEMO_VOICE_TO. Dial blockers are off while
    calls.yaml has enforce_limits: false (hackathon stage default).
    """
    cfg = call_limits()
    items = [i for i in state.get("inbox") or [] if i["school_id"] == school["id"] and i["status"] == "open"]
    cap = int(cfg.get("max_questions_per_call") or 5)
    items = items[:cap]
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
    else:
        blocked = why_blocked(state, school, cfg)
        if blocked:
            call["status"] = "blocked"
            call["fallback_reason"] = blocked
            call["error"] = blocked
        elif not enabled():
            call["status"] = "off"
            call["fallback_reason"] = "Voice calling is off; questions go by email."
        else:
            try:
                import boto3

                client = boto3.client("connect", region_name=AWS_REGION)
                dest = destination_number()
                call["destination"] = dest
                response = client.start_outbound_voice_contact(
                    InstanceId=os.environ["VOICE_INSTANCE_ID"],
                    ContactFlowId=os.environ["VOICE_FLOW_ID"],
                    SourcePhoneNumber=os.environ["VOICE_SOURCE"],
                    DestinationPhoneNumber=dest,
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
                call["fallback_reason"] = "The call could not be placed; questions go by email."
    state.setdefault("calls", {})[call["id"]] = call
    return call


def why_blocked(state: dict, school: dict, cfg: dict | None = None) -> str | None:
    """Reason a dial must not happen, or None when a call may proceed.

    With enforce_limits: false (demo default) this always returns None so an
    on-stage call to DEMO_VOICE_TO is never refused for hours/caps/spacing.
    """
    cfg = cfg or call_limits()
    if not cfg.get("enforce_limits"):
        return None
    school_id = school["id"]
    if school_id in set(cfg.get("do_not_call") or []) or school_id in set(state.get("do_not_call") or []):
        return "This school asked not to be called; questions go by email."
    spacing = int(cfg.get("min_days_between_calls") or 0)
    last = _last_placed(state, school_id)
    if spacing > 0 and last is not None and (TODAY - last).days < spacing:
        return f"Already called this school within the last {spacing} days; questions go by email."
    cap = int(cfg.get("global_daily_cap") or 0)
    if cap > 0 and _placed_today(state) >= cap:
        return "Daily call limit reached; questions go by email."
    hours = cfg.get("business_hours") or {}
    if hours and not _in_business_hours(school, hours, cfg):
        start, end = hours.get("start", "00:00"), hours.get("end", "23:59")
        return f"Outside school office hours ({start}–{end} local); questions go by email."
    return None


def set_do_not_call(state: dict, school_id: str, opted_out: bool = True) -> list[str]:
    """School opt-out: do-not-call means email only. Returns the current list."""
    opted = list(state.get("do_not_call") or [])
    if opted_out and school_id not in opted:
        opted.append(school_id)
    if not opted_out:
        opted = [row for row in opted if row != school_id]
    state["do_not_call"] = opted
    return opted


def _last_placed(state: dict, school_id: str) -> date | None:
    best = None
    for call in (state.get("calls") or {}).values():
        if call.get("school_id") != school_id or not _was_placed(call):
            continue
        when = _call_day(call)
        if when and (best is None or when > best):
            best = when
    return best


def _placed_today(state: dict) -> int:
    return sum(1 for call in (state.get("calls") or {}).values() if _was_placed(call) and _call_day(call) == TODAY)


def _was_placed(call: dict) -> bool:
    # Dialed or finished a real attempt. blocked/off never left the building.
    return call.get("status") not in {"blocked", "off", "failed"} or bool(call.get("contact_id"))


def _call_day(call: dict) -> date | None:
    raw = call.get("created") or ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except ValueError:
        return None


def _in_business_hours(school: dict, hours: dict, cfg: dict, now: datetime | None = None) -> bool:
    tz_name = (cfg.get("time_zones") or {}).get(school.get("state")) or cfg.get("default_time_zone") or "America/New_York"
    try:
        tz = ZoneInfo(str(tz_name))
    except Exception:
        tz = ZoneInfo("America/New_York")
    local = now.astimezone(tz) if now else datetime.now(tz)
    days = {_WEEKDAYS.get(str(d).lower()[:3], -1) for d in (hours.get("days") or [])}
    if days and local.weekday() not in days:
        return False
    start = _parse_clock(hours.get("start") or "09:00")
    end = _parse_clock(hours.get("end") or "15:30")
    if start is None or end is None:
        return True
    return start <= local.time() <= end


def _parse_clock(text: str) -> time | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text).strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


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
        reply_to_question(state, item["id"], f'By phone: "{quote}"', value, channel="call")
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
    keys = (
        "id",
        "school_id",
        "school_name",
        "questions",
        "parent_count",
        "status",
        "transcript",
        "answers",
        "error",
        "fallback_reason",
    )
    return {key: call.get(key) for key in keys}
