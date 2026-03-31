"""Collect events from all integrated sources."""

from __future__ import annotations

import asyncio
import logging
from typing import List

from config import settings
from models import Event

logger = logging.getLogger(__name__)


class EventCollector:
    """Aggregates events from Slack, GitHub, and Notion concurrently."""

    def __init__(self) -> None:
        if not settings.demo_mode:
            from integrations.slack import SlackClient
            from integrations.github import GitHubClient
            from integrations.notion import NotionClient
            self.slack = SlackClient()
            self.github = GitHubClient()
            self.notion = NotionClient()

    async def collect_all(self, minutes: int = 30) -> List[Event]:
        """Fetch events from all sources concurrently."""
        if settings.demo_mode:
            return self._collect_demo()

        results = await asyncio.gather(
            self._safe(self.slack.fetch_all_channels, minutes),
            self._safe(self.github.fetch_all_repos, minutes),
            self._safe(self.notion.fetch_blocked_and_overdue),
            return_exceptions=True,
        )

        all_events: List[Event] = []
        for name, result in zip(["Slack", "GitHub", "Notion"], results):
            if isinstance(result, Exception):
                logger.error("Failed to collect from %s: %s", name, result)
            elif isinstance(result, list):
                all_events.extend(result)
                logger.info("Collected %d events from %s", len(result), name)

        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        return all_events

    @staticmethod
    def _collect_demo() -> List[Event]:
        from demo_data import get_all_mock_events
        events = get_all_mock_events()
        logger.info("DEMO MODE: Loaded %d mock events", len(events))
        return events

    @staticmethod
    async def _safe(coro_func, *args) -> List[Event]:
        try:
            return await coro_func(*args)
        except Exception as exc:
            logger.error("Collection error: %s", exc)
            return []
