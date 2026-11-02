import sqlite3

from app.db.database import init_db
from app.repositories.posts import list_posts


def test_init_db_adds_genres_and_source_key_to_existing_post_table(
    tmp_path, monkeypatch
) -> None:
    database_path = tmp_path / "existing.db"
    monkeypatch.setenv("INSTAKILL_DB_PATH", str(database_path))
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE post (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES user(id),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO user (username) VALUES ('old-user');
        INSERT INTO post (user_id, content) VALUES (1, 'old post');
        """
    )
    connection.close()

    init_db()

    connection = sqlite3.connect(database_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(post)")}
    connection.close()
    assert {"genres", "source_key"} <= columns
    assert list_posts()[0].genres == []
