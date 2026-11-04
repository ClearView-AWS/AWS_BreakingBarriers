"""Threads, replies, votes, demand counts, school answers, and the school digest.

State lives under state["community"] in the same JSON file that stands in for
DynamoDB. The first time it is missing, it is filled from the seed file.

    community = {
      "posts": [post, ...],              # opening posts and replies
      "votes": {post_id: [persona, ...]},
      "asks":  [{school_id, need, month, asker, origin}, ...],
      "school_answers": {school_id: {need: {post_id, value, offers, as_of}}},
    }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from community.safety import check_post
from community.tags import label_for, stance, suggest_tags
from gaps.inbox import _apply_overlay, _path_for
from runtime_config import SYNTHETIC_DIR, TODAY

SEED_PATH = SYNTHETIC_DIR / "community_seed.json"

PERSONAS = [
    {"id": "parent_a", "name": "Parent A", "role": "parent"},
    {"id": "parent_b", "name": "Parent B", "role": "parent"},
    {"id": "school_staff", "name": "School staff", "role": "school"},
]
_PERSONA_BY_ID = {row["id"]: row for row in PERSONAS}
KINDS = {"question", "experience"}
TIME_NEEDS = {"after_care", "extended_day", "before_care"}


# ---------- state ----------

def ensure(state: dict) -> dict:
    community = state.get("community")
    if isinstance(community, dict) and "posts" in community:
        community.setdefault("votes", {})
        community.setdefault("asks", [])
        community.setdefault("school_answers", {})
        return community
    seed = {"posts": [], "votes": {}, "asks": []}
    if SEED_PATH.exists():
        seed = json.loads(SEED_PATH.read_text())
    community = {
        "posts": list(seed.get("posts") or []),
        "votes": dict(seed.get("votes") or {}),
        "asks": list(seed.get("asks") or []),
        "school_answers": {},
    }
    state["community"] = community
    return community


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return TODAY.isoformat()


def _month(day: str | None = None) -> str:
    return (day or _today())[:7]


def _next_id(community: dict) -> str:
    biggest = 0
    for post in community["posts"]:
        raw = str(post.get("post_id", "")).split("_")[-1]
        if raw.isdigit():
            biggest = max(biggest, int(raw))
    return f"p_{biggest + 1}"


def persona(persona_id: str | None) -> dict:
    return _PERSONA_BY_ID.get(persona_id or "", _PERSONA_BY_ID["parent_a"])


# ---------- demand counts ----------

def record_ask(state: dict, school_id: str, need: str, asker: str, origin: str) -> int:
    """Count once per parent, per school, per need, per calendar month. Returns the new count."""
    community = ensure(state)
    month = _month()
    for row in community["asks"]:
        if (row["school_id"], row["need"], row["month"], row["asker"]) == (school_id, need, month, asker):
            break
    else:
        community["asks"].append(
            {"school_id": school_id, "need": need, "month": month, "asker": asker, "origin": origin}
        )
    return demand_for(state, school_id, need)


def demand_for(state: dict, school_id: str, need: str, month: str | None = None) -> int:
    month = month or _month()
    askers = {
        row["asker"]
        for row in ensure(state)["asks"]
        if row["school_id"] == school_id and row["need"] == need and row["month"] == month
    }
    return len(askers)


def demand(state: dict, school_id: str, month: str | None = None) -> list[dict]:
    month = month or _month()
    counts: dict[str, set[str]] = {}
    for row in ensure(state)["asks"]:
        if row["school_id"] == school_id and row["month"] == month:
            counts.setdefault(row["need"], set()).add(row["asker"])
    rows = [{"need": need, "label": label_for(need), "count": len(askers)} for need, askers in counts.items()]
    rows.sort(key=lambda row: (-row["count"], row["label"]))
    return rows


# ---------- reading ----------

def _votes(community: dict, post_id: str) -> int:
    return len(community["votes"].get(post_id) or [])


def _public(community: dict, post: dict, viewer: str | None = None) -> dict:
    out = dict(post)
    out["votes"] = _votes(community, post["post_id"])
    out["voted"] = bool(viewer and viewer in (community["votes"].get(post["post_id"]) or []))
    out["need_labels"] = [label_for(need) for need in post.get("needs") or []]
    out["verified_school"] = (post.get("author") or {}).get("role") == "school"
    return out


def threads_for(state: dict, school_id: str, sort: str = "top", need: str | None = None, viewer: str | None = None) -> list[dict]:
    community = ensure(state)
    openers = [
        post for post in community["posts"]
        if post["school_id"] == school_id and post["post_id"] == post["thread_id"]
        and (need is None or need in (post.get("needs") or []))
    ]
    out = []
    for post in openers:
        replies = [p for p in community["posts"] if p["thread_id"] == post["thread_id"] and p["post_id"] != post["post_id"]]
        row = _public(community, post, viewer)
        row["reply_count"] = len(replies)
        row["school_answered"] = any(p.get("kind") == "school_answer" for p in replies)
        out.append(row)
    if sort == "new":
        out.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    else:
        out.sort(key=lambda row: (-row["votes"], row.get("created_at") or ""))
    return out


def thread(state: dict, thread_id: str, viewer: str | None = None) -> dict | None:
    community = ensure(state)
    posts = [p for p in community["posts"] if p["thread_id"] == thread_id]
    opener = next((p for p in posts if p["post_id"] == thread_id), None)
    if not opener:
        return None
    replies = [_public(community, p, viewer) for p in posts if p["post_id"] != thread_id]
    replies.sort(key=lambda row: (row.get("kind") != "school_answer", row.get("created_at") or ""))
    return {"thread": _public(community, opener, viewer), "replies": replies}


# ---------- writing ----------

def create_thread(
    state: dict,
    school: dict,
    persona_id: str,
    kind: str,
    text: str,
    need_ids: list[str],
    origin: str = "community",
    asker: str | None = None,
) -> dict:
    """Run the safety check, then publish. Returns {'ok': True, 'post': ...} or {'ok': False, 'safety': ...}."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "safety": {"ok": False, "findings": [], "message": "Write something first."}}
    if kind not in KINDS:
        kind = "question"
    safety = check_post(text)
    if not safety["ok"]:
        return {"ok": False, "safety": safety}
    community = ensure(state)
    who = persona(persona_id)
    post_id = _next_id(community)
    need_ids = [need for need in need_ids if need] or [row["need"] for row in suggest_tags(text)]
    post = {
        "post_id": post_id,
        "thread_id": post_id,
        "school_id": school["id"],
        "author": {"persona": who["id"], "role": who["role"]},
        "kind": kind,
        "needs": need_ids,
        "text": text,
        "stance": stance(text, kind),
        "origin": origin,
        "created_at": _today(),
        "_synthetic": False,
    }
    community["posts"].append(post)
    community["votes"][post_id] = []
    if kind == "question" and who["role"] == "parent":
        for need in need_ids:
            record_ask(state, school["id"], need, asker or who["id"], origin)
    return {"ok": True, "post": _public(community, post, who["id"]), "safety": safety}


