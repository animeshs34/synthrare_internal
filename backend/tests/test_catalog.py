import pytest
from fastapi.testclient import TestClient

from app.models.domain import Domain
from app.models.dataset import Dataset
from app.services.auth import create_access_token
from app.models.user import User, UserRole


def _make_admin(db) -> str:
    """Create an admin user and return a valid access token."""
    from app.services.auth import hash_password
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Admin",
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_access_token(user.id)


def _make_user(db, email: str = "user@example.com") -> tuple[User, str]:
    from app.services.auth import hash_password
    user = User(
        email=email,
        hashed_password=hash_password("userpass1"),
        full_name="Regular",
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


def _make_dataset(db, domain: Domain, credit_cost: int = 1) -> Dataset:
    ds = Dataset(
        name="Test Dataset",
        description="desc",
        domain_id=domain.id,
        storage_path="seed/test/data.csv",
        row_count=100,
        column_count=5,
        credit_cost=credit_cost,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


# ---------------------------------------------------------------------------
# GET /catalog
# ---------------------------------------------------------------------------

def test_list_datasets_empty(client: TestClient) -> None:
    response = client.get("/catalog")
    assert response.status_code == 200
    assert response.json() == []


def test_list_datasets_returns_active(client: TestClient, db) -> None:
    domain = _make_domain(db)
    _make_dataset(db, domain)
    response = client.get("/catalog")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_datasets_filter_by_domain(client: TestClient, db) -> None:
    d1 = _make_domain(db, "finance")
    d2 = _make_domain(db, "aviation")
    _make_dataset(db, d1)
    _make_dataset(db, d2)
    response = client.get("/catalog?domain_slug=finance")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["domain"]["slug"] == "finance"


# ---------------------------------------------------------------------------
# GET /catalog/{id}
# ---------------------------------------------------------------------------

def test_get_dataset_success(client: TestClient, db) -> None:
    domain = _make_domain(db)
    ds = _make_dataset(db, domain)
    response = client.get(f"/catalog/{ds.id}")
    assert response.status_code == 200
    assert response.json()["id"] == ds.id


def test_get_dataset_not_found(client: TestClient) -> None:
    response = client.get("/catalog/99999")
    assert response.status_code == 404


def test_get_dataset_returns_domain(client: TestClient, db) -> None:
    domain = _make_domain(db)
    ds = _make_dataset(db, domain)
    data = client.get(f"/catalog/{ds.id}").json()
    assert data["domain"]["slug"] == domain.slug


# ---------------------------------------------------------------------------
# POST /catalog (admin only)
# ---------------------------------------------------------------------------

def test_create_dataset_as_admin(client: TestClient, db) -> None:
    admin_token = _make_admin(db)
    domain = _make_domain(db)
    response = client.post(
        "/catalog",
        json={
            "name": "New Dataset",
            "description": "fresh",
            "domain_id": domain.id,
            "storage_path": "uploads/new.csv",
            "row_count": 500,
            "column_count": 10,
            "credit_cost": 2,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "New Dataset"


def test_create_dataset_requires_auth(client: TestClient, db) -> None:
    domain = _make_domain(db)
    response = client.post(
        "/catalog",
        json={"name": "X", "domain_id": domain.id, "storage_path": "x.csv"},
    )
    assert response.status_code == 403


def test_create_dataset_non_admin_forbidden(client: TestClient, db) -> None:
    _, token = _make_user(db)
    domain = _make_domain(db)
    response = client.post(
        "/catalog",
        json={"name": "X", "domain_id": domain.id, "storage_path": "x.csv"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_create_dataset_bad_domain(client: TestClient, db) -> None:
    admin_token = _make_admin(db)
    response = client.post(
        "/catalog",
        json={"name": "X", "domain_id": 99999, "storage_path": "x.csv"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /catalog/{id}/download
# ---------------------------------------------------------------------------

def test_download_deducts_credits(client: TestClient, db) -> None:
    domain = _make_domain(db)
    ds = _make_dataset(db, domain, credit_cost=2)
    user, token = _make_user(db)
    # user starts with 10 credits
    response = client.post(
        f"/catalog/{ds.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["credits_remaining"] == "8"


def test_download_insufficient_credits(client: TestClient, db) -> None:
    domain = _make_domain(db)
    ds = _make_dataset(db, domain, credit_cost=100)
    _, token = _make_user(db, email="broke@example.com")
    response = client.post(
        f"/catalog/{ds.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 402


def test_download_requires_auth(client: TestClient, db) -> None:
    response = client.post("/catalog/1/download")
    assert response.status_code == 403


def test_download_not_found(client: TestClient, db) -> None:
    _, token = _make_user(db, email="lost@example.com")
    response = client.post(
        "/catalog/99999/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
