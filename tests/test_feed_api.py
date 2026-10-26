def test_feed_for_you_over_seeded_database(client) -> None:
    response = client.get("/feed", params={"user_id": 1, "limit": 20, "strategy": "for_you"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == 1
    assert payload["strategy"] == "for_you"
    assert payload["results"]

    post_ids = []
    scores = []
    for item in payload["results"]:
        assert {"post_id", "user_id", "content", "created_at", "score"} <= set(item)
        assert item["user_id"] != 1
        assert item["post_id"] not in {1, 2, 3, 6}
        post_ids.append(item["post_id"])
        scores.append(item["score"])
    assert scores == sorted(scores, reverse=True)
    for i in range(len(scores) - 1):
        if scores[i] == scores[i + 1]:
            assert post_ids[i] < post_ids[i + 1]


def test_feed_chronological_omits_score_and_uses_newest_first(client) -> None:
    response = client.get(
        "/feed", params={"user_id": 1, "limit": 20, "strategy": "chronological"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "chronological"
    created = [item["created_at"] for item in payload["results"]]
    assert created == sorted(created, reverse=True)
    assert all("score" not in item for item in payload["results"])


def test_feed_unknown_user_returns_404(client) -> None:
    response = client.get("/feed", params={"user_id": 999})
    assert response.status_code == 404


def test_feed_rejects_missing_user_id(client) -> None:
    response = client.get("/feed", params={"limit": 5})
    assert response.status_code == 400
    assert "user_id" in response.json()["detail"]


def test_feed_rejects_bad_limit_and_strategy(client) -> None:
    too_large = client.get("/feed", params={"user_id": 1, "limit": 51})
    unknown = client.get("/feed", params={"user_id": 1, "strategy": "random"})
    assert too_large.status_code == 400
    assert unknown.status_code == 400
