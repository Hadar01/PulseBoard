"""RAG evaluation — generate golden QA pairs and score retrieval quality.

Bug fixes vs. prototype:
1. CRASH BUG: `json.loads(raw)` was called directly on LLM output with no error
   handling.  A malformed or truncated LLM response (e.g. rate-limited partial
   reply) raised an unhandled JSONDecodeError that bubbled up as a 500 to the
   API caller.
   Fixed: `_safe_json_loads` tries multiple extraction strategies and logs
   a structured warning instead of crashing.

2. The evaluate_pair method had no per-pair error isolation — one bad LLM response
   would abort the entire evaluation run.  Fixed: each pair is wrapped individually.

3. Scoring keys were accessed via dict.get() returning floats, but if the LLM
   returned strings (e.g. "0.85") Pydantic would reject them.
   Fixed: explicit float() cast with fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from config import settings
from llm import get_llm
from models import EvalResult, QAPair

from .query import RAGQueryEngine
from .store import VectorStore

logger = logging.getLogger(__name__)

QA_GENERATION_PROMPT = """You are an expert ML engineer building a golden evaluation dataset for a RAG system.

Given the following transcript chunks from a video, generate {n} high-quality question-answer pairs.

STRICT CRITERIA:
- Each question must be answerable from ONE specific chunk (not spread across chunks)
- Questions must test SEMANTIC understanding, not keyword matching
- Mix types: conceptual definition, mechanism/process, comparison, "why" explanation, technical detail
- Answers: 2-4 sentences, grounded in the transcript, no padding
- Include a "retrieval_challenge" — what confusable chunk would a wrong retrieval return?

Video: {title}
URL: {url}

Chunks (with timestamps):
{chunks}

Return ONLY a JSON array of objects with these exact keys:
"question", "answer", "timestamp", "section_description", "retrieval_challenge"
"""

SCORING_PROMPT = """You are evaluating a RAG system's answer against a ground-truth answer.

Question: {question}
Expected answer: {expected}
Generated answer: {generated}
Retrieved chunks: {chunks}

Score on two dimensions (0.0 to 1.0):
1. retrieval_score: Did the retrieved chunks contain the information needed to answer?
2. answer_score: How close is the generated answer to the expected answer in meaning?

