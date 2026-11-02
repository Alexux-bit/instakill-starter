from datetime import datetime


def test_user_crud_and_duplicate_username(client) -> None:
    created = client.post("/users", json={"username": "  new-user  "})
    assert created.status_code == 201
    user = created.json()
    assert user["username"] == "new-user"

    duplicate = client.post("/users", json={"username": "new-user"})
    assert duplicate.status_code == 409
    assert client.get(f"/users/{user['id']}").json()["username"] == "new-user"
    assert any(item["id"] == user["id"] for item in client.get("/users").json())

    patched = client.patch(f"/users/{user['id']}", json={"username": "renamed"})
    assert patched.status_code == 200
    assert patched.json()["username"] == "renamed"
    assert client.delete(f"/users/{user['id']}").status_code == 204
    assert client.get(f"/users/{user['id']}").status_code == 404


def test_deleting_user_removes_owned_posts_and_social_links(client) -> None:
    user = client.post("/users", json={"username": "temporary-author"}).json()
    post = client.post(
        "/posts",
        json={"user_id": user["id"], "content": "temporary post"},
    ).json()
    assert client.post(f"/users/{user['id']}/following/1").status_code == 201
    assert client.post("/posts/5/likes", json={"user_id": user["id"]}).status_code == 201

    assert client.delete(f"/users/{user['id']}").status_code == 204
    assert client.get(f"/posts/{post['id']}").status_code == 404
    assert post["id"] not in client.app.state.search_index.post_ids
    assert client.delete("/posts/5/likes/" + str(user["id"])).status_code == 404


def test_post_crud_updates_search_index(client) -> None:
    created = client.post(
        "/posts",
        json={
            "user_id": 1,
            "content": "  a newly created post  ",
            "genres": ["Drama", "Drama"],
        },
    )
    assert created.status_code == 201
    post = created.json()
    assert post["content"] == "a newly created post"
    assert post["genres"] == ["Drama"]
    assert post["id"] in client.app.state.search_index.post_ids

    patched = client.patch(
        f"/posts/{post['id']}",
        json={"content": "updated post content", "genres": ["Comedy"]},
    )
    assert patched.status_code == 200
    assert patched.json()["content"] == "updated post content"
    assert patched.json()["genres"] == ["Comedy"]
    assert client.get(f"/posts/{post['id']}").status_code == 200
    assert any(item["id"] == post["id"] for item in client.get("/posts").json())

    assert client.delete(f"/posts/{post['id']}").status_code == 204
    assert client.get(f"/posts/{post['id']}").status_code == 404
    assert post["id"] not in client.app.state.search_index.post_ids

    missing_author = client.post(
        "/posts", json={"user_id": 999, "content": "not persisted"}
    )
    assert missing_author.status_code == 404


def test_follow_and_like_crud_preserve_timestamps(client) -> None:
    followed = client.post("/users/1/following/3")
    assert followed.status_code == 201
    assert followed.json()["followee_id"] == 3
    assert client.post("/users/1/following/3").status_code == 200
    assert any(user["id"] == 3 for user in client.get("/users/1/following").json())
    assert any(user["id"] == 1 for user in client.get("/users/3/followers").json())
    assert client.delete("/users/1/following/3").status_code == 204

    created_at = "2024-01-02T03:04:05"
    liked = client.post(
        "/posts/5/likes",
        json={"user_id": 1, "created_at": created_at},
    )
    assert liked.status_code == 201
    assert datetime.fromisoformat(liked.json()["created_at"]) == datetime.fromisoformat(
        created_at
    )
    duplicate = client.post("/posts/5/likes", json={"user_id": 1})
    assert duplicate.status_code == 200
    assert duplicate.json()["created_at"] == liked.json()["created_at"]
    assert client.delete("/posts/5/likes/1").status_code == 204
