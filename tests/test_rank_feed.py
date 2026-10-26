import copy
from datetime import datetime

from app.ranking import DEFAULT_WEIGHTS, FeedCandidate, FeedSignals, rank_feed

NOW = datetime(2026, 10, 26, 18, 0, 0)


def _candidate(post_id: int, author_id: int, created_at: datetime) -> FeedCandidate:
    return FeedCandidate(
        post_id=post_id,
        author_id=author_id,
        content=f"post {post_id}",
        created_at=created_at,
    )


def _signals(**overrides) -> FeedSignals:
    values = dict(
        followed_author_ids=frozenset({2}),
        likes_by_author={2: 1},
        viewer_like_total=1,
        like_counts={1: 1, 2: 4, 3: 1},
        max_like_count=4,
    )
    values.update(overrides)
    return FeedSignals(**values)


def test_rank_feed_orders_by_descending_score() -> None:
    older = _candidate(1, 9, datetime(2026, 10, 1, 0, 0, 0))
    newer = _candidate(2, 2, datetime(2026, 10, 26, 12, 0, 0))
    ranked = rank_feed([older, newer], _signals(), NOW, DEFAULT_WEIGHTS, limit=2)
    assert [item.post.post_id for item in ranked] == [2, 1]
    assert ranked[0].score > ranked[1].score


def test_rank_feed_breaks_ties_by_ascending_post_id() -> None:
    first = _candidate(4, 2, datetime(2026, 10, 26, 12, 0, 0))
    second = _candidate(7, 2, datetime(2026, 10, 26, 12, 0, 0))
    ranked = rank_feed([second, first], _signals(), NOW, DEFAULT_WEIGHTS, limit=2)
    assert ranked[0].score == ranked[1].score
    assert [item.post.post_id for item in ranked] == [4, 7]


def test_rank_feed_is_deterministic() -> None:
    candidates = [
        _candidate(3, 9, datetime(2026, 10, 20, 0, 0, 0)),
        _candidate(1, 2, datetime(2026, 10, 25, 0, 0, 0)),
        _candidate(2, 2, datetime(2026, 10, 24, 0, 0, 0)),
    ]
    signals = _signals()
    first = rank_feed(candidates, signals, NOW, DEFAULT_WEIGHTS, limit=3)
    second = rank_feed(candidates, signals, NOW, DEFAULT_WEIGHTS, limit=3)
    assert [(item.post.post_id, item.score) for item in first] == [
        (item.post.post_id, item.score) for item in second
    ]


def test_rank_feed_does_not_mutate_inputs() -> None:
    candidates = [
        _candidate(1, 2, datetime(2026, 10, 25, 0, 0, 0)),
        _candidate(2, 9, datetime(2026, 10, 20, 0, 0, 0)),
    ]
    signals = _signals(like_counts={1: 2, 2: 1}, max_like_count=2)
    snapshot_candidates = copy.deepcopy(candidates)
    snapshot_signals = copy.deepcopy(signals)
    snapshot_weights = copy.deepcopy(DEFAULT_WEIGHTS)

    rank_feed(candidates, signals, NOW, DEFAULT_WEIGHTS, limit=1)

    assert candidates == snapshot_candidates
    assert signals == snapshot_signals
    assert DEFAULT_WEIGHTS == snapshot_weights


def test_rank_feed_respects_limit() -> None:
    candidates = [
        _candidate(i, 2, datetime(2026, 10, 20 + i, 0, 0, 0)) for i in range(1, 6)
    ]
    ranked = rank_feed(candidates, _signals(), NOW, DEFAULT_WEIGHTS, limit=2)
    assert len(ranked) == 2
