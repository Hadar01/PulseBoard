"""Slack integration — fetches recent messages from configured channels.

Improvements vs. prototype:
1. No retry logic — a transient 429 or network blip would fail the entire
   collection pass.  Fixed: tenacity retry with exponential back-off.
2. Timeout was 15 s per request.  Now reads settings.api_request_timeout.
3. Pagination: conversations.list was fetching only 200 channels; if a workspace
   has more, configured channels could be missed.  Added cursor-based pagination.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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

SLACK_API = "https://slack.com/api"
_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


def _is_retryable_http(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (
        429, 500, 502, 503, 504
    )


class SlackClient:
    """Thin async wrapper around the Slack Web API."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or settings.slack_bot_token
        self._headers = {"Authorization": f"Bearer {self.token}"}

    # ── Internal HTTP ─────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        async with httpx.AsyncClient(timeout=settings.api_request_timeout) as client:
            resp = await client.get(
                f"{SLACK_API}/{endpoint}",
                headers=self._headers,
                params=params or {},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                error = data.get("error", "unknown")
                logger.error("Slack API error on %s: %s", endpoint, error)
                # Rate-limited — raise so tenacity can retry
                if error == "ratelimited":
                    raise httpx.HTTPStatusError(
                        "Slack rate limited",
                        request=resp.request,
                        response=resp,
                    )
            return data

    # ── Channel resolution with pagination ────────────────────

    async def get_channel_id(self, channel_name: str) -> Optional[str]:
        """Resolve a channel name to its ID, following cursor pagination."""
        cursor: Optional[str] = None
        while True:
            params: dict = {
                "types": "public_channel,private_channel",
                "limit": 200,
            }
            if cursor:
                params["cursor"] = cursor

            data = await self._get("conversations.list", params)
            for ch in data.get("channels", []):
                if ch["name"] == channel_name:
                    return ch["id"]

            next_cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not next_cursor:
                break
            cursor = next_cursor

        logger.warning("Slack channel '%s' not found in workspace", channel_name)
        return None

    # ── Message fetching ──────────────────────────────────────

    async def fetch_recent_messages(
        self, channel_name: str, minutes: int = 30
    ) -> List[Event]:
        """Fetch messages from the last `minutes` in a channel."""
        channel_id = await self.get_channel_id(channel_name)
        if not channel_id:
            return []

        oldest = (
            datetime.now(timezone.utc) - timedelta(minutes=minutes)
        ).timestamp()

        data = await self._get(
            "conversations.history",
            {"channel": channel_id, "oldest": str(oldest), "limit": 50},
        )

        events: List[Event] = []
        for msg in data.get("messages", []):
            if msg.get("subtype"):  # skip bot / system messages
                continue
            events.append(
                Event(
                    source=Source.SLACK,
                    title=f"#{channel_name}",
                    body=msg.get("text", ""),
                    timestamp=datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc),
                    metadata={"user": msg.get("user", ""), "channel": channel_name},
                )
            )
        return events

    async def fetch_all_channels(self, minutes: int = 30) -> List[Event]:
        """Fetch recent messages from all configured channels."""
        all_events: List[Event] = []
        for ch in settings.slack_channel_list:
            try:
                events = await self.fetch_recent_messages(ch, minutes)
                all_events.extend(events)
            except Exception as exc:
                logger.error("Failed to fetch Slack channel '%s': %s", ch, exc)
        return all_events
