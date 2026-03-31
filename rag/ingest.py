"""Ingest data from all sources into the vector store."""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Tuple

from config import settings
from models import ChunkMetadata, Event

from .store import VectorStore

logger = logging.getLogger(__name__)


class Ingestor:
    """Ingests content from various sources into the vector store."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store

    @staticmethod
    def _make_id(text: str, source: str) -> str:
        """Deterministic chunk ID to avoid duplicates on re-ingest."""
        return hashlib.sha256(f"{source}:{text[:200]}".encode()).hexdigest()[:16]

    def ingest_events(self, events: List[Event]) -> int:
        """Ingest heartbeat events (Slack messages, GitHub PRs, Notion tasks)."""
        docs, metas, ids = [], [], []
        for ev in events:
            content = f"{ev.title}\n{ev.body}"
            doc_id = self._make_id(content, ev.source.value)
            docs.append(content)
            metas.append(
                ChunkMetadata(
                    source_type=ev.source.value,
                    source_id=doc_id,
                    title=ev.title,
                    timestamp=ev.timestamp.isoformat(),
                    url=ev.url,
                ).model_dump()
            )
            ids.append(doc_id)

        if docs:
            self.store.add(documents=docs, metadatas=metas, ids=ids)
            logger.info("Ingested %d events into vector store", len(docs))
        return len(docs)

    def ingest_youtube_video(
        self,
        url: str,
        title: str,
        chunk_seconds: int | None = None,
        languages: Tuple[str, ...] = ("en",),
    ) -> int:
        """Ingest a single YouTube video's transcript as chunks."""
        import asyncio

        from integrations.youtube import YouTubeTranscriptFetcher

        yt = YouTubeTranscriptFetcher()
        # YouTubeTranscriptFetcher.fetch_video is now async
        video_data = asyncio.run(
            yt.fetch_video(url, title, chunk_seconds, languages)
        )
        docs, metas, ids = [], [], []

        for chunk in video_data["chunks"]:
            doc_id = self._make_id(chunk["text"], video_data["video_id"])
            docs.append(chunk["text"])
            metas.append(
                ChunkMetadata(
                    source_type="youtube",
                    source_id=video_data["video_id"],
                    title=title,
                    timestamp=chunk["timestamp"],
                    url=url,
                ).model_dump()
            )
            ids.append(doc_id)

        if docs:
            self.store.add(documents=docs, metadatas=metas, ids=ids)
            logger.info("Ingested %d chunks from '%s'", len(docs), title)
        return len(docs)

    def ingest_all_videos(self, videos: List[Dict]) -> int:
        """Batch-ingest multiple videos."""
        total = 0
        for v in videos:
            total += self.ingest_youtube_video(
                url=v["url"],
                title=v["title"],
                languages=tuple(v.get("languages", ["en"])),
            )
        return total
