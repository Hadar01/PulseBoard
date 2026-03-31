# PulseBoard-RAG — Full Repository Contents
# Source: https://github.com/Hadar01/PulseBoard-Rag
# Fetched: 2026-03-31

---

## DIRECTORY / FILE TREE

```
PulseBoard-Rag/
├── .env.example
├── .gitignore
├── Dockerfile
├── INTEGRATION_GUIDE.md
├── Procfile
├── README.md
├── config.py
├── dashboard.py
├── demo_data.py
├── docker-compose.yml
├── llm.py
├── main.py
├── models.py
├── render.yaml
├── requirements.txt
├── scheduler.py
├── docs/
│   └── screenshots/
├── heartbeat/
│   ├── __init__.py
│   ├── classifier.py
│   ├── collector.py
│   └── digest.py
├── integrations/
│   ├── __init__.py
│   ├── github.py
│   ├── notion.py
│   ├── slack.py
│   └── youtube.py
├── rag/
│   ├── __init__.py
│   ├── evaluate.py
│   ├── ingest.py
│   ├── query.py
│   └── store.py
└── routes/
    ├── __init__.py
    ├── heartbeat.py
    ├── query.py
    └── rag.py
```

---

## requirements.txt

```
fastapi>=0.103.0
uvicorn>=0.23.0
anthropic>=0.25.0
faiss-cpu>=1.7.0
sentence-transformers>=2.2.0
python-dotenv>=1.0.0
httpx>=0.25.0
apscheduler>=3.10.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
streamlit>=1.29.0
youtube-transcript-api>=0.6.1
numpy>=1.24.0
```

---

## .env.example

```
# === LLM (set at least one — Claude is primary, Gemini is fallback) ===
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# === Slack Integration ===
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNELS=client-pharma,client-insurance,general

# === GitHub Integration ===
GITHUB_TOKEN=ghp_...
GITHUB_REPOS=livo-ai/pharma-portal,livo-ai/doc-pipeline

# === Notion Integration ===
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=your-database-id-here

# === Optional ===
DIGEST_INTERVAL_MINUTES=30
CHROMA_PERSIST_DIR=./chroma_db
LOG_LEVEL=INFO
```

---

## .gitignore

```
.env
__pycache__/
*.pyc
chroma_db/
*.egg-info/
dist/
.venv/
.claude/
*.pkl
*.faiss
```

---

## Procfile

```
web: python main.py
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps for FAISS
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose ports
EXPOSE 8000 8501

# Default: run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## docker-compose.yml

```yaml
version: "3.9"

services:
  api:
    build: .
    container_name: pulseboard-api
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - faiss_data:/app/chroma_db
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  dashboard:
    build: .
    container_name: pulseboard-dashboard
    command: streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
    ports:
      - "8501:8501"
    env_file:
      - .env
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

  scheduler:
    build: .
    container_name: pulseboard-scheduler
    command: python scheduler.py
    env_file:
      - .env
    volumes:
      - faiss_data:/app/chroma_db
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

volumes:
  faiss_data:
```

---

## render.yaml

```yaml
# Render Blueprint — deploy to render.com
services:
  - type: web
    name: pulseboard-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: SLACK_BOT_TOKEN
        sync: false
      - key: GITHUB_TOKEN
        sync: false
      - key: NOTION_TOKEN
        sync: false
      - key: NOTION_DATABASE_ID
        sync: false
      - key: DEMO_MODE
        value: "true"
      - key: CHROMA_PERSIST_DIR
        value: /tmp/chroma_db
    healthCheckPath: /health
    plan: free
```

---

## config.py

```python
"""Central configuration loaded from environment variables."""

from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- LLM (Claude primary, Gemini fallback) ---
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # --- Slack ---
    slack_bot_token: str = ""
    slack_channels: str = "general"  # comma-separated

    # --- GitHub ---
    github_token: str = ""
    github_repos: str = ""  # comma-separated, e.g. "org/repo1,org/repo2"

    # --- Notion ---
    notion_token: str = ""
    notion_database_id: str = ""

    # --- App ---
    demo_mode: bool = True  # Set to False when real API keys are configured
    digest_interval_minutes: int = 30
    chroma_persist_dir: str = "./chroma_db"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # --- Helpers ---
    @property
    def slack_channel_list(self) -> List[str]:
        return [c.strip() for c in self.slack_channels.split(",") if c.strip()]

    @property
    def github_repo_list(self) -> List[str]:
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]


settings = Settings()
```

---

## models.py

```python
"""Shared Pydantic models used across the application."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel


# ── Event models ──────────────────────────────────────────────


class Urgency(str, Enum):
    URGENT = "urgent"
    INFO = "informational"


class Source(str, Enum):
    SLACK = "slack"
    GITHUB = "github"
    NOTION = "notion"


class Event(BaseModel):
    source: Source
    title: str
    body: str
    url: str = ""
    timestamp: datetime = datetime.now()
    urgency: Urgency = Urgency.INFO
    metadata: Dict = {}


# ── Digest models ─────────────────────────────────────────────


class DigestItem(BaseModel):
    urgency: Urgency
    summary: str
    source: Source
    url: str = ""


class Digest(BaseModel):
    generated_at: datetime
    urgent: List[DigestItem] = []
    informational: List[DigestItem] = []
    natural_language_summary: str = ""


# ── RAG models ────────────────────────────────────────────────


class ChunkMetadata(BaseModel):
    source_type: str  # "slack", "github", "notion", "youtube"
    source_id: str
    title: str
    timestamp: str = ""
    url: str = ""


class QAPair(BaseModel):
    question: str
    answer: str
    source_video: str = ""
    source_url: str = ""
    timestamp: str = ""
    section_description: str = ""
    retrieval_challenge: str = ""


class EvalResult(BaseModel):
    question: str
    expected_answer: str
    retrieved_chunks: List[str]
    generated_answer: str
    retrieval_score: float  # 0-1, how relevant the retrieved chunk was
    answer_score: float  # 0-1, how close generated answer is to expected


class QueryResponse(BaseModel):
    answer: str
    sources: List[ChunkMetadata] = []
    confidence: float = 0.0
```

---

## main.py

```python
"""PulseBoard-RAG — FastAPI application entry point."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the project root is on sys.path so imports work regardless of cwd
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes import heartbeat_router, rag_router, query_router

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PulseBoard-RAG starting up")
    yield
    logger.info("PulseBoard-RAG shutting down")


# ── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="PulseBoard-RAG",
    description=(
        "Intelligent project monitor with RAG-powered knowledge base. "
        "Aggregates Slack, GitHub, and Notion into heartbeat digests, "
        "and supports natural-language queries over project history."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────

app.include_router(heartbeat_router)
app.include_router(rag_router)
app.include_router(query_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pulseboard-rag"}


# ── Run directly ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    os.chdir(_PROJECT_ROOT)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
```

---

## llm.py

```python
"""Unified LLM provider with automatic Claude -> Gemini fallback."""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class LLMProvider:
    """Calls Claude as primary, falls back to Gemini if Claude fails or is unavailable.

    Usage:
        llm = LLMProvider()
        response = llm.generate("Summarize this text...", system="You are a helpful assistant.")
    """

    def __init__(
        self,
        claude_model: str = "claude-sonnet-4-20250514",
        gemini_model: str = "gemini-2.0-flash",
    ):
        self.claude_model = claude_model
        self.gemini_model = gemini_model
        self._provider = self._detect_provider()
        logger.info("LLM provider initialized: %s", self._provider)

    def _detect_provider(self) -> str:
        """Determine which provider to use based on available API keys."""
        if settings.demo_mode:
            return "demo"
        if settings.anthropic_api_key:
            return "claude"
        if settings.gemini_api_key:
            return "gemini"
        logger.warning("No LLM API key configured -- LLM calls will fail")
        return "none"

    @property
    def active_provider(self) -> str:
        return self._provider

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 512,
    ) -> str:
        """Generate a response. Tries Claude first, falls back to Gemini."""
        # Demo mode -- return contextual mock responses
        if settings.demo_mode:
            return self._demo_response(prompt)

        # Try Claude
        if settings.anthropic_api_key:
            try:
                return self._call_claude(prompt, system, max_tokens)
            except Exception as e:
                logger.warning("Claude failed (%s), falling back to Gemini", e)

        # Fallback to Gemini
        if settings.gemini_api_key:
            try:
                return self._call_gemini(prompt, system, max_tokens)
            except Exception as e:
                logger.error("Gemini also failed: %s", e)
                raise RuntimeError("Both Claude and Gemini failed") from e

        raise RuntimeError(
            "No LLM API key configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env"
        )

    def _call_claude(self, prompt: str, system: str, max_tokens: int) -> str:
        """Call Anthropic Claude API."""
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        kwargs = {
            "model": self.claude_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        return response.content[0].text

    def _call_gemini(self, prompt: str, system: str, max_tokens: int) -> str:
        """Call Google Gemini API via REST (no heavy SDK needed)."""
        url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(
            self.gemini_model
        )
        headers = {"Content-Type": "application/json"}
        params = {"key": settings.gemini_api_key}

        # Build Gemini request
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
            },
        }

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=headers, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Extract text from Gemini response
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        return parts[0]["text"] if parts else ""

    def _demo_response(self, prompt: str) -> str:
        """Return realistic mock responses in demo mode."""
        from demo_data import MOCK_DIGEST_SUMMARY, MOCK_QA_PAIRS, MOCK_RAG_ANSWER

        prompt_lower = prompt.lower()

        # Digest summarization
        if "urgent" in prompt_lower and "informational" in prompt_lower:
            return MOCK_DIGEST_SUMMARY

        # QA pair generation
        if "golden" in prompt_lower or "question-answer pair" in prompt_lower:
            return json.dumps(MOCK_QA_PAIRS[:2])

        # RAG evaluation scoring
        if "retrieval_score" in prompt_lower or "answer_score" in prompt_lower:
            return json.dumps({"retrieval_score": 0.85, "answer_score": 0.78,
                               "reasoning": "Retrieved chunk covers the topic well."})

        # Default: RAG question answering
        if "context:" in prompt_lower and "question:" in prompt_lower:
            return MOCK_RAG_ANSWER

        return "Demo mode: This is a placeholder response. Set DEMO_MODE=false and configure API keys for real LLM responses."


