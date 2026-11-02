"""Domain schema: User and Post. Pydantic models mirroring the SQL DDL in app/db/database.py."""
from datetime import datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    id: int | None = None
    username: str
    created_at: datetime | None = None


class Post(BaseModel):
    id: int | None = None
    user_id: int
    content: str
    created_at: datetime | None = None
    genres: list[str] = Field(default_factory=list)
