# API contract

The API includes user/post CRUD, follow and like operations, semantic search, and three feed strategies.

## `GET /feed`

Personalized home feed. The HTTP layer validates `user_id`, `limit`, and `strategy`, then calls `build_feed` in `app.services.feed`. Follows, likes, and posts are read from repositories. `for_you` ranking uses `rank_feed` in `app.ranking`; `learned` uses the saved NumPy model and does not use search embeddings.

### Candidates

Always excluded: the viewer's own posts, and posts the viewer already liked.

- If the viewer follows anyone, candidates are posts by those followed authors (after the exclusions above).
- Cold start: if the viewer follows nobody, candidates are every remaining post. Ranking then leans on freshness and popularity; affinity is 0 except where the viewer already liked that author.

### `learned` score

The model is loaded once from `app/models/like_model.npz` during application startup. The artifact supplies the network weights, feature order, normalization arrays, and signal constants. Each candidate gets a row in one NumPy feature matrix; the MLP predicts the probability of a like for all rows without a Python scoring loop.

Features use the exact notebook order and formulas:

1. **freshness** = `0.5 ** (age_days / half_life_days)`
2. **affinity** = genre overlap with the viewer's liked posts, divided by the viewer's total liked-genre count and the candidate's genre count; 0 when either is unavailable
3. **popularity** = recent likes on the post divided by the maximum recent likes for any post
4. **activity** = `min(1, log1p(viewer_like_count) / log1p(activity_cap))`
5. **lifetime** = `log1p(post_like_count) / log1p(max(1, corpus_max_lifetime_likes))`
6. **age** = `min(1, age_days / age_cap_days)`

`half_life_days`, `popularity_days`, `activity_cap`, and `age_cap_days` are read from the model artifact. New posts may provide a `genres` array; MovieLens imports populate it from `movies.csv`. Results are sorted by descending predicted probability, then ascending `post_id`, and include that probability as `score`. If the model file is missing, the app remains available for other routes and this strategy returns `503 Service Unavailable`.

### `for_you` score

Each signal is scaled to `[0, 1]`:

- **freshness** = `0.5 ** (age_hours / 48)` — half-life of two days, so a social post fades in hours, not years.
- **affinity** = `(follow_bonus + like_share) / 2` — `follow_bonus` is 1 if the author is followed, else 0; `like_share` is the fraction of the viewer's likes that went to this author.
- **popularity** = `like_count(post) / max_like_count` — 0 if the corpus has no likes.

```text
score = 1.4 * freshness + 2.2 * affinity + 0.8 * popularity
```

Weights are not the lab's `(1, 1, 1)` and not `2 * likes + comments - age_hours`. Affinity is strongest so followed authors outrank global hits; freshness is next so the feed stays current; popularity is a light boost so a widely liked post can surface without flattening everyone onto the same ranking.

`for_you` order: descending `score`, then ascending `post_id`. Chronological order: newest `created_at`, then ascending `post_id`. Chronological results omit `score`.

### Request

| Parameter  | Type    | Required | Rules                                                |
|------------|---------|----------|------------------------------------------------------|
| `user_id`  | integer | yes      | Must identify an existing user                       |
| `limit`    | integer | no       | Default `20`. Must be in `1..50` inclusive           |
| `strategy` | string  | no       | Default `for_you`. Must be `for_you`, `chronological`, or `learned` |

Example:

```http
GET /feed?user_id=1&limit=20&strategy=for_you
```

### Successful response

- **Status:** `200 OK`

```json
{
  "user_id": 1,
  "strategy": "for_you",
  "results": [
    {
      "post_id": 7,
      "user_id": 4,
      "content": "affinity should beat raw like count or everyone sees the same hits",
      "created_at": "2026-10-26T10:00:00",
      "score": 3.1
    }
  ]
}
```

### Validation and error cases

| Status | When | Example body |
|--------|------|----------------|
| `400 Bad Request` | `user_id` is missing | `{"detail": "Query parameter 'user_id' must be an integer."}` |
| `400 Bad Request` | `limit` is outside `1..50` | `{"detail": "Query parameter 'limit' must be an integer between 1 and 50."}` |
| `400 Bad Request` | `strategy` is not `for_you`, `chronological`, or `learned` | Strategy validation detail |
| `404 Not Found` | `user_id` does not match an existing user | `{"detail": "User not found."}` |
| `503 Service Unavailable` | `strategy=learned` and the model file is missing | `{"detail": "The learned feed model is unavailable."}` |

## `GET /search`

Semantic search over posts. The HTTP layer validates `q` and `limit`, then calls `search_posts` in `app.services.search`. Corpus rows come from `app.repositories.posts.list_posts`. Embeddings come from the encoder adapter. Ranking uses `retrieve_top_k` in `app.retrieval`.

### Request

| Parameter | Type    | Required | Rules                                      |
|-----------|---------|----------|--------------------------------------------|
| `q`       | string  | yes      | Non-empty after trimming whitespace        |
| `limit`   | integer | no       | Default `10`. Must be in `1..20` inclusive |

Example:

