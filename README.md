# InstaKill — Starter Repo

Mini social-media platform. Mandatory backend: Python + FastAPI + SQLite (default) / PostgreSQL (allowed). See the full brief and grading rubric in `masterplan.md` (course root).

The app provides:

- `app/main.py` — FastAPI app with health, search, feed, CRUD, follow, and like routes
- `app/db/database.py` — SQLite bootstrap and forward-compatible schema migration
- `app/domain/models.py` — `User` / `Post` domain models
- `scripts/seed_db.py` — small synthetic fixture data
- `scripts/seed_movielens.py` — bounded import from a locally supplied MovieLens zip

Semantic search, three feed strategies, and user/post/social CRUD are implemented.

## Running it

```bash
pip install -e .
python scripts/seed_db.py
# Optional: import MovieLens latest-small (the zip is local input, not repository data)
python scripts/seed_movielens.py <path-to-ml-latest-small.zip>
uvicorn app.main:app --reload
# other terminal:
curl localhost:8000/health
curl "localhost:8000/search?q=cosine%20similarity&limit=5"
curl "localhost:8000/feed?user_id=1&limit=20&strategy=for_you"

pytest
```

The first process start downloads `all-MiniLM-L6-v2` (sentence-transformers) if it is not already cached.
The trained learned-feed model is stored at `app/models/like_model.npz`. If it is absent,
the app still starts, but `GET /feed?strategy=learned` responds with `503`.
MovieLens zip files and extracted data are ignored by Git.

## Semantic search index

On application startup, `create_app` in `app/main.py` runs FastAPI lifespan:

1. `init_db()` creates tables if needed.
2. `list_posts()` in `app/repositories/posts.py` reads seeded posts from SQLite.
3. The encoder adapter (`MiniLMEncoder` in `app/adapters/encoder.py`) loads the pretrained model and encodes post content.
4. `SearchIndex.build` stores posts and their embedding matrix in memory on `app.state`.

`GET /search` does not scan SQLite per request. It encodes the query, then `retrieve_top_k` in `app/retrieval.py` scores the in-memory matrix with NumPy cosine similarity and a deterministic top-*k* (score descending, `post_id` ascending).

Post create, edit, and delete routes keep this index synchronized with the database.

## Feed ranking

`GET /feed` does not use the search encoder. The service loads posts, follows, and likes from repositories, drops the viewer's own posts and already-liked posts, then sorts by `created_at` (`strategy=chronological`), calls `rank_feed` (`strategy=for_you`), or applies the saved NumPy MLP (`strategy=learned`).

The learned scorer consumes the notebook's six signals in the saved feature order: freshness, genre affinity, recent popularity, user activity, lifetime popularity, and age. Weights, scaler arrays, and the signal constants are read from `like_model.npz` once at startup. All candidate scores are predicted in one NumPy matrix operation. The formula and default weights for `for_you` are in `docs/api-contract.md`; `rank_feed` is a pure function that receives `now`, performs no I/O, and does not mutate its inputs.

**Complexity.** Let `C` be the number of candidate posts after filtering and `k` the `limit`. Scoring is `O(C)`. The heap keeps at most `k` items, so selection is `O(C log k)`, then the heap is sorted in `O(k log k)`. One request is **O(C log k)** time (plus the SQL reads that produce the candidate set).

The first thing to precompute is **per-post popularity** (and freshness at a shared `now`): both are the same for every viewer. The learned affinity and activity features are per-user and are built for the request's candidate matrix.

## MovieLens import

Pass the locally downloaded `ml-latest-small.zip` to `scripts/seed_movielens.py`.
The importer reads the CSVs directly from the archive without extracting them. It
imports at most 200 users and 2,000 movies, uses each movie's first rating time as
the post time, and turns ratings of at least 4 into likes using each rating's
timestamp. Since movies do not have authors in MovieLens, posts are assigned to
the imported users in a deterministic round-robin order. Stable source IDs make
repeated imports idempotent; unrelated database records are preserved. Do not
commit the zip or extracted MovieLens data.

## Milestones (see masterplan.md for full details)

W1 Repo+API → W3 CRUD+DB → W4 Feed v0 → W7 Baseline+eval plan → W9 ML+pretrained feature → W11 Profile+optimize → W13 Feature freeze+E2E → W14 Red-team+Demo Day.

At the end of each week: a demonstrable commit/tag.
