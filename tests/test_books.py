import pytest

import app.security

# ---- auth guard (level 5) ----

@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/books"),
        ("get", "/books/1"),
        ("post", "/books"),
        ("put", "/books/1"),
        ("delete", "/books/1"),
    ],
)
def test_books_require_auth(client, method, path):
    res = client.request(method, path, json={"title": "x", "author": "y"})
    assert res.status_code == 401


def test_books_reject_invalid_token(client):
    res = client.get("/books", headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401


def test_books_public_when_auth_disabled(client, monkeypatch):
    monkeypatch.setattr(app.security, "AUTH_REQUIRED", False)
    assert client.get("/books").status_code == 200
    assert client.post("/books", json={"title": "Dune", "author": "Frank Herbert"}).status_code == 201


# ---- create & read (level 3) ----

def test_create_book(client, auth):
    res = client.post(
        "/books", json={"title": "Dune", "author": "Frank Herbert", "year": 1965}, headers=auth
    )
    assert res.status_code == 201
    assert res.json() == {"id": 1, "title": "Dune", "author": "Frank Herbert", "year": 1965}


def test_create_book_without_year(client, auth):
    res = client.post("/books", json={"title": "Dune", "author": "Frank Herbert"}, headers=auth)
    assert res.status_code == 201
    assert res.json()["year"] is None


def test_list_books_empty(client, auth):
    res = client.get("/books", headers=auth)
    assert res.status_code == 200
    assert res.json() == []


def test_list_books(client, auth, make_book):
    a = make_book("Dune", "Frank Herbert")
    b = make_book("1984", "George Orwell")
    res = client.get("/books", headers=auth)
    assert res.status_code == 200
    assert res.json() == [a, b]


def test_get_book(client, auth, make_book):
    book = make_book("Dune", "Frank Herbert", 1965)
    res = client.get(f"/books/{book['id']}", headers=auth)
    assert res.status_code == 200
    assert res.json() == book


def test_ids_increment(make_book):
    assert make_book()["id"] == 1
    assert make_book()["id"] == 2


# ---- update & delete (level 4) ----

def test_update_book(client, auth, make_book):
    book = make_book("Dune", "Frank Herbert", 1965)
    new = {"title": "Dune Messiah", "author": "Frank Herbert", "year": 1969}
    res = client.put(f"/books/{book['id']}", json=new, headers=auth)
    assert res.status_code == 200
    assert res.json() == {"id": book["id"], **new}
    assert client.get(f"/books/{book['id']}", headers=auth).json() == {"id": book["id"], **new}


def test_update_missing_book(client, auth):
    res = client.put("/books/999", json={"title": "x", "author": "y"}, headers=auth)
    assert res.status_code == 404


def test_update_book_invalid_body(client, auth, make_book):
    book = make_book()
    res = client.put(f"/books/{book['id']}", json={"title": ""}, headers=auth)
    assert res.status_code == 400


def test_delete_book(client, auth, make_book):
    book = make_book()
    res = client.delete(f"/books/{book['id']}", headers=auth)
    assert res.status_code == 204
    assert res.content == b""
    assert client.get(f"/books/{book['id']}", headers=auth).status_code == 404
    assert client.get("/books", headers=auth).json() == []


def test_delete_missing_book(client, auth):
    assert client.delete("/books/999", headers=auth).status_code == 404


def test_delete_twice(client, auth, make_book):
    book = make_book()
    assert client.delete(f"/books/{book['id']}", headers=auth).status_code == 204
    assert client.delete(f"/books/{book['id']}", headers=auth).status_code == 404


def test_delete_only_removes_one(client, auth, make_book):
    a = make_book("A", "X")
    b = make_book("B", "Y")
    client.delete(f"/books/{a['id']}", headers=auth)
    assert client.get("/books", headers=auth).json() == [b]


# ---- search & paginate (level 6) ----

@pytest.fixture
def library(make_book):
    return [
        make_book("Dune", "Frank Herbert"),
        make_book("1984", "George Orwell"),
        make_book("Animal Farm", "George Orwell"),
        make_book("Brave New World", "Aldous Huxley"),
        make_book("Homage to Catalonia", "George Orwell"),
    ]


def test_filter_by_author(client, auth, library):
    res = client.get("/books", params={"author": "George Orwell"}, headers=auth)
    assert res.status_code == 200
    assert [b["title"] for b in res.json()] == ["1984", "Animal Farm", "Homage to Catalonia"]


def test_filter_by_author_partial_and_case_insensitive(client, auth, library):
    res = client.get("/books", params={"author": "orwell"}, headers=auth)
    assert len(res.json()) == 3


def test_filter_by_author_no_match(client, auth, library):
    assert client.get("/books", params={"author": "Tolkien"}, headers=auth).json() == []


def test_paginate_first_page(client, auth, library):
    res = client.get("/books", params={"page": 1, "limit": 2}, headers=auth)
    assert res.status_code == 200
    assert res.json() == library[0:2]


def test_paginate_second_page(client, auth, library):
    assert client.get("/books", params={"page": 2, "limit": 2}, headers=auth).json() == library[2:4]


def test_paginate_last_partial_page(client, auth, library):
    assert client.get("/books", params={"page": 3, "limit": 2}, headers=auth).json() == library[4:5]


def test_paginate_past_end(client, auth, library):
    assert client.get("/books", params={"page": 10, "limit": 2}, headers=auth).json() == []


def test_limit_only_defaults_to_first_page(client, auth, library):
    assert client.get("/books", params={"limit": 3}, headers=auth).json() == library[0:3]


def test_page_only_uses_default_limit(client, auth, library):
    # default page size is 10, so all 5 books fit on page 1
    assert client.get("/books", params={"page": 1}, headers=auth).json() == library


def test_filter_and_paginate_together(client, auth, library):
    res = client.get("/books", params={"author": "Orwell", "page": 2, "limit": 2}, headers=auth)
    assert [b["title"] for b in res.json()] == ["Homage to Catalonia"]


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page": -1}, {"limit": 0}, {"limit": 101}, {"page": "abc"}, {"limit": "x"}],
)
def test_invalid_pagination_params(client, auth, params):
    assert client.get("/books", params=params, headers=auth).status_code == 400