# Singleton instance
_default_llm = None  # type: Optional[LLMProvider]


def get_llm() -> LLMProvider:
    """Get or create the default LLM provider singleton."""
    global _default_llm
    if _default_llm is None:
        _default_llm = LLMProvider()
    return _default_llm
```

---

## scheduler.py

```python
"""APScheduler-based heartbeat scheduler — runs every 30 minutes."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from routes.heartbeat import run_heartbeat_cycle

logger = logging.getLogger(__name__)


async def heartbeat_job():
    """Scheduled job: run the full heartbeat pipeline."""
    try:
        digest = await run_heartbeat_cycle()
        urgent_count = len(digest.urgent)
        info_count = len(digest.informational)
        logger.info(
            "Heartbeat complete — %d urgent, %d informational",
            urgent_count,
            info_count,
        )
    except Exception as e:
        logger.error("Heartbeat job failed: %s", e)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the heartbeat scheduler."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        heartbeat_job,
        "interval",
        minutes=settings.digest_interval_minutes,
        id="heartbeat",
        name="Heartbeat Digest",
        replace_existing=True,
    )
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    )
    logger.info(
        "Starting heartbeat scheduler (every %d min)",
        settings.digest_interval_minutes,
    )

    scheduler = create_scheduler()
    scheduler.start()

    # Run initial heartbeat immediately
    loop = asyncio.new_event_loop()
    loop.run_until_complete(heartbeat_job())

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")
```

---

## dashboard.py

```python
"""PulseBoard-RAG  Streamlit Dashboard."""

from __future__ import annotations

import json
from typing import Any, Optional, Union

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="PulseBoard-RAG", layout="wide")


# -- Helpers -------------------------------------------------------------------


def api(method, path, **kwargs):
    # type: (str, str, Any) -> Optional[Union[dict, list]]
    """Call the FastAPI backend."""
    try:
        resp = getattr(httpx, method)("{}{}".format(API_BASE, path), timeout=120, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        st.error("Backend not running. Start with: `uvicorn main:app --app-dir pulseboard-rag`")
        return None
    except Exception as e:
        st.error("API error: {}".format(e))
        return None


# -- Sidebar -------------------------------------------------------------------

st.sidebar.title("PulseBoard-RAG")
st.sidebar.caption("Intelligent project monitor + RAG evaluation")
page = st.sidebar.radio(
    "Navigate",
    ["Heartbeat Digest", "Ask a Question", "RAG Evaluation", "Ingest Videos"],
)

# -- Page: Heartbeat Digest ----------------------------------------------------

if page == "Heartbeat Digest":
    st.header("Heartbeat Digest")
    st.caption("Real-time project status for non-technical stakeholders")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Trigger Heartbeat Now", type="primary"):
            with st.spinner("Collecting events from Slack, GitHub, Notion..."):
                data = api("post", "/heartbeat/trigger")
            if data:
                st.success("Heartbeat complete!")

    # Show latest digest
    data = api("get", "/heartbeat/latest")
    if data:
        st.subheader("Latest Digest")
        st.caption("Generated at: {}".format(data.get("generated_at", "N/A")))

        # Natural language summary
        summary = data.get("natural_language_summary", "")
        if summary:
            st.info(summary)

        # Urgent items
        urgent = data.get("urgent", [])
        if urgent:
            st.error("**{} Urgent Items**".format(len(urgent)))
            for item in urgent:
                with st.container():
                    link = " [link]({})".format(item["url"]) if item.get("url") else ""
                    st.markdown("- **[{}]** {}{}".format(item["source"], item["summary"], link))
        else:
            st.success("No urgent items")

        # Informational items
        info = data.get("informational", [])
        if info:
            with st.expander("Informational ({} items)".format(len(info)), expanded=False):
                for item in info:
                    link = " [link]({})".format(item["url"]) if item.get("url") else ""
                    st.markdown("- **[{}]** {}{}".format(item["source"], item["summary"], link))
    else:
        st.info("No digest yet. Click 'Trigger Heartbeat Now' to generate one.")

    # History
    history = api("get", "/heartbeat/history")
    if history and len(history) > 1:
        with st.expander("Digest History ({} entries)".format(len(history))):
            for i, d in enumerate(reversed(history)):
                u = len(d.get("urgent", []))
                inf = len(d.get("informational", []))
                st.markdown("**{}** - {} urgent, {} info".format(d["generated_at"], u, inf))

# -- Page: Ask a Question ------------------------------------------------------

elif page == "Ask a Question":
    st.header("Ask a Question")
    st.caption("Query the knowledge base using natural language")

    question = st.text_input("Your question:", placeholder="What's the status of the pharma portal?")
    source_filter = st.selectbox(
        "Filter by source (optional):",
        [None, "slack", "github", "notion", "youtube"],
        format_func=lambda x: "All sources" if x is None else x.capitalize(),
    )

    if st.button("Ask", type="primary") and question:
        with st.spinner("Searching knowledge base..."):
            data = api(
                "post",
                "/query/ask",
                json={
                    "question": question,
                    "source_filter": source_filter,
                    "n_results": 5,
                },
            )
        if data:
            st.subheader("Answer")
            st.write(data["answer"])

            confidence = data.get("confidence", 0)
            st.progress(confidence, text="Confidence: {:.0%}".format(confidence))

            sources = data.get("sources", [])
            if sources:
                with st.expander("Sources ({})".format(len(sources))):
                    for s in sources:
                        link = " | [link]({})".format(s["url"]) if s.get("url") else ""
                        st.markdown("- **{}** | {} | {}{}".format(
                            s["source_type"], s["title"], s["timestamp"], link
                        ))

# -- Page: RAG Evaluation ------------------------------------------------------

elif page == "RAG Evaluation":
    st.header("RAG Evaluation")
    st.caption("Generate golden QA datasets and benchmark retrieval quality")

    tab1, tab2 = st.tabs(["Generate Dataset", "Run Evaluation"])

    with tab1:
        pairs_per_video = st.slider("QA pairs per video:", 1, 5, 2)
        if st.button("Generate Golden Dataset", type="primary"):
            with st.spinner("Generating QA pairs from video transcripts (this takes ~1 min)..."):
                data = api(
                    "post",
                    "/rag/generate-dataset",
                    params={"pairs_per_video": pairs_per_video},
                )
            if data:
                st.success("Generated {} QA pairs!".format(len(data)))
                st.session_state["qa_pairs"] = data

                for i, qa in enumerate(data, 1):
                    with st.expander("Q{}: {}...".format(i, qa["question"][:80])):
                        st.markdown("**Answer:** {}".format(qa["answer"]))
                        st.markdown("**Source:** {} @ {}".format(qa["source_video"], qa["timestamp"]))
                        st.markdown("**Section:** {}".format(qa["section_description"]))
                        st.markdown("**Retrieval Challenge:** {}".format(qa["retrieval_challenge"]))

                # Download as JSON
                st.download_button(
                    "Download Dataset (JSON)",
                    data=json.dumps(data, indent=2),
                    file_name="golden_dataset.json",
                    mime="application/json",
                )

    with tab2:
        if "qa_pairs" not in st.session_state:
            st.warning("Generate a dataset first (use the tab above).")
        else:
            st.info("Ready to evaluate {} QA pairs".format(len(st.session_state["qa_pairs"])))
            if st.button("Run Evaluation", type="primary"):
                with st.spinner("Evaluating RAG pipeline..."):
                    data = api(
                        "post",
                        "/rag/evaluate",
                        json=st.session_state["qa_pairs"],
                    )
                if data:
                    st.subheader("Results")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Avg Retrieval Score", "{:.2f}".format(data["avg_retrieval"]))
                    col2.metric("Avg Answer Score", "{:.2f}".format(data["avg_answer"]))
                    col3.metric("Questions Evaluated", data["count"])

                    for r in data.get("results", []):
                        with st.expander("Q: {}...".format(r["question"][:60])):
                            st.markdown("**Expected:** {}".format(r["expected_answer"]))
                            st.markdown("**Generated:** {}".format(r["generated_answer"]))
                            st.markdown("**Retrieval Score:** {:.2f}".format(r["retrieval_score"]))
                            st.markdown("**Answer Score:** {:.2f}".format(r["answer_score"]))

# -- Page: Ingest Videos -------------------------------------------------------

elif page == "Ingest Videos":
    st.header("Ingest Video Transcripts")
    st.caption("Pull YouTube transcripts into the RAG knowledge base")

    st.subheader("Default Video Set")
    st.markdown("""
    1. 3Blue1Brown - *But what is a Neural Network?*
    2. 3Blue1Brown - *Transformers, the tech behind LLMs*
    3. CampusX - *What is Deep Learning?* (Hindi)
    4. CodeWithHarry - *All About ML & Deep Learning* (Hindi)
    """)

    if st.button("Ingest All Default Videos", type="primary"):
        with st.spinner("Fetching transcripts and building embeddings..."):
            data = api("post", "/rag/ingest")
        if data:
            st.success(
                "Ingested {} chunks from {} videos!".format(
                    data["total_chunks"], data["videos_processed"]
                )
            )

    st.divider()

    st.subheader("Add Custom Video")
    custom_url = st.text_input("YouTube URL:")
    custom_title = st.text_input("Video Title:")
    custom_lang = st.text_input("Languages (comma-separated):", value="en")

    if st.button("Ingest Custom Video") and custom_url and custom_title:
        langs = [lang.strip() for lang in custom_lang.split(",")]
        with st.spinner("Processing..."):
            data = api(
                "post",
                "/rag/ingest",
                json=[{"url": custom_url, "title": custom_title, "languages": langs}],
            )
        if data:
            st.success("Ingested {} chunks!".format(data["total_chunks"]))

    st.divider()
    stats = api("get", "/rag/stats")
    if stats:
        st.metric("Total Documents in Vector Store", stats["total_documents"])
```

---

## demo_data.py

```python
"""Demo/mock data for testing PulseBoard-RAG without real API keys.

