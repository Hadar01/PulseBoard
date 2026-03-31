"""Shared Pydantic models used across the application.

Bug fixes vs. prototype:
- Event.timestamp used `datetime.now()` as a class-level default — evaluated ONCE
  at class definition, so all events without an explicit timestamp got the same time.
  Fixed with `Field(default_factory=...)` so it's evaluated per instance.
- Added timezone-awareness (UTC) to all default timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Event models ──────────────────────────────────────────────


class Urgency(str, Enum):
    URGENT = "urgent"
    INFO = "informational"


class Source(str, Enum):
    SLACK = "slack"
    GITHUB = "github"
    NOTION = "notion"
    YOUTUBE = "youtube"


class Event(BaseModel):
    source: Source
    title: str
    body: str
    url: str = ""
    # FIX: was `datetime.now()` — a mutable class-level default evaluated once.
    # Now uses default_factory so each Event gets its own UTC timestamp.
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    urgency: Urgency = Urgency.INFO
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Digest models ─────────────────────────────────────────────


class DigestItem(BaseModel):
    urgency: Urgency
    summary: str
    source: Source
    url: str = ""


class Digest(BaseModel):
    generated_at: datetime
    urgent: List[DigestItem] = Field(default_factory=list)
    informational: List[DigestItem] = Field(default_factory=list)
    natural_language_summary: str = ""


# ── RAG models ────────────────────────────────────────────────


class ChunkMetadata(BaseModel):
    source_type: str  # "slack", "github", "notion", "youtube"
    source_id: str
    title: str
    timestamp: str = ""
    url: str = ""


class QAPair(BaseModel):
    question: str
    answer: str
    source_video: str = ""
    source_url: str = ""
    timestamp: str = ""
    section_description: str = ""
    retrieval_challenge: str = ""


class EvalResult(BaseModel):
    question: str
    expected_answer: str
    retrieved_chunks: List[str]
    generated_answer: str
    retrieval_score: float  # 0–1: how relevant the retrieved chunks were
    answer_score: float     # 0–1: how close the generated answer is to expected


class QueryResponse(BaseModel):
    answer: str
    sources: List[ChunkMetadata] = Field(default_factory=list)
    confidence: float = 0.0
    is_answerable: bool = True   # False when RAG chain determined it can't answer
