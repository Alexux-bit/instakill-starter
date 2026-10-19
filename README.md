# InstaKill — Starter Repo

Mini social-media platform. Mandatory backend: Python + FastAPI + SQLite (default) / PostgreSQL (allowed). See the full brief and grading rubric in `masterplan.md` (course root).

What the instructor provides (this starter):

- `app/main.py` — FastAPI app with `GET /health` and `GET /search`
- `app/db/database.py` — SQLite bootstrap (creates tables on startup)
- `app/domain/models.py` — `User` / `Post` schema
- `scripts/seed_db.py` — 5-10 synthetic users/posts
- `tests/test_health.py` — test skeleton

Semantic search is implemented this week. Feed, ranking, user/post CRUD, and extra ML work are still later.

## Running it

```bash
pip install -e .
python scripts/seed_db.py
uvicorn app.main:app --reload
# other terminal:
curl localhost:8000/health
curl "localhost:8000/search?q=cosine%20similarity&limit=5"

pytest
```

The first process start downloads `all-MiniLM-L6-v2` (sentence-transformers) if it is not already cached.

## Semantic search index

On application startup, `create_app` in `app/main.py` runs FastAPI lifespan:

1. `init_db()` creates tables if needed.
2. `list_posts()` in `app/repositories/posts.py` reads seeded posts from SQLite.
3. The encoder adapter (`MiniLMEncoder` in `app/adapters/encoder.py`) loads the pretrained model and encodes post content.
4. `SearchIndex.build` stores posts and their embedding matrix in memory on `app.state`.

`GET /search` does not scan SQLite per request. It encodes the query, then `retrieve_top_k` in `app/retrieval.py` scores the in-memory matrix with NumPy cosine similarity and a deterministic top-*k* (score descending, `post_id` ascending).

When a future create-post path persists a new row, refresh the index by calling `SearchIndex.add_post` with that `Post` and the same encoder (encode the new content and append one row). A full rebuild via `SearchIndex.build(list_posts(), encoder)` is the fallback if the in-memory copy drifts.

## Milestones (see masterplan.md for full details)

W1 Repo+API → W3 CRUD+DB → W4 Feed v0 → W7 Baseline+eval plan → W9 ML+pretrained feature → W11 Profile+optimize → W13 Feature freeze+E2E → W14 Red-team+Demo Day.

At the end of each week: a demonstrable commit/tag.
