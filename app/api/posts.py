"""HTTP endpoints for post CRUD."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import Post
from app.repositories.posts import (
    create_post,
    delete_post,
    get_post,
    list_posts_page,
    update_post,
)
from app.repositories.users import get_user
from app.services.posts import (
    MAX_POST_CONTENT_LENGTH,
    PostCompositionError,
    compose_post,
)

router = APIRouter(tags=["posts"])


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    content: str
    genres: list[str] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Post content must not be empty.")
        if len(normalized) > MAX_POST_CONTENT_LENGTH:
            raise ValueError(
                f"Post content must be at most {MAX_POST_CONTENT_LENGTH} characters."
            )
        return normalized


class PostPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = None
    genres: list[str] | None = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Post content must not be empty.")
        if len(normalized) > MAX_POST_CONTENT_LENGTH:
            raise ValueError(
                f"Post content must be at most {MAX_POST_CONTENT_LENGTH} characters."
            )
        return normalized


@router.post("/posts", response_model=Post, status_code=status.HTTP_201_CREATED)
def post_post(payload: PostCreate, request: Request) -> Post:
    author = get_user(payload.user_id)
    if author is None:
        raise HTTPException(status_code=404, detail="User not found.")
    try:
        draft = compose_post(author, payload.content)
    except PostCompositionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    draft.genres = payload.genres
    post = create_post(draft)
    request.app.state.search_index.add_post(post, request.app.state.encoder)
    return post


@router.get("/posts", response_model=list[Post])
def get_posts(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Post]:
    return list_posts_page(limit, offset)


@router.get("/posts/{post_id}", response_model=Post)
def get_post_by_id(post_id: int) -> Post:
    post = get_post(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    return post


@router.patch("/posts/{post_id}", response_model=Post)
def patch_post(post_id: int, payload: PostPatch, request: Request) -> Post:
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=422,
            detail="At least one post field must be provided.",
        )
    if "content" in payload.model_fields_set and payload.content is None:
        raise HTTPException(status_code=422, detail="Post content must not be null.")
    if "genres" in payload.model_fields_set and payload.genres is None:
        raise HTTPException(status_code=422, detail="Post genres must not be null.")
    post = update_post(
        post_id,
        content=payload.content,
        genres=payload.genres,
    )
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    request.app.state.search_index.update_post(post, request.app.state.encoder)
    return post


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_post(post_id: int, request: Request) -> Response:
    post = get_post(post_id)
    if post is None or not delete_post(post_id):
        raise HTTPException(status_code=404, detail="Post not found.")
    request.app.state.search_index.remove_posts({post_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
