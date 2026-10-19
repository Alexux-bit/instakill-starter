"""Pure vector retrieval: cosine similarity and deterministic top-k.

These functions take arrays only. They must not load a model, read the
database, or format HTTP responses.
"""

from __future__ import annotations

import numpy as np

_ZERO_DENOMINATOR = 0.0


def cosine_similarity(query_vector: np.ndarray, corpus_vectors: np.ndarray) -> np.ndarray:
    """Return one cosine score for every row in `corpus_vectors`.

    A zero query or corpus row yields 0.0 rather than NaN or infinity.
    """
    query = np.asarray(query_vector, dtype=np.float64).reshape(-1)
    corpus = np.asarray(corpus_vectors, dtype=np.float64)
    if corpus.ndim != 2:
        raise ValueError("corpus_vectors must be a 2-D matrix")
    if corpus.shape[0] == 0:
        return np.zeros(0, dtype=np.float64)
    if corpus.shape[1] != query.shape[0]:
        raise ValueError("query and corpus vectors must have the same dimension")

    dots = corpus @ query
    query_norm = np.linalg.norm(query)
    corpus_norms = np.linalg.norm(corpus, axis=1)
    denominators = query_norm * corpus_norms
    scores = np.zeros(corpus.shape[0], dtype=np.float64)
    nonzero = denominators > _ZERO_DENOMINATOR
    scores[nonzero] = dots[nonzero] / denominators[nonzero]
    return scores


def stable_top_k(scores: np.ndarray, post_ids: np.ndarray, k: int) -> np.ndarray:
    """Return corpus indices ordered by score descending, then post_id ascending."""
    if k <= 0 or scores.size == 0:
        return np.zeros(0, dtype=np.int64)
    k = min(int(k), scores.size)
    order = np.lexsort((np.asarray(post_ids), -np.asarray(scores)))
    return order[:k]


def retrieve_top_k(
    query_vector: np.ndarray,
    corpus_vectors: np.ndarray,
    post_ids: np.ndarray,
    k: int,
) -> list[tuple[int, float]]:
    """Return ordered `(corpus_index, score)` pairs for the top `k` hits."""
    scores = cosine_similarity(query_vector, corpus_vectors)
    indices = stable_top_k(scores, post_ids, k)
    return [(int(index), float(scores[index])) for index in indices]