def reply(state: dict, thread_id: str, persona_id: str, text: str, answer: dict | None = None) -> dict:
    """A reply from a parent, or a school answer when the persona is school staff."""
    community = ensure(state)
    opener = next((p for p in community["posts"] if p["post_id"] == thread_id), None)
    if not opener:
        return {"ok": False, "safety": {"ok": False, "findings": [], "message": "Thread not found."}}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "safety": {"ok": False, "findings": [], "message": "Write something first."}}
    safety = check_post(text)
    if not safety["ok"]:
        return {"ok": False, "safety": safety}
    who = persona(persona_id)
    kind = "school_answer" if who["role"] == "school" else "reply"
    post_id = _next_id(community)
    post = {
        "post_id": post_id,
        "thread_id": thread_id,
        "school_id": opener["school_id"],
        "author": {"persona": who["id"], "role": who["role"]},
        "kind": kind,
        "needs": list(opener.get("needs") or []),
        "text": text,
        "stance": "neutral" if kind == "school_answer" else stance(text, "reply"),
        "origin": "community",
        "created_at": _today(),
        "_synthetic": False,
    }
    if kind == "school_answer" and answer:
        post["answer"] = {
            "need": answer.get("need") or (post["needs"][0] if post["needs"] else None),
            "value": answer.get("value") or None,
            "offers": answer.get("offers"),
        }
    community["posts"].append(post)
    community["votes"][post_id] = []
    if kind == "school_answer":
        _apply_school_answer(state, post)
    return {"ok": True, "post": _public(community, post, who["id"]), "safety": safety}


