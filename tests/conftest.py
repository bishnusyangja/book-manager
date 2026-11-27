import pytest
from fastapi.testclient import TestClient

import app.db
import app.main
import app.security

ADMIN = {"username": "admin", "password": "password"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client backed by a fresh SQLite file for every test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(app.db, "DB_PATH", db_path)
    monkeypatch.setattr(app.main, "DB_PATH", db_path)
    # Cheap hashing keeps the suite fast; real cost is used in production.
    monkeypatch.setattr(app.security, "_ITERATIONS", 1_000)
    with TestClient(app.main.app) as c:  # `with` runs the startup lifespan
        yield c


@pytest.fixture
def token(client):
    res = client.post("/auth/token", json=ADMIN)
    assert res.status_code == 200
    return res.json()["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_book(client, auth):
    def _make(title="Dune", author="Frank Herbert", year=None):
        body = {"title": title, "author": author}
        if year is not None:
            body["year"] = year
        res = client.post("/books", json=body, headers=auth)
        assert res.status_code == 201
        return res.json()

    return _make
