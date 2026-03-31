"""Generate human-readable digests using Claude/Gemini."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from llm import get_llm
from models import Digest, DigestItem, Event, Urgency

logger = logging.getLogger(__name__)

DIGEST_PROMPT = """You are a project assistant for a non-technical founder at an AI company.
She manages client relationships, BD, and delivery — she does NOT read code or logs.

Summarize these events into a SHORT digest (max 5 bullet points).
Group into URGENT (needs her attention now) and INFORMATIONAL (awareness only).
Use plain English — no technical jargon, no code references, no PR numbers.
If something is blocked or overdue, say whose attention it needs.

Events:
{events}

Format your response as:
URGENT:
- ...

INFORMATIONAL:
- ...

SUMMARY: (one sentence overall status)
"""


class DigestGenerator:
    """Turns classified events into a concise natural-language digest."""

    def generate(self, events: List[Event]) -> Digest:
        if not events:
            return Digest(
                generated_at=datetime.now(timezone.utc),
                natural_language_summary="No new activity in the last 30 minutes.",
            )

        urgent = [e for e in events if e.urgency == Urgency.URGENT]
        info = [e for e in events if e.urgency == Urgency.INFO]

        digest = Digest(
            generated_at=datetime.now(timezone.utc),
            urgent=[
                DigestItem(
                    urgency=Urgency.URGENT,
                    summary=f"{e.title}: {e.body[:120]}",
                    source=e.source,
                    url=e.url,
                )
                for e in urgent
            ],
            informational=[
                DigestItem(
                    urgency=Urgency.INFO,
                    summary=f"{e.title}: {e.body[:120]}",
                    source=e.source,
                    url=e.url,
                )
                for e in info
            ],
        )

        digest.natural_language_summary = self._summarize_with_llm(events)
        return digest

    def _summarize_with_llm(self, events: List[Event]) -> str:
        events_text = "\n".join(
            "[{urgency}] [{source}] {title}: {body}".format(
                urgency=e.urgency.value.upper(),
                source=e.source.value,
                title=e.title,
                body=e.body[:200],
            )
            for e in events
        )
        prompt = DIGEST_PROMPT.format(events=events_text)
        try:
            return get_llm().generate(prompt, max_tokens=512)
        except Exception as exc:
            logger.error("LLM summarization failed: %s", exc)
            urgent_count = sum(1 for e in events if e.urgency == Urgency.URGENT)
            return f"{len(events)} events collected. {urgent_count} need your attention."
