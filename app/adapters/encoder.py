"""Text-encoding adapter. Model loading stays here, not in retrieval or HTTP."""

from __future__ import annotations

from typing import Protocol, Sequence

import numpy as np

MINILM_MODEL_NAME = "all-MiniLM-L6-v2"


class TextEncoder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return a float matrix with one row per input text."""


class MiniLMEncoder:
    """Loads `all-MiniLM-L6-v2` once and encodes text to normalized embeddings."""

    def __init__(self, model_name: str = MINILM_MODEL_NAME) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            dim = self._model.get_sentence_embedding_dimension()
            return np.zeros((0, dim), dtype=np.float64)
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float64)