Return ONLY JSON: {{"retrieval_score": 0.X, "answer_score": 0.X, "reasoning": "..."}}
"""


def _safe_json_loads(raw: str, context: str = "") -> Optional[Any]:
    """Try to parse JSON from an LLM response that may contain markdown fences.

    Tries four strategies in order:
    1. Direct parse (LLM returned clean JSON)
    2. Extract content inside ```json ... ``` fence
    3. Extract content inside ``` ... ``` fence
    4. Find the first {...} or [...] block via regex

    Returns None if all strategies fail (caller must handle gracefully).
    """
    # Strategy 1 — clean JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2 — ```json fence
    fence_json = re.search(r"```json\s*([\s\S]*?)```", raw)
    if fence_json:
        try:
            return json.loads(fence_json.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3 — generic ``` fence
    fence_generic = re.search(r"```\s*([\s\S]*?)```", raw)
    if fence_generic:
        try:
            return json.loads(fence_generic.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 4 — find first JSON object or array
    brace = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
    if brace:
        try:
            return json.loads(brace.group(1))
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse JSON from LLM output [%s]: %.200s", context, raw)
    return None


class RAGEvaluator:
    """Generate golden QA datasets and evaluate RAG pipeline quality."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store
        self.llm = get_llm()
        self.query_engine = RAGQueryEngine(store)

    # ── QA generation ─────────────────────────────────────────

    def generate_qa_pairs(
        self,
        video_title: str,
        video_url: str,
        chunks: List[Dict],
        n_pairs: int = 2,
    ) -> List[QAPair]:
        """Use LLM to generate golden QA pairs from video chunks."""
        chunks_text = "\n\n".join(
            "[{}] {}".format(c["timestamp"], c["text"]) for c in chunks
        )
        prompt = QA_GENERATION_PROMPT.format(
            n=n_pairs, title=video_title, url=video_url, chunks=chunks_text
        )

        raw = self.llm.generate(prompt, max_tokens=2048)
        # FIX: was json.loads(raw) with no error handling
        pairs_data = _safe_json_loads(raw, context="qa_generation")

        if not isinstance(pairs_data, list):
            logger.error(
                "QA generation for '%s' returned non-list: %r — skipping",
                video_title, pairs_data,
            )
            return []

        result = []
        for p in pairs_data:
            try:
                result.append(
                    QAPair(
                        question=p["question"],
                        answer=p["answer"],
                        source_video=video_title,
                        source_url=video_url,
                        timestamp=p.get("timestamp", ""),
                        section_description=p.get("section_description", ""),
                        retrieval_challenge=p.get("retrieval_challenge", ""),
                    )
                )
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed QA pair: %s — %s", p, exc)

        return result

    def generate_dataset_from_videos(
        self, videos: List[Dict], pairs_per_video: int = 2
    ) -> List[QAPair]:
        """Generate a golden dataset spanning multiple videos."""
        all_pairs: List[QAPair] = []
        for video in videos:
            if not video.get("chunks"):
                logger.warning("No chunks for '%s', skipping", video.get("title", "?"))
                continue
            try:
                pairs = self.generate_qa_pairs(
                    video_title=video["title"],
                    video_url=video["url"],
                    chunks=video["chunks"],
                    n_pairs=pairs_per_video,
                )
                all_pairs.extend(pairs)
                logger.info("Generated %d QA pairs for '%s'", len(pairs), video["title"])
            except Exception as exc:
                logger.error("Failed to generate QA for '%s': %s", video.get("title"), exc)
        return all_pairs

    # ── Evaluation ────────────────────────────────────────────

    def evaluate_pair(self, qa: QAPair) -> Optional[EvalResult]:
        """Run a single QA pair through the pipeline and score it.

        Returns None if scoring fails (instead of raising, so callers can skip).
        """
        response = self.query_engine.ask(qa.question)

        scoring_prompt = SCORING_PROMPT.format(
            question=qa.question,
            expected=qa.answer,
            generated=response.answer,
            chunks="\n---\n".join(
                "[{}: {}] {}".format(s.source_type, s.title, s.timestamp)
                for s in response.sources
            ),
        )

        raw = self.llm.generate(scoring_prompt, max_tokens=256)
        # FIX: was json.loads(raw) with no error handling
        scores = _safe_json_loads(raw, context="scoring")

        if not isinstance(scores, dict):
            logger.warning("Scoring returned non-dict for '%s'", qa.question[:50])
            return None

        return EvalResult(
            question=qa.question,
            expected_answer=qa.answer,
            retrieved_chunks=[
                "[{}: {}]".format(s.source_type, s.title) for s in response.sources
            ],
            generated_answer=response.answer,
            # FIX: explicit float() cast — LLM sometimes returns string numbers
            retrieval_score=float(scores.get("retrieval_score", 0.0)),
            answer_score=float(scores.get("answer_score", 0.0)),
        )

    def evaluate_dataset(self, qa_pairs: List[QAPair]) -> List[EvalResult]:
        """Evaluate all QA pairs; failed pairs are skipped, not fatal."""
        results: List[EvalResult] = []
        for qa in qa_pairs:
            try:
                result = self.evaluate_pair(qa)
                if result is not None:
                    results.append(result)
                    logger.info(
                        "Q: '%s...' → retrieval=%.2f answer=%.2f",
                        qa.question[:50],
                        result.retrieval_score,
                        result.answer_score,
                    )
            except Exception as exc:
                logger.error("Error evaluating '%s': %s", qa.question[:50], exc)
        return results

    @staticmethod
    def summary_stats(results: List[EvalResult]) -> Dict:
        if not results:
            return {"count": 0, "avg_retrieval": 0.0, "avg_answer": 0.0,
                    "min_retrieval": 0.0, "max_retrieval": 0.0}
        return {
            "count": len(results),
            "avg_retrieval": sum(r.retrieval_score for r in results) / len(results),
            "avg_answer": sum(r.answer_score for r in results) / len(results),
            "min_retrieval": min(r.retrieval_score for r in results),
            "max_retrieval": max(r.retrieval_score for r in results),
        }