def _apply_school_answer(state: dict, post: dict) -> None:
    """The school answers once, in its thread. Every open question on that need closes."""
    answer = post.get("answer") or {}
    need = answer.get("need")
    if not need:
        return
    school_id = post["school_id"]
    record = {
        "post_id": post["post_id"],
        "value": answer.get("value"),
        "offers": answer.get("offers"),
        "as_of": _today(),
    }
    ensure(state)["school_answers"].setdefault(school_id, {})[need] = record
    if answer.get("value") and _path_for(need):
        # Same path the inbox uses, so the evidence engine reads it as school_reported.
        _apply_overlay(state, school_id, need, str(answer["value"]))
    for item in state.get("inbox") or []:
        if item["school_id"] == school_id and item["need"] == need and item["status"] == "open":
            item["status"] = "answered"
            item.setdefault("replies", []).append(
                {"text": post["text"], "at": _now(), "value": answer.get("value"), "thread_post": post["post_id"]}
            )


def vote(state: dict, post_id: str, persona_id: str) -> dict:
    community = ensure(state)
    if not any(p["post_id"] == post_id for p in community["posts"]):
        return {"ok": False}
    voters = community["votes"].setdefault(post_id, [])
    who = persona(persona_id)["id"]
    if who in voters:
        voters.remove(who)
        voted = False
    else:
        voters.append(who)
        voted = True
    return {"ok": True, "votes": len(voters), "voted": voted}


# ---------- drafts and digest ----------

def draft_question(school: dict, need: str) -> dict:
    """The agent drafts a question for the school's thread. The parent edits and approves it."""
    from catalog import needs

    spec = needs().get(need) or {}
    base = spec.get("visit_question") or f"Can anyone tell me about {label_for(need).lower()} here?"
    text = f"Parents at {school['name']}: {base}"
    return {"text": text, "needs": [need], "need_labels": [label_for(need)]}


def digest(state: dict, school: dict) -> dict:
    """One summary email per school, grouped by need, with counts and a link to answer."""
    rows = demand(state, school["id"])
    open_questions = [
        t for t in threads_for(state, school["id"], sort="top")
        if t.get("kind") == "question" and not t.get("school_answered")
    ]
    lines = [f"Families asked {school['name']} these questions this month:", ""]
    for row in rows:
        lines.append(f"- {row['label']}: {row['count']} parent{'s' if row['count'] != 1 else ''}")
        for thread_row in open_questions:
            if row["need"] in (thread_row.get("needs") or []):
                lines.append(f"    \"{thread_row['text']}\" ({thread_row['votes']} upvotes)")
    lines += ["", "Answer once in your community page and every parent who asked will see it."]
    item = {
        "email_to": f"office@{school['id'].lower().replace(' ', '-')}.example.org",
        "school_name": school["name"],
        "question": "\n".join(lines),
    }
    from gaps.ses_mailer import send_school_question

    email = send_school_question(item)
    email["subject"] = f"{sum(r['count'] for r in rows)} parent questions for {school['name']} this month"
    return {"school_id": school["id"], "demand": rows, "email": email}


# ---------- evidence ----------

def support(state: dict, school_id: str, need: str) -> dict:
    """Weighted positive/negative counts from parent posts tagged with this need."""
    community = ensure(state)
    positive = negative = 0.0
    post_ids: list[str] = []
    threads: set[str] = set()
    authors: set[str] = set()
    newest = None
    for post in community["posts"]:
        if post["school_id"] != school_id or need not in (post.get("needs") or []):
            continue
        if (post.get("author") or {}).get("role") != "parent":
            continue
        threads.add(post["thread_id"])
        authors.add((post.get("author") or {}).get("persona") or post["post_id"])
        when = post.get("created_at")
        newest = max(newest or when, when) if when else newest
        weight = 0.5 if when and int(when[:4]) < TODAY.year - 5 else 1.0
        if post.get("stance") == "positive":
            positive += weight
            post_ids.append(post["post_id"])
        elif post.get("stance") == "negative":
            negative += weight
            post_ids.append(post["post_id"])
    return {
        "positive": positive,
        "negative": negative,
        "post_ids": post_ids,
        "threads": sorted(threads),
        "parents": len(authors),
        "newest": newest,
    }


