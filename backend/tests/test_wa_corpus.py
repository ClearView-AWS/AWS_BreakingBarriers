"""Public OSPI Washington corpus loads and searches like the FL synthetic set."""

from __future__ import annotations

from contracts import Criterion
from search.corpus import clear_corpus_cache, load_programs, load_schools
from search.engine import search_schools


def test_wa_schools_present():
    clear_corpus_cache()
    wa = [s for s in load_schools() if str(s.get("id", "")).startswith("School wa-")]
    assert len(wa) >= 1000
    seattle = [s for s in wa if s.get("city") == "Seattle"]
    assert seattle
    assert all(s.get("state") == "WA" for s in seattle[:20])


def test_seattle_middle_search():
    clear_corpus_cache()
    criteria = [
        Criterion(id="c1", text="Seattle", kind="location", value="Seattle", strength="require"),
        Criterion(id="c2", text="middle", kind="grade", value="m", strength="require"),
    ]
    rows = search_schools(
        load_schools(),
        load_programs(),
        criteria,
        "middle school in Seattle",
        limit=20,
    )
    assert rows
    assert all(r.get("city") == "Seattle" for r in rows[:5])
    assert any("m" in (r.get("level_codes") or []) for r in rows[:10])
