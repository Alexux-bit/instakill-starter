"""HTTP endpoints for user CRUD."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import User
from app.repositories.posts import list_posts
from app.repositories.users import (
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)

router = APIRouter(tags=["users"])


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=80)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username must not be empty.")
        return normalized


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username must not be empty.")
        return normalized


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
def post_user(payload: UserCreate) -> User:
    try:
        return create_user(payload.username)
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed: user.username" not in str(error):
            raise
        raise HTTPException(status_code=409, detail="Username already exists.") from None


@router.get("/users", response_model=list[User])
def get_users(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    return list_users(limit, offset)


@router.get("/users/{user_id}", response_model=User)
def get_user_by_id(user_id: int) -> User:
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, payload: UserPatch) -> User:
    if not payload.model_fields_set or payload.username is None:
        raise HTTPException(
            status_code=422,
            detail="At least one valid user field must be provided.",
        )
    try:
        user = update_user(user_id, payload.username)
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed: user.username" not in str(error):
            raise
        raise HTTPException(status_code=409, detail="Username already exists.") from None
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(user_id: int, request: Request) -> Response:
    if get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    deleted_post_ids = {
        post.id
        for post in list_posts()
        if post.user_id == user_id and post.id is not None
    }
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    request.app.state.search_index.remove_posts(deleted_post_ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