When DEMO_MODE=true in .env, the system uses this data instead of
calling Slack, GitHub, Notion, or LLM APIs.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from models import Event, Source, Urgency

# ---------------------------------------------------------------------------
# Mock Events (simulating a real Livo AI workday)
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def _ago(minutes):
    # type: (int) -> datetime
    return _NOW - timedelta(minutes=minutes)


MOCK_SLACK_EVENTS = [
    Event(
        source=Source.SLACK,
        title="Client message in #client-pharma",
        body="Hey team, the invoice PDF parser is giving wrong totals for March invoices. Can someone look at this today? Our CA team is waiting.",
        url="https://livoai.slack.com/archives/C05PHARMA/p1711400000",
        timestamp=_ago(45),
        metadata={"user": "Ritu (PharmaCorp)", "channel": "client-pharma"},
    ),
    Event(
        source=Source.SLACK,
        title="Team discussion in #engineering",
        body="Pushed the new chunking strategy for the doc pipeline. Embeddings are 15% more accurate on the insurance test set now.",
        url="https://livoai.slack.com/archives/C05ENG/p1711401000",
        timestamp=_ago(20),
        metadata={"user": "Arjun", "channel": "engineering"},
    ),
    Event(
        source=Source.SLACK,
        title="Client message in #client-insurance",
        body="The search results on the portal are much better this week. Good work! One thing though -- can we add a date filter?",
        url="https://livoai.slack.com/archives/C05INS/p1711402000",
        timestamp=_ago(10),
        metadata={"user": "Meena (InsureCo)", "channel": "client-insurance"},
    ),
    Event(
        source=Source.SLACK,
        title="Message in #general",
        body="Reminder: Friday standup moved to 3pm this week. Also, we're ordering lunch for the offsite planning session.",
        url="https://livoai.slack.com/archives/C05GEN/p1711403000",
        timestamp=_ago(5),
        metadata={"user": "Priya", "channel": "general"},
    ),
]

MOCK_GITHUB_EVENTS = [
    Event(
        source=Source.GITHUB,
        title="PR merged: Fix PDF table extraction for multi-page invoices",
        body="Resolved edge case where tables spanning multiple pages were split incorrectly. Added 12 test cases covering CA firm invoice formats.",
        url="https://github.com/livo-ai/doc-pipeline/pull/247",
        timestamp=_ago(35),
        metadata={"repo": "livo-ai/doc-pipeline", "state": "merged", "user": "arjun-dev"},
    ),
    Event(
        source=Source.GITHUB,
        title="CI Failed: pharma-portal main branch",
        body="Test suite failed on main branch after dependency update. 3 tests failing in the search module. Error: FAISS index dimension mismatch after model update.",
        url="https://github.com/livo-ai/pharma-portal/actions/runs/12345",
        timestamp=_ago(15),
        metadata={"repo": "livo-ai/pharma-portal", "workflow": "CI/CD Pipeline"},
    ),
    Event(
        source=Source.GITHUB,
        title="PR opened: Add date filter to insurance search portal",
        body="Implements the date range filter requested by InsureCo. Uses Elasticsearch date_range query. Ready for review.",
        url="https://github.com/livo-ai/insurance-portal/pull/89",
        timestamp=_ago(25),
        metadata={"repo": "livo-ai/insurance-portal", "state": "open", "user": "neha-dev"},
    ),
]

MOCK_NOTION_EVENTS = [
    Event(
        source=Source.NOTION,
        title="Task BLOCKED: Pharma Portal - SSO Integration",
        body="Waiting on PharmaCorp IT team to provide SAML metadata. Sent follow-up email 2 days ago, no response. This blocks the March 28 demo.",
        url="https://notion.so/livo/task-sso-integration",
        timestamp=_ago(60),
        metadata={"status": "blocked", "assignee": "Arjun", "due_date": "2026-03-28"},
    ),
    Event(
        source=Source.NOTION,
        title="Task completed: Insurance Portal - Search Relevance v2",
        body="Deployed new embedding model and reindexed all documents. Client confirmed the results are much better now.",
        url="https://notion.so/livo/task-search-v2",
        timestamp=_ago(40),
        metadata={"status": "done", "assignee": "Neha", "due_date": "2026-03-25"},
    ),
    Event(
        source=Source.NOTION,
        title="Task in-progress: Nonprofit Dashboard - Donor Report Generator",
        body="Building the PDF report template. 60% complete, on track for Friday delivery.",
        url="https://notion.so/livo/task-donor-reports",
        timestamp=_ago(30),
        metadata={"status": "in_progress", "assignee": "Vikram", "due_date": "2026-03-28"},
    ),
    Event(
        source=Source.NOTION,
        title="Task OVERDUE: CA Firm - Monthly Reconciliation Automation",
        body="Was due March 24. Delayed because the bank statement format changed. Need 2 more days.",
        url="https://notion.so/livo/task-reconciliation",
        timestamp=_ago(120),
        metadata={"status": "in_progress", "assignee": "Arjun", "due_date": "2026-03-24"},
    ),
]


def get_all_mock_events() -> List[Event]:
    """Return all mock events combined and sorted by timestamp."""
    all_events = MOCK_SLACK_EVENTS + MOCK_GITHUB_EVENTS + MOCK_NOTION_EVENTS
    return sorted(all_events, key=lambda e: e.timestamp, reverse=True)


# ---------------------------------------------------------------------------
# Mock LLM Responses (so we don't need any API key)
# ---------------------------------------------------------------------------

MOCK_DIGEST_SUMMARY = """URGENT:
- PharmaCorp client reported invoice PDF parser errors -- CA team is waiting. Needs same-day fix.
- CI pipeline broken on pharma-portal main branch (FAISS dimension mismatch after model update).
- SSO integration for Pharma Portal is BLOCKED -- waiting on client IT team since 2 days. This blocks the March 28 demo.
- CA firm reconciliation task is OVERDUE (was due March 24). Arjun needs 2 more days.

INFORMATIONAL:
- InsureCo is happy with search improvements, requested a date filter (PR already open).
- Doc pipeline PR merged -- PDF table extraction fix with 12 new tests.
- Nonprofit donor report generator is 60% done, on track for Friday.
- Friday standup moved to 3pm.

SUMMARY: Four items need your attention today -- a client-reported bug, a broken CI pipeline, a blocked task threatening the March 28 demo, and an overdue deliverable. Everything else is on track."""


MOCK_RAG_ANSWER = """Based on the project data, the pharma portal has a CI pipeline failure on the main branch caused by a FAISS index dimension mismatch after a model update. Additionally, the SSO integration task is blocked waiting on PharmaCorp's IT team to provide SAML metadata, which threatens the March 28 demo. The invoice PDF parser bug reported by the client is being prioritized for a same-day fix."""


# ---------------------------------------------------------------------------
# Mock YouTube Transcript Chunks (from the 4 assessment videos)
# ---------------------------------------------------------------------------

