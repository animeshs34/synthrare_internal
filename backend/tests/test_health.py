def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data


def test_health_not_post(client):
    response = client.post("/health")
    assert response.status_code == 405


def test_health_returns_json(client):
    response = client.get("/health")
    assert response.headers["content-type"].startswith("application/json")
