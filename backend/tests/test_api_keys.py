from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.models.domain import Domain
from app.models.user import User, UserRole
from app.services.auth import create_access_token, hash_password


def _make_user(db, email: str = "apikey@example.com") -> tuple[User, str]:
    user = User(
        email=email,
        hashed_password=hash_password("testpass1"),
        full_name="Key User",
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, create_access_token(user.id)


def _make_domain(db, slug: str = "finance") -> Domain:
    domain = Domain(name=slug.title(), slug=slug, description="test")
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


def _mock_queue():
    mock_rq_job = MagicMock()
    mock_rq_job.id = "mock-rq-api-123"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_rq_job
    return patch("app.routers.api_keys.Queue")


# ---------------------------------------------------------------------------
# POST /api-keys
# ---------------------------------------------------------------------------

def test_create_api_key_success(client: TestClient, db) -> None:
    _, token = _make_user(db)
    response = client.post(
        "/api-keys",
        json={"name": "My Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Key"
    assert data["raw_key"].startswith("sr_")
    assert "raw_key" in data


def test_create_api_key_requires_auth(client: TestClient) -> None:
    response = client.post("/api-keys", json={"name": "X"})
    assert response.status_code == 403


def test_create_api_key_missing_name(client: TestClient, db) -> None:
    _, token = _make_user(db, email="no_name@example.com")
    response = client.post(
        "/api-keys",
        json={"name": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api-keys
# ---------------------------------------------------------------------------

def test_list_api_keys_empty(client: TestClient, db) -> None:
    _, token = _make_user(db, email="empty_keys@example.com")
    response = client.get("/api-keys", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_api_keys_returns_own(client: TestClient, db) -> None:
    _, token = _make_user(db, email="list_keys@example.com")
    client.post("/api-keys", json={"name": "K1"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/api-keys", json={"name": "K2"}, headers={"Authorization": f"Bearer {token}"})
    response = client.get("/api-keys", headers={"Authorization": f"Bearer {token}"})
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# DELETE /api-keys/{id}
# ---------------------------------------------------------------------------

def test_delete_api_key_success(client: TestClient, db) -> None:
    _, token = _make_user(db, email="del_keys@example.com")
    created = client.post(
        "/api-keys", json={"name": "ToDelete"}, headers={"Authorization": f"Bearer {token}"}
    ).json()
    response = client.delete(
        f"/api-keys/{created['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204
    # Should no longer appear in list
    remaining = client.get("/api-keys", headers={"Authorization": f"Bearer {token}"}).json()
    assert all(k["id"] != created["id"] for k in remaining)


def test_delete_api_key_not_found(client: TestClient, db) -> None:
    _, token = _make_user(db, email="del_notfound@example.com")
    response = client.delete("/api-keys/99999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_delete_api_key_requires_auth(client: TestClient) -> None:
    response = client.delete("/api-keys/1")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/v1/generate
# ---------------------------------------------------------------------------

def test_v1_generate_success(client: TestClient, db) -> None:
    _, token = _make_user(db, email="v1gen@example.com")
    created_key = client.post(
        "/api-keys", json={"name": "V1Key"}, headers={"Authorization": f"Bearer {token}"}
    ).json()
    raw_key = created_key["raw_key"]
    domain = _make_domain(db)

    # Redis not available in tests; router swallows the connection error gracefully
    response = client.post(
        "/api/v1/generate",
        json={"domain_id": domain.id, "row_count": 100},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_v1_generate_invalid_key(client: TestClient, db) -> None:
    domain = _make_domain(db, "aviation")
    response = client.post(
        "/api/v1/generate",
        json={"domain_id": domain.id, "row_count": 50},
        headers={"Authorization": "Bearer sr_totallyfakekey"},
    )
    assert response.status_code == 401


def test_v1_generate_no_auth(client: TestClient, db) -> None:
    domain = _make_domain(db, "healthcare")
    response = client.post("/api/v1/generate", json={"domain_id": domain.id})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{id}
# ---------------------------------------------------------------------------

def test_v1_get_job_success(client: TestClient, db) -> None:
    _, token = _make_user(db, email="v1getjob@example.com")
    raw_key = client.post(
        "/api-keys", json={"name": "V1GetKey"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["raw_key"]
    domain = _make_domain(db, "bio")

    job = client.post(
        "/api/v1/generate",
        json={"domain_id": domain.id, "row_count": 50},
        headers={"Authorization": f"Bearer {raw_key}"},
    ).json()

    response = client.get(
        f"/api/v1/jobs/{job['id']}",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == job["id"]


def test_v1_get_job_not_found(client: TestClient, db) -> None:
    _, token = _make_user(db, email="v1notfound@example.com")
    raw_key = client.post(
        "/api-keys", json={"name": "V1NF"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["raw_key"]
    response = client.get(
        "/api/v1/jobs/99999",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 404