# ---- error handling (level 7) ----

@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": "Dune"},                                       # missing author
        {"author": "Frank Herbert"},                             # missing title
        {"title": "", "author": "Frank Herbert"},                # empty title
        {"title": "Dune", "author": ""},                         # empty author
        {"title": "x" * 256, "author": "Frank Herbert"},         # title too long
        {"title": "Dune", "author": "Frank Herbert", "year": -1},
        {"title": "Dune", "author": "Frank Herbert", "year": "soon"},
        {"title": None, "author": "Frank Herbert"},
        {"title": "   ", "author": "Frank Herbert"},               # blank title
        {"title": "Dune", "author": "\t\n "},                      # blank author
        {"title": "Dune", "author": "Frank Herbert", "year": True},
        {"title": "Dune", "author": "Frank Herbert", "year": "1965"},
        {"title": "Dune", "author": "Frank Herbert", "year": 1965.5},
        {"title": 123, "author": "Frank Herbert"},
        {"title": ["Dune"], "author": "Frank Herbert"},
    ],
)
def test_create_book_invalid(client, auth, body):
    res = client.post("/books", json=body, headers=auth)
    assert res.status_code == 400
    data = res.json()
    assert data["detail"] == "Validation failed"
    assert data["errors"] and all({"field", "message"} <= e.keys() for e in data["errors"])


def test_create_book_invalid_reports_fields(client, auth):
    res = client.post("/books", json={"title": ""}, headers=auth)
    fields = {e["field"] for e in res.json()["errors"]}
    assert fields == {"title", "author"}


def test_create_book_malformed_json(client, auth):
    res = client.post(
        "/books", content=b"{not json", headers={**auth, "Content-Type": "application/json"}
    )
    assert res.status_code == 400


def test_invalid_book_is_not_saved(client, auth):
    client.post("/books", json={"title": ""}, headers=auth)
    assert client.get("/books", headers=auth).json() == []


def test_get_missing_book(client, auth):
    res = client.get("/books/999", headers=auth)
    assert res.status_code == 404
    assert res.json() == {"detail": "Book not found"}


@pytest.mark.parametrize("book_id", ["nonexistent", "abc", "-1", "1.5", "0", "999999"])
def test_unknown_ids_return_404(client, auth, make_book, book_id):
    make_book()
    body = {"title": "x", "author": "y"}
    assert client.get(f"/books/{book_id}", headers=auth).status_code == 404
    assert client.put(f"/books/{book_id}", json=body, headers=auth).status_code == 404
    assert client.delete(f"/books/{book_id}", headers=auth).status_code == 404


