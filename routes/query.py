"""Natural-language query API — ask questions against the knowledge base."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from models import QueryResponse
from rag.query import RAGQueryEngine
from rag.store import VectorStore

router = APIRouter(prefix="/query", tags=["query"])

# Singleton shared across requests (avoids reloading FAISS index each call)
_store: Optional[VectorStore] = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


class QuestionInput(BaseModel):
    question: str
    source_filter: Optional[str] = None  # "slack", "github", "notion", "youtube"
    n_results: int = 5


@router.post("/ask", response_model=QueryResponse)
async def ask_question(inp: QuestionInput) -> QueryResponse:
    """Ask a natural-language question against all ingested data."""
    engine = RAGQueryEngine(_get_store())
    return engine.ask(
        question=inp.question,
        n_results=inp.n_results,
        source_filter=inp.source_filter,
    )
