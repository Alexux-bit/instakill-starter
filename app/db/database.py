"""SQLite bootstrap for InstaKill. Uses the stdlib sqlite3 module (see R11)."""
import os
import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "instakill.db"


def get_db_path() -> Path:
    override = os.environ.get("INSTAKILL_DB_PATH")
    if override:
        return Path(override)
    return _DEFAULT_DB_PATH


DB_PATH = _DEFAULT_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS post (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    genres TEXT NOT NULL DEFAULT '[]',
    source_key TEXT
);

CREATE TABLE IF NOT EXISTS follow (
    follower_id INTEGER NOT NULL REFERENCES user(id),
    followee_id INTEGER NOT NULL REFERENCES user(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (follower_id, followee_id),
    CHECK (follower_id != followee_id)
);

CREATE TABLE IF NOT EXISTS "like" (
    user_id INTEGER NOT NULL REFERENCES user(id),
    post_id INTEGER NOT NULL REFERENCES post(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, post_id)
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        post_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(post)").fetchall()
        }
        if "genres" not in post_columns:
            conn.execute(
                "ALTER TABLE post ADD COLUMN genres TEXT NOT NULL DEFAULT '[]'"
            )
        if "source_key" not in post_columns:
            conn.execute("ALTER TABLE post ADD COLUMN source_key TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_post_source_key "
            "ON post(source_key)"
        )


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {get_db_path()}")
