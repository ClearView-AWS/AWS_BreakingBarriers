"""Fold community posts and school answers into an evidence record.

Rules (see docs/plan.md, Rules in Code):
- A school's own answer in its thread is school_reported evidence and can confirm.
- Parent posts can support a criterion (Partial) or flag it (Needs attention).
  They never confirm one, and they carry low confidence so they never move a
  school into "Missed a must-have" on their own.
- 2+ posts on the need, mostly positive  -> Partial      (only if it was Unknown)
- 3+ posts on the need, mostly negative  -> Needs attention (never over Confirmed)
"""

from __future__ import annotations

from catalog import needs
from community.service import school_answer_for, support
from community.tags import label_for
from contracts import EvidenceRecord, Source
from evidence.status import answer_expired, parse_date, stale_note
from runtime_config import TODAY


def apply_community(record: EvidenceRecord, school: dict, criterion, state: dict) -> EvidenceRecord:
    need = criterion.need
    if criterion.kind != "need" or not need or need not in needs():
        return record
    label = (needs()[need].get("label") or label_for(need))

    answer = school_answer_for(state, school["id"], need)
    if answer:
        if answer.get("value") and record.source and record.source.type == "school_reported":
            # The overlay already turned the field into school_reported evidence. Link the thread.
            record.post_ids = [*record.post_ids, answer["post_id"]]
            return record
        offers = answer.get("offers")
        upgrades = offers is True and record.status != "confirmed"
        if upgrades or offers is False:
            status = "confirmed" if offers else "needs_attention"
            word = "confirmed" if offers else "a miss"
            said = "offers it" if offers else "does not offer it"
            stale = answer_expired(need, answer.get("as_of"))
            if stale:
                # Past the need's max_age_days: the old answer only partly supports it.
                status, word = "partial", "only partly supported"
            return EvidenceRecord(
                school_id=school["id"],
                criterion_id=criterion.id,
                status=status,
                value="school answered" if offers else "not offered",
                source=Source(type="school_reported", path=answer["post_id"], as_of=answer.get("as_of"), confidence="high"),
                note=f"{label} is {word}: the school answered in its community thread that it {said} [[cite:{answer['post_id']}]]."
                + (f" {stale_note(answer.get('as_of'))}" if stale else ""),
                review_ids=record.review_ids,
                post_ids=[answer["post_id"]],
                answered_at=answer.get("as_of"),
                stale=stale,
            )

    found = support(state, school["id"], need)
    if not found["post_ids"]:
        return record
    record.post_ids = [*record.post_ids, *found["post_ids"]]
    first = found["post_ids"][0]
    as_of = (parse_date(found.get("newest")) or TODAY).isoformat()
    if found["negative"] >= 3 and found["negative"] > found["positive"] and record.status not in {"confirmed", "needs_attention"}:
        record.status = "needs_attention"
        record.value = f"{found['negative']:.0f} parent posts raise concerns"
        record.source = Source(type="community", path=first, as_of=as_of, confidence="low")
        record.note = f"{label} needs attention: parents in the community raise concerns [[cite:{first}]]."
    elif found["positive"] >= 2 and found["positive"] > found["negative"] and record.status == "unknown":
        record.status = "partial"
        record.value = "Parents say yes"
        record.source = Source(type="community", path=first, as_of=as_of, confidence="low")
        record.note = (
            f"{label} is only partly supported: parents say so in the community, "
            f"but the school has not confirmed it [[cite:{first}]]."
        )
    return record
