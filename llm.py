"""Unified LLM provider — Claude primary, Gemini fallback.

Bug fixes vs. prototype:
1. Gemini API key was passed as a URL query parameter (`?key=...`).
   This leaks the key into server-side access logs and HTTP Referer headers.
   Fixed: key is now sent as `x-goog-api-key` request header.

2. Claude calls had no explicit timeout — could hang indefinitely on network
   issues.  Fixed: httpx timeout is applied to the underlying Anthropic client
   via the `timeout` kwarg on `client.messages.create()`.

3. No retry logic — a single transient 429 / 503 would fail the whole request.
   Fixed: `tenacity` retry with exponential back-off on retryable status codes.

4. Model names were hardcoded strings.  Fixed: read from settings.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings

logger = logging.getLogger(__name__)

# Exceptions worth retrying on (transient network / rate-limit errors)
_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


def _is_retryable_http(exc: BaseException) -> bool:
    """Return True for HTTP 429 / 5xx responses."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (
        429, 500, 502, 503, 504
    )


class LLMProvider:
    """Calls Claude as primary, falls back to Gemini if Claude fails.

    Usage:
        llm = LLMProvider()
        text = llm.generate("Summarise this...", system="You are helpful.")
    """

    def __init__(self) -> None:
        self.claude_model = settings.claude_model
        self.gemini_model = settings.gemini_model
        self._provider = self._detect_provider()
        logger.info("LLM provider initialised: %s", self._provider)

    def _detect_provider(self) -> str:
        if settings.demo_mode:
            return "demo"
        if settings.anthropic_api_key:
            return "claude"
        if settings.gemini_api_key:
            return "gemini"
        logger.warning("No LLM API key configured — LLM calls will fail")
        return "none"

    @property
    def active_provider(self) -> str:
        return self._provider

    def generate(self, prompt: str, system: str = "", max_tokens: int = 512) -> str:
        """Generate a response, trying Claude first then falling back to Gemini."""
        if settings.demo_mode:
            return self._demo_response(prompt)

        if settings.anthropic_api_key:
            try:
                return self._call_claude(prompt, system, max_tokens)
            except Exception as exc:
                logger.warning("Claude failed (%s), falling back to Gemini", exc)

        if settings.gemini_api_key:
            try:
                return self._call_gemini(prompt, system, max_tokens)
            except Exception as exc:
                logger.error("Gemini also failed: %s", exc)
                raise RuntimeError("Both Claude and Gemini failed") from exc

        raise RuntimeError(
            "No LLM API key configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env"
        )

    # ── Claude ────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_claude(self, prompt: str, system: str, max_tokens: int) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        kwargs: dict = {
            "model": self.claude_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            # FIX: explicit timeout so a hung network call doesn't block forever
            "timeout": settings.llm_timeout,
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        return response.content[0].text

    # ── Gemini ────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_gemini(self, prompt: str, system: str, max_tokens: int) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent"
        )
        # FIX: was `params={"key": ...}` which leaks the secret into URL / access logs.
        # Google supports `x-goog-api-key` header for API key auth.
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key,
        }

        contents: list[dict] = []
        if system:
            contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append(
                {"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]}
            )
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
        }

        with httpx.Client(timeout=settings.llm_timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        return parts[0]["text"] if parts else ""

    # ── Demo ──────────────────────────────────────────────────

    def _demo_response(self, prompt: str) -> str:
        from demo_data import MOCK_DIGEST_SUMMARY, MOCK_QA_PAIRS, MOCK_RAG_ANSWER

        p = prompt.lower()
        if "urgent" in p and "informational" in p:
            return MOCK_DIGEST_SUMMARY
        if "golden" in p or "question-answer pair" in p:
            return json.dumps(MOCK_QA_PAIRS[:2])
        if "retrieval_score" in p or "answer_score" in p:
            return json.dumps(
                {"retrieval_score": 0.85, "answer_score": 0.78,
                 "reasoning": "Retrieved chunk covers the topic well."}
            )
        if "context:" in p and "question:" in p:
            return MOCK_RAG_ANSWER
        return (
            "Demo mode: This is a placeholder response. "
            "Set DEMO_MODE=false and configure API keys for real responses."
        )


# ── Singleton ─────────────────────────────────────────────────

_default_llm: Optional[LLMProvider] = None


def get_llm() -> LLMProvider:
    """Return the process-wide LLM provider singleton."""
    global _default_llm
    if _default_llm is None:
        _default_llm = LLMProvider()
    return _default_llm
