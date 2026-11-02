"""NumPy-only loading, feature construction, and prediction for the learned feed."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from app.domain.models import Post
from app.ranking import FeedCandidate

FEATURES = (
    "freshness",
    "affinity",
    "popularity",
    "activity",
    "lifetime",
    "age",
)
MODEL_PATH = Path(__file__).resolve().parent / "models" / "like_model.npz"
_SECONDS_PER_DAY = 86_400.0


def load_model(path: Path = MODEL_PATH) -> dict[str, np.ndarray]:
    """Load and validate the notebook-exported model once during app startup."""
    required = {
        "W1",
        "b1",
        "W2",
        "b2",
        "mu",
        "sd",
        "features",
        "half_life_days",
        "popularity_days",
        "activity_cap",
        "age_cap_days",
    }
    with np.load(path, allow_pickle=False) as archive:
        missing = required.difference(archive.files)
        if missing:
            raise ValueError(f"Learned model is missing arrays: {sorted(missing)}")
        model = {name: archive[name].copy() for name in required}

    if tuple(str(name) for name in model["features"].tolist()) != FEATURES:
        raise ValueError("Learned model feature order does not match the feed contract.")
    if model["W1"].shape != (6, 15) or model["b1"].shape != (15,):
        raise ValueError("Learned model hidden-layer arrays have invalid shapes.")
    if model["W2"].shape != (15, 1) or model["b2"].shape != (1,):
        raise ValueError("Learned model output-layer arrays have invalid shapes.")
    if model["mu"].shape != (6,) or model["sd"].shape != (6,):
        raise ValueError("Learned model scaler arrays have invalid shapes.")
    numeric_arrays = ("W1", "b1", "W2", "b2", "mu", "sd")
    if any(not np.isfinite(model[name]).all() for name in numeric_arrays):
        raise ValueError("Learned model contains non-finite parameters.")
    if np.any(model["sd"] <= 0):
        raise ValueError("Learned model standard deviations must be positive.")
    for name in ("half_life_days", "popularity_days", "activity_cap", "age_cap_days"):
        if int(model[name]) <= 0:
            raise ValueError(f"Learned model constant '{name}' must be positive.")
    return model


def predict(model: Mapping[str, np.ndarray], features: np.ndarray) -> np.ndarray:
    """Predict P(like) for an (n, 6) feature matrix without I/O or global state."""
    values = np.asarray(features, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(FEATURES):
        raise ValueError("features must be a 2-D matrix with exactly 6 columns.")
    if values.shape[0] == 0:
        return np.zeros(0, dtype=np.float64)

    standardized = (values - model["mu"]) / model["sd"]
    hidden = np.tanh(standardized @ model["W1"] + model["b1"])
    logits = (hidden @ model["W2"] + model["b2"])[:, 0]
    probabilities = np.empty_like(logits)
    positive = logits >= 0
    probabilities[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    exponentials = np.exp(logits[~positive])
    probabilities[~positive] = exponentials / (1.0 + exponentials)
    return probabilities


def _epoch_seconds(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.timestamp()


def build_features(
    candidates: Sequence[FeedCandidate],
    all_posts: Sequence[Post],
    liked_post_ids: set[int],
    total_user_likes: int,
    lifetime_likes: Mapping[int, int],
    recent_likes: Mapping[int, int],
    now: datetime,
    model: Mapping[str, np.ndarray],
) -> np.ndarray:
    """Build the notebook's six signals for all candidates in one feature matrix."""
    count = len(candidates)
    if count == 0:
        return np.zeros((0, len(FEATURES)), dtype=np.float64)

    genre_names = sorted({genre for post in all_posts for genre in post.genres})
    genre_index = {genre: index for index, genre in enumerate(genre_names)}
    candidate_genres = np.zeros((count, len(genre_names)), dtype=np.float64)
    candidate_rows: list[int] = []
    candidate_columns: list[int] = []
    for row, candidate in enumerate(candidates):
        for genre in candidate.genres:
            candidate_rows.append(row)
            candidate_columns.append(genre_index[genre])
    if candidate_rows:
        candidate_genres[candidate_rows, candidate_columns] = 1.0

    user_genre_counts = np.zeros(len(genre_names), dtype=np.float64)
    if genre_names and liked_post_ids:
        liked_genres = [
            genre_index[genre]
            for post in all_posts
            if post.id in liked_post_ids
            for genre in post.genres
        ]
        if liked_genres:
            np.add.at(user_genre_counts, np.asarray(liked_genres, dtype=np.int64), 1.0)
    user_genre_total = user_genre_counts.sum()
    candidate_genre_counts = candidate_genres.sum(axis=1)
    affinity_numerator = candidate_genres @ user_genre_counts
    affinity = np.zeros(count, dtype=np.float64)
    affinity_denominator = user_genre_total * candidate_genre_counts
    np.divide(
        affinity_numerator,
        affinity_denominator,
        out=affinity,
        where=affinity_denominator > 0,
    )

    now_seconds = _epoch_seconds(now)
    created_seconds = np.fromiter(
        (_epoch_seconds(candidate.created_at) for candidate in candidates),
        dtype=np.float64,
        count=count,
    )
    age_days = (now_seconds - created_seconds) / _SECONDS_PER_DAY
    half_life_days = float(model["half_life_days"])
    freshness = np.power(0.5, age_days / half_life_days)

    post_ids = np.fromiter(
        (candidate.post_id for candidate in candidates), dtype=np.int64, count=count
    )
    recent_values = np.fromiter(
        (recent_likes.get(int(post_id), 0) for post_id in post_ids),
        dtype=np.float64,
        count=count,
    )
    lifetime_values = np.fromiter(
        (lifetime_likes.get(int(post_id), 0) for post_id in post_ids),
        dtype=np.float64,
        count=count,
    )
    popularity = recent_values / max(float(max(recent_likes.values(), default=0)), 1.0)
    lifetime_denominator = np.log1p(
        max(float(max(lifetime_likes.values(), default=0)), 1.0)
    )
    lifetime = np.log1p(lifetime_values) / lifetime_denominator
    activity = min(
        1.0,
        np.log1p(total_user_likes) / np.log1p(float(model["activity_cap"])),
    )
    age = np.minimum(1.0, age_days / float(model["age_cap_days"]))
    return np.column_stack(
        (freshness, affinity, popularity, np.full(count, activity), lifetime, age)
    )
