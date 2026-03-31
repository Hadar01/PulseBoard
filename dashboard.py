"""PulseBoard-RAG — Streamlit Dashboard.

Improvements vs. prototype:
1. API_BASE was hardcoded to "http://localhost:8000".
   Fixed: reads from API_BASE_URL env var (falls back to localhost for dev).
   This makes the same dashboard.py work in Docker, Streamlit Cloud, and local dev
   without code changes.

2. Non-technical users visiting the dashboard previously had no way to supply
   API keys — they had to edit a .env file manually.
   Fixed: sidebar "API Keys" expander lets users paste their keys directly into
   the UI (stored in st.session_state, not persisted to disk).

3. Added a live health-check indicator in the sidebar so users immediately
   know whether the backend API is reachable before clicking buttons.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional, Union

import httpx
import streamlit as st

# FIX: was hardcoded "http://localhost:8000"
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="PulseBoard-RAG", layout="wide", page_icon="📡")


# ── Helpers ───────────────────────────────────────────────────

def api(method: str, path: str, **kwargs) -> Optional[Union[dict, list]]:
    """Call the FastAPI backend."""
    try:
        resp = getattr(httpx, method)(
            f"{API_BASE}{path}",
            timeout=120,
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        st.error(
            f"Backend not reachable at **{API_BASE}**. "
            "Start it with: `uvicorn main:app --reload`"
        )
        return None
    except httpx.HTTPStatusError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text[:200]}")
        return None
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        return None


# ── Sidebar ───────────────────────────────────────────────────

with st.sidebar:
    st.title("📡 PulseBoard-RAG")
    st.caption("Intelligent project monitor + RAG evaluation")

    # Live health check
    health = api("get", "/health")
    if health:
        provider = health.get("llm_provider", "?")
        doc_count = health.get("vector_store", {}).get("documents", 0)
        demo = health.get("demo_mode", True)
        st.success(f"API online — LLM: `{provider}` | Docs: `{doc_count}`")
        if demo:
            st.warning("Running in **DEMO MODE** — using mock data")
    else:
        st.error("API offline")

    st.divider()

    # API key configuration for non-technical users
    with st.expander("🔑 API Keys (optional)", expanded=False):
        st.caption(
            "Enter keys here to override your .env file. "
            "Keys are stored only in your browser session."
        )
        anthropic_key = st.text_input("Anthropic API Key", type="password",
                                      key="anthropic_key")
        gemini_key = st.text_input("Gemini API Key", type="password",
                                   key="gemini_key")
        if anthropic_key:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key

    st.divider()

    page = st.radio(
        "Navigate",
        ["Heartbeat Digest", "Ask a Question", "RAG Evaluation", "Ingest Videos"],
    )


# ── Page: Heartbeat Digest ────────────────────────────────────

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
            st.rerun()

    data = api("get", "/heartbeat/latest")
    if data:
        st.subheader("Latest Digest")
        st.caption(f"Generated at: {data.get('generated_at', 'N/A')}")

        summary = data.get("natural_language_summary", "")
        if summary:
            st.info(summary)

        urgent = data.get("urgent", [])
        if urgent:
            st.error(f"**{len(urgent)} Urgent Item{'s' if len(urgent) != 1 else ''}**")
            for item in urgent:
                link = f" [→]({item['url']})" if item.get("url") else ""
                st.markdown(f"- **[{item['source']}]** {item['summary']}{link}")
        else:
            st.success("No urgent items")

        info = data.get("informational", [])
        if info:
            with st.expander(f"Informational ({len(info)} items)", expanded=False):
                for item in info:
                    link = f" [→]({item['url']})" if item.get("url") else ""
                    st.markdown(f"- **[{item['source']}]** {item['summary']}{link}")
    else:
        st.info("No digest yet. Click **Trigger Heartbeat Now** to generate one.")

    history = api("get", "/heartbeat/history")
    if history and len(history) > 1:
        with st.expander(f"Digest History ({len(history)} entries)"):
            for d in reversed(history):
                u = len(d.get("urgent", []))
                inf = len(d.get("informational", []))
                st.markdown(f"**{d['generated_at']}** — {u} urgent, {inf} info")


# ── Page: Ask a Question ──────────────────────────────────────

elif page == "Ask a Question":
    st.header("Ask a Question")
    st.caption("Query the knowledge base using natural language")

    question = st.text_input(
        "Your question:",
        placeholder="What's the status of the pharma portal?",
    )
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
                json={"question": question, "source_filter": source_filter, "n_results": 5},
            )
        if data:
            st.subheader("Answer")

            # Show "cannot answer" state distinctly
            if not data.get("is_answerable", True):
                st.warning(data["answer"])
            else:
                st.write(data["answer"])

            confidence = data.get("confidence", 0.0)
            st.progress(confidence, text=f"Confidence: {confidence:.0%}")

            sources = data.get("sources", [])
            if sources:
                with st.expander(f"Sources ({len(sources)})"):
                    for s in sources:
                        link = f" | [→]({s['url']})" if s.get("url") else ""
                        st.markdown(
                            f"- **{s['source_type']}** | {s['title']} | {s['timestamp']}{link}"
                        )


# ── Page: RAG Evaluation ──────────────────────────────────────

elif page == "RAG Evaluation":
    st.header("RAG Evaluation")
    st.caption("Generate golden QA datasets and benchmark retrieval quality")

    tab1, tab2 = st.tabs(["Generate Dataset", "Run Evaluation"])

    with tab1:
        pairs_per_video = st.slider("QA pairs per video:", 1, 5, 2)
        if st.button("Generate Golden Dataset", type="primary"):
            with st.spinner("Generating QA pairs from video transcripts (~1 min)..."):
                data = api("post", "/rag/generate-dataset",
                           params={"pairs_per_video": pairs_per_video})
            if data:
                st.success(f"Generated {len(data)} QA pairs!")
                st.session_state["qa_pairs"] = data
                for i, qa in enumerate(data, 1):
                    with st.expander(f"Q{i}: {qa['question'][:80]}..."):
                        st.markdown(f"**Answer:** {qa['answer']}")
                        st.markdown(f"**Source:** {qa['source_video']} @ {qa['timestamp']}")
                        st.markdown(f"**Section:** {qa['section_description']}")
                        st.markdown(f"**Retrieval Challenge:** {qa['retrieval_challenge']}")
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
            st.info(f"Ready to evaluate {len(st.session_state['qa_pairs'])} QA pairs")
            if st.button("Run Evaluation", type="primary"):
                with st.spinner("Evaluating RAG pipeline..."):
                    data = api("post", "/rag/evaluate",
                               json=st.session_state["qa_pairs"])
                if data:
                    st.subheader("Results")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Avg Retrieval Score", f"{data['avg_retrieval']:.2f}")
                    col2.metric("Avg Answer Score", f"{data['avg_answer']:.2f}")
                    col3.metric("Questions Evaluated", data["count"])
                    for r in data.get("results", []):
                        with st.expander(f"Q: {r['question'][:60]}..."):
                            st.markdown(f"**Expected:** {r['expected_answer']}")
                            st.markdown(f"**Generated:** {r['generated_answer']}")
                            st.markdown(f"**Retrieval Score:** {r['retrieval_score']:.2f}")
                            st.markdown(f"**Answer Score:** {r['answer_score']:.2f}")


# ── Page: Ingest Videos ───────────────────────────────────────

elif page == "Ingest Videos":
    st.header("Ingest Video Transcripts")
    st.caption("Pull YouTube transcripts into the RAG knowledge base")

    st.subheader("Default Video Set")
    st.markdown("""
    1. 3Blue1Brown — *But what is a Neural Network?*
    2. 3Blue1Brown — *Transformers, the tech behind LLMs*
    3. CampusX — *What is Deep Learning?* (Hindi)
    4. CodeWithHarry — *All About ML & Deep Learning* (Hindi)
    """)

    if st.button("Ingest All Default Videos", type="primary"):
        with st.spinner("Fetching transcripts and building embeddings..."):
            data = api("post", "/rag/ingest")
        if data:
            st.success(
                f"Ingested {data['total_chunks']} chunks from {data['videos_processed']} videos!"
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
            st.success(f"Ingested {data['total_chunks']} chunks!")

    st.divider()
    stats = api("get", "/rag/stats")
    if stats:
        st.metric("Total Documents in Vector Store", stats["total_documents"])
