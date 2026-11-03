"""Shared shapes for a turn. Tracks build against these models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Strength = Literal["require", "prefer", "avoid"]
EvidenceStatus = Literal["confirmed", "partial", "needs_attention", "unknown"]
SourceType = Literal[
    "state_data",
    "school_reported",
    "school_website",
    "parent_reviews",
    "program",
    "funding_rule",
    "glossary",
]
Route = Literal[
    "new_search",
    "refine",
    "compare",
    "school_detail",
    "define",
    "why_not",
    "cost",
    "save",
    "feedback",
    "inbox",
]


class MappingInfo(BaseModel):
    score: float
    runner_up: str | None = None
    margin: float | None = None


class Ambiguity(BaseModel):
    kind: str
    options: list[str]
    option_ids: list[str] = Field(default_factory=list)
    question: str | None = None
    default: str | None = None


class Criterion(BaseModel):
    id: str
    text: str
    need: str | None = None
    strength: Strength = "prefer"
    params: dict[str, Any] = Field(default_factory=dict)
    mapping: MappingInfo | None = None
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    kind: Literal["need", "location", "grade", "school_type", "distance"] = "need"
    value: Any = None
    resolved_reading: str | None = None


class Source(BaseModel):
    type: SourceType
    path: str
    as_of: str | None = None
    confidence: str | None = None


class Conflict(BaseModel):
    path: str
    profile_value: Any = None
    website_value: Any = None
    as_of: str | None = None


class EvidenceRecord(BaseModel):
    school_id: str
    criterion_id: str
    status: EvidenceStatus
    value: Any = None
    source: Source | None = None
    note: str = ""
    conflict: Conflict | None = None
    review_ids: list[str] = Field(default_factory=list)


class SchoolResult(BaseModel):
    id: str
    name: str
    city: str
    state: str
    entity_type: str | None = None
    level_codes: list[str] = Field(default_factory=list)
    match: float
    verified: str
    coverage: float
    missed_must: bool = False
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    summary: str = ""
    distance_miles: float | None = None
    lat: float | None = None
    lon: float | None = None


class Block(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


EngineName = Literal["bedrock", "rules", "rules_fallback"]


class EngineStep(BaseModel):
    """Who answered one step: Bedrock, the rules (Bedrock off), or the rules after Bedrock failed."""

    engine: EngineName
    error: str | None = None


class Engine(BaseModel):
    """Per-turn record of who answered each step. None means the step did not run."""

    route: EngineName | None = None
    extract: EngineName | None = None
    explain: EngineName | None = None
    errors: list[str] = Field(default_factory=list)


class TurnResponse(BaseModel):
    session_id: str
    route: Route
    criteria: list[Criterion] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)
    assumption: str | None = None
    engine: Engine = Field(default_factory=Engine)
