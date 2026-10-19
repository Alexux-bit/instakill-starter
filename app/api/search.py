"""HTTP edge for semantic search: query parsing and response serialization."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.search import SearchResponse, search_posts

router = APIRouter()

MIN_LIMIT = 1
MAX_LIMIT = 20


@router.get("/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str | None = Query(default=None),
    limit: int = Query(default=10),
) -> SearchResponse:
    if q is None or not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'q' must be a non-empty string.",
        )
    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'limit' must be an integer between 1 and 20.",
        )

    return search_posts(
        q.strip(),
        limit,
        index=request.app.state.search_index,
        encoder=request.app.state.encoder,
    )
