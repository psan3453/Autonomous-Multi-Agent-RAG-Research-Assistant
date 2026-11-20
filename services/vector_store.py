"""
FAISS CPU Vector Store for local similarity search and metadata retrieval.
Uses Inner Product (Cosine Similarity on normalized BGE vectors).
Saves and loads indices and chunk metadata per research project.
"""

import os
import json
import pickle
from typing import List, Dict, Any, Optional
import numpy as np

from config import INDEXES_DIR, EMBEDDING_DIMENSION


class FAISSVectorStore:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.index_path = INDEXES_DIR / f"{project_id}.faiss"
        self.metadata_path = INDEXES_DIR / f"{project_id}_chunks.pkl"
        self.index = None
        self.chunks: List[Dict[str, Any]] = []

    def build_and_save(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> bool:
        """Build FAISS CPU index from embeddings and persist along with chunk metadata."""
        import faiss

        if len(chunks) == 0 or embeddings.shape[0] == 0:
            return False

        try:
            dim = embeddings.shape[1]
            # IndexFlatIP calculates inner product (cosine similarity for normalized vectors)
            index = faiss.IndexFlatIP(dim)
            index.add(embeddings)

            self.index = index
            self.chunks = chunks

            # Save to disk
            faiss.write_index(index, str(self.index_path))
            with open(self.metadata_path, "wb") as f:
                pickle.dump(chunks, f)

            return self.exists()
        except Exception:
            return False

    def load(self) -> bool:
        """Load FAISS index and chunk metadata from disk if available."""
        import faiss

        if not self.index_path.exists() or not self.metadata_path.exists():
            return False

        try:
            self.index = faiss.read_index(str(self.index_path))
            with open(self.metadata_path, "rb") as f:
                self.chunks = pickle.load(f)
            return True
        except Exception:
            return False

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        paper_id_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for top-k nearest chunks.
        Optionally filter results to a specific paper_id.
        """
        if self.index is None:
            if not self.load():
                return []

        # If filtering is needed, search across all available chunks to guarantee retrieval
        search_k = len(self.chunks) if paper_id_filter else min(len(self.chunks), top_k)
        if search_k <= 0:
            return []

        scores, indices = self.index.search(query_embedding, search_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = dict(self.chunks[idx])
            chunk["score"] = float(score)

            if paper_id_filter and chunk.get("paper_id") != paper_id_filter:
                continue

            results.append(chunk)
            if len(results) >= top_k:
                break

        return results

    def get_all_chunks_for_paper(self, paper_id: str) -> List[Dict[str, Any]]:
        """Retrieve all chunks belonging to a specific paper."""
        if not self.chunks:
            self.load()
        return [c for c in self.chunks if c.get("paper_id") == paper_id]

    def exists(self) -> bool:
        return self.index_path.exists() and self.metadata_path.exists()
