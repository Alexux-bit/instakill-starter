"""User persistence. SQLite stays here, not in services or HTTP handlers."""

from app.db.database import get_connection
from app.domain.models import User


def get_user(user_id: int) -> User | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, created_at FROM user WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return User(id=row["id"], username=row["username"], created_at=row["created_at"])
