"""Heartbeat API — trigger digests on demand and view history.

Bug fixes vs. prototype:
1. THREAD SAFETY: _latest_digest and _digest_history were plain module-level
   Python lists with no synchronisation.  Under concurrent requests (uvicorn
   with multiple workers or async tasks) reads and writes could race.
   Fixed: replaced list with collections.deque(maxlen=...) + threading.Lock.
   deque.append() is atomic in CPython but the Lock makes this explicit and
   safe across multiple workers.

2. O(n) list.pop(0): trimming the history used pop(0) which copies the entire
   list every call.  Fixed: deque(maxlen=N) handles eviction in O(1).

3. VectorStore was instantiated inside run_heartbeat_cycle() on every call,
   causing a full disk load + sentence-transformer init on each heartbeat.
   Fixed: VectorStore is obtained from the process-wide singleton via
   get_vector_store() (defined in main.py and shared across routes).

4. History ceiling (48) was a magic number inside the route.
   Fixed: now reads settings.max_digest_history.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import List, Optional

from fastapi import APIRouter

from config import settings
from heartbeat.classifier import classify_events
from heartbeat.collector import EventCollector
from heartbeat.digest import DigestGenerator
from models import Digest
from rag.ingest import Ingestor
from rag.store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/heartbeat", tags=["heartbeat"])

# ── Thread-safe in-memory state ────────────────────────────────
# FIX: was a plain list + manual pop(0).  deque(maxlen) evicts oldest in O(1).
# Lock makes concurrent access from async tasks + background scheduler safe.

_lock = threading.Lock()
_latest_digest: Optional[Digest] = None
_digest_history: deque = deque(maxlen=settings.max_digest_history)

# Process-wide VectorStore singleton (avoids disk reload on every request)
_store: Optional[VectorStore] = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


# ── Public accessors (used by scheduler) ──────────────────────

def get_latest_digest() -> Optional[Digest]:
    with _lock:
        return _latest_digest


def get_digest_history() -> List[Digest]:
    with _lock:
        return list(_digest_history)


# ── Core pipeline ─────────────────────────────────────────────

async def run_heartbeat_cycle() -> Digest:
    """Full heartbeat pipeline: collect → classify → ingest → digest."""
    global _latest_digest

    collector = EventCollector()
    generator = DigestGenerator()
    store = _get_store()
    ingestor = Ingestor(store)

    events = await collector.collect_all()
    logger.info("Collected %d events", len(events))

    events = classify_events(events)
    ingestor.ingest_events(events)
    digest = generator.generate(events)

    with _lock:
        _latest_digest = digest
        _digest_history.append(digest)   # deque handles maxlen eviction

    return digest


# ── Routes ────────────────────────────────────────────────────

@router.post("/trigger", response_model=Digest)
async def trigger_heartbeat():
    """Manually trigger a heartbeat cycle."""
    return await run_heartbeat_cycle()


@router.get("/latest")
async def latest_digest():
    """Get the most recent digest."""
    return get_latest_digest()


@router.get("/history", response_model=List[Digest])
async def digest_history():
    """Get recent digest history (up to max_digest_history entries)."""
    return get_digest_history()
