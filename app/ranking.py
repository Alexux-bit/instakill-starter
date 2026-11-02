"""Pure feed ranking: score candidates and keep a heap-based top-k.

`rank_feed` takes `now` as an argument, performs no I/O, and does not mutate inputs.
"""

from __future__ import annotations

import heapq
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

HALF_LIFE_HOURS = 48.0

# Social feeds should prefer people you chose, then recency, then a light global boost.
# Equal (1, 1, 1) weights from the lab let popularity flatten every user's feed;
# these defaults keep affinity strongest and popularity from collapsing the ranking.
DEFAULT_WEIGHTS: dict[str, float] = {
    "freshness": 1.4,
    "affinity": 2.2,
    "popularity": 0.8,
}


@dataclass(frozen=True)
class FeedCandidate:
    post_id: int
    author_id: int
    content: str
    created_at: datetime
    genres: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedSignals:
    followed_author_ids: frozenset[int]
    likes_by_author: Mapping[int, int]
    viewer_like_total: int
    like_counts: Mapping[int, int]
    max_like_count: int


@dataclass(frozen=True)
class ScoredPost:
    post: FeedCandidate
    score: float


def freshness(created_at: datetime, now: datetime) -> float:
    """1.0 for a brand-new post, 0.5 after HALF_LIFE_HOURS, decaying after that."""
    age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
    return 0.5 ** (age_hours / HALF_LIFE_HOURS)


def affinity(author_id: int, signals: FeedSignals) -> float:
    """Follow bonus plus how often the viewer already liked this author, in [0, 1]."""
    follow_bonus = 1.0 if author_id in signals.followed_author_ids else 0.0
    if signals.viewer_like_total <= 0:
        like_share = 0.0
    else:
        like_share = signals.likes_by_author.get(author_id, 0) / signals.viewer_like_total
    return (follow_bonus + like_share) / 2.0


def popularity(post_id: int, signals: FeedSignals) -> float:
    """Likes on this post divided by the most-liked post (0 if nobody liked anything)."""
    if signals.max_like_count <= 0:
        return 0.0
    return signals.like_counts.get(post_id, 0) / signals.max_like_count


def score_candidate(
    candidate: FeedCandidate,
    signals: FeedSignals,
    now: datetime,
    weights: Mapping[str, float],
) -> float:
    return (
        weights.get("freshness", 0.0) * freshness(candidate.created_at, now)
        + weights.get("affinity", 0.0) * affinity(candidate.author_id, signals)
        + weights.get("popularity", 0.0) * popularity(candidate.post_id, signals)
    )


def rank_feed(
    candidates: Sequence[FeedCandidate],
    signals: FeedSignals,
    now: datetime,
    weights: Mapping[str, float],
    limit: int,
) -> list[ScoredPost]:
    """Return up to `limit` candidates by descending score, then ascending post_id."""
    if limit <= 0:
        return []

    heap: list[tuple[float, int, FeedCandidate]] = []
    for candidate in candidates:
        score = score_candidate(candidate, signals, now, weights)
        item = (score, -candidate.post_id, candidate)
        if len(heap) < limit:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)

    ordered = sorted(heap, key=lambda row: (-row[0], -row[1]))
    return [ScoredPost(post=row[2], score=row[0]) for row in ordered]
