"""Import a bounded MovieLens latest-small sample from a local zip archive."""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import get_connection, init_db

MAX_USERS = 2_000
MAX_POSTS = 20_000
USER_PREFIX = "movielens-user-"
POST_PREFIX = "movielens:"


def _csv_reader(archive: zipfile.ZipFile, entry: str) -> csv.DictReader:
    return csv.DictReader(
        io.TextIOWrapper(archive.open(entry), encoding="utf-8", newline="")
    )


def _find_entry(archive: zipfile.ZipFile, filename: str) -> str:
    matches = [
        name for name in archive.namelist() if PurePosixPath(name).name == filename
    ]
    if len(matches) != 1:
        raise ValueError(f"Archive must contain exactly one {filename}.")
    return matches[0]


def _as_timestamp(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def seed(archive_path: Path) -> tuple[int, int, int]:
    if not archive_path.is_file():
        raise FileNotFoundError(f"MovieLens archive not found: {archive_path}")
    init_db()

    with zipfile.ZipFile(archive_path) as archive:
        ratings_entry = _find_entry(archive, "ratings.csv")
        movies_entry = _find_entry(archive, "movies.csv")
        movies: dict[int, tuple[str, list[str]]] = {}
        for row in _csv_reader(archive, movies_entry):
            movie_id = int(row["movieId"])
            genres = [
                genre
                for genre in row["genres"].split("|")
                if genre and genre != "(no genres listed)"
            ]
            movies[movie_id] = (row["title"], genres)

        first_seen: dict[int, int] = {}
        user_ids: set[int] = set()
        for row in _csv_reader(archive, ratings_entry):
            user_id = int(row["userId"])
            movie_id = int(row["movieId"])
            timestamp = int(row["timestamp"])
            user_ids.add(user_id)
            first_seen[movie_id] = min(timestamp, first_seen.get(movie_id, timestamp))

        selected_users = sorted(user_ids)[:MAX_USERS]
        selected_movies = sorted(
            first_seen,
            key=lambda movie_id: (first_seen[movie_id], movie_id),
        )[:MAX_POSTS]
        selected_user_set = set(selected_users)
        selected_movie_set = set(selected_movies)
        imported_likes: list[tuple[int, int, str]] = []
        for row in _csv_reader(archive, ratings_entry):
            user_id = int(row["userId"])
            movie_id = int(row["movieId"])
            if (
                user_id in selected_user_set
                and movie_id in selected_movie_set
                and float(row["rating"]) >= 4.0
            ):
                imported_likes.append(
                    (user_id, movie_id, _as_timestamp(int(row["timestamp"])))
                )

    with get_connection() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO user (username) VALUES (?)",
            [(f"{USER_PREFIX}{user_id}",) for user_id in selected_users],
        )
        names = [f"{USER_PREFIX}{user_id}" for user_id in selected_users]
        user_rows = (
            conn.execute(
                f"SELECT id, username FROM user WHERE username IN "
                f"({','.join('?' for _ in names)})",
                names,
            ).fetchall()
            if names
            else []
        )
        db_user_ids = {
            int(row["username"][len(USER_PREFIX) :]): row["id"] for row in user_rows
        }

        movie_posts: dict[int, int] = {}
        for movie_position, movie_id in enumerate(selected_movies):
            author_id = db_user_ids[
                selected_users[movie_position % len(selected_users)]
            ]
            title, genres = movies.get(movie_id, (f"Movie {movie_id}", []))
            created_at = _as_timestamp(first_seen[movie_id])
            source_key = f"{POST_PREFIX}{movie_id}"
            conn.execute(
                """
                INSERT INTO post (user_id, content, created_at, genres, source_key)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    user_id = excluded.user_id,
                    content = excluded.content,
                    created_at = excluded.created_at,
                    genres = excluded.genres
                """,
                (
                    author_id,
                    title,
                    created_at,
                    json.dumps(sorted(set(genres))),
                    source_key,
                ),
            )
            post_row = conn.execute(
                "SELECT id FROM post WHERE source_key = ?", (source_key,)
            ).fetchone()
            movie_posts[movie_id] = post_row["id"]

        imported_like_rows = []
        for source_user_id, movie_id, created_at in imported_likes:
            imported_like_rows.append(
                (
                    db_user_ids[source_user_id],
                    movie_posts[movie_id],
                    created_at,
                )
            )
        conn.executemany(
            """
            INSERT INTO "like" (user_id, post_id, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, post_id) DO UPDATE
            SET created_at = excluded.created_at
            """,
            imported_like_rows,
        )
    return len(selected_users), len(selected_movies), len(imported_like_rows)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: python scripts/seed_movielens.py <ml-latest-small.zip>")
        return 2
    try:
        users, posts, likes = seed(Path(args[0]))
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
        print(f"MovieLens import failed: {error}", file=sys.stderr)
        return 1
    print(f"Imported {users} users, {posts} posts, and {likes} likes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
