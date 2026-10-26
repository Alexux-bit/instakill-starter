"""Seeds the InstaKill database with users, posts, follows, and likes."""
from app.db.database import get_connection, init_db

USERS = ["alice", "bob", "carol", "dave", "erin", "frank"]

# (author_id, content, created_at) — staggered times so chronological order is non-trivial.
POSTS = [
    (1, "hello world, this is my first post", "2026-10-19 08:00:00"),
    (1, "does anyone else think the feed is chronological only? boring", "2026-10-24 12:00:00"),
    (2, "just shipped a cosine similarity search, feels great", "2026-10-21 09:30:00"),
    (2, "shipping notes: heap-based top-k is enough for a small feed", "2026-10-25 18:00:00"),
    (3, "spam spam spam buy now click here", "2026-10-22 11:00:00"),
    (4, "benchmarking my ranker against popularity baseline today", "2026-10-23 15:00:00"),
    (4, "affinity should beat raw like count or everyone sees the same hits", "2026-10-26 10:00:00"),
    (5, "red-team week is going to be brutal, good luck everyone", "2026-10-18 20:00:00"),
    (5, "fresh posts should outrank week-old ones when scores tie on taste", "2026-10-26 16:00:00"),
]

# (follower_id, followee_id) — frank (6) follows nobody (cold start).
FOLLOWS = [
    (1, 2),
    (1, 4),
    (2, 1),
    (2, 3),
    (3, 4),
    (3, 5),
    (4, 1),
    (5, 2),
    (5, 3),
    (5, 4),
]

# (user_id, post_id) — ids match insert order on an empty database.
LIKES = [
    (1, 3),
    (1, 6),
    (2, 1),
    (2, 6),
    (3, 6),
    (3, 7),
    (4, 1),
    (5, 4),
    (5, 6),
    (6, 5),
]


def seed() -> None:
    init_db()
    with get_connection() as conn:
        for username in USERS:
            conn.execute(
                "INSERT OR IGNORE INTO user (username) VALUES (?)", (username,)
            )
        for user_id, content, created_at in POSTS:
            conn.execute(
                "INSERT INTO post (user_id, content, created_at) VALUES (?, ?, ?)",
                (user_id, content, created_at),
            )
        for follower_id, followee_id in FOLLOWS:
            conn.execute(
                """
                INSERT OR IGNORE INTO follow (follower_id, followee_id)
                VALUES (?, ?)
                """,
                (follower_id, followee_id),
            )
        for user_id, post_id in LIKES:
            conn.execute(
                """
                INSERT OR IGNORE INTO "like" (user_id, post_id)
                VALUES (?, ?)
                """,
                (user_id, post_id),
            )
        conn.commit()
    print(
        f"Seeded {len(USERS)} users, {len(POSTS)} posts, "
        f"{len(FOLLOWS)} follows, and {len(LIKES)} likes."
    )


if __name__ == "__main__":
    seed()