```http
GET /search?q=cosine%20similarity&limit=5
```

### Successful response

- **Status:** `200 OK`
- **Body:** the original query (trimmed) and up to `limit` hits, ordered by descending `score`, then ascending `post_id`

```json
{
  "query": "cosine similarity",
  "results": [
    {
      "post_id": 3,
      "user_id": 2,
      "content": "just shipped a cosine similarity search, feels great",
      "score": 0.72
    }
  ]
}
```

Each result includes `post_id`, `user_id`, `content`, and a finite numeric `score`.

### Validation and error cases

| Status | When | Example body |
|--------|------|----------------|
| `400 Bad Request` | `q` is missing, empty, or only whitespace | `{"detail": "Query parameter 'q' must be a non-empty string."}` |
| `400 Bad Request` | `limit` is outside `1..20` | `{"detail": "Query parameter 'limit' must be an integer between 1 and 20."}` |
| `422 Unprocessable Entity` | `limit` is not an integer | FastAPI validation error for the query parameter |

An empty index (no posts in the database) is not an error: the response is `200` with `"results": []`.

## Users

| Method and path | Behavior |
|---|---|
| `POST /users` | Create a user from `{"username": "alice"}`; returns `201` and the created user. |
| `GET /users` | List users in ID order; optional `limit` (`1..100`, default `20`) and `offset` (default `0`). |
| `GET /users/{user_id}` | Get one user; `404` if missing. |
| `PATCH /users/{user_id}` | Update `username`; at least one field is required. |
| `DELETE /users/{user_id}` | Delete the user and their authored posts, likes, and follow relationships; returns `204`. |

Usernames are trimmed, non-empty, at most 80 characters, and unique. Duplicate usernames return `409`; invalid payloads return `422`.

## Posts

Create a post authored by an existing user.

### Request

- **Content-Type:** `application/json`
- **Body:**

| Field     | Type   | Required | Rules                                      |
|-----------|--------|----------|--------------------------------------------|
| `user_id` | integer | yes     | Must identify an existing user (`User.id`) |
| `content` | string  | yes     | Non-empty after trim; max 2000 characters  |
| `genres`  | string array | no | Genre labels used by the learned feed; defaults to `[]` |

Example:

```json
{
  "user_id": 1,
  "content": "hello world, this is my first post",
  "genres": ["Drama"]
}
```

### Successful response

- **Status:** `201 Created`
- **Body:** a `Post` (`id` and `created_at` assigned at persist time)

```json
{
  "id": 12,
  "user_id": 1,
  "content": "hello world, this is my first post",
  "created_at": "2026-10-19T17:10:00",
  "genres": []
}
```

### Validation and error cases

| Status | When | Example body |
|--------|------|----------------|
| `422 Unprocessable Entity` | Missing `user_id` or `content`, wrong types, empty/whitespace `content`, or `content` longer than 2000 characters | `{"detail": "Post content must not be empty."}` |
| `404 Not Found` | `user_id` does not match an existing user | `{"detail": "User not found."}` |

`compose_post` covers author-without-id, empty content, and over-long content (`PostCompositionError`). The endpoint checks that the author exists before composition.

The remaining post operations are `GET /posts` (paginated list), `GET /posts/{post_id}`, `PATCH /posts/{post_id}` (update `content` and/or `genres`), and `DELETE /posts/{post_id}`. List pagination uses the same `limit` and `offset` rules as users. A post delete also removes its likes. Create, edit, and delete keep the in-memory semantic-search index synchronized. Author and creation time cannot be changed through `PATCH`.

## Follows

- `POST /users/{user_id}/following/{followee_id}` creates a follow relationship and returns its `created_at`; repeating the request is idempotent and returns `200` with the original relationship.
- `DELETE /users/{user_id}/following/{followee_id}` removes it (`204`; `404` if it does not exist).
- `GET /users/{user_id}/following` and `GET /users/{user_id}/followers` return arrays of user records.

Both users must exist. Self-follows return `400`; missing users return `404`.

## Likes

- `POST /posts/{post_id}/likes` accepts `{"user_id": 1}` with optional ISO-8601 `created_at`. If omitted, SQLite assigns the current timestamp. The response includes `user_id`, `post_id`, and `created_at`; a repeated like returns `200` and preserves the original timestamp.
- `DELETE /posts/{post_id}/likes/{user_id}` removes a like (`204`; `404` if the user, post, or like does not exist).

Likes are unique per user/post pair. The MovieLens importer supplies the original rating timestamp when creating each like.

## MovieLens importer

Run `python scripts/seed_movielens.py <path-to-ml-latest-small.zip>`. It reads `ratings.csv` and `movies.csv` from the zip without extracting data, imports up to 200 users and 2,000 movies deterministically, and is safe to rerun. Each movie becomes a post authored by an imported user in deterministic round-robin order because MovieLens does not define authors. Movie genres are retained on posts; ratings of at least 4 become likes using the original rating timestamp. MovieLens IDs are recorded as internal source keys, and unrelated database rows are not deleted. The archive and extracted dataset are not repository files.