MOCK_VIDEO_CHUNKS = {
    "aircAruvnKk": {
        "title": "But what is a Neural Network?",
        "url": "https://youtube.com/watch?v=aircAruvnKk",
        "chunks": [
            {"timestamp": "00:00", "text": "The brain is made up of neurons, and what we want to do is build a computational analog. A neural network in the machine learning sense is really just a function, it takes in some input, say an image, and spits out some output, like a label. The network is organized into layers. The first layer holds the raw input pixels, and the last layer holds the output."},
            {"timestamp": "01:30", "text": "Between the input and output layers, there are hidden layers. Each neuron in a hidden layer holds a number, called its activation, between 0 and 1. The activation of a neuron in the second layer is determined by a weighted sum of all the activations in the first layer. You add a bias, then wrap it in a sigmoid function to squish the result between 0 and 1."},
            {"timestamp": "04:12", "text": "Why layers? The hope is that the first layer picks up on edges, the second on patterns and textures, the third on larger structures. This hierarchical feature detection is the core idea: each layer builds on the abstractions of the previous one. A 28x28 pixel image of a digit has 784 input neurons and 10 output neurons, one per digit."},
            {"timestamp": "07:45", "text": "The weights and biases are the parameters of the network -- there are about 13,000 of them for this small network. Learning means finding the right set of weights and biases so the network correctly classifies digits. We use a cost function that measures how wrong the network is, and gradient descent to minimize that cost."},
            {"timestamp": "11:20", "text": "ReLU, the rectified linear unit, has largely replaced the sigmoid in modern networks. Instead of squishing everything between 0 and 1, ReLU just outputs max(0, x). It's much easier to train because the gradient doesn't vanish for large values the way sigmoid's does."},
            {"timestamp": "14:00", "text": "The total number of parameters can be huge. A network with 784 inputs, two hidden layers of 16 neurons each, and 10 outputs has about 13,000 weights and biases. Each is a knob you can tune. The learning process is really just finding the setting for all these knobs that makes the cost function as small as possible."},
        ],
    },
    "wjZofJX0v4M": {
        "title": "Transformers, the tech behind LLMs",
        "url": "https://youtube.com/watch?v=wjZofJX0v4M",
        "chunks": [
            {"timestamp": "00:00", "text": "A transformer is the neural network architecture behind all large language models. It was introduced in the 2017 paper Attention Is All You Need. The key insight is the attention mechanism, which lets the model look at all parts of the input simultaneously rather than processing it sequentially like RNNs."},
            {"timestamp": "03:20", "text": "The attention mechanism works by computing three vectors for each token: a Query, a Key, and a Value. The query asks what am I looking for, the key says what do I contain, and the value is the actual information passed along. Attention scores are computed by the dot product of queries and keys, scaled by the square root of the dimension."},
            {"timestamp": "07:00", "text": "Multi-head attention runs several attention operations in parallel. Each head can focus on a different type of relationship -- one might track syntactic structure while another tracks semantic meaning. The outputs are concatenated and linearly projected. This gives the model much richer representations than single-head attention."},
            {"timestamp": "10:45", "text": "Positional encoding is necessary because the transformer has no built-in notion of word order. The original paper used sine and cosine functions of different frequencies. Without positional encoding, the sentence 'dog bites man' would look identical to 'man bites dog' to the model."},
            {"timestamp": "14:30", "text": "The feed-forward network in each transformer block is actually where most of the parameters live -- roughly two-thirds of the model's total parameters. It processes each token independently and can be thought of as a lookup table that stores factual knowledge learned during training."},
            {"timestamp": "18:00", "text": "Temperature in language model sampling controls randomness. A temperature of 0 always picks the most likely next token (greedy decoding). Higher temperatures flatten the probability distribution, making rare tokens more likely. This is why creative writing tasks use higher temperature than factual QA."},
        ],
    },
    "fHF22Wxuyw4": {
        "title": "What is Deep Learning?",
        "url": "https://youtube.com/watch?v=fHF22Wxuyw4",
        "chunks": [
            {"timestamp": "00:00", "text": "Deep learning is a subset of machine learning where we use neural networks with many layers. The word deep refers to the number of layers in the network, not the depth of understanding. Traditional ML uses hand-crafted features -- you manually decide what features to extract. Deep learning automatically learns the features from raw data."},
            {"timestamp": "05:30", "text": "The key difference between machine learning and deep learning is feature engineering. In traditional ML you might manually extract edges, corners, textures from an image and feed those features to a classifier. In deep learning, the network learns these features itself through backpropagation. This is why deep learning excels at unstructured data like images, audio, and text."},
            {"timestamp": "10:00", "text": "Deep learning became practical because of three things: large datasets from the internet, GPU computing power, and algorithmic improvements like batch normalization, dropout, and better activation functions. Before GPUs, training a network with millions of parameters would take months. Now it takes hours."},
            {"timestamp": "15:30", "text": "Convolutional neural networks use a special operation called convolution that slides a small filter across the image. This is much more efficient than connecting every pixel to every neuron. A 3x3 filter has only 9 parameters but can detect edges anywhere in the image. This parameter sharing is why CNNs work so well for images."},
            {"timestamp": "20:00", "text": "Overfitting happens when your model memorizes the training data instead of learning general patterns. The training accuracy is high but test accuracy is low. Dropout is a regularization technique where you randomly turn off neurons during training, forcing the network to not rely on any single neuron. It's like training an ensemble of smaller networks."},
        ],
    },
    "C6YtPJxNULA": {
        "title": "All About ML & Deep Learning",
        "url": "https://youtube.com/watch?v=C6YtPJxNULA",
        "chunks": [
            {"timestamp": "00:00", "text": "Machine learning is basically teaching computers to learn from data without being explicitly programmed. There are three main types: supervised learning where you have labeled data, unsupervised learning where you find patterns without labels, and reinforcement learning where an agent learns by trial and error with rewards and penalties."},
            {"timestamp": "06:00", "text": "The bias-variance tradeoff is fundamental to ML. A model with high bias is too simple -- it underfits and misses patterns. A model with high variance is too complex -- it overfits and memorizes noise. The sweet spot is finding a model complex enough to capture real patterns but simple enough to generalize to new data."},
            {"timestamp": "12:00", "text": "Transfer learning is one of the most important practical techniques in deep learning. Instead of training a model from scratch, you take a model pre-trained on a large dataset like ImageNet and fine-tune it on your specific task. The early layers already know how to detect edges and textures. You only need to retrain the last few layers for your specific problem."},
            {"timestamp": "18:00", "text": "Batch normalization normalizes the activations in each layer so they have zero mean and unit variance. This makes training much faster and more stable because each layer doesn't have to constantly adapt to shifting input distributions. It also acts as a slight regularizer. Without batch norm, training deep networks was extremely difficult."},
            {"timestamp": "24:00", "text": "The vanishing gradient problem occurs in very deep networks when gradients become extremely small as they backpropagate through many layers. The sigmoid activation is particularly bad because its gradient is at most 0.25. This means after 10 layers, the gradient is multiplied by 0.25 ten times, becoming negligibly small. ReLU and residual connections solve this."},
        ],
    },
}


def get_mock_video_chunks() -> List[Dict]:
    """Return mock video data in the same format as YouTubeTranscriptFetcher."""
    result = []
    for vid_id, data in MOCK_VIDEO_CHUNKS.items():
        result.append({
            "title": data["title"],
            "url": data["url"],
            "video_id": vid_id,
            "chunks": data["chunks"],
        })
    return result


# ---------------------------------------------------------------------------
# Mock QA Pairs (golden dataset)
# ---------------------------------------------------------------------------

