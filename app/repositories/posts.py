"""Post persistence. SQLite stays here, not in services or HTTP handlers."""

import json
import sqlite3

from app.db.database import get_connection
from app.domain.models import Post


def _post_from_row(row: sqlite3.Row) -> Post:
    return Post(
        id=row["id"],
        user_id=row["user_id"],
        content=row["content"],
        created_at=row["created_at"],
        genres=json.loads(row["genres"]),
    )


def _normalize_genres(genres: list[str]) -> list[str]:
    return sorted({genre.strip() for genre in genres if genre.strip()})


def list_posts() -> list[Post]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, content, created_at, genres FROM post ORDER BY id"
        ).fetchall()
    return [_post_from_row(row) for row in rows]


def get_post(post_id: int) -> Post | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, user_id, content, created_at, genres FROM post WHERE id = ?",
            (post_id,),
        ).fetchone()
    return None if row is None else _post_from_row(row)


def list_posts_page(limit: int, offset: int) -> list[Post]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, content, created_at, genres "
            "FROM post ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_post_from_row(row) for row in rows]


def create_post(post: Post, *, source_key: str | None = None) -> Post:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO post (user_id, content, genres, source_key)
            VALUES (?, ?, ?, ?)
            """,
            (
                post.user_id,
                post.content,
                json.dumps(_normalize_genres(post.genres)),
                source_key,
            ),
        )
        row = conn.execute(
            "SELECT id, user_id, content, created_at, genres FROM post WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _post_from_row(row)


def update_post(
    post_id: int,
    *,
    content: str | None = None,
    genres: list[str] | None = None,
) -> Post | None:
    assignments: list[str] = []
    values: list[object] = []
    if content is not None:
        assignments.append("content = ?")
        values.append(content)
    if genres is not None:
        assignments.append("genres = ?")
        values.append(json.dumps(_normalize_genres(genres)))
    if not assignments:
        return get_post(post_id)

    values.append(post_id)
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE post SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, user_id, content, created_at, genres FROM post WHERE id = ?",
            (post_id,),
        ).fetchone()
    return _post_from_row(row)


def delete_post(post_id: int) -> bool:
    with get_connection() as conn:
        conn.execute('DELETE FROM "like" WHERE post_id = ?', (post_id,))
        cursor = conn.execute("DELETE FROM post WHERE id = ?", (post_id,))
    return cursor.rowcount > 0
