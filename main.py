"""PulseBoard-RAG — FastAPI application entry point.

Improvements vs. prototype:
1. CORS: was allow_origins=["*"] — exposes the API to any browser origin.
   Fixed: reads settings.cors_origins_list (configurable via CORS_ORIGINS env var).
   Defaults to localhost only; production deployments set their domain explicitly.

2. Health check now includes live system status (demo mode, LLM provider,
   vector store document count) so monitoring tools get real signal, not just
   a static {"status": "ok"}.

3. Startup/shutdown lifecycle logs the active configuration summary so operators
   immediately see which keys are loaded and which features are in demo mode.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from config import settings
from routes import heartbeat_router, query_router, rag_router

# ── Logging ───────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — log active configuration so operators know what's loaded
    logger.info("=" * 60)
    logger.info("PulseBoard-RAG starting up")
    logger.info("  demo_mode        : %s", settings.demo_mode)
    logger.info("  claude_key       : %s", "set" if settings.anthropic_api_key else "MISSING")
    logger.info("  gemini_key       : %s", "set" if settings.gemini_api_key else "MISSING")
    logger.info("  slack_channels   : %s", settings.slack_channel_list or "none")
    logger.info("  github_repos     : %s", settings.github_repo_list or "none")
    logger.info("  cors_origins     : %s", settings.cors_origins_list)
    logger.info("  heartbeat_every  : %d min", settings.digest_interval_minutes)
    logger.info("=" * 60)
    yield
    logger.info("PulseBoard-RAG shutting down")


# ── App ───────────────────────────────────────────────────────

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

# FIX: was allow_origins=["*"] — now reads from settings (configurable per env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Dashboard HTML (read once at startup) ─────────────────────

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_HTML_FILE = _STATIC_DIR / "index.html"
_DASHBOARD_HTML: str = ""
if _HTML_FILE.exists():
    _DASHBOARD_HTML = _HTML_FILE.read_text(encoding="utf-8")
    logger.info("Dashboard HTML loaded from %s", _HTML_FILE)
else:
    logger.warning("static/index.html not found — dashboard will show plain message")


@app.get("/")
async def serve_root():
    """Serve the Stitch HTML dashboard."""
    if _DASHBOARD_HTML:
        return HTMLResponse(content=_DASHBOARD_HTML)
    return HTMLResponse(content="<h1>PulseBoard-RAG</h1><p>Visit <a href='/docs'>/docs</a> for the API.</p>")


@app.get("/dashboard")
async def serve_dashboard():
    """Alias for root — same dashboard."""
    if _DASHBOARD_HTML:
        return HTMLResponse(content=_DASHBOARD_HTML)
    return HTMLResponse(content="<h1>PulseBoard-RAG</h1><p>Visit <a href='/docs'>/docs</a> for the API.</p>")


# ── Routes ────────────────────────────────────────────────────

app.include_router(heartbeat_router)
app.include_router(rag_router)
app.include_router(query_router)


# ── Health check ──────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    """Liveness + readiness probe with live system status."""
    from llm import get_llm
    from rag.store import VectorStore

    llm = get_llm()
    try:
        store = VectorStore()
        doc_count = store.count()
        store_status = "ok"
    except Exception as exc:
        doc_count = -1
        store_status = str(exc)

    return {
        "status": "ok",
        "service": "pulseboard-rag",
        "demo_mode": settings.demo_mode,
        "llm_provider": llm.active_provider,
        "vector_store": {"status": store_status, "documents": doc_count},
    }


# ── Direct run ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    os.chdir(_PROJECT_ROOT)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
