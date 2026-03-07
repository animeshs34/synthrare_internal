import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.models.domain import Domain
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole
from app.models.validation_report import ReportStatus, ValidationReport
from app.services.auth import create_access_token, hash_password
from app.services.validation import FidelityReport, compute_fidelity


# ---------------------------------------------------------------------------
# Unit tests — fidelity scoring
# ---------------------------------------------------------------------------

def _make_dfs(n: int = 300) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(42)
    real = pd.DataFrame({
        "x": rng.normal(0, 1, n),
        "y": rng.exponential(2, n),
        "z": rng.uniform(0, 100, n),
    })
    synth = pd.DataFrame({
        "x": rng.normal(0.1, 1.1, n),
        "y": rng.exponential(2.2, n),
        "z": rng.uniform(1, 99, n),
    })
    return real, synth


def test_fidelity_scores_range():
    real, synth = _make_dfs()
    report = compute_fidelity(real, synth)
    assert 0.0 <= report.overall_score <= 1.0
    assert 0.0 <= report.ks_statistic <= 1.0
    assert 0.0 <= report.coverage_score <= 1.0


def test_fidelity_identical_data_high_score():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"a": rng.normal(0, 1, 500), "b": rng.normal(5, 2, 500)})
    report = compute_fidelity(df, df.copy())
    assert report.overall_score >= 0.8
    assert report.ks_statistic <= 0.15


def test_fidelity_completely_different_low_score():
    real = pd.DataFrame({"a": np.zeros(200), "b": np.ones(200)})
    synth = pd.DataFrame({"a": np.full(200, 1000.0), "b": np.full(200, -1000.0)})
    report = compute_fidelity(real, synth)
    assert report.overall_score <= 0.5


def test_fidelity_column_scores_present():
    real, synth = _make_dfs()
    report = compute_fidelity(real, synth)
    assert len(report.column_scores) == 3
    for col_score in report.column_scores:
        assert "column" in col_score
        assert "score" in col_score
        assert "ks" in col_score


def test_fidelity_no_numeric_columns():
    real = pd.DataFrame({"cat": ["a", "b", "c"] * 50})
    synth = pd.DataFrame({"cat": ["a", "b", "d"] * 50})
    report = compute_fidelity(real, synth)
    assert report.overall_score == 0.0


# ---------------------------------------------------------------------------
# Integration tests — GET /jobs/{id}/report
# ---------------------------------------------------------------------------

def _make_user_and_token(db, email: str = "val@example.com") -> tuple[User, str]:
    user = User(
        email=email,
        hashed_password=hash_password("testpass1"),
        full_name="Val User",
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, create_access_token(user.id)


def _make_domain(db) -> Domain:
    domain = Domain(name="Finance", slug="finance", description="test")
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


def _make_completed_job(db, user_id: int, domain_id: int) -> Job:
    job = Job(
        user_id=user_id,
        domain_id=domain_id,
        row_count=100,
        parameters="{}",
        status=JobStatus.COMPLETED,
        result_path="results/job_1/out.csv",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _make_pending_job(db, user_id: int, domain_id: int) -> Job:
    job = Job(
        user_id=user_id,
        domain_id=domain_id,
        row_count=100,
        parameters="{}",
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_get_report_success(client: TestClient, db) -> None:
    user, token = _make_user_and_token(db)
    domain = _make_domain(db)
    job = _make_completed_job(db, user.id, domain.id)

    response = client.get(
        f"/jobs/{job.id}/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.id
    assert data["status"] == "completed"
    assert data["overall_score"] is not None
    assert isinstance(data["column_scores"], list)


def test_get_report_requires_auth(client: TestClient, db) -> None:
    response = client.get("/jobs/1/report")
    assert response.status_code == 403


def test_get_report_job_not_found(client: TestClient, db) -> None:
    _, token = _make_user_and_token(db, email="notfound_val@example.com")
    response = client.get(
        "/jobs/99999/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_get_report_job_not_completed(client: TestClient, db) -> None:
    user, token = _make_user_and_token(db, email="pending_val@example.com")
    domain = _make_domain(db)
    job = _make_pending_job(db, user.id, domain.id)

    response = client.get(
        f"/jobs/{job.id}/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_get_report_returns_cached(client: TestClient, db) -> None:
    user, token = _make_user_and_token(db, email="cached_val@example.com")
    domain = _make_domain(db)
    job = _make_completed_job(db, user.id, domain.id)

    # Pre-seed a completed report
    report = ValidationReport(
        job_id=job.id,
        status=ReportStatus.COMPLETED,
        overall_score=0.91,
        ks_statistic=0.05,
        correlation_delta=0.03,
        coverage_score=0.97,
        column_scores=json.dumps([{"column": "x", "score": 0.95, "ks": 0.05}]),
    )
    db.add(report)
    db.commit()

    response = client.get(
        f"/jobs/{job.id}/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["overall_score"] == pytest.approx(0.91)


def test_get_report_not_owned_by_user(client: TestClient, db) -> None:
    user1, _ = _make_user_and_token(db, email="owner_val@example.com")
    _, token2 = _make_user_and_token(db, email="other_val@example.com")
    domain = _make_domain(db)
    job = _make_completed_job(db, user1.id, domain.id)

    response = client.get(
        f"/jobs/{job.id}/report",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert response.status_code == 404
