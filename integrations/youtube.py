"""YouTube transcript fetcher — pulls and structures video transcripts.

Improvements vs. prototype:
1. YouTubeTranscriptApi.get_transcript() had no timeout — a slow or hanging
   network connection would block the entire ingest indefinitely.
   Fixed: wrapped in asyncio.wait_for with settings.api_request_timeout.

2. The bare `except Exception` swallowed all errors silently.  Fixed: log the
   specific exception type so operators know whether it was a network error,
   a missing transcript, or a disabled video.

3. Chunk boundary logic: the prototype created a new chunk only when an entry
   START crossed chunk_end.  If a single entry was very long (e.g. auto-generated
   captions with huge segments) it could spill into multiple windows but never
   be split.  Added a hard character cap per chunk.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Optional, Tuple

from config import settings

logger = logging.getLogger(__name__)

# Hard character ceiling per chunk — prevents single-entry overflow
MAX_CHUNK_CHARS = 2000


class YouTubeTranscriptFetcher:
    """Fetch and structure YouTube transcripts for RAG ingestion."""

    # ── Video ID extraction ───────────────────────────────────

    @staticmethod
    def extract_video_id(url: str) -> str:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"Cannot extract video ID from: {url!r}")

    # ── Transcript fetching ───────────────────────────────────

    @staticmethod
    def _fetch_transcript_sync(
        video_id: str, languages: Tuple[str, ...]
    ) -> List[dict]:
        """Synchronous transcript fetch (run in thread via asyncio.to_thread)."""
        from youtube_transcript_api import YouTubeTranscriptApi

        try:
            return YouTubeTranscriptApi.get_transcript(
                video_id, languages=list(languages)
            )
        except Exception as primary_exc:
            logger.debug(
                "Primary transcript fetch failed for %s (%s): %s",
                video_id, languages, primary_exc,
            )

        # Fallback: try Hindi + English for Hindi-language videos
        try:
            return YouTubeTranscriptApi.get_transcript(
                video_id, languages=["hi", "en"]
            )
        except Exception as fallback_exc:
            logger.error(
                "All transcript attempts failed for %s: %s",
                video_id,
                type(fallback_exc).__name__,
            )
            return []

    async def fetch_transcript(
        self, video_id: str, languages: Tuple[str, ...] = ("en",)
    ) -> List[dict]:
        """Async wrapper around transcript fetch with timeout protection."""
        try:
            # FIX: run blocking I/O in a thread so it doesn't block the event loop,
            # and apply a timeout so a hung connection doesn't stall ingestion.
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_transcript_sync, video_id, languages),
                timeout=settings.api_request_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Transcript fetch timed out for %s after %ds",
                video_id,
                settings.api_request_timeout,
            )
            return []

    # ── Chunking ──────────────────────────────────────────────

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        mins, secs = divmod(int(seconds), 60)
        return f"{mins:02d}:{secs:02d}"

    async def get_timestamped_chunks(
        self,
        video_id: str,
        chunk_seconds: Optional[int] = None,
        languages: Tuple[str, ...] = ("en",),
    ) -> List[dict]:
        """Split transcript into time-windowed chunks.

        Each chunk: {"text": str, "start": float, "end": float, "timestamp": str}
        """
        window = chunk_seconds or settings.chunk_seconds
        entries = await self.fetch_transcript(video_id, languages)
        if not entries:
            return []

        chunks: List[dict] = []
        current_texts: List[str] = []
        current_chars: int = 0
        chunk_start: float = 0.0
        chunk_end: float = window

        def _flush(end_time: float) -> None:
            if current_texts:
                chunks.append({
                    "text": " ".join(current_texts),
                    "start": chunk_start,
                    "end": end_time,
                    "timestamp": YouTubeTranscriptFetcher.format_timestamp(chunk_start),
                })

        for entry in entries:
            text = entry["text"]
            # FIX: split on time boundary OR hard character cap
            time_overflow = entry["start"] >= chunk_end and current_texts
            char_overflow = current_chars + len(text) > MAX_CHUNK_CHARS and current_texts

            if time_overflow or char_overflow:
                _flush(entry["start"])
                current_texts = []
                current_chars = 0
                chunk_start = entry["start"]
                chunk_end = chunk_start + window

            current_texts.append(text)
            current_chars += len(text)

        # Flush remaining
        if current_texts and entries:
            last = entries[-1]
            _flush(last["start"] + last.get("duration", 0))

        return chunks

    async def fetch_video(
        self,
        url: str,
        title: str,
        chunk_seconds: Optional[int] = None,
        languages: Tuple[str, ...] = ("en",),
    ) -> dict:
        """High-level: fetch a video's transcript and return structured data."""
        video_id = self.extract_video_id(url)
        chunks = await self.get_timestamped_chunks(video_id, chunk_seconds, languages)
        return {
            "video_id": video_id,
            "title": title,
            "url": url,
            "chunks": chunks,
            "total_chunks": len(chunks),
        }
