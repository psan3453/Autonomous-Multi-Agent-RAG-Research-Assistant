"""
Embedding service using local BGE (BAAI/bge-small-en-v1.5) via Sentence Transformers.
Lightweight, high-performance CPU inference with cosine-normalized vectors.
"""

import os
from typing import List, Union
import numpy as np
from config import EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION

_GLOBAL_EMBEDDER = None


class BGEEmbeddingService:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                # Use cached weights without outbound network calls
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device="cpu")
            except Exception as e:
                # Fallback to online if offline load failed
                try:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                    os.environ.pop("TRANSFORMERS_OFFLINE", None)
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self.model_name, device="cpu")
                except Exception as inner_e:
                    raise RuntimeError(
                        f"Failed to load embedding model '{self.model_name}': {str(inner_e)}"
                    )

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate normalized vector embeddings for a list of text strings."""
        if not texts:
            return np.empty((0, EMBEDDING_DIMENSION), dtype=np.float32)

        self._load_model()
        # BGE models benefit from instruction prefix for queries, but standard representation for documents
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True
        )
        return embeddings.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single search query (shape: 1, dim)."""
        self._load_model()
        # BGE query instruction format: "Represent this sentence for searching relevant passages: "
        query_text = f"Represent this sentence for searching relevant passages: {query}"
        emb = self._model.encode(
            [query_text],
            normalize_embeddings=True,
            convert_to_numpy=True
        )
        return emb.astype(np.float32)


def get_embedder() -> BGEEmbeddingService:
    """Singleton getter for the BGE embedding service."""
    global _GLOBAL_EMBEDDER
    if _GLOBAL_EMBEDDER is None:
        _GLOBAL_EMBEDDER = BGEEmbeddingService()
    return _GLOBAL_EMBEDDER
