"""FAISS-based vector store with sentence-transformers embeddings.

Bug fixes vs. prototype:
1. SECURITY: Metadata was persisted via pickle.dump/pickle.load. Loading a pickle
   file is equivalent to executing arbitrary Python — if the ./chroma_db directory
   is writable by untrusted processes the store becomes an RCE vector.
   Fixed: metadata is now stored as plain JSON. The FAISS binary index (written
   by faiss.write_index) is NOT a pickle and remains safe.

2. Embedding model and dimension were hardcoded strings.
   Fixed: read from settings.embedding_model / settings.embedding_dim.
"""

from __future__ import annotations

import json
import logging
import os
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
        collection_name: str = "pulseboard",
        persist_dir: Optional[str] = None,
    ) -> None:
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name
        self.encoder = SentenceTransformer(settings.embedding_model)
        self.dim = settings.embedding_dim

        self._documents: List[str] = []
        self._metadatas: List[Dict] = []
        self._ids: List[str] = []
        self._index: Optional[faiss.IndexFlatIP] = None

        self._load()
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dim)

        logger.info(
            "VectorStore ready — collection '%s' (%d docs)",
            collection_name,
            self.count(),
        )

    # ── Paths ─────────────────────────────────────────────────

    def _index_path(self) -> str:
        return os.path.join(self.persist_dir, f"{self.collection_name}.faiss")

    def _meta_path(self) -> str:
        # FIX: was .pkl — now .json (eliminates arbitrary-code-execution risk)
        return os.path.join(self.persist_dir, f"{self.collection_name}.json")

    # ── Persistence ───────────────────────────────────────────

    def _save(self) -> None:
        os.makedirs(self.persist_dir, exist_ok=True)
        faiss.write_index(self._index, self._index_path())
        # FIX: JSON instead of pickle
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "documents": self._documents,
                    "metadatas": self._metadatas,
                    "ids": self._ids,
                },
                f,
                ensure_ascii=False,
            )

    def _load(self) -> None:
        idx_path = self._index_path()
        meta_path = self._meta_path()
        if not (os.path.exists(idx_path) and os.path.exists(meta_path)):
            return
        try:
            self._index = faiss.read_index(idx_path)
            # FIX: JSON instead of pickle
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._documents = data["documents"]
            self._metadatas = data["metadatas"]
            self._ids = data["ids"]
            logger.info("Loaded %d docs from disk", len(self._documents))
        except Exception as exc:
            logger.error("Failed to load vector store from disk: %s — starting fresh", exc)
            self._index = None
            self._documents = []
            self._metadatas = []
            self._ids = []

    # ── Core operations ───────────────────────────────────────

    def _embed(self, texts: List[str]) -> np.ndarray:
        vecs = self.encoder.encode(texts, normalize_embeddings=True)
        return np.array(vecs, dtype=np.float32)

    def add(self, documents: List[str], metadatas: List[Dict], ids: List[str]) -> None:
        """Upsert documents. Silently skips IDs already present."""
        existing = set(self._ids)
        new_docs, new_metas, new_ids = [], [], []
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            if doc_id not in existing:
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

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict] = None,
    ) -> Dict:
        """Semantic search. Returns dict in ChromaDB-compatible shape."""
        if self.count() == 0:
            return {"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]}

        query_vec = self._embed([query_text])
        k = min(n_results * 3, self.count())  # oversample then filter
        scores, indices = self._index.search(query_vec, k)

        docs, metas, result_ids, dists = [], [], [], []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            meta = self._metadatas[idx]
            if where and not all(meta.get(wk) == wv for wk, wv in where.items()):
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

    def count(self) -> int:
        return self._index.ntotal if self._index is not None else 0

    def reset(self) -> None:
        self._index = faiss.IndexFlatIP(self.dim)
        self._documents = []
        self._metadatas = []
        self._ids = []
        self._save()
        logger.info("VectorStore reset")
