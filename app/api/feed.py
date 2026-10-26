"""HTTP edge for the home feed: query parsing and response serialization."""

from fastapi import APIRouter, HTTPException, Query

from app.services.feed import (
    STRATEGIES,
    FeedResponse,
    UserNotFoundError,
    build_feed,
)

router = APIRouter()

MIN_LIMIT = 1
MAX_LIMIT = 50
DEFAULT_LIMIT = 20
DEFAULT_STRATEGY = "for_you"


@router.get("/feed", response_model=FeedResponse, response_model_exclude_none=True)
def feed(
    user_id: int | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT),
    strategy: str = Query(default=DEFAULT_STRATEGY),
) -> FeedResponse:
    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'user_id' must be an integer.",
        )
    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'limit' must be an integer between 1 and 50.",
        )
    if strategy not in STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'strategy' must be 'for_you' or 'chronological'.",
        )
    try:
        return build_feed(user_id, limit, strategy)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found.") from None
