# API contract

`POST /posts` remains a Week 2 planned endpoint and is not implemented. `GET /search` and `GET /feed` are implemented.

## `GET /feed`

Personalized home feed. The HTTP layer validates `user_id`, `limit`, and `strategy`, then calls `build_feed` in `app.services.feed`. Follows, likes, and posts are read from repositories. `for_you` ranking uses `rank_feed` in `app.ranking` (no search embeddings).

### Candidates

Always excluded: the viewer's own posts, and posts the viewer already liked.

- If the viewer follows anyone, candidates are posts by those followed authors (after the exclusions above).
- Cold start: if the viewer follows nobody, candidates are every remaining post. Ranking then leans on freshness and popularity; affinity is 0 except where the viewer already liked that author.

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
| `strategy` | string  | no       | Default `for_you`. Must be `for_you` or `chronological` |

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
| `400 Bad Request` | `strategy` is not `for_you` or `chronological` | `{"detail": "Query parameter 'strategy' must be 'for_you' or 'chronological'."}` |
| `404 Not Found` | `user_id` does not match an existing user | `{"detail": "User not found."}` |

## `GET /search`

Semantic search over seeded posts. The HTTP layer validates `q` and `limit`, then calls `search_posts` in `app.services.search`. Corpus rows come from `app.repositories.posts.list_posts`. Embeddings come from the encoder adapter. Ranking uses `retrieve_top_k` in `app.retrieval`.

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

## `POST /posts` (planned, not implemented)

Create a post authored by an existing user.

### Request

- **Content-Type:** `application/json`
- **Body:**

| Field     | Type   | Required | Rules                                      |
|-----------|--------|----------|--------------------------------------------|
| `user_id` | integer | yes     | Must identify an existing user (`User.id`) |
| `content` | string  | yes     | Non-empty after trim; max 2000 characters  |

Example:

```json
{
  "user_id": 1,
  "content": "hello world, this is my first post"
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
  "created_at": "2026-10-19T17:10:00"
}
```

### Validation and error cases

| Status | When | Example body |
|--------|------|----------------|
| `422 Unprocessable Entity` | Missing `user_id` or `content`, wrong types, empty/whitespace `content`, or `content` longer than 2000 characters | `{"detail": "Post content must not be empty."}` |
| `404 Not Found` | `user_id` does not match an existing user | `{"detail": "User not found."}` |

`compose_post` covers author-without-id, empty content, and over-long content (`PostCompositionError`). User-not-found is a persistence lookup that the future endpoint will handle before calling the service.
