"""User persistence. SQLite stays here, not in services or HTTP handlers."""

from app.db.database import get_connection
from app.domain.models import User


def create_user(username: str) -> User:
    with get_connection() as conn:
        cursor = conn.execute("INSERT INTO user (username) VALUES (?)", (username,))
        row = conn.execute(
            "SELECT id, username, created_at FROM user WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return User(id=row["id"], username=row["username"], created_at=row["created_at"])


def get_user(user_id: int) -> User | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, created_at FROM user WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return User(id=row["id"], username=row["username"], created_at=row["created_at"])


def list_users(limit: int, offset: int) -> list[User]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, username, created_at FROM user ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [
        User(id=row["id"], username=row["username"], created_at=row["created_at"])
        for row in rows
    ]


def update_user(user_id: int, username: str) -> User | None:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE user SET username = ? WHERE id = ?",
            (username, user_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, username, created_at FROM user WHERE id = ?",
            (user_id,),
        ).fetchone()
    return User(id=row["id"], username=row["username"], created_at=row["created_at"])


def delete_user(user_id: int) -> bool:
    with get_connection() as conn:
        conn.execute(
            'DELETE FROM "like" WHERE user_id = ? OR post_id IN '
            "(SELECT id FROM post WHERE user_id = ?)",
            (user_id, user_id),
        )
        conn.execute(
            "DELETE FROM follow WHERE follower_id = ? OR followee_id = ?",
            (user_id, user_id),
        )
        conn.execute("DELETE FROM post WHERE user_id = ?", (user_id,))
        cursor = conn.execute("DELETE FROM user WHERE id = ?", (user_id,))
    return cursor.rowcount > 0
