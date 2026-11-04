"""Write data/synthetic/community_seed.json: seed threads, votes, and demand counts.

Run from the repo root:  python data/synthetic/generate_community.py

Every seed record is marked _synthetic: true. Posts follow the topics and tone
of the sample reviews and never name a student or staff member. Dates sit in
October and early November 2026 so "this month" demand counts are not empty
with the repo clock (GS_TODAY = 2026-11-03).

Delete data/runtime/state.json after regenerating so the app reloads the seed.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "community_seed.json"

BEAUCLERC = "School fl-180019"  # demo school: after-school care is unknown in the profile
CEDAR = "School fl-180100"      # parents say after-care is good, school has not confirmed
ARLINGTON = "School fl-180003"
TIDEWATER = "School fl-180001"
RIVERSIDE = "School fl-180005"
LANDMARK = "School fl-180021"
MANDARIN = "School fl-180004"
MARINER = "School fl-95390"     # sample school with real-looking reviews about substitutes

# (school, need tags, kind, stance, date, votes, text, replies[(stance, date, text)])
THREADS = [
    (BEAUCLERC, ["after_care"], "question", "neutral", "2026-11-01", 23,
     "Does after-care run past 5:30? I work until 5 and the drive takes a while.",
     [
         ("neutral", "2026-11-01", "I think it ends around 5:30 but the times changed last year, so I'm not sure."),
         ("neutral", "2026-11-02", "We use the YMCA program a few blocks away instead. It goes until 6."),
         ("neutral", "2026-11-02", "Same question here. The front office told us to check back in January."),
     ]),
    (BEAUCLERC, ["stem"], "question", "neutral", "2026-10-24", 17,
     "How is the robotics club? Is it worth signing up in sixth grade?",
     [
         ("positive", "2026-10-25", "My kid loves it. They meet twice a week and went to a regional competition last spring."),
         ("positive", "2026-10-26", "Great club. The coaches are supportive and beginners are welcome."),
         ("neutral", "2026-10-28", "There is a waitlist some years, so sign up early in August."),
     ]),
    (BEAUCLERC, ["special_education"], "experience", "positive", "2026-10-12", 9,
     "Our experience with the IEP process here has been good. The team met with us twice in the first month and actually followed the plan.",
     [
         ("positive", "2026-10-14", "Same for us. The resource room teacher is very helpful."),
     ]),
    (BEAUCLERC, ["transportation"], "question", "neutral", "2026-11-02", 4,
     "Does the bus route cover the neighborhoods south of Beach Blvd?",
     []),
    (CEDAR, ["after_care"], "experience", "positive", "2026-10-20", 11,
     "After-care here has been great for us. Homework time first, then outside, and pickup is easy.",
     [
         ("positive", "2026-10-21", "Agree, the after-care staff are wonderful and it runs late enough for my shift."),
         ("neutral", "2026-10-23", "Is there a waitlist this year?"),
     ]),
    (CEDAR, ["clubs"], "question", "neutral", "2026-10-30", 3,
     "What clubs are running this semester?",
     [("neutral", "2026-10-31", "Chess, yearbook, and a coding club that started in September.")]),
    (ARLINGTON, ["stem"], "experience", "positive", "2026-10-05", 14,
     "The STEM labs are excellent. Projects every week and the science fair is a big deal here.",
     [("positive", "2026-10-06", "Happy with it too. Homework load is reasonable.")]),
    (ARLINGTON, ["sports"], "question", "neutral", "2026-10-28", 5,
     "Do middle schoolers get to play on a team, or is it intramural only?",
     [("neutral", "2026-10-29", "There is flag football and volleyball, plus intramurals at lunch.")]),
    (TIDEWATER, ["after_care"], "question", "neutral", "2026-11-03", 6,
     "Is after-care on campus or do they bus kids somewhere else?",
     []),
    (TIDEWATER, ["family_engagement"], "experience", "positive", "2026-10-18", 8,
     "The family nights are fun and the teachers reply to emails within a day.",
     []),
    (RIVERSIDE, ["low_cost"], "question", "neutral", "2026-10-27", 12,
     "Has anyone used the Florida scholarship here? How long did approval take?",
     [("neutral", "2026-10-28", "It took about six weeks for us. Apply as early as the window opens.")]),
    (LANDMARK, ["arts"], "experience", "positive", "2026-10-09", 4,
     "The music program is wonderful. The spring concert was the best one we've been to.",
     []),
    (MANDARIN, ["safety"], "question", "neutral", "2026-10-22", 7,
     "How does pickup work? The line looked long when we toured.",
     [("neutral", "2026-10-22", "It moves faster after the first two weeks. Get there by 3:10.")]),
    (MARINER, ["teacher_stability"], "experience", "negative", "2026-10-03", 10,
     "We had long stretches with substitutes last year. Frustrating for our kid and hard to keep up with homework.",
     [
         ("negative", "2026-10-04", "Same. Three different teachers in one year and communication was poor."),
         ("negative", "2026-10-06", "We were disappointed too. It felt chaotic until spring."),
         ("neutral", "2026-10-08", "I heard they hired more full-time staff this fall. Has anyone seen a change?"),
     ]),
]

# (school, need, askers this month, askers last month)
ASKS = [
    (BEAUCLERC, "after_care", 13, 4),
    (BEAUCLERC, "stem", 6, 2),
    (BEAUCLERC, "transportation", 3, 1),
    (CEDAR, "after_care", 5, 2),
    (TIDEWATER, "after_care", 4, 1),
    (ARLINGTON, "sports", 2, 0),
    (RIVERSIDE, "low_cost", 7, 3),
    (MANDARIN, "safety", 3, 1),
]


def main() -> None:
    posts = []
    votes: dict[str, list[str]] = {}
    seq = 0
    author = 0

    def next_id() -> str:
        nonlocal seq
        seq += 1
        return f"p_{seq}"

    def next_author() -> str:
        nonlocal author
        author += 1
        return f"seed_parent_{author}"

    for school_id, need_ids, kind, stance, day, vote_count, text, replies in THREADS:
        post_id = next_id()
        posts.append({
            "post_id": post_id,
            "thread_id": post_id,
            "school_id": school_id,
            "author": {"persona": next_author(), "role": "parent"},
            "kind": kind,
            "needs": need_ids,
            "text": text,
            "stance": stance,
            "origin": "community",
            "created_at": day,
            "_synthetic": True,
        })
        votes[post_id] = [f"seed_voter_{i}" for i in range(1, vote_count + 1)]
        for reply_stance, reply_day, reply_text in replies:
            reply_id = next_id()
            posts.append({
                "post_id": reply_id,
                "thread_id": post_id,
                "school_id": school_id,
                "author": {"persona": next_author(), "role": "parent"},
                "kind": "reply",
                "needs": need_ids,
                "text": reply_text,
                "stance": reply_stance,
                "origin": "community",
                "created_at": reply_day,
                "_synthetic": True,
            })
            votes[reply_id] = [f"seed_voter_{i}" for i in range(1, max(1, vote_count // 4) + 1)]

    asks = []
    for school_id, need, this_month, last_month in ASKS:
        for i in range(this_month):
            asks.append({"school_id": school_id, "need": need, "month": "2026-11",
                         "asker": f"seed_asker_{need}_{i}", "origin": "seed", "_synthetic": True})
        for i in range(last_month):
            asks.append({"school_id": school_id, "need": need, "month": "2026-10",
                         "asker": f"seed_asker_{need}_old_{i}", "origin": "seed", "_synthetic": True})

    OUT.write_text(json.dumps({"posts": posts, "votes": votes, "asks": asks}, indent=2) + "\n")
    print(f"wrote {len(posts)} posts and {len(asks)} demand records to {OUT}")


if __name__ == "__main__":
    main()
