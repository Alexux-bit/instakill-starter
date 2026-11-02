"""Application service for semantic post search.

Coordinates domain `Post` records, the encoder adapter, and pure retrieval.
It does not parse HTTP or issue SQL.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from app.adapters.encoder import TextEncoder
from app.domain.models import Post
from app.retrieval import retrieve_top_k


class SearchHit(BaseModel):
    post_id: int
    user_id: int
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit] = Field(default_factory=list)


class SearchIndex:
    """In-memory corpus embeddings plus the posts they were built from."""

    def __init__(
        self,
        posts: list[Post],
        embeddings: np.ndarray,
        post_ids: np.ndarray,
    ) -> None:
        self.posts = posts
        self.embeddings = embeddings
        self.post_ids = post_ids

    @classmethod
    def build(cls, posts: list[Post], encoder: TextEncoder) -> SearchIndex:
        identified = [post for post in posts if post.id is not None]
        embeddings = encoder.encode([post.content for post in identified])
        post_ids = np.array([post.id for post in identified], dtype=np.int64)
        return cls(posts=identified, embeddings=embeddings, post_ids=post_ids)

    def add_post(self, post: Post, encoder: TextEncoder) -> None:
        """Append one newly persisted post. Call this after a future create-post path."""
        if post.id is None:
            raise ValueError("Indexed posts must have an id")
        vector = encoder.encode([post.content])
        if self.embeddings.size == 0:
            self.embeddings = vector
            self.post_ids = np.array([post.id], dtype=np.int64)
        else:
            self.embeddings = np.vstack([self.embeddings, vector])
            self.post_ids = np.append(self.post_ids, post.id)
        self.posts.append(post)

    def update_post(self, post: Post, encoder: TextEncoder) -> None:
        if post.id is None:
            raise ValueError("Indexed posts must have an id")
        matches = np.flatnonzero(self.post_ids == post.id)
        if matches.size == 0:
            self.add_post(post, encoder)
            return
        index = int(matches[0])
        self.embeddings[index] = encoder.encode([post.content])[0]
        self.posts[index] = post

    def remove_posts(self, post_ids: set[int]) -> None:
        if not post_ids:
            return
        keep = ~np.isin(self.post_ids, np.fromiter(post_ids, dtype=np.int64))
        self.post_ids = self.post_ids[keep]
        self.embeddings = self.embeddings[keep]
        self.posts = [
            post for post in self.posts if post.id is None or post.id not in post_ids
        ]


def search_posts(
    query: str,
    limit: int,
    *,
    index: SearchIndex,
    encoder: TextEncoder,
) -> SearchResponse:
    """Encode `query` and return up to `limit` posts by cosine similarity."""
    if not index.posts:
        return SearchResponse(query=query, results=[])

    query_vector = encoder.encode([query])[0]
    ranked = retrieve_top_k(query_vector, index.embeddings, index.post_ids, limit)
    hits: list[SearchHit] = []
    for corpus_index, score in ranked:
        post = index.posts[corpus_index]
        assert post.id is not None
        hits.append(
            SearchHit(
                post_id=post.id,
                user_id=post.user_id,
                content=post.content,
                score=score,
            )
        )
    return SearchResponse(query=query, results=hits)