def test_put_missing_book_with_bad_body_is_404(client, auth):
    assert client.put("/books/nonexistent", json={}, headers=auth).status_code == 404
    assert client.put("/books/999", content=b"{bad", headers=auth).status_code == 404


def test_put_malformed_json_on_existing_book_is_400(client, auth, make_book):
    book = make_book()
    res = client.put(
        f"/books/{book['id']}", content=b"{bad", headers={**auth, "Content-Type": "application/json"}
    )
    assert res.status_code == 400


# ---- boss level: full flow (level 8) ----

def test_full_flow(client):
    assert client.get("/ping").status_code == 200
    assert client.post("/echo", json={"hi": 1}).json() == {"hi": 1}

    assert client.post("/auth/register", json={"username": "reader", "password": "secret1"}).status_code == 201
    token = client.post("/auth/token", json={"username": "reader", "password": "secret1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    created = client.post("/books", json={"title": "Dune", "author": "Frank Herbert"}, headers=h).json()
    client.post("/books", json={"title": "1984", "author": "George Orwell"}, headers=h)
    assert len(client.get("/books", headers=h).json()) == 2
    assert client.get("/books", params={"author": "Orwell"}, headers=h).json()[0]["title"] == "1984"
    assert len(client.get("/books", params={"page": 1, "limit": 1}, headers=h).json()) == 1

    updated = client.put(
        f"/books/{created['id']}", json={"title": "Dune", "author": "Frank Herbert", "year": 1965}, headers=h
    ).json()
    assert updated["year"] == 1965

    assert client.delete(f"/books/{created['id']}", headers=h).status_code == 204
    assert client.get(f"/books/{created['id']}", headers=h).status_code == 404
    assert client.post("/books", json={}, headers=h).status_code == 400

    assert client.post("/auth/logout", headers=h).status_code == 204
    assert client.get("/books", headers=h).status_code == 401


# ---- graceful error messages ----

def _errors(res):
    assert res.status_code == 400
    return res.json()["errors"]


def test_titles_are_trimmed(client, auth):
    res = client.post("/books", json={"title": "  Dune ", "author": " Frank Herbert "}, headers=auth)
    assert res.status_code == 201
    assert (res.json()["title"], res.json()["author"]) == ("Dune", "Frank Herbert")


def test_missing_body_error(client, auth):
    assert _errors(client.post("/books", headers=auth)) == [
        {"field": "body", "message": "Request body is required"}
    ]


def test_malformed_json_error(client, auth):
    res = client.post("/books", content=b"{bad", headers={**auth, "Content-Type": "application/json"})
    assert _errors(res) == [{"field": "body", "message": "Request body is not valid JSON"}]


@pytest.mark.parametrize("body", [[], "text", 5, None])
def test_non_object_body_error(client, auth, body):
    errors = _errors(client.post("/books", json=body, headers=auth))
    assert errors[0]["field"] == "body"


def test_put_invalid_body_reports_fields(client, auth, make_book):
    book = make_book()
    errors = _errors(client.put(f"/books/{book['id']}", json={"title": " "}, headers=auth))
    assert {e["field"] for e in errors} == {"title", "author"}


def test_failed_put_leaves_book_unchanged(client, auth, make_book):
    book = make_book("Dune", "Frank Herbert")
    client.put(f"/books/{book['id']}", json={"title": ""}, headers=auth)
    assert client.get(f"/books/{book['id']}", headers=auth).json() == book


def test_unknown_route_is_404(client):
    res = client.get("/does-not-exist")
    assert res.status_code == 404
    assert "detail" in res.json()


def test_wrong_method_is_405(client, auth):
    assert client.patch("/books/1", headers=auth).status_code == 405


def test_unexpected_error_returns_json_500(client, auth, monkeypatch):
    from fastapi.testclient import TestClient

    import app.main

    def boom(_token):
        raise RuntimeError("database exploded")

    monkeypatch.setattr(app.security, "decode_token", boom)
    with TestClient(app.main.app, raise_server_exceptions=False) as c:
        res = c.get("/books", headers=auth)
    assert res.status_code == 500
    assert res.json() == {"detail": "Internal server error"}
