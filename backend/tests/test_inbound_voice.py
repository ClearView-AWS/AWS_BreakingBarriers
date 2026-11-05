"""Inbound parent line: pipeline result → short spoken summary."""

from __future__ import annotations

from contracts import Block, TurnResponse
from gaps.inbound import spoken_summary


def test_spoken_summary_names_top_three_under_sixty_words():
    response = TurnResponse(
        session_id="s1",
        route="new_search",
        blocks=[
            Block(
                type="results",
                payload={
                    "schools": [
                        {"name": "Beauclerc STEM Middle", "city": "Jacksonville", "summary": "Strong STEM and after-care until six."},
                        {"name": "Tidewater School", "city": "Jacksonville", "summary": "Solid academics near downtown."},
                        {"name": "Bayside High", "city": "Jacksonville", "summary": "Arts focus with late pickup."},
                        {"name": "Fourth School", "city": "Jacksonville", "summary": "Should not be spoken."},
                    ]
                },
            )
        ],
    )
    line = spoken_summary(response)
    words = line.split()
    assert len(words) <= 60
    assert "Beauclerc" in line and "Tidewater" in line and "Bayside" in line
    assert "Fourth School" not in line
    assert line.startswith("Top schools.")


def test_spoken_summary_empty_results():
    line = spoken_summary({"blocks": [{"type": "results", "payload": {"schools": []}}]})
    assert "could not find" in line.lower()
    assert len(line.split()) <= 60


def test_spoken_summary_trims_long_text():
    long = "word " * 80
    line = spoken_summary(
        {
            "blocks": [
                {
                    "type": "results",
                    "payload": {"schools": [{"name": "Long Name School", "city": "Jacksonville", "summary": long}]},
                }
            ]
        }
    )
    assert len(line.split()) <= 60
