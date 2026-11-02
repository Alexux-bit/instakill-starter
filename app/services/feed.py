"""Application service for the home feed.

Coordinates candidate selection, signals, and `rank_feed`. No HTTP and no SQL.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import Post
from app.learned import build_features, predict
from app.ranking import (
    DEFAULT_WEIGHTS,
    FeedCandidate,
    FeedSignals,
    rank_feed,
)
from app.repositories.posts import list_posts
from app.repositories.social import (
    like_counts_by_post,
    like_counts_by_post_since,
    list_followee_ids,
    list_liked_post_ids,
    viewer_likes_by_author,
)
from app.repositories.users import get_user

FOR_YOU = "for_you"
CHRONOLOGICAL = "chronological"
LEARNED = "learned"
STRATEGIES = frozenset({FOR_YOU, CHRONOLOGICAL, LEARNED})


class UserNotFoundError(LookupError):
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(f"User {user_id} not found.")


class LearnedModelUnavailable(RuntimeError):
    pass


class FeedItem(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    post_id: int
    user_id: int
    content: str
    created_at: datetime
    score: float | None = None


class FeedResponse(BaseModel):
    user_id: int
    strategy: str
    results: list[FeedItem] = Field(default_factory=list)


def _as_candidate(post: Post) -> FeedCandidate | None:
    if post.id is None or post.created_at is None:
        return None
    created = post.created_at
    if created.tzinfo is not None:
        created = created.astimezone(timezone.utc).replace(tzinfo=None)
    return FeedCandidate(
        post_id=post.id,
        author_id=post.user_id,
        content=post.content,
        created_at=created,
        genres=tuple(post.genres),
    )


def _select_candidates(
    viewer_id: int,
    posts: list[Post],
    followee_ids: set[int],
    liked_post_ids: set[int],
) -> list[FeedCandidate]:
    """Exclude the viewer's own posts and posts they already liked.

    Followed authors are the candidate pool. If the viewer follows nobody,
    fall back to every remaining post (cold-start discovery).
    """
    selected: list[FeedCandidate] = []
    for post in posts:
        if post.id is None or post.user_id == viewer_id or post.id in liked_post_ids:
            continue
        if followee_ids and post.user_id not in followee_ids:
            continue
        candidate = _as_candidate(post)
        if candidate is not None:
            selected.append(candidate)
    return selected


def _chronological(candidates: list[FeedCandidate], limit: int) -> list[FeedItem]:
    ordered = sorted(candidates, key=lambda item: (-item.created_at.timestamp(), item.post_id))
    return [
        FeedItem(
            post_id=item.post_id,
            user_id=item.author_id,
            content=item.content,
            created_at=item.created_at,
        )
        for item in ordered[:limit]
    ]


def build_feed(
    user_id: int,
    limit: int,
    strategy: str,
    *,
    now: datetime | None = None,
    weights: dict[str, float] | None = None,
    learned_model: Mapping[str, np.ndarray] | None = None,
) -> FeedResponse:
    if get_user(user_id) is None:
        raise UserNotFoundError(user_id)

    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is not None:
        clock = clock.astimezone(timezone.utc).replace(tzinfo=None)

    followee_ids = list_followee_ids(user_id)
    liked_post_ids = list_liked_post_ids(user_id)
    posts = list_posts()
    candidates = _select_candidates(user_id, posts, followee_ids, liked_post_ids)

    if strategy == CHRONOLOGICAL:
        return FeedResponse(
            user_id=user_id,
            strategy=strategy,
            results=_chronological(candidates, limit),
        )

    if strategy == LEARNED:
        if learned_model is None:
            raise LearnedModelUnavailable("The learned feed model is unavailable.")
        lifetime_likes = like_counts_by_post()
        recent_cutoff = clock - timedelta(days=int(learned_model["popularity_days"]))
        recent_likes = like_counts_by_post_since(recent_cutoff)
        features = build_features(
            candidates,
            posts,
            liked_post_ids,
            len(liked_post_ids),
            lifetime_likes,
            recent_likes,
            clock,
            learned_model,
        )
        scores = predict(learned_model, features)
        post_ids = np.fromiter(
            (candidate.post_id for candidate in candidates),
            dtype=np.int64,
            count=len(candidates),
        )
        order = np.lexsort((post_ids, -scores))[:limit]
        results = [
            FeedItem(
                post_id=candidates[int(index)].post_id,
                user_id=candidates[int(index)].author_id,
                content=candidates[int(index)].content,
                created_at=candidates[int(index)].created_at,
                score=float(scores[index]),
            )
            for index in order
        ]
        return FeedResponse(user_id=user_id, strategy=strategy, results=results)

    like_counts = like_counts_by_post()
    likes_by_author = viewer_likes_by_author(user_id)
    signals = FeedSignals(
        followed_author_ids=frozenset(followee_ids),
        likes_by_author=likes_by_author,
        viewer_like_total=sum(likes_by_author.values()),
        like_counts=like_counts,
        max_like_count=max(like_counts.values(), default=0),
    )
    ranked = rank_feed(
        candidates,
        signals,
        clock,
        weights if weights is not None else DEFAULT_WEIGHTS,
        limit,
    )
    results = [
        FeedItem(
            post_id=item.post.post_id,
            user_id=item.post.author_id,
            content=item.post.content,
            created_at=item.post.created_at,
            score=item.score,
        )
        for item in ranked
    ]
    return FeedResponse(user_id=user_id, strategy=strategy, results=results)