MOCK_QA_PAIRS = [
    {
        "question": "Why did ReLU replace sigmoid as the dominant activation function in modern neural networks?",
        "answer": "ReLU replaced sigmoid because it solves the vanishing gradient problem. Sigmoid's maximum gradient is 0.25, so after many layers the gradient becomes negligibly small. ReLU outputs max(0, x), so its gradient is either 0 or 1, which allows gradients to flow through deep networks without shrinking.",
        "source_video": "But what is a Neural Network?",
        "source_url": "https://youtube.com/watch?v=aircAruvnKk",
        "timestamp": "11:20",
        "section_description": "ReLU activation replacing sigmoid",
        "retrieval_challenge": "A chunk about the sigmoid function being used to squish weighted sums (01:30) is lexically similar but describes sigmoid's role, not why it was replaced.",
    },
    {
        "question": "In a transformer, what role does the feed-forward network play compared to the attention mechanism?",
        "answer": "The feed-forward network in each transformer block is where most parameters live -- roughly two-thirds of the total. While the attention mechanism handles relationships between tokens, the feed-forward network processes each token independently and acts as a lookup table storing factual knowledge learned during training.",
        "source_video": "Transformers, the tech behind LLMs",
        "source_url": "https://youtube.com/watch?v=wjZofJX0v4M",
        "timestamp": "14:30",
        "section_description": "Feed-forward network role in transformers",
        "retrieval_challenge": "The multi-head attention chunk (07:00) discusses transformer components but focuses on attention heads, not the feed-forward network's knowledge storage role.",
    },
    {
        "question": "How does deep learning's approach to feature extraction differ from traditional machine learning?",
        "answer": "In traditional ML, engineers manually design and extract features like edges, corners, and textures from raw data before feeding them to a classifier. Deep learning eliminates this step entirely -- the network automatically learns hierarchical features from raw data through backpropagation. This is why deep learning excels at unstructured data like images, audio, and text.",
        "source_video": "What is Deep Learning?",
        "source_url": "https://youtube.com/watch?v=fHF22Wxuyw4",
        "timestamp": "05:30",
        "section_description": "Feature engineering: ML vs deep learning",
        "retrieval_challenge": "The chunk about three factors enabling deep learning (10:00) mentions related concepts like GPUs and datasets but doesn't explain the feature extraction difference.",
    },
    {
        "question": "Why is positional encoding necessary in the transformer architecture?",
        "answer": "Transformers have no built-in notion of word order because attention operates on all tokens simultaneously. Without positional encoding, 'dog bites man' and 'man bites dog' would look identical to the model. The original paper used sine and cosine functions of different frequencies to inject position information into token representations.",
        "source_video": "Transformers, the tech behind LLMs",
        "source_url": "https://youtube.com/watch?v=wjZofJX0v4M",
        "timestamp": "10:45",
        "section_description": "Positional encoding for word order",
        "retrieval_challenge": "The Query-Key-Value attention chunk (03:20) discusses how tokens interact but doesn't address the ordering problem that positional encoding solves.",
    },
    {
        "question": "What is the vanishing gradient problem and which specific property of sigmoid makes it worse?",
        "answer": "The vanishing gradient problem occurs when gradients become extremely small as they backpropagate through many layers. Sigmoid is particularly bad because its maximum gradient is only 0.25. After 10 layers, the gradient is multiplied by 0.25 ten times, becoming negligibly small. ReLU and residual connections were introduced to solve this.",
        "source_video": "All About ML & Deep Learning",
        "source_url": "https://youtube.com/watch?v=C6YtPJxNULA",
        "timestamp": "24:00",
        "section_description": "Vanishing gradient and sigmoid's role",
        "retrieval_challenge": "The batch normalization chunk (18:00) also discusses training stability but addresses a different problem -- internal covariate shift, not vanishing gradients.",
    },
]
```

---

## heartbeat/__init__.py

```python
from .collector import EventCollector
from .classifier import classify_events
from .digest import DigestGenerator

__all__ = ["EventCollector", "classify_events", "DigestGenerator"]
```

---

## heartbeat/collector.py

```python
"""Collect events from all integrated sources."""

from __future__ import annotations

import asyncio
import logging
from typing import List

from config import settings
from models import Event

logger = logging.getLogger(__name__)


class EventCollector:
    """Aggregates events from Slack, GitHub, and Notion."""

    def __init__(self):
        if not settings.demo_mode:
            from integrations.slack import SlackClient
            from integrations.github import GitHubClient
            from integrations.notion import NotionClient
            self.slack = SlackClient()
            self.github = GitHubClient()
            self.notion = NotionClient()

    async def collect_all(self, minutes=30):
        # type: (int) -> List[Event]
        """Fetch events from all sources concurrently."""
        if settings.demo_mode:
            return self._collect_demo()

        results = await asyncio.gather(
            self._safe(self.slack.fetch_all_channels, minutes),
            self._safe(self.github.fetch_all_repos, minutes),
            self._safe(self.notion.fetch_blocked_and_overdue),
            return_exceptions=True,
        )

        all_events = []  # type: List[Event]
        source_names = ["Slack", "GitHub", "Notion"]
        for name, result in zip(source_names, results):
            if isinstance(result, Exception):
                logger.error("Failed to collect from %s: %s", name, result)
            elif isinstance(result, list):
                all_events.extend(result)
                logger.info("Collected %d events from %s", len(result), name)

        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        return all_events

    @staticmethod
    def _collect_demo():
        # type: () -> List[Event]
        """Return realistic mock events for demo mode."""
        from demo_data import get_all_mock_events
        events = get_all_mock_events()
        logger.info("DEMO MODE: Loaded %d mock events", len(events))
        return events

    @staticmethod
    async def _safe(coro_func, *args):
        """Call an async function, catching errors gracefully."""
        try:
            return await coro_func(*args)
        except Exception as e:
            logger.error("Collection error: %s", e)
            return []
```

---

## heartbeat/classifier.py

```python
"""Rule-based urgency classifier for events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from models import Event, Source, Urgency

# Keywords that signal urgency in message bodies
URGENT_KEYWORDS = {
    "urgent", "asap", "blocker", "blocked", "down", "outage",
    "broken", "critical", "hotfix", "p0", "incident", "deadline",
    "failed", "failure", "error", "crash",
}


def classify_events(events):
    # type: (List[Event]) -> List[Event]
    """Apply urgency classification to a list of events.

    Rules (any match -> urgent):
    1. CI failure on GitHub
    2. Notion task is blocked or overdue
    3. Slack message contains urgent keywords
    4. Slack message is unanswered for >1 hour in a client channel
    """
    now = datetime.now(timezone.utc)

    for event in events:
        if _is_urgent(event, now):
            event.urgency = Urgency.URGENT
        else:
            event.urgency = Urgency.INFO

    return events


def _is_urgent(event, now):
    # type: (Event, datetime) -> bool
    """Determine if a single event is urgent."""

    # Rule 1: GitHub CI failures are always urgent
    if event.source == Source.GITHUB and "CI Failed" in event.title:
        return True

    # Rule 2: Notion blocked / overdue tasks
    if event.source == Source.NOTION:
        status = event.metadata.get("status", "").lower()
        if "block" in status:
            return True
        due = event.metadata.get("due_date", event.metadata.get("due", ""))
        if due:
            try:
                if datetime.fromisoformat(str(due)).date() < now.date():
                    return True
            except ValueError:
                pass

    # Rule 3: Urgent keywords in any message body
    body_lower = event.body.lower()
    if any(kw in body_lower for kw in URGENT_KEYWORDS):
        return True

    # Rule 4: Slack message older than 1 hour in client channel (unanswered)
    if event.source == Source.SLACK:
        channel = event.metadata.get("channel", "")
        is_client_channel = channel.startswith("client-")
        ts = event.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = now - ts
        if is_client_channel and age > timedelta(hours=1):
            return True

    return False
```

---

## heartbeat/digest.py

```python
"""Generate human-readable digests using Claude/Gemini."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from config import settings
from llm import get_llm
from models import Digest, DigestItem, Event, Urgency

logger = logging.getLogger(__name__)

DIGEST_PROMPT = """You are a project assistant for a non-technical founder at an AI company.
She manages client relationships, BD, and delivery -- she does NOT read code or logs.

Summarize these events into a SHORT digest (max 5 bullet points).
Group into URGENT (needs her attention now) and INFORMATIONAL (awareness only).
Use plain English -- no technical jargon, no code references, no PR numbers.
If something is blocked or overdue, say whose attention it needs.

Events:
{events}

Format your response as:
URGENT:
- ...

INFORMATIONAL:
- ...

SUMMARY: (one sentence overall status)
"""


class DigestGenerator:
    """Turns classified events into a concise natural-language digest."""

    def generate(self, events: List[Event]) -> Digest:
        """Create a structured digest from classified events."""
        if not events:
            return Digest(
                generated_at=datetime.now(timezone.utc),
                natural_language_summary="No new activity in the last 30 minutes.",
            )

        urgent = [e for e in events if e.urgency == Urgency.URGENT]
        info = [e for e in events if e.urgency == Urgency.INFO]

        digest = Digest(
            generated_at=datetime.now(timezone.utc),
            urgent=[
                DigestItem(
                    urgency=Urgency.URGENT,
                    summary="{}: {}".format(e.title, e.body[:120]),
                    source=e.source,
                    url=e.url,
                )
                for e in urgent
            ],
            informational=[
                DigestItem(
                    urgency=Urgency.INFO,
                    summary="{}: {}".format(e.title, e.body[:120]),
                    source=e.source,
                    url=e.url,
                )
                for e in info
            ],
        )

        digest.natural_language_summary = self._summarize_with_llm(events)
        return digest

    def _summarize_with_llm(self, events: List[Event]) -> str:
        """Use Claude/Gemini to produce a plain-English summary."""
        events_text = "\n".join(
            "[{urgency}] [{source}] {title}: {body}".format(
                urgency=e.urgency.value.upper(),
                source=e.source.value,
                title=e.title,
                body=e.body[:200],
            )
            for e in events
        )
        prompt = DIGEST_PROMPT.format(events=events_text)

        try:
            llm = get_llm()
            return llm.generate(prompt, max_tokens=512)
        except Exception as e:
            logger.error("LLM summarization failed: %s", e)
            urgent_count = sum(1 for ev in events if ev.urgency == Urgency.URGENT)
            return "{} events collected. {} need your attention.".format(
                len(events), urgent_count
            )
```

---

## integrations/__init__.py

```python
from .slack import SlackClient
from .github import GitHubClient
from .notion import NotionClient
from .youtube import YouTubeTranscriptFetcher

