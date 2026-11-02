from datetime import datetime, timedelta

import numpy as np

from app.domain.models import Post
from app.learned import build_features, load_model, predict
from app.ranking import FeedCandidate


def test_predict_matches_saved_forward_pass() -> None:
    model = load_model()
    features = np.array(
        [
            [0.8, 0.4, 0.2, 0.7, 0.5, 0.1],
            [0.2, 0.0, 0.9, 0.1, 0.8, 0.7],
        ],
        dtype=np.float64,
    )
    standardized = (features - model["mu"]) / model["sd"]
    hidden = np.tanh(standardized @ model["W1"] + model["b1"])
    logits = (hidden @ model["W2"] + model["b2"])[:, 0]
    expected = 1.0 / (1.0 + np.exp(-logits))

    np.testing.assert_allclose(predict(model, features), expected)
    assert predict(model, np.zeros((0, 6))).shape == (0,)


def test_build_features_uses_the_notebook_six_signals() -> None:
    model = load_model()
    now = datetime(2026, 10, 26, 12, 0, 0)
    candidate_created = now - timedelta(days=int(model["half_life_days"]))
    candidate = FeedCandidate(
        post_id=2,
        author_id=3,
        content="target",
        created_at=candidate_created,
        genres=("Comedy", "Drama"),
    )
    posts = [
        Post(
            id=1,
            user_id=2,
            content="liked",
            created_at=now - timedelta(days=10),
            genres=["Action", "Drama"],
        ),
        Post(
            id=2,
            user_id=3,
            content="target",
            created_at=candidate_created,
            genres=["Comedy", "Drama"],
        ),
    ]

    features = build_features(
        [candidate],
        posts,
        {1},
        total_user_likes=1,
        lifetime_likes={1: 4, 2: 1},
        recent_likes={1: 2, 2: 1},
        now=now,
        model=model,
    )
    expected_affinity = 1.0 / (2 * 2)
    expected = np.array(
        [
            [
                0.5,
                expected_affinity,
                0.5,
                np.log1p(1) / np.log1p(float(model["activity_cap"])),
                np.log1p(1) / np.log1p(4),
                float(model["half_life_days"]) / float(model["age_cap_days"]),
            ]
        ]
    )
    np.testing.assert_allclose(features, expected)


def test_learned_feed_returns_probability_scores(client) -> None:
    response = client.get(
        "/feed",
        params={"user_id": 6, "limit": 5, "strategy": "learned"},
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert results
    scores = [item["score"] for item in results]
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert scores == sorted(scores, reverse=True)


def test_learned_feed_is_unavailable_without_model(client) -> None:
    client.app.state.learned_model = None

    response = client.get("/feed", params={"user_id": 6, "strategy": "learned"})

    assert response.status_code == 503
    assert response.json()["detail"] == "The learned feed model is unavailable."
