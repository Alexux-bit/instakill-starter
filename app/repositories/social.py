"""Follow and like persistence. SQLite stays here, not in services or HTTP handlers."""

from app.db.database import get_connection


def list_followee_ids(user_id: int) -> set[int]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT followee_id FROM follow WHERE follower_id = ?",
            (user_id,),
        ).fetchall()
    return {row["followee_id"] for row in rows}


def list_liked_post_ids(user_id: int) -> set[int]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT post_id FROM "like" WHERE user_id = ?',
            (user_id,),
        ).fetchall()
    return {row["post_id"] for row in rows}


def like_counts_by_post() -> dict[int, int]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT post_id, COUNT(*) AS n FROM "like" GROUP BY post_id'
        ).fetchall()
    return {row["post_id"]: row["n"] for row in rows}


def viewer_likes_by_author(user_id: int) -> dict[int, int]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.user_id AS author_id, COUNT(*) AS n
            FROM "like" AS l
            JOIN post AS p ON p.id = l.post_id
            WHERE l.user_id = ?
            GROUP BY p.user_id
            """,
            (user_id,),
        ).fetchall()
    return {row["author_id"]: row["n"] for row in rows}
