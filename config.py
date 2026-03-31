"""Central configuration — loaded from environment variables and validated on startup.

Bug fixes vs. prototype:
- model_validator ensures at least one LLM key is set when demo_mode=False
- All tunable constants (model names, chunk size, history length, timeouts) are
  configurable instead of scattered as magic numbers throughout the codebase.
- cors_origins is now a configurable list (was hardcoded "*" in main.py).
- api_request_timeout controls all outbound HTTP calls (Slack, GitHub, Notion).
"""

from __future__ import annotations

from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Model names — configurable so you can swap without touching code
    claude_model: str = "claude-sonnet-4-6"
    gemini_model: str = "gemini-2.0-flash"

    # ── Embeddings ───────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384   # must match embedding_model output dimension

    # ── Slack ────────────────────────────────────────────────────
    slack_bot_token: str = ""
    slack_channels: str = "general"  # comma-separated channel names

    # ── GitHub ───────────────────────────────────────────────────
    github_token: str = ""
    github_repos: str = ""  # comma-separated, e.g. "org/repo1,org/repo2"

    # ── Notion ───────────────────────────────────────────────────
    notion_token: str = ""
    notion_database_id: str = ""

    # ── App behaviour ────────────────────────────────────────────
    demo_mode: bool = True          # set False when real API keys are configured
    digest_interval_minutes: int = 30
    max_digest_history: int = 48    # was hardcoded 48 in routes/heartbeat.py
    chunk_seconds: int = 120        # was hardcoded 120 in rag/ingest.py

    # ── Storage ──────────────────────────────────────────────────
    chroma_persist_dir: str = "./chroma_db"

    # ── HTTP / timeouts ──────────────────────────────────────────
    api_request_timeout: int = 20   # seconds for Slack / GitHub / Notion calls
    llm_timeout: int = 60           # seconds for LLM API calls

    # ── Security / CORS ──────────────────────────────────────────
    # Comma-separated origins, e.g. "http://localhost:8501,https://myapp.com"
    # Use "*" only in development.
    cors_origins: str = "http://localhost:8501"

    # ── Dashboard ────────────────────────────────────────────────
    api_base_url: str = "http://localhost:8000"  # consumed by dashboard.py

    # ── Logging ──────────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Startup validation ───────────────────────────────────────

    @model_validator(mode="after")
    def _validate_keys(self) -> "Settings":
        """Fail fast at startup if required keys are missing."""
        if not self.demo_mode:
            if not self.anthropic_api_key and not self.gemini_api_key:
                raise ValueError(
                    "DEMO_MODE=false but neither ANTHROPIC_API_KEY nor GEMINI_API_KEY "
                    "is set. Configure at least one LLM provider, or set DEMO_MODE=true."
                )
        return self

    # ── Convenience helpers ──────────────────────────────────────

    @property
    def slack_channel_list(self) -> List[str]:
        return [c.strip() for c in self.slack_channels.split(",") if c.strip()]

    @property
    def github_repo_list(self) -> List[str]:
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


# Singleton — import this everywhere
settings = Settings()
