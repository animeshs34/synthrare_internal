from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.domain import Domain
from app.models.user import User, UserRole
from app.services.auth import create_access_token, hash_password


def _make_user(db, email: str = "worker@example.com") -> tuple[User, str]:
    user = User(
        email=email,
        hashed_password=hash_password("userpass1"),
        full_name="Worker",
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, create_access_token(user.id)


def _make_domain(db, slug: str = "finance") -> Domain:
    domain = Domain(name=slug.title(), slug=slug, description="Test domain")
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


def _mock_queue():
    """Return a patch context that makes RQ Queue.enqueue a no-op."""
    mock_rq_job = MagicMock()
    mock_rq_job.id = "mock-rq-id-123"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_rq_job
    return patch("app.routers.jobs._get_queue", return_value=mock_queue)


# ---------------------------------------------------------------------------
# POST /jobs
# ---------------------------------------------------------------------------

def test_create_job_success(client: TestClient, db) -> None:
    _, token = _make_user(db)
    domain = _make_domain(db)
    with _mock_queue():
        response = client.post(
            "/jobs",
            json={"domain_id": domain.id, "row_count": 500},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["domain_id"] == domain.id
    assert data["row_count"] == 500
    assert data["status"] == "pending"


def test_create_job_requires_auth(client: TestClient, db) -> None:
    domain = _make_domain(db)
    response = client.post("/jobs", json={"domain_id": domain.id})
    assert response.status_code == 403


def test_create_job_bad_domain(client: TestClient, db) -> None:
    _, token = _make_user(db, email="baddom@example.com")
    with _mock_queue():
        response = client.post(
            "/jobs",
            json={"domain_id": 99999, "row_count": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404


def test_create_job_invalid_row_count(client: TestClient, db) -> None:
    _, token = _make_user(db, email="rowcheck@example.com")
    domain = _make_domain(db, "aviation")
    response = client.post(
        "/jobs",
        json={"domain_id": domain.id, "row_count": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------

def test_list_jobs_empty(client: TestClient, db) -> None:
    _, token = _make_user(db, email="empty@example.com")
    response = client.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_jobs_returns_user_jobs_only(client: TestClient, db) -> None:
    _, token1 = _make_user(db, email="u1@example.com")
    _, token2 = _make_user(db, email="u2@example.com")
    domain = _make_domain(db, "healthcare")
    with _mock_queue():
        client.post(
            "/jobs",
            json={"domain_id": domain.id, "row_count": 100},
            headers={"Authorization": f"Bearer {token1}"},
        )
    response = client.get("/jobs", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_jobs_requires_auth(client: TestClient) -> None:
    response = client.get("/jobs")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /jobs/{id}
# ---------------------------------------------------------------------------

def test_get_job_success(client: TestClient, db) -> None:
    _, token = _make_user(db, email="getjob@example.com")
    domain = _make_domain(db, "fintech")
    with _mock_queue():
        created = client.post(
            "/jobs",
            json={"domain_id": domain.id, "row_count": 200},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
    response = client.get(f"/jobs/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_job_not_found(client: TestClient, db) -> None:
    _, token = _make_user(db, email="notfound@example.com")
    response = client.get("/jobs/99999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_get_job_requires_auth(client: TestClient) -> None:
    response = client.get("/jobs/1")
    assert response.status_code == 403


def test_get_job_not_owned_by_user(client: TestClient, db) -> None:
    _, token1 = _make_user(db, email="owner@example.com")
    _, token2 = _make_user(db, email="other@example.com")
    domain = _make_domain(db, "bio")
    with _mock_queue():
        created = client.post(
            "/jobs",
            json={"domain_id": domain.id, "row_count": 50},
            headers={"Authorization": f"Bearer {token1}"},
        ).json()
    response = client.get(f"/jobs/{created['id']}", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 404
