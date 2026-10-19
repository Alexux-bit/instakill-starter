# API contract

`POST /posts` remains a Week 2 planned endpoint and is not implemented. `GET /search` is implemented.

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