def school_answer_for(state: dict, school_id: str, need: str) -> dict | None:
    return (ensure(state)["school_answers"].get(school_id) or {}).get(need)


def card_summary(state: dict, school_id: str, need_ids: list[str]) -> dict:
    """What a result card shows: discussion counts per need and this month's demand."""
    discussed = []
    for need in need_ids:
        found = support(state, school_id, need)
        if found["threads"]:
            discussed.append(
                {
                    "need": need,
                    "label": label_for(need),
                    "parents": found["parents"],
                    "threads": len(found["threads"]),
                    "thread_ids": found["threads"],
                }
            )
    total = len(threads_for(state, school_id))
    return {"threads": total, "discussed": discussed, "demand": demand(state, school_id)}


# ---------- community home and questions to the school ----------

def schools_index(state: dict, schools: list[dict], query: str | None = None, limit: int = 20) -> list[dict]:
    """Schools for the Community tab, busiest first.

    Without a query, only schools with threads or asks this month. With one, any school whose
    name matches, so a parent can open a school's page before anyone has posted there.
    """
    community = ensure(state)
    threads: dict[str, int] = {}
    newest: dict[str, str] = {}
    for post in community["posts"]:
        if post["post_id"] == post["thread_id"]:
            threads[post["school_id"]] = threads.get(post["school_id"], 0) + 1
        newest[post["school_id"]] = max(newest.get(post["school_id"], ""), post.get("created_at") or "")
    month = _month()
    asked = {row["school_id"] for row in community["asks"] if row["month"] == month}
    needle = (query or "").strip().casefold()
    rows = []
    for school in schools:
        school_id = school["id"]
        if needle:
            if needle not in school["name"].casefold():
                continue
        elif school_id not in threads and school_id not in asked:
            continue
        wanted = demand(state, school_id)
        rows.append(
            {
                "id": school_id,
                "name": school["name"],
                "city": school.get("city"),
                "threads": threads.get(school_id, 0),
                "asked_this_month": sum(row["count"] for row in wanted),
                "top_asks": wanted[:3],
                "newest": newest.get(school_id) or None,
            }
        )
    rows.sort(key=lambda row: (-(row["threads"] + row["asked_this_month"]), row["name"]))
    return rows[:limit]


def open_questions(state: dict, school_id: str) -> list[dict]:
    """"Ask the school" questions still waiting for this school, with how many parents asked."""
    return [
        {
            "id": item["id"],
            "need": item["need"],
            "label": label_for(item["need"]),
            "question": item["question"],
            "parents": max(demand_for(state, school_id, item["need"]), int(item.get("parent_count") or 1)),
        }
        for item in state.get("inbox") or []
        if item["school_id"] == school_id and item["status"] == "open"
    ]


def answer_question(state: dict, school: dict, question_id: str, text: str, answer: dict | None = None) -> dict:
    """The school answers an "Ask the school" question in its community.

    The question opens a thread and the answer is the school's reply, so every parent can read
    it, and the reply goes through the same path as any school answer: safety check, Verified
    school badge, school_reported evidence, open questions on that need closed.
    """
    item = next((row for row in state.get("inbox") or [] if row["id"] == question_id and row["school_id"] == school["id"]), None)
    if not item or item["status"] != "open":
        return {"ok": False, "safety": {"ok": False, "findings": [], "message": "That question is already answered."}}
    community = ensure(state)
    post_id = _next_id(community)
    community["posts"].append(
        {
            "post_id": post_id,
            "thread_id": post_id,
            "school_id": school["id"],
            # Not a parent post: it never counts as parents discussing a need.
            "author": {"persona": "ask_the_school", "role": "agent"},
            "kind": "question",
            "needs": [item["need"]],
            "text": item["question"],
            "stance": "neutral",
            "origin": "ask_school",
            "created_at": _today(),
            "_synthetic": False,
        }
    )
    community["votes"][post_id] = []
    result = reply(state, post_id, "school_staff", text, {"need": item["need"], **(answer or {})})
    if not result["ok"]:
        # Blocked by the safety check: leave no empty question thread behind.
        community["posts"] = [post for post in community["posts"] if post["post_id"] != post_id]
        community["votes"].pop(post_id, None)
    return result