__all__ = ["SlackClient", "GitHubClient", "NotionClient", "YouTubeTranscriptFetcher"]
```

---

## integrations/slack.py

```python
"""Slack integration — fetches recent messages from configured channels."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from config import settings
from models import Event, Source

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


class SlackClient:
    """Thin async wrapper around Slack Web API."""

    def __init__(self, token: str | None = None):
        self.token = token or settings.slack_bot_token
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SLACK_API}/{endpoint}",
                headers=self.headers,
                params=params or {},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                logger.error("Slack API error on %s: %s", endpoint, data.get("error"))
            return data

    async def get_channel_id(self, channel_name: str) -> str | None:
        """Resolve a channel name to its ID."""
        data = await self._get("conversations.list", {"types": "public_channel,private_channel", "limit": 200})
        for ch in data.get("channels", []):
            if ch["name"] == channel_name:
                return ch["id"]
        return None

    async def fetch_recent_messages(
        self, channel_name: str, minutes: int = 30
    ) -> list[Event]:
        """Fetch messages from the last `minutes` in a channel."""
        channel_id = await self.get_channel_id(channel_name)
        if not channel_id:
            logger.warning("Channel '%s' not found", channel_name)
            return []

        oldest = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).timestamp()
        data = await self._get(
            "conversations.history",
            {"channel": channel_id, "oldest": str(oldest), "limit": 50},
        )

        events: list[Event] = []
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

    async def fetch_all_channels(self, minutes: int = 30) -> list[Event]:
        """Fetch recent messages from all configured channels."""
        all_events: list[Event] = []
        for ch in settings.slack_channel_list:
            all_events.extend(await self.fetch_recent_messages(ch, minutes))
        return all_events
```

---

## integrations/github.py

```python
"""GitHub integration — fetches PRs, issues, and CI status."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from config import settings
from models import Event, Source

logger = logging.getLogger(__name__)

GH_API = "https://api.github.com"


class GitHubClient:
    """Async wrapper around GitHub REST API."""

    def __init__(self, token: str | None = None):
        self.token = token or settings.github_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GH_API}{path}",
                headers=self.headers,
                params=params or {},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

    async def fetch_recent_prs(self, repo: str, minutes: int = 30) -> list[Event]:
        """Open / recently updated PRs."""
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        pulls = await self._get(
            f"/repos/{repo}/pulls",
            {"state": "all", "sort": "updated", "direction": "desc", "per_page": 10},
        )

        events: list[Event] = []
        for pr in pulls:
            updated = pr.get("updated_at", "")
            if updated >= since:
                events.append(
                    Event(
                        source=Source.GITHUB,
                        title=f"PR #{pr['number']}: {pr['title']}",
                        body=pr.get("body", "") or "",
                        url=pr["html_url"],
                        timestamp=datetime.fromisoformat(updated.replace("Z", "+00:00")),
                        metadata={
                            "repo": repo,
                            "state": pr["state"],
                            "user": pr["user"]["login"],
                            "merged": pr.get("merged", False),
                        },
                    )
                )
        return events

    async def fetch_failed_runs(self, repo: str) -> list[Event]:
        """Most recent failed CI workflow runs."""
        runs = await self._get(
            f"/repos/{repo}/actions/runs",
            {"status": "failure", "per_page": 5},
        )

        events: list[Event] = []
        for run in runs.get("workflow_runs", []):
            events.append(
                Event(
                    source=Source.GITHUB,
                    title=f"CI Failed: {run['name']}",
                    body=f"Branch: {run['head_branch']} | Commit: {run['head_sha'][:7]}",
                    url=run["html_url"],
                    timestamp=datetime.fromisoformat(
                        run["updated_at"].replace("Z", "+00:00")
                    ),
                    metadata={"repo": repo, "workflow": run["name"]},
                )
            )
        return events

    async def fetch_all_repos(self, minutes: int = 30) -> list[Event]:
        """Aggregate events from all configured repos."""
        all_events: list[Event] = []
        for repo in settings.github_repo_list:
            all_events.extend(await self.fetch_recent_prs(repo, minutes))
            all_events.extend(await self.fetch_failed_runs(repo))
        return all_events
```

---

## integrations/notion.py

```python
"""Notion integration — fetches project tasks and their statuses."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from config import settings
from models import Event, Source

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Async wrapper around Notion API for reading project-tracker databases."""

    def __init__(self, token: str | None = None, database_id: str | None = None):
        self.token = token or settings.notion_token
        self.database_id = database_id or settings.notion_database_id
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{NOTION_API}{path}",
                headers=self.headers,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _extract_title(properties: dict) -> str:
        """Pull plain text from Notion title property."""
        for prop in properties.values():
            if prop["type"] == "title":
                return "".join(t["plain_text"] for t in prop["title"])
        return "Untitled"

    @staticmethod
    def _extract_status(properties: dict) -> str:
        """Pull status / select value."""
        for prop in properties.values():
            if prop["type"] == "status" and prop.get("status"):
                return prop["status"]["name"]
            if prop["type"] == "select" and prop.get("select"):
                return prop["select"]["name"]
        return "Unknown"

    @staticmethod
    def _extract_date(properties: dict) -> str | None:
        """Pull due date if present."""
        for prop in properties.values():
            if prop["type"] == "date" and prop.get("date"):
                return prop["date"].get("start")
        return None

    @staticmethod
    def _extract_assignee(properties: dict) -> str:
        """Pull assignee name from people property."""
        for prop in properties.values():
            if prop["type"] == "people":
                names = [p.get("name", "") for p in prop.get("people", [])]
                return ", ".join(n for n in names if n) or "Unassigned"
        return "Unassigned"

    async def fetch_tasks(self, status_filter: str | None = None) -> list[Event]:
        """Query the project database. Optionally filter by status."""
        payload: dict = {"page_size": 50}
        if status_filter:
            payload["filter"] = {
                "property": "Status",
                "status": {"equals": status_filter},
            }

        data = await self._post(
            f"/databases/{self.database_id}/query", payload
        )

        events: list[Event] = []
        for page in data.get("results", []):
            props = page["properties"]
            title = self._extract_title(props)
            status = self._extract_status(props)
            due = self._extract_date(props)
            assignee = self._extract_assignee(props)

            events.append(
                Event(
                    source=Source.NOTION,
                    title=title,
                    body=f"Status: {status} | Assignee: {assignee}"
                    + (f" | Due: {due}" if due else ""),
                    url=page.get("url", ""),
                    timestamp=datetime.fromisoformat(
                        page["last_edited_time"].replace("Z", "+00:00")
                    ),
                    metadata={
                        "status": status,
                        "assignee": assignee,
                        "due": due,
                        "page_id": page["id"],
                    },
                )
            )
        return events

    async def fetch_blocked_and_overdue(self) -> list[Event]:
        """Convenience: fetch tasks that are blocked or past due date."""
        all_tasks = await self.fetch_tasks()
        now = datetime.now(timezone.utc).date()
        flagged: list[Event] = []
        for task in all_tasks:
            status = task.metadata.get("status", "").lower()
            due = task.metadata.get("due")
            is_blocked = "block" in status
            is_overdue = False
            if due:
                try:
                    is_overdue = datetime.fromisoformat(due).date() < now
                except ValueError:
                    pass
            if is_blocked or is_overdue:
                flagged.append(task)
        return flagged
```

---

## integrations/youtube.py

```python
"""YouTube transcript fetcher — pulls and structures video transcripts."""

from __future__ import annotations

import logging
import re

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

logger = logging.getLogger(__name__)


class YouTubeTranscriptFetcher:
    """Fetch and structure YouTube transcripts for RAG ingestion."""

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
        raise ValueError(f"Cannot extract video ID from: {url}")

    @staticmethod
    def fetch_transcript(
        video_id: str, languages: tuple[str, ...] = ("en",)
    ) -> list[dict]:
        """Fetch transcript entries with timestamps.

        Each entry: {"text": "...", "start": 12.5, "duration": 3.2}
        """
        try:
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id, languages=list(languages)
            )
            return transcript
        except Exception:
            # Fallback: try auto-generated Hindi for Hindi videos
            try:
                transcript = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=["hi", "en"]
                )
                return transcript
            except Exception as e:
                logger.error("Failed to fetch transcript for %s: %s", video_id, e)
                return []

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Convert seconds to MM:SS format."""
        mins, secs = divmod(int(seconds), 60)
        return f"{mins:02d}:{secs:02d}"

    def get_full_text(self, video_id: str, languages: tuple[str, ...] = ("en",)) -> str:
        """Get the full transcript as plain text."""
        entries = self.fetch_transcript(video_id, languages)
        formatter = TextFormatter()
        return formatter.format_transcript(entries)

    def get_timestamped_chunks(
        self,
        video_id: str,
        chunk_seconds: int = 120,
        languages: tuple[str, ...] = ("en",),
    ) -> list[dict]:
        """Split transcript into time-windowed chunks for RAG ingestion.

        Returns list of:
        {
            "text": "combined text of chunk",
            "start": 0.0,
            "end": 120.0,
            "timestamp": "00:00"
        }
        """
        entries = self.fetch_transcript(video_id, languages)
        if not entries:
            return []

        chunks: list[dict] = []
        current_texts: list[str] = []
        chunk_start = 0.0
        chunk_end = chunk_seconds

        for entry in entries:
            if entry["start"] >= chunk_end and current_texts:
                chunks.append(
                    {
                        "text": " ".join(current_texts),
                        "start": chunk_start,
                        "end": entry["start"],
                        "timestamp": self.format_timestamp(chunk_start),
                    }
                )
                current_texts = []
                chunk_start = entry["start"]
                chunk_end = chunk_start + chunk_seconds

            current_texts.append(entry["text"])

        # Flush remaining
        if current_texts:
            chunks.append(
                {
                    "text": " ".join(current_texts),
                    "start": chunk_start,
                    "end": entries[-1]["start"] + entries[-1]["duration"],
                    "timestamp": self.format_timestamp(chunk_start),
                }
            )
        return chunks

    def fetch_video(
        self,
        url: str,
        title: str,
        chunk_seconds: int = 120,
        languages: tuple[str, ...] = ("en",),
    ) -> dict:
        """High-level: fetch a video's transcript and return structured data."""
        video_id = self.extract_video_id(url)
        chunks = self.get_timestamped_chunks(video_id, chunk_seconds, languages)
        return {
            "video_id": video_id,
            "title": title,
            "url": url,
            "chunks": chunks,
            "total_chunks": len(chunks),
        }
