def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json() == {"message": "Welcome to Book Manager By Bishnu"}


def test_ping(client):
    res = client.get("/ping")
    assert res.status_code == 200
    assert res.json() == {"success": True}


def test_ping_needs_no_auth(client):
    assert client.get("/ping").status_code == 200


def test_echo_object(client):
    body = {"a": 1, "nested": {"b": [1, 2, 3]}, "ok": True, "none": None}
    res = client.post("/echo", json=body)
    assert res.status_code == 200
    assert res.json() == body


def test_echo_list(client):
    assert client.post("/echo", json=[1, "two", 3.0]).json() == [1, "two", 3.0]


def test_echo_scalar(client):
    assert client.post("/echo", json="hello").json() == "hello"


def test_echo_empty_body(client):
    res = client.post("/echo")
    assert res.status_code == 200
    assert res.json() is None
