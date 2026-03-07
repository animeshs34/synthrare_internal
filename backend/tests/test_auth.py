import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_success(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "securepass1", "full_name": "Alice"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["full_name"] == "Alice"
    assert data["role"] == "user"
    assert data["credits"] == 10
    assert "id" in data


def test_register_duplicate_email(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "securepass1"}
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 409


def test_register_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "securepass1"},
    )
    assert response.status_code == 422


def test_register_short_password(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_success(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "securepass1"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "securepass1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "carol@example.com", "password": "securepass1"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "carol@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_login_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "securepass1"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

def test_refresh_success(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "dave@example.com", "password": "securepass1"},
    )
    login = client.post(
        "/auth/login",
        json={"email": "dave@example.com", "password": "securepass1"},
    )
    refresh_token = login.json()["refresh_token"]

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_invalid_token(client: TestClient) -> None:
    response = client.post("/auth/refresh", json={"refresh_token": "not.a.valid.token"})
    assert response.status_code == 401


def test_refresh_with_access_token_rejected(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "eve@example.com", "password": "securepass1"},
    )
    login = client.post(
        "/auth/login",
        json={"email": "eve@example.com", "password": "securepass1"},
    )
    access_token = login.json()["access_token"]
    response = client.post("/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401
