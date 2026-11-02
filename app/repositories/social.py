"""Follow and like persistence. SQLite stays here, not in services or HTTP handlers."""

from datetime import datetime, timezone

from app.db.database import get_connection


def add_follow(follower_id: int, followee_id: int) -> tuple[str, bool]:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO follow (follower_id, followee_id) VALUES (?, ?)",
            (follower_id, followee_id),
        )
        row = conn.execute(
            "SELECT created_at FROM follow WHERE follower_id = ? AND followee_id = ?",
            (follower_id, followee_id),
        ).fetchone()
    return row["created_at"], cursor.rowcount > 0


def remove_follow(follower_id: int, followee_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM follow WHERE follower_id = ? AND followee_id = ?",
            (follower_id, followee_id),
        )
    return cursor.rowcount > 0


def list_followee_ids(user_id: int) -> set[int]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT followee_id FROM follow WHERE follower_id = ?",
            (user_id,),
        ).fetchall()
    return {row["followee_id"] for row in rows}


def list_following(user_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.created_at
            FROM follow AS f JOIN user AS u ON u.id = f.followee_id
            WHERE f.follower_id = ? ORDER BY u.id
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_followers(user_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.created_at
            FROM follow AS f JOIN user AS u ON u.id = f.follower_id
            WHERE f.followee_id = ? ORDER BY u.id
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_liked_post_ids(user_id: int) -> set[int]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT post_id FROM "like" WHERE user_id = ?',
            (user_id,),
        ).fetchall()
    return {row["post_id"] for row in rows}


def add_like(
    user_id: int,
    post_id: int,
    created_at: datetime | None = None,
) -> tuple[str, bool]:
    if created_at is not None and created_at.tzinfo is not None:
        created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
    timestamp = None if created_at is None else created_at.strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        if timestamp is None:
            cursor = conn.execute(
                'INSERT OR IGNORE INTO "like" (user_id, post_id) VALUES (?, ?)',
                (user_id, post_id),
            )
        else:
            cursor = conn.execute(
                'INSERT OR IGNORE INTO "like" (user_id, post_id, created_at) '
                "VALUES (?, ?, ?)",
                (user_id, post_id, timestamp),
            )
        row = conn.execute(
            'SELECT created_at FROM "like" WHERE user_id = ? AND post_id = ?',
            (user_id, post_id),
        ).fetchone()
    return row["created_at"], cursor.rowcount > 0


def remove_like(user_id: int, post_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            'DELETE FROM "like" WHERE user_id = ? AND post_id = ?',
            (user_id, post_id),
        )
    return cursor.rowcount > 0


def like_counts_by_post() -> dict[int, int]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT post_id, COUNT(*) AS n FROM "like" GROUP BY post_id'
        ).fetchall()
    return {row["post_id"]: row["n"] for row in rows}


def like_counts_by_post_since(cutoff: datetime) -> dict[int, int]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT post_id, COUNT(*) AS n FROM "like" '
            "WHERE datetime(created_at) >= datetime(?) GROUP BY post_id",
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
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
