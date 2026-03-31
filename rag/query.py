"""RAG query engine — retrieves context then generates answers via Claude/Gemini.

Improvements vs. prototype:
1. HALLUCINATION GUARD: The prototype's "unanswerable" path only triggered when
   the vector store returned zero chunks (empty knowledge base).  If the store had
   documents but none were semantically relevant, the LLM would still receive them
   and hallucinate an answer.
   Fixed: similarity score threshold (MIN_RELEVANCE_SCORE).  Chunks below the
   threshold are filtered out.  If nothing passes, the engine returns a structured
   "cannot answer" response WITHOUT calling the LLM, preventing hallucinations.

2. Confidence score was `len(chunks) / n_results` — purely a count ratio with no
   regard for actual semantic relevance.  Fixed: weighted average of similarity
   scores, clamped to [0, 1].

3. is_answerable field added to QueryResponse so callers (dashboard, API) can
   render a distinct "I don't know" UI state.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from llm import get_llm
from models import ChunkMetadata, QueryResponse

from .store import VectorStore

logger = logging.getLogger(__name__)

# Cosine similarity threshold below which a chunk is considered irrelevant.
# all-MiniLM-L6-v2 with normalize_embeddings=True produces scores in [-1, 1].
# Empirically, scores below ~0.30 are noise for this model.
MIN_RELEVANCE_SCORE = 0.30

SYSTEM_PROMPT = """You are an AI assistant for a project management tool called PulseBoard.
Answer questions based ONLY on the provided context chunks.

IMPORTANT RULES:
- If the context does not contain enough information to answer confidently, respond with:
  "I cannot answer this question based on the available project data."
- Do NOT fabricate facts, numbers, dates, or names not present in the context.
- Keep answers concise (2-4 sentences).
- Cite the source type (Slack / GitHub / Notion / YouTube) when relevant."""


class RAGQueryEngine:
    """Retrieve relevant chunks, then generate an answer with Claude/Gemini."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store
        self.llm = get_llm()

    def retrieve(
        self,
        question: str,
        n_results: int = 5,
        source_filter: Optional[str] = None,
    ) -> Tuple[List[str], List[ChunkMetadata], List[float]]:
        """Retrieve top-k chunks above the relevance threshold.

        Returns (chunks, metadatas, scores) — scores are the similarity values.
        """
        where = {"source_type": source_filter} if source_filter else None
        results = self.store.query(question, n_results=n_results, where=where)

        chunks: List[str] = []
        metas: List[ChunkMetadata] = []
        scores: List[float] = []

        for doc, meta, score in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # FIX: filter out low-relevance chunks to prevent hallucination
            if score < MIN_RELEVANCE_SCORE:
                logger.debug(
                    "Chunk below relevance threshold (%.3f < %.3f): '%s...'",
                    score, MIN_RELEVANCE_SCORE, doc[:60],
                )
                continue
            chunks.append(doc)
            metas.append(ChunkMetadata(**meta))
            scores.append(score)

        return chunks, metas, scores

    def generate(self, question: str, context_chunks: List[str]) -> str:
        """Call LLM with retrieved context to generate an answer."""
        context_block = "\n\n---\n\n".join(
            "[Chunk {}]\n{}".format(i + 1, chunk)
            for i, chunk in enumerate(context_chunks)
        )
        prompt = "Context:\n{}\n\nQuestion: {}".format(context_block, question)
        return self.llm.generate(prompt, system=SYSTEM_PROMPT, max_tokens=512)

    def ask(
        self,
        question: str,
        n_results: int = 5,
        source_filter: Optional[str] = None,
    ) -> QueryResponse:
        """End-to-end: retrieve → filter → generate → structured response."""
        chunks, metas, scores = self.retrieve(question, n_results, source_filter)

        # FIX: was only checking len(chunks) == 0 (empty store).
        # Now also catches the "store has docs but nothing relevant" case.
        if not chunks:
            logger.info(
                "No relevant chunks found for question: '%s'", question[:80]
            )
            return QueryResponse(
                answer=(
                    "I cannot find relevant information in the knowledge base to answer "
                    "this question. Try ingesting more data or rephrasing your question."
                ),
                sources=[],
                confidence=0.0,
                is_answerable=False,
            )

        answer = self.generate(question, chunks)

        # FIX: confidence is now the mean relevance score of retrieved chunks
        confidence = min(1.0, sum(scores) / len(scores)) if scores else 0.0

        # If the LLM itself said it cannot answer, mark accordingly
        is_answerable = "cannot answer" not in answer.lower()

        return QueryResponse(
            answer=answer,
            sources=metas,
            confidence=round(confidence, 3),
            is_answerable=is_answerable,
        )
