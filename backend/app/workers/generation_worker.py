"""RQ worker task for synthetic data generation.

Generation priority (see app/services/gradient.py for details):
  1. DO Gradient Inference  — LLM-generated realistic data (requires DO_GRADIENT_API_KEY +
                               DO_GRADIENT_INFERENCE_ENDPOINT)
  2. Statistical fallback   — always available, no external dependencies

After generation the CSV is uploaded via the storage service (DO Spaces or local),
and the job record is updated with the result path.
"""
import io
import json
import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.domain import Domain
from app.models.job import Job, JobStatus
from app.services.gradient import dataframe_to_csv_bytes, generate_for_domain
from app.services.storage import upload_file

log = logging.getLogger(__name__)


def generate_synthetic_data(job_id: int) -> None:
    """Entry point executed by the RQ worker."""
    db: Session = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            log.error("Job %d not found", job_id)
            return

        job.status = JobStatus.RUNNING
        db.commit()

        result_path = _run_generation(db, job)

        job.status = JobStatus.COMPLETED
        job.result_path = result_path
        db.commit()
        log.info("Job %d completed — result: %s", job_id, result_path)

    except Exception as exc:
        log.exception("Job %d failed: %s", job_id, exc)
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


def _run_generation(db: Session, job: Job) -> str:
    """
    Generate synthetic data and upload it. Returns the storage path.

    Steps:
      1. Resolve domain slug from job.domain_id
      2. Call generate_for_domain (Gradient → statistical fallback)
      3. Serialise DataFrame to CSV bytes
      4. Upload via storage service (DO Spaces or local)
    """
    domain = db.query(Domain).filter(Domain.id == job.domain_id).first()
    domain_slug = domain.slug if domain else "finance"
    parameters = json.loads(job.parameters) if job.parameters else {}

    log.info("Generating %d rows for domain '%s' (job %d)", job.row_count, domain_slug, job.id)
    df = generate_for_domain(domain_slug, job.row_count, parameters)

    csv_bytes = dataframe_to_csv_bytes(df)
    storage_path = f"results/job_{job.id}/synthetic_{job.row_count}_rows.csv"
    upload_file(io.BytesIO(csv_bytes), storage_path, content_type="text/csv")

    return storage_path
