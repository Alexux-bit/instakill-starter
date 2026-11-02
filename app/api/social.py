"""HTTP endpoints for follow and like relationships."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import User
from app.repositories.posts import get_post
from app.repositories.social import (
    add_follow,
    add_like,
    list_followers,
    list_following,
    remove_follow,
    remove_like,
)
from app.repositories.users import get_user

router = APIRouter(tags=["social"])


class FollowResponse(BaseModel):
    follower_id: int
    followee_id: int
    created_at: datetime


class LikeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    created_at: datetime | None = None


class LikeResponse(BaseModel):
    user_id: int
    post_id: int
    created_at: datetime


@router.post(
    "/users/{user_id}/following/{followee_id}",
    response_model=FollowResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_follow(
    user_id: int,
    followee_id: int,
    response: Response,
) -> FollowResponse:
    if get_user(user_id) is None or get_user(followee_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user_id == followee_id:
        raise HTTPException(status_code=400, detail="Users cannot follow themselves.")
    created_at, created = add_follow(user_id, followee_id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return FollowResponse(
        follower_id=user_id,
        followee_id=followee_id,
        created_at=created_at,
    )


@router.delete(
    "/users/{user_id}/following/{followee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_follow(user_id: int, followee_id: int) -> Response:
    if get_user(user_id) is None or get_user(followee_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if not remove_follow(user_id, followee_id):
        raise HTTPException(status_code=404, detail="Follow relationship not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/following", response_model=list[User])
def get_following(user_id: int) -> list[User]:
    if get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return [User(**user) for user in list_following(user_id)]


@router.get("/users/{user_id}/followers", response_model=list[User])
def get_followers(user_id: int) -> list[User]:
    if get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return [User(**user) for user in list_followers(user_id)]


@router.post(
    "/posts/{post_id}/likes",
    response_model=LikeResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_like(
    post_id: int,
    payload: LikeCreate,
    response: Response,
) -> LikeResponse:
    if get_user(payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if get_post(post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    created_at, created = add_like(payload.user_id, post_id, payload.created_at)
    if not created:
        response.status_code = status.HTTP_200_OK
    return LikeResponse(user_id=payload.user_id, post_id=post_id, created_at=created_at)


@router.delete(
    "/posts/{post_id}/likes/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_like(post_id: int, user_id: int) -> Response:
    if get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if get_post(post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    if not remove_like(user_id, post_id):
        raise HTTPException(status_code=404, detail="Like not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
