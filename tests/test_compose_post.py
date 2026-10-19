import pytest

from app.domain.models import User
from app.services.posts import MAX_POST_CONTENT_LENGTH, PostCompositionError, compose_post


def test_compose_post_returns_unpersisted_post() -> None:
    author = User(id=1, username="alice")
    post = compose_post(author, "  hello world  ")

    assert post.user_id == 1
    assert post.content == "hello world"
    assert post.id is None
    assert post.created_at is None


def test_compose_post_rejects_author_without_id() -> None:
    author = User(username="alice")
    with pytest.raises(PostCompositionError) as exc:
        compose_post(author, "hello")
    assert exc.value.code == "author_unidentified"


def test_compose_post_rejects_empty_content() -> None:
    author = User(id=1, username="alice")
    with pytest.raises(PostCompositionError) as exc:
        compose_post(author, "   ")
    assert exc.value.code == "empty_content"


def test_compose_post_rejects_overlong_content() -> None:
    author = User(id=1, username="alice")
    with pytest.raises(PostCompositionError) as exc:
        compose_post(author, "x" * (MAX_POST_CONTENT_LENGTH + 1))
    assert exc.value.code == "content_too_long"
