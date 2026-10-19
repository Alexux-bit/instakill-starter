"""Application service that composes posts from existing domain models.

This module coordinates User and Post. It does not handle HTTP or talk to SQLite.
Persistence and routing are later layers that call `compose_post`.
"""

from app.domain.models import Post, User

MAX_POST_CONTENT_LENGTH = 2000


class PostCompositionError(ValueError):
    """Raised when a post cannot be composed from the given author and content."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def compose_post(author: User, content: str) -> Post:
    """Return an unpersisted Post for `author` and `content`.

    `id` and `created_at` stay unset so a later persistence step can fill them in.
    """
    if author.id is None:
        raise PostCompositionError(
            "author_unidentified",
            "Author must have an id before a post can be composed.",
        )

    normalized = content.strip()
    if not normalized:
        raise PostCompositionError("empty_content", "Post content must not be empty.")
    if len(normalized) > MAX_POST_CONTENT_LENGTH:
        raise PostCompositionError(
            "content_too_long",
            f"Post content must be at most {MAX_POST_CONTENT_LENGTH} characters.",
        )

    return Post(user_id=author.id, content=normalized)
