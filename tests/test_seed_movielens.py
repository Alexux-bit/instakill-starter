import csv
import io
import zipfile

from app.db.database import get_connection
from scripts.seed_movielens import seed


def _csv_text(header: list[str], rows: list[list[object]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


def test_seed_movielens_is_bounded_input_idempotent_and_preserves_like_time(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("INSTAKILL_DB_PATH", str(tmp_path / "seed.db"))
    archive_path = tmp_path / "ml-latest-small.zip"
    ratings = _csv_text(
        ["userId", "movieId", "rating", "timestamp"],
        [
            [10, 100, 5.0, 100],
            [10, 200, 3.0, 200],
            [20, 100, 4.0, 300],
            [30, 300, 3.0, 400],
        ],
    )
    movies = _csv_text(
        ["movieId", "title", "genres"],
        [
            [100, "Movie A (2000)", "Drama|Comedy"],
            [200, "Movie B (2001)", "Action"],
            [300, "Movie C (2002)", "(no genres listed)"],
        ],
    )
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("ml-latest-small/ratings.csv", ratings)
        archive.writestr("ml-latest-small/movies.csv", movies)

    assert seed(archive_path) == (3, 3, 2)
    assert seed(archive_path) == (3, 3, 2)
    with get_connection() as conn:
        users = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
        posts = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
        likes = conn.execute('SELECT COUNT(*) FROM "like"').fetchone()[0]
        like_time = conn.execute(
            'SELECT created_at FROM "like" WHERE user_id = '
            "(SELECT id FROM user WHERE username = 'movielens-user-10') "
            "AND post_id = (SELECT id FROM post WHERE source_key = 'movielens:100')"
        ).fetchone()[0]
        genres = conn.execute(
            "SELECT genres FROM post WHERE source_key = 'movielens:100'"
        ).fetchone()[0]

    assert (users, posts, likes) == (3, 3, 2)
    assert like_time == "1970-01-01 00:01:40"
    assert genres == '["Comedy", "Drama"]'
