"""RAG API — ingest videos, generate golden datasets, run evaluations."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from config import settings
from models import EvalResult, QAPair
from rag.evaluate import RAGEvaluator
from rag.ingest import Ingestor
from rag.store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])

# ── Request / response models ─────────────────────────────────

class VideoInput(BaseModel):
    url: str
    title: str
    languages: List[str] = ["en"]


class IngestResponse(BaseModel):
    total_chunks: int
    videos_processed: int


class EvalSummary(BaseModel):
    count: int
    avg_retrieval: float
    avg_answer: float
    min_retrieval: float = 0.0
    max_retrieval: float = 0.0
    results: List[EvalResult]


# ── Default video set ─────────────────────────────────────────

DEFAULT_VIDEOS = [
    VideoInput(
        url="https://www.youtube.com/watch?v=aircAruvnKk",
        title='3Blue1Brown — "But what is a Neural Network?"',
    ),
    VideoInput(
        url="https://www.youtube.com/watch?v=wjZofJX0v4M",
        title='3Blue1Brown — "Transformers, the tech behind LLMs"',
    ),
    VideoInput(
        url="https://www.youtube.com/watch?v=fHF22Wxuyw4",
        title='CampusX — "What is Deep Learning?" (Hindi)',
        languages=["hi", "en"],
    ),
    VideoInput(
        url="https://www.youtube.com/watch?v=C6YtPJxNULA",
        title='CodeWithHarry — "All About ML & Deep Learning" (Hindi)',
        languages=["hi", "en"],
    ),
]

# Process-wide VectorStore singleton — avoids disk reload per request
_store: Optional[VectorStore] = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


async def _get_video_data(vids: List[VideoInput]) -> List[Dict]:
    """Fetch video data — mock in demo mode, real transcripts otherwise."""
    if settings.demo_mode:
        from demo_data import get_mock_video_chunks
        logger.info("DEMO MODE: Using mock video transcripts")
        return get_mock_video_chunks()

    from integrations.youtube import YouTubeTranscriptFetcher
    yt = YouTubeTranscriptFetcher()
    video_data = []
    for v in vids:
        data = await yt.fetch_video(v.url, v.title, languages=tuple(v.languages))
        video_data.append(data)
    return video_data


# ── Routes ────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse)
async def ingest_videos(videos: Optional[List[VideoInput]] = None) -> IngestResponse:
    """Ingest YouTube video transcripts into the vector store."""
    vids = videos or DEFAULT_VIDEOS
    store = _get_store()
    video_data = await _get_video_data(vids)

    total = 0
    for vd in video_data:
        for chunk in vd.get("chunks", []):
            doc_id = "yt-{}-{}".format(vd.get("video_id", vd["title"]), chunk["timestamp"])
            store.add(
                documents=[chunk["text"]],
                metadatas=[{
                    "source_type": "youtube",
                    "source_id": vd.get("video_id", ""),
                    "title": vd["title"],
                    "timestamp": chunk["timestamp"],
                    "url": vd["url"],
                }],
                ids=[doc_id],
            )
            total += 1

    return IngestResponse(total_chunks=total, videos_processed=len(video_data))


@router.post("/generate-dataset", response_model=List[QAPair])
async def generate_golden_dataset(
    videos: Optional[List[VideoInput]] = None,
    pairs_per_video: int = 2,
) -> List[QAPair]:
    """Generate a golden QA evaluation dataset from video transcripts."""
    if settings.demo_mode:
        from demo_data import MOCK_QA_PAIRS
        logger.info("DEMO MODE: Returning %d pre-built QA pairs", len(MOCK_QA_PAIRS))
        return [QAPair(**p) for p in MOCK_QA_PAIRS]

    vids = videos or DEFAULT_VIDEOS
    video_data = await _get_video_data(vids)
    evaluator = RAGEvaluator(_get_store())
    return evaluator.generate_dataset_from_videos(video_data, pairs_per_video)


@router.post("/evaluate", response_model=EvalSummary)
async def evaluate_pipeline(qa_pairs: List[QAPair]) -> EvalSummary:
    """Evaluate the RAG pipeline against a set of QA pairs."""
    evaluator = RAGEvaluator(_get_store())
    results = evaluator.evaluate_dataset(qa_pairs)
    stats = evaluator.summary_stats(results)
    return EvalSummary(**stats, results=results)


@router.get("/stats")
async def store_stats() -> dict:
    """Get vector store statistics."""
    return {"total_documents": _get_store().count()}
