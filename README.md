# PulseBoard-RAG

> Intelligent project monitor with 30-minute heartbeat digests and a RAG-powered knowledge base.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)

---

## What it does

PulseBoard-RAG aggregates everything happening across your team — Slack messages, GitHub PRs & CI results, Notion tasks — and turns it into one clear digest every 30 minutes. It also indexes everything into a vector store so you can ask natural-language questions about your project history.

**Stop switching between 4 tools. Get one intelligent digest.**

---

## Features

- **30-min Heartbeat Digests** — collects events from Slack, GitHub, Notion and summarises them into URGENT vs INFORMATIONAL items using Claude
- **RAG Knowledge Base** — every event and YouTube transcript is embedded with `sentence-transformers` and stored in FAISS for semantic search
- **Natural-Language Queries** — ask "what is blocking the pharma demo?" and get a direct answer grounded in your actual project data
- **Hallucination Guard** — if the answer is not in the knowledge base, the system says so instead of making something up
- **Urgency Classifier** — rule-based classifier flags CI failures, blocked/overdue Notion tasks, and unanswered client Slack messages
- **Beautiful Dashboard** — dark Stitch UI with 4 views: Dashboard, Heartbeat Feed, RAG Lab, Settings
- **Demo Mode** — runs entirely on mock data with no API keys needed
- **Production-grade** — tenacity retry on all LLM + API calls, thread-safe history, JSON vector store metadata, startup config validation

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| LLM | Claude (primary) · Gemini (fallback) |
| Embeddings | `sentence-transformers` all-MiniLM-L6-v2 |
| Vector Store | FAISS |
| Scheduler | APScheduler |
| Dashboard | Vanilla HTML/CSS/JS (Stitch design system) |
| Config | Pydantic-settings + `.env` |

---

## Quick Start (Demo Mode — no API keys needed)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/PulseBoard-Rag.git
cd PulseBoard-Rag

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install
pip install -e .

# 4. Create .env (demo mode is on by default)
cp .env.example .env

# 5. Run
python main.py

# 6. Open browser
# http://localhost:8000         ← Dashboard
# http://localhost:8000/docs    ← API reference
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your keys:

```env
# ── Mode ──────────────────────────────────
DEMO_MODE=false              # true = mock data, no keys needed

# ── LLM (need at least one) ───────────────
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...       # optional fallback

# ── Slack ──────────────────────────────────
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNELS=general,engineering

# ── GitHub ─────────────────────────────────
GITHUB_TOKEN=ghp_...
GITHUB_REPOS=YourOrg/YourRepo

# ── Notion ─────────────────────────────────
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=your-database-id

# ── App ────────────────────────────────────
DIGEST_INTERVAL_MINUTES=30
```

See the **Settings** tab in the dashboard for a full step-by-step guide on getting each API key.

---

## Project Structure

```
PulseBoard-Rag/
├── main.py                  # FastAPI app entry point
├── config.py                # Pydantic settings + startup validation
├── models.py                # Shared Pydantic models
├── llm.py                   # Claude + Gemini with tenacity retry
├── scheduler.py             # APScheduler heartbeat runner
├── demo_data.py             # Mock data for demo mode
├── cli.py                   # Interactive setup wizard CLI
├── static/
│   └── index.html           # Single-page dashboard (Stitch UI)
├── heartbeat/
│   ├── classifier.py        # Rule-based urgency classifier
│   ├── collector.py         # Aggregates events from all sources
│   └── digest.py            # LLM digest generator
├── integrations/
│   ├── slack.py             # Slack API with cursor pagination
│   ├── github.py            # GitHub REST API
│   ├── notion.py            # Notion API
│   └── youtube.py           # YouTube transcript fetcher
├── rag/
│   ├── store.py             # FAISS vector store wrapper
│   ├── ingest.py            # Chunking + embedding pipeline
│   ├── query.py             # RAG query engine + hallucination guard
│   └── evaluate.py          # Golden dataset eval pipeline
├── routes/
│   ├── heartbeat.py         # POST /heartbeat/trigger, GET /heartbeat/latest
│   ├── query.py             # POST /query/ask
│   └── rag.py               # POST /rag/ingest, /rag/evaluate, GET /rag/stats
├── pyproject.toml           # pip-installable package
└── .env.example             # Environment variable template
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Dashboard UI |
| `GET` | `/health` | System health + LLM provider status |
| `POST` | `/heartbeat/trigger` | Manually trigger a digest cycle |
| `GET` | `/heartbeat/latest` | Get the most recent digest |
| `GET` | `/heartbeat/history` | Get all past digests |
| `POST` | `/query/ask` | Ask a question against the knowledge base |
| `POST` | `/rag/ingest` | Ingest YouTube video transcripts |
| `POST` | `/rag/generate-dataset` | Generate a golden QA evaluation dataset |
| `POST` | `/rag/evaluate` | Evaluate RAG pipeline against QA pairs |
| `GET` | `/rag/stats` | Vector store document count |

Full interactive docs at `http://localhost:8000/docs`

---

## License

MIT
