"""RQ worker task for synthetic data generation."""
import json
import time

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.job import Job, JobStatus


def generate_synthetic_data(job_id: int) -> None:
    """
    Entry point executed by the RQ worker.

    In production this calls the ML inference layer (DO Gradient / HuggingFace).
    For now it simulates generation with a placeholder.
    """
    db: Session = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = JobStatus.RUNNING
        db.commit()

        result_path = _run_generation(job_id, job.domain_id, job.row_count, json.loads(job.parameters))

        job.status = JobStatus.COMPLETED
        job.result_path = result_path
        db.commit()
    except Exception as exc:
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def _run_generation(job_id: int, domain_id: int, row_count: int, parameters: dict) -> str:
    """
    Placeholder — replace with real ML inference call.
    Returns the storage path of the generated file.
    """
    # Simulate work
    time.sleep(0.1)
    return f"results/job_{job_id}/synthetic_{row_count}_rows.csv"