```

---

## rag/__init__.py

```python
from .ingest import Ingestor
from .store import VectorStore
from .query import RAGQueryEngine
from .evaluate import RAGEvaluator

__all__ = ["Ingestor", "VectorStore", "RAGQueryEngine", "RAGEvaluator"]
```

---

## rag/store.py

```python
"""FAISS-based vector store with sentence-transformers embeddings."""

from __future__ import annotations

import logging
import os
import pickle
from typing import Dict, List, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Lightweight FAISS vector store with local persistence."""

    def __init__(
        self,
        collection_name="pulseboard",
        persist_dir=None,
    ):
        # type: (str, Optional[str]) -> None
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self.dim = 384  # all-MiniLM-L6-v2 output dimension

        # Storage
        self._documents = []  # type: List[str]
        self._metadatas = []  # type: List[Dict]
        self._ids = []  # type: List[str]
        self._index = None  # type: Optional[faiss.IndexFlatIP]

        # Try loading from disk
        self._load()
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dim)

        logger.info(
            "VectorStore ready -- collection '%s' (%d docs)",
            collection_name,
            self.count(),
        )

    def _index_path(self):
        # type: () -> str
        return os.path.join(self.persist_dir, "{}.faiss".format(self.collection_name))

    def _meta_path(self):
        # type: () -> str
        return os.path.join(self.persist_dir, "{}.pkl".format(self.collection_name))

    def _save(self):
        # type: () -> None
        os.makedirs(self.persist_dir, exist_ok=True)
        faiss.write_index(self._index, self._index_path())
        with open(self._meta_path(), "wb") as f:
            pickle.dump(
                {"documents": self._documents, "metadatas": self._metadatas, "ids": self._ids},
                f,
            )

    def _load(self):
        # type: () -> None
        idx_path = self._index_path()
        meta_path = self._meta_path()
        if os.path.exists(idx_path) and os.path.exists(meta_path):
            self._index = faiss.read_index(idx_path)
            with open(meta_path, "rb") as f:
                data = pickle.load(f)
            self._documents = data["documents"]
            self._metadatas = data["metadatas"]
            self._ids = data["ids"]
            logger.info("Loaded %d docs from disk", len(self._documents))

    def _embed(self, texts):
        # type: (List[str]) -> np.ndarray
        vecs = self.encoder.encode(texts, normalize_embeddings=True)
        return np.array(vecs, dtype=np.float32)

    def add(self, documents, metadatas, ids):
        # type: (List[str], List[Dict], List[str]) -> None
        """Upsert documents. Skips IDs already present."""
        new_docs, new_metas, new_ids = [], [], []
        existing_ids = set(self._ids)
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            if doc_id not in existing_ids:
                new_docs.append(doc)
                new_metas.append(meta)
                new_ids.append(doc_id)

        if not new_docs:
            return

        vectors = self._embed(new_docs)
        self._index.add(vectors)
        self._documents.extend(new_docs)
        self._metadatas.extend(new_metas)
        self._ids.extend(new_ids)
        self._save()

    def query(self, query_text, n_results=5, where=None):
        # type: (str, int, Optional[Dict]) -> Dict
        """Semantic search. Returns dict matching ChromaDB query format."""
        if self.count() == 0:
            return {"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]}

        query_vec = self._embed([query_text])
        k = min(n_results * 3, self.count())  # oversample for filtering
        scores, indices = self._index.search(query_vec, k)

        docs, metas, result_ids, dists = [], [], [], []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            meta = self._metadatas[idx]
            # Apply metadata filter
            if where:
                match = all(meta.get(wk) == wv for wk, wv in where.items())
                if not match:
                    continue
            docs.append(self._documents[idx])
            metas.append(meta)
            result_ids.append(self._ids[idx])
            dists.append(float(score))
            if len(docs) >= n_results:
                break

        return {
            "documents": [docs],
            "metadatas": [metas],
            "ids": [result_ids],
            "distances": [dists],
        }

    def count(self):
        # type: () -> int
        if self._index is None:
            return 0
        return self._index.ntotal

    def reset(self):
        # type: () -> None
        """Delete all documents."""
        self._index = faiss.IndexFlatIP(self.dim)
        self._documents = []
        self._metadatas = []
        self._ids = []
        self._save()
        logger.info("VectorStore reset")
```

---

## rag/ingest.py

```python
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

    def __init__(self, store):
        # type: (VectorStore) -> None
        self.store = store

    @staticmethod
    def _make_id(text, source):
        # type: (str, str) -> str
        """Deterministic chunk ID to avoid duplicates."""
        return hashlib.sha256("{}:{}".format(source, text[:200]).encode()).hexdigest()[:16]

    def ingest_events(self, events):
        # type: (List[Event]) -> int
        """Ingest heartbeat events (Slack messages, GitHub PRs, Notion tasks)."""
        docs, metas, ids = [], [], []
        for ev in events:
            content = "{}\n{}".format(ev.title, ev.body)
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
        url,
        title,
        chunk_seconds=120,
        languages=("en",),
    ):
        # type: (str, str, int, Tuple[str, ...]) -> int
        """Ingest a single YouTube video's transcript as chunks."""
        from integrations.youtube import YouTubeTranscriptFetcher
        yt = YouTubeTranscriptFetcher()
        video_data = yt.fetch_video(url, title, chunk_seconds, languages)
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

    def ingest_all_videos(self, videos):
        # type: (List[Dict]) -> int
        """Batch-ingest multiple videos."""
        total = 0
        for v in videos:
            total += self.ingest_youtube_video(
                url=v["url"],
                title=v["title"],
                languages=v.get("languages", ("en",)),
            )
        return total
```

---

## rag/query.py

```python
"""RAG query engine -- retrieves context and generates answers via Claude/Gemini."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from config import settings
from llm import get_llm
from models import ChunkMetadata, QueryResponse

from .store import VectorStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI assistant for a project management tool called PulseBoard.
You answer questions based ONLY on the provided context chunks. If the context does not
contain enough information, say so -- do not fabricate answers.

Keep answers concise (2-4 sentences). Cite the source when possible."""


class RAGQueryEngine:
    """Retrieve relevant chunks, then generate an answer with Claude/Gemini."""

    def __init__(self, store: VectorStore):
        self.store = store
        self.llm = get_llm()

    def retrieve(
        self, question: str, n_results: int = 5, source_filter: Optional[str] = None
    ) -> Tuple[List[str], List[ChunkMetadata]]:
        """Retrieve top-k chunks for a question."""
        where = {"source_type": source_filter} if source_filter else None
        results = self.store.query(question, n_results=n_results, where=where)

        chunks = []  # type: List[str]
        metas = []  # type: List[ChunkMetadata]
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            chunks.append(doc)
            metas.append(ChunkMetadata(**meta))
        return chunks, metas

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
        """End-to-end: retrieve -> generate -> return structured response."""
        chunks, metas = self.retrieve(question, n_results, source_filter)

        if not chunks:
            return QueryResponse(
                answer="No relevant information found in the knowledge base.",
                sources=[],
                confidence=0.0,
            )

        answer = self.generate(question, chunks)
        return QueryResponse(
            answer=answer,
            sources=metas,
            confidence=min(1.0, len(chunks) / n_results),
        )
```

---

## rag/evaluate.py

```python
"""RAG evaluation -- generate golden QA pairs and score retrieval quality."""

from __future__ import annotations

import json
import logging
from typing import Dict, List

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
- Include a "retrieval_challenge" -- what confusable chunk would a wrong retrieval return?

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


def _extract_json(raw: str) -> str:
    """Extract JSON from LLM response that may include markdown code blocks."""
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


