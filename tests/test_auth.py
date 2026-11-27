import time

import app.db
import app.security
from tests.conftest import ADMIN

ALICE = {"username": "alice", "password": "secret1"}


# ---- register ----

def test_register(client):
    res = client.post("/auth/register", json=ALICE)
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "alice"
    assert isinstance(body["id"], int)
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_username(client):
    client.post("/auth/register", json=ALICE)
    res = client.post("/auth/register", json=ALICE)
    assert res.status_code == 409


def test_register_admin_already_seeded(client):
    assert client.post("/auth/register", json=ADMIN).status_code == 409


def test_register_validation(client):
    cases = [
        {"username": "al", "password": "secret1"},      # username too short
        {"username": "alice", "password": "123"},       # password too short
        {"username": "alice"},                          # missing password
        {"password": "secret1"},                        # missing username
        {},
    ]
    for body in cases:
        res = client.post("/auth/register", json=body)
        assert res.status_code == 400, body
        assert res.json()["detail"] == "Validation failed"


# ---- token ----

def test_token_for_seeded_admin(client):
    res = client.post("/auth/token", json=ADMIN)
    assert res.status_code == 200
    body = res.json()
    assert body["token"] and body["token"] == body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


def test_token_for_registered_user(client):
    client.post("/auth/register", json=ALICE)
    assert client.post("/auth/token", json=ALICE).status_code == 200


def test_token_wrong_password(client):
    res = client.post("/auth/token", json={**ADMIN, "password": "wrongpass"})
    assert res.status_code == 401


def test_token_unknown_user(client):
    res = client.post("/auth/token", json={"username": "nobody", "password": "secret1"})
    assert res.status_code == 401


def test_token_missing_fields(client):
    assert client.post("/auth/token", json={}).status_code == 401


def test_token_short_wrong_password(client):
    # Register rules (min lengths) must not apply to login.
    res = client.post("/auth/token", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_token_short_unknown_username(client):
    res = client.post("/auth/token", json={"username": "x", "password": "y"})
    assert res.status_code == 401


import pytest


@pytest.mark.parametrize(
    "kwargs",
    [
        {},                                                        # no body at all
        {"content": b""},                                          # empty body
        {"content": b"{not json", "headers": {"Content-Type": "application/json"}},
        {"json": None},
        {"json": []},
        {"json": "admin"},
        {"json": {"username": 123, "password": ["a"]}},            # wrong types
        {"json": {"username": "admin"}},                           # missing password
        {"json": {"user": "admin", "pass": "password"}},           # wrong field names
        {"data": {"username": "admin", "password": "nope"}},       # form, wrong password
        {"content": b"username=admin&password=wrong", "headers": {"Content-Type": "text/plain"}},
    ],
)
def test_token_bad_requests_return_401(client, kwargs):
    assert client.post("/auth/token", **kwargs).status_code == 401


def test_token_form_body_with_right_password(client):
    res = client.post("/auth/token", data={"username": "admin", "password": "password"})
    assert res.status_code == 200


def test_tokens_are_unique(client):
    t1 = client.post("/auth/token", json=ADMIN).json()["token"]
    t2 = client.post("/auth/token", json=ADMIN).json()["token"]
    assert t1 != t2


# ---- me ----

def test_me(client, auth):
    res = client.get("/auth/me", headers=auth)
    assert res.status_code == 200
    assert res.json()["username"] == "admin"


def test_me_returns_the_right_user(client):
    client.post("/auth/register", json=ALICE)
    token = client.post("/auth/token", json=ALICE).json()["token"]
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.json()["username"] == "alice"


def test_me_without_token(client):
    res = client.get("/auth/me")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


def test_me_with_invalid_token(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_me_with_wrong_scheme(client, token):
    res = client.get("/auth/me", headers={"Authorization": f"Basic {token}"})
    assert res.status_code == 401


def test_expired_token_is_rejected(client, auth, monkeypatch):
    real_time = time.time
    monkeypatch.setattr(app.security.time, "time", lambda: real_time() + 25 * 3600)
    assert client.get("/auth/me", headers=auth).status_code == 401


def test_token_lasts_at_least_23_hours(client, auth, monkeypatch):
    real_time = time.time
    monkeypatch.setattr(app.security.time, "time", lambda: real_time() + 23 * 3600)
    assert client.get("/auth/me", headers=auth).status_code == 200


def test_token_survives_database_reset(client, auth, tmp_path):
    # Simulates a redeploy without a persistent volume: the database file is
    # deleted and recreated on startup, but issued tokens must keep working.
    import os

    from fastapi.testclient import TestClient

    import app.main

    os.remove(app.db.DB_PATH)
    with TestClient(app.main.app) as fresh:
        assert fresh.get("/books", headers=auth).status_code == 200
        assert fresh.get("/auth/me", headers=auth).json()["username"] == "admin"


def test_tampered_token_is_rejected(client, token):
    payload, sig = token.split(".")
    other = client.post("/auth/token", json=ADMIN).json()["token"]
    forged = f"{other.split('.')[0]}.{sig}"
    for bad in [forged, payload, token + "x", "a.b", "a.b.c", ""]:
        res = client.get("/books", headers={"Authorization": f"Bearer {bad}"})
        assert res.status_code == 401, bad


def test_token_from_another_key_is_rejected(client, token, monkeypatch):
    monkeypatch.setattr(app.security, "_KEY", b"different-secret")
    assert client.get("/books", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_logout_survives_for_books_too(client, auth):
    client.post("/auth/logout", headers=auth)
    assert client.get("/books", headers=auth).status_code == 401


# ---- logout ----

def test_logout_revokes_token(client, auth):
    assert client.post("/auth/logout", headers=auth).status_code == 204
    assert client.get("/auth/me", headers=auth).status_code == 401


def test_logout_only_revokes_that_token(client):
    t1 = client.post("/auth/token", json=ADMIN).json()["token"]
    t2 = client.post("/auth/token", json=ADMIN).json()["token"]
    client.post("/auth/logout", headers={"Authorization": f"Bearer {t1}"})
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {t2}"}).status_code == 200


def test_logout_without_token(client):
    assert client.post("/auth/logout").status_code == 401
