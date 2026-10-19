def test_search_returns_query_and_scored_hits(client) -> None:
    response = client.get("/search", params={"q": "cosine similarity", "limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "cosine similarity"
    assert 1 <= len(payload["results"]) <= 5
    scores = []
    post_ids = []
    for hit in payload["results"]:
        assert {"post_id", "user_id", "content", "score"} <= set(hit)
        assert isinstance(hit["post_id"], int)
        assert isinstance(hit["user_id"], int)
        assert isinstance(hit["content"], str)
        assert isinstance(hit["score"], float)
        scores.append(hit["score"])
        post_ids.append(hit["post_id"])
    assert scores == sorted(scores, reverse=True)
    for i in range(len(scores) - 1):
        if scores[i] == scores[i + 1]:
            assert post_ids[i] < post_ids[i + 1]


def test_search_trims_query(client) -> None:
    response = client.get("/search", params={"q": "  cosine  ", "limit": 1})
    assert response.status_code == 200
    assert response.json()["query"] == "cosine"


def test_search_rejects_missing_query(client) -> None:
    response = client.get("/search", params={"limit": 5})
    assert response.status_code == 400
    assert "q" in response.json()["detail"]


def test_search_rejects_empty_query(client) -> None:
    response = client.get("/search", params={"q": "   "})
    assert response.status_code == 400


def test_search_rejects_limit_out_of_range(client) -> None:
    too_small = client.get("/search", params={"q": "hello", "limit": 0})
    too_large = client.get("/search", params={"q": "hello", "limit": 21})
    assert too_small.status_code == 400
    assert too_large.status_code == 400
    assert "limit" in too_small.json()["detail"]
