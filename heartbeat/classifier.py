"""Rule-based urgency classifier for events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from models import Event, Source, Urgency

# Keywords that signal urgency in message bodies
URGENT_KEYWORDS = frozenset({
    "urgent", "asap", "blocker", "blocked", "down", "outage",
    "broken", "critical", "hotfix", "p0", "incident", "deadline",
    "failed", "failure", "error", "crash",
})


def classify_events(events: List[Event]) -> List[Event]:
    """Apply urgency classification to a list of events.

    Rules (any match → URGENT):
    1. CI failure on GitHub
    2. Notion task is blocked or overdue
    3. Any message body contains urgent keywords
    4. Slack message in a client-* channel is older than 1 hour (unanswered)
    """
    now = datetime.now(timezone.utc)
    for event in events:
        event.urgency = Urgency.URGENT if _is_urgent(event, now) else Urgency.INFO
    return events


def _is_urgent(event: Event, now: datetime) -> bool:
    # Rule 1: GitHub CI failures
    if event.source == Source.GITHUB and "CI Failed" in event.title:
        return True

    # Rule 2: Notion blocked / overdue tasks
    if event.source == Source.NOTION:
        status = event.metadata.get("status", "").lower()
        if "block" in status:
            return True
        due = event.metadata.get("due_date") or event.metadata.get("due", "")
        if due:
            try:
                if datetime.fromisoformat(str(due)).date() < now.date():
                    return True
            except ValueError:
                pass

    # Rule 3: Urgent keywords in message body
    body_lower = event.body.lower()
    if any(kw in body_lower for kw in URGENT_KEYWORDS):
        return True

    # Rule 4: Unanswered client channel message older than 1 hour
    if event.source == Source.SLACK:
        channel = event.metadata.get("channel", "")
        if channel.startswith("client-"):
            ts = event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (now - ts) > timedelta(hours=1):
                return True

    return False
