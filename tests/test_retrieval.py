import numpy as np

from app.retrieval import cosine_similarity, retrieve_top_k, stable_top_k


def test_cosine_similarity_matches_lab_fixture() -> None:
    query = np.array([1.0, 0.0])
    corpus = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.0], [0.0, 0.0]])
    scores = cosine_similarity(query, corpus)
    assert np.allclose(scores, [1.0, 0.0, 1.0, 0.0])
    assert np.isfinite(cosine_similarity(np.array([0.0, 0.0]), corpus)).all()


def test_stable_top_k_breaks_ties_by_ascending_post_id() -> None:
    indices = stable_top_k(np.array([0.7, 0.9, 0.9]), np.array([7, 5, 2]), k=2)
    assert list(indices) == [2, 1]


def test_retrieve_top_k_returns_ordered_index_score_pairs() -> None:
    query = np.array([1.0, 0.0])
    corpus = np.array([[0.0, 1.0], [1.0, 0.0], [1.0, 0.0]])
    post_ids = np.array([10, 8, 3])
    hits = retrieve_top_k(query, corpus, post_ids, k=2)
    assert hits[0][0] == 2
    assert hits[1][0] == 1
    assert hits[0][1] >= hits[1][1]
