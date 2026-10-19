"""Post persistence. SQLite stays here, not in services or HTTP handlers."""

from app.db.database import get_connection
from app.domain.models import Post


def list_posts() -> list[Post]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, content, created_at FROM post ORDER BY id"
        ).fetchall()
    return [
        Post(
            id=row["id"],
            user_id=row["user_id"],
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
