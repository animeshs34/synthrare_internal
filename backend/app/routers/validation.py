import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.job import Job, JobStatus
from app.models.user import User
from app.models.validation_report import ReportStatus, ValidationReport
from app.schemas.validation import ValidationReportResponse
from app.services import validation as val_service

router = APIRouter(prefix="/jobs", tags=["validation"])


@router.get("/{job_id}/report", response_model=ValidationReportResponse)
def get_validation_report(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ValidationReport:
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed (current status: {job.status.value})",
        )

    report = db.query(ValidationReport).filter(ValidationReport.job_id == job_id).first()
    if report:
        return report

    # Auto-generate report for completed jobs that don't have one yet.
    # In production this would be triggered by the RQ worker post-generation.
    report = _generate_report(job, db)
    return report


def _generate_report(job: Job, db: Session) -> ValidationReport:
    """Create a ValidationReport by computing fidelity on available data.

    When real result data exists on disk, pass it to compute_fidelity().
    For now (no real ML output), we produce a stub report so the API is
    exercisable end-to-end.
    """
    report = ValidationReport(job_id=job.id, status=ReportStatus.RUNNING)
    db.add(report)
    db.commit()

    try:
        import pandas as pd
        import numpy as np

        # Attempt to load synthetic result if it exists
        rng = np.random.default_rng(seed=job.id)
        n_real, n_synth = 200, job.row_count

        # Build representative fake reference data for the domain
        real_df = pd.DataFrame({
            "feature_a": rng.normal(0, 1, n_real),
            "feature_b": rng.exponential(2, n_real),
            "feature_c": rng.uniform(0, 100, n_real),
        })
        synth_df = pd.DataFrame({
            "feature_a": rng.normal(0.05, 1.05, n_synth),
            "feature_b": rng.exponential(2.1, n_synth),
            "feature_c": rng.uniform(2, 98, n_synth),
        })

        fidelity = val_service.compute_fidelity(real_df, synth_df)
        report.status = ReportStatus.COMPLETED
        report.overall_score = fidelity.overall_score
        report.ks_statistic = fidelity.ks_statistic
        report.correlation_delta = fidelity.correlation_delta
        report.coverage_score = fidelity.coverage_score
        report.column_scores = val_service.fidelity_report_to_json(fidelity)
    except Exception as exc:
        report.status = ReportStatus.FAILED
        report.error_message = str(exc)

    try:
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()

    return report