class RAGEvaluator:
    """Generate golden QA datasets and evaluate RAG pipeline quality."""

    def __init__(self, store: VectorStore):
        self.store = store
        self.llm = get_llm()
        self.query_engine = RAGQueryEngine(store)

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
        raw = _extract_json(raw)
        pairs_data = json.loads(raw)

        return [
            QAPair(
                question=p["question"],
                answer=p["answer"],
                source_video=video_title,
                source_url=video_url,
                timestamp=p.get("timestamp", ""),
                section_description=p.get("section_description", ""),
                retrieval_challenge=p.get("retrieval_challenge", ""),
            )
            for p in pairs_data
        ]

    def generate_dataset_from_videos(
        self, videos: List[Dict], pairs_per_video: int = 2
    ) -> List[QAPair]:
        """Generate a golden dataset spanning multiple videos."""
        all_pairs = []  # type: List[QAPair]
        for video in videos:
            if not video.get("chunks"):
                logger.warning("No chunks for '%s', skipping", video["title"])
                continue
            pairs = self.generate_qa_pairs(
                video_title=video["title"],
                video_url=video["url"],
                chunks=video["chunks"],
                n_pairs=pairs_per_video,
            )
            all_pairs.extend(pairs)
            logger.info("Generated %d QA pairs for '%s'", len(pairs), video["title"])
        return all_pairs

    def evaluate_pair(self, qa: QAPair) -> EvalResult:
        """Run a single QA pair through the RAG pipeline and score it."""
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
        raw = _extract_json(raw)
        scores = json.loads(raw)

        return EvalResult(
            question=qa.question,
            expected_answer=qa.answer,
            retrieved_chunks=[
                "[{}: {}]".format(s.source_type, s.title) for s in response.sources
            ],
            generated_answer=response.answer,
            retrieval_score=scores.get("retrieval_score", 0.0),
            answer_score=scores.get("answer_score", 0.0),
        )

    def evaluate_dataset(self, qa_pairs: List[QAPair]) -> List[EvalResult]:
        """Evaluate all QA pairs and return scored results."""
        results = []  # type: List[EvalResult]
        for qa in qa_pairs:
            try:
                result = self.evaluate_pair(qa)
                results.append(result)
                logger.info(
                    "Q: '%s' -> retrieval=%.2f, answer=%.2f",
                    qa.question[:50],
                    result.retrieval_score,
                    result.answer_score,
                )
            except Exception as e:
                logger.error("Failed to evaluate '%s': %s", qa.question[:50], e)
        return results

    @staticmethod
    def summary_stats(results: List[EvalResult]) -> Dict:
        """Compute aggregate evaluation metrics."""
        if not results:
            return {"count": 0, "avg_retrieval": 0, "avg_answer": 0,
                    "min_retrieval": 0, "max_retrieval": 0}
        return {
            "count": len(results),
            "avg_retrieval": sum(r.retrieval_score for r in results) / len(results),
            "avg_answer": sum(r.answer_score for r in results) / len(results),
            "min_retrieval": min(r.retrieval_score for r in results),
            "max_retrieval": max(r.retrieval_score for r in results),
        }
```

---

## routes/__init__.py

```python
from .heartbeat import router as heartbeat_router
from .rag import router as rag_router
from .query import router as query_router

__all__ = ["heartbeat_router", "rag_router", "query_router"]
```

---

## routes/heartbeat.py

```python
"""Heartbeat API — trigger digests on demand and view history."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter

from heartbeat.collector import EventCollector
from heartbeat.classifier import classify_events
from heartbeat.digest import DigestGenerator
from models import Digest
from rag.ingest import Ingestor
from rag.store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/heartbeat", tags=["heartbeat"])

# Shared state — latest digest
_latest_digest: Optional[Digest] = None
_digest_history: List[Digest] = []


def get_latest_digest() -> Optional[Digest]:
    return _latest_digest


def get_digest_history() -> List[Digest]:
    return _digest_history


async def run_heartbeat_cycle() -> Digest:
    """Full heartbeat pipeline: collect -> classify -> ingest -> digest."""
    global _latest_digest

    collector = EventCollector()
    generator = DigestGenerator()
    store = VectorStore()
    ingestor = Ingestor(store)

    # 1. Collect events from all sources
    events = await collector.collect_all()
    logger.info("Collected %d events", len(events))

    # 2. Classify urgency
    events = classify_events(events)

    # 3. Ingest into vector store for RAG queries
    ingestor.ingest_events(events)

    # 4. Generate digest
    digest = generator.generate(events)
    _latest_digest = digest
    _digest_history.append(digest)

    # Keep only last 48 digests (24 hours at 30-min intervals)
    if len(_digest_history) > 48:
        _digest_history.pop(0)

    return digest


@router.post("/trigger", response_model=Digest)
async def trigger_heartbeat():
    """Manually trigger a heartbeat cycle."""
    return await run_heartbeat_cycle()


@router.get("/latest")
async def latest_digest():
    """Get the most recent digest."""
    return _latest_digest


@router.get("/history", response_model=List[Digest])
async def digest_history():
    """Get recent digest history."""
    return _digest_history
```

---

## routes/rag.py

```python
"""RAG API -- ingest videos, generate golden datasets, run evaluations."""

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


# -- Default video set from the assessment ------------------------------------

DEFAULT_VIDEOS = [
    VideoInput(
        url="https://www.youtube.com/watch?v=aircAruvnKk",
        title='3Blue1Brown -- "But what is a Neural Network?"',
    ),
    VideoInput(
        url="https://www.youtube.com/watch?v=wjZofJX0v4M",
        title='3Blue1Brown -- "Transformers, the tech behind LLMs"',
    ),
    VideoInput(
        url="https://www.youtube.com/watch?v=fHF22Wxuyw4",
        title='CampusX -- "What is Deep Learning?" (Hindi)',
        languages=["hi", "en"],
    ),
    VideoInput(
        url="https://www.youtube.com/watch?v=C6YtPJxNULA",
        title='CodeWithHarry -- "All About ML & Deep Learning" (Hindi)',
        languages=["hi", "en"],
    ),
]


def _get_video_data(vids):
    # type: (List[VideoInput]) -> List[Dict]
    """Fetch video data -- uses mock data in demo mode, real transcripts otherwise."""
    if settings.demo_mode:
        from demo_data import get_mock_video_chunks
        logger.info("DEMO MODE: Using mock video transcripts")
        return get_mock_video_chunks()

    from integrations.youtube import YouTubeTranscriptFetcher
    yt = YouTubeTranscriptFetcher()
    video_data = []
    for v in vids:
        data = yt.fetch_video(v.url, v.title, languages=tuple(v.languages))
        video_data.append(data)
    return video_data


@router.post("/ingest", response_model=IngestResponse)
async def ingest_videos(videos=None):
    # type: (Optional[List[VideoInput]]) -> IngestResponse
    """Ingest YouTube video transcripts into the vector store."""
    vids = videos or DEFAULT_VIDEOS
    store = VectorStore()
    ingestor = Ingestor(store)
    video_data = _get_video_data(vids)

    total = 0
    for vd in video_data:
        chunks = vd.get("chunks", [])
        for chunk in chunks:
            doc_id = "yt-{}-{}".format(vd.get("video_id", vd["title"]), chunk["timestamp"])
            ingestor.store.add(
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
    videos=None,
    pairs_per_video=2,
):
    # type: (Optional[List[VideoInput]], int) -> List[QAPair]
    """Generate a golden QA evaluation dataset from video transcripts."""
    vids = videos or DEFAULT_VIDEOS

    if settings.demo_mode:
        # Return pre-built golden QA pairs in demo mode
        from demo_data import MOCK_QA_PAIRS
        logger.info("DEMO MODE: Returning %d pre-built QA pairs", len(MOCK_QA_PAIRS))
        return [QAPair(**p) for p in MOCK_QA_PAIRS]

    video_data = _get_video_data(vids)
    store = VectorStore()
    evaluator = RAGEvaluator(store)
    pairs = evaluator.generate_dataset_from_videos(video_data, pairs_per_video)
    return pairs


@router.post("/evaluate", response_model=EvalSummary)
async def evaluate_pipeline(qa_pairs):
    # type: (List[QAPair]) -> EvalSummary
    """Evaluate the RAG pipeline against a set of QA pairs."""
    store = VectorStore()
    evaluator = RAGEvaluator(store)
    results = evaluator.evaluate_dataset(qa_pairs)
    stats = evaluator.summary_stats(results)
    return EvalSummary(**stats, results=results)


@router.get("/stats")
async def store_stats():
    """Get vector store statistics."""
    store = VectorStore()
    return {"total_documents": store.count()}
```

---

## routes/query.py

```python
"""Natural-language query API — ask questions against the knowledge base."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from models import QueryResponse
from rag.query import RAGQueryEngine
from rag.store import VectorStore

router = APIRouter(prefix="/query", tags=["query"])


class QuestionInput(BaseModel):
    question: str
    source_filter: Optional[str] = None  # "slack", "github", "notion", "youtube"
    n_results: int = 5


@router.post("/ask", response_model=QueryResponse)
async def ask_question(inp: QuestionInput):
    """Ask a natural-language question against all ingested data."""
    store = VectorStore()
    engine = RAGQueryEngine(store)
    return engine.ask(
        question=inp.question,
        n_results=inp.n_results,
        source_filter=inp.source_filter,
    )
```
