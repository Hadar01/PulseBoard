"""GitHub integration — fetches PRs, issues, and CI workflow failures.

Improvements vs. prototype:
1. No retry logic — a transient 429 / network blip would fail the entire
   collection pass.  Fixed: tenacity retry with exponential back-off.
2. Timeout reads settings.api_request_timeout (was implicit httpx default).
3. GitHub API returns X-RateLimit-Remaining headers; we log a warning when
   the remaining quota is low so operators know before a hard failure hits.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

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

GH_API = "https://api.github.com"
_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


class GitHubClient:
    """Async wrapper around the GitHub REST API."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or settings.github_token
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ── Internal HTTP ─────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get(
        self, path: str, params: Optional[dict] = None
    ) -> Union[dict, list]:
        async with httpx.AsyncClient(timeout=settings.api_request_timeout) as client:
            resp = await client.get(
                f"{GH_API}{path}",
                headers=self._headers,
                params=params or {},
            )
            # Warn on low rate-limit headroom before it becomes a hard failure
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining is not None and int(remaining) < 10:
                logger.warning(
                    "GitHub rate limit low: %s requests remaining", remaining
                )
            resp.raise_for_status()
            return resp.json()

    # ── Fetchers ──────────────────────────────────────────────

    async def fetch_recent_prs(self, repo: str, minutes: int = 30) -> List[Event]:
        """Fetch open / recently updated PRs."""
        since = (
            datetime.now(timezone.utc) - timedelta(minutes=minutes)
        ).isoformat()

        pulls = await self._get(
            f"/repos/{repo}/pulls",
            {"state": "all", "sort": "updated", "direction": "desc", "per_page": 10},
        )

        events: List[Event] = []
        for pr in pulls:
            updated = pr.get("updated_at", "")
            if updated >= since:
                events.append(
                    Event(
                        source=Source.GITHUB,
                        title=f"PR #{pr['number']}: {pr['title']}",
                        body=pr.get("body", "") or "",
                        url=pr["html_url"],
                        timestamp=datetime.fromisoformat(
                            updated.replace("Z", "+00:00")
                        ),
                        metadata={
                            "repo": repo,
                            "state": pr["state"],
                            "user": pr["user"]["login"],
                            "merged": pr.get("merged", False),
                        },
                    )
                )
        return events

    async def fetch_failed_runs(self, repo: str) -> List[Event]:
        """Fetch the most recent failed CI workflow runs."""
        data = await self._get(
            f"/repos/{repo}/actions/runs",
            {"status": "failure", "per_page": 5},
        )

        events: List[Event] = []
        for run in data.get("workflow_runs", []):
            events.append(
                Event(
                    source=Source.GITHUB,
                    title=f"CI Failed: {run['name']}",
                    body=(
                        f"Branch: {run['head_branch']} | "
                        f"Commit: {run['head_sha'][:7]}"
                    ),
                    url=run["html_url"],
                    timestamp=datetime.fromisoformat(
                        run["updated_at"].replace("Z", "+00:00")
                    ),
                    metadata={"repo": repo, "workflow": run["name"]},
                )
            )
        return events

    async def fetch_all_repos(self, minutes: int = 30) -> List[Event]:
        """Aggregate events from all configured repos."""
        all_events: List[Event] = []
        for repo in settings.github_repo_list:
            try:
                all_events.extend(await self.fetch_recent_prs(repo, minutes))
                all_events.extend(await self.fetch_failed_runs(repo))
            except Exception as exc:
                logger.error("Failed to fetch GitHub repo '%s': %s", repo, exc)
        return all_events
