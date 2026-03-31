"""Notion integration — fetches project tasks and their statuses.

Improvements vs. prototype:
1. No retry logic. Fixed: tenacity retry with exponential back-off.
2. Timeout reads settings.api_request_timeout.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from models import Event, Source

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


class NotionClient:
    """Async wrapper around the Notion API for reading project databases."""

    def __init__(
        self,
        token: Optional[str] = None,
        database_id: Optional[str] = None,
    ) -> None:
        self.token = token or settings.notion_token
        self.database_id = database_id or settings.notion_database_id
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    # ── Internal HTTP ─────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=settings.api_request_timeout) as client:
            resp = await client.post(
                f"{NOTION_API}{path}",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Property extractors ───────────────────────────────────

    @staticmethod
    def _extract_title(properties: dict) -> str:
        for prop in properties.values():
            if prop["type"] == "title":
                return "".join(t["plain_text"] for t in prop["title"])
        return "Untitled"

    @staticmethod
    def _extract_status(properties: dict) -> str:
        for prop in properties.values():
            if prop["type"] == "status" and prop.get("status"):
                return prop["status"]["name"]
            if prop["type"] == "select" and prop.get("select"):
                return prop["select"]["name"]
        return "Unknown"

    @staticmethod
    def _extract_date(properties: dict) -> Optional[str]:
        for prop in properties.values():
            if prop["type"] == "date" and prop.get("date"):
                return prop["date"].get("start")
        return None

    @staticmethod
    def _extract_assignee(properties: dict) -> str:
        for prop in properties.values():
            if prop["type"] == "people":
                names = [p.get("name", "") for p in prop.get("people", [])]
                return ", ".join(n for n in names if n) or "Unassigned"
        return "Unassigned"

    # ── Fetchers ──────────────────────────────────────────────

    async def fetch_tasks(self, status_filter: Optional[str] = None) -> List[Event]:
        """Query the project database, optionally filtering by status."""
        payload: dict = {"page_size": 50}
        if status_filter:
            payload["filter"] = {
                "property": "Status",
                "status": {"equals": status_filter},
            }

        data = await self._post(f"/databases/{self.database_id}/query", payload)

        events: List[Event] = []
        for page in data.get("results", []):
            props = page["properties"]
            title = self._extract_title(props)
            status = self._extract_status(props)
            due = self._extract_date(props)
            assignee = self._extract_assignee(props)

            body = f"Status: {status} | Assignee: {assignee}"
            if due:
                body += f" | Due: {due}"

            events.append(
                Event(
                    source=Source.NOTION,
                    title=title,
                    body=body,
                    url=page.get("url", ""),
                    timestamp=datetime.fromisoformat(
                        page["last_edited_time"].replace("Z", "+00:00")
                    ),
                    metadata={
                        "status": status,
                        "assignee": assignee,
                        "due": due,
                        "page_id": page["id"],
                    },
                )
            )
        return events

    async def fetch_blocked_and_overdue(self) -> List[Event]:
        """Convenience: return tasks that are blocked or past their due date."""
        all_tasks = await self.fetch_tasks()
        now = datetime.now(timezone.utc).date()
        flagged: List[Event] = []
        for task in all_tasks:
            status = task.metadata.get("status", "").lower()
            due = task.metadata.get("due")
            is_blocked = "block" in status
            is_overdue = False
            if due:
                try:
                    is_overdue = datetime.fromisoformat(due).date() < now
                except ValueError:
                    pass
            if is_blocked or is_overdue:
                flagged.append(task)
        return flagged
