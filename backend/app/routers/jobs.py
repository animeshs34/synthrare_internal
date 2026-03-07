import json

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.domain import Domain
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.jobs import JobCreate, JobResponse
from app.workers.generation_worker import generate_synthetic_data

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_queue() -> Queue:
    redis_conn = Redis.from_url(settings.redis_url)
    return Queue("generation", connection=redis_conn)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    domain = db.query(Domain).filter(Domain.id == payload.domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    job = Job(
        user_id=current_user.id,
        domain_id=payload.domain_id,
        dataset_id=payload.dataset_id,
        row_count=payload.row_count,
        parameters=json.dumps(payload.parameters),
    )
    db.add(job)
    try:
        db.commit()
        db.refresh(job)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create job") from exc

    # Enqueue the generation task
    try:
        q = _get_queue()
        rq_job = q.enqueue(generate_synthetic_data, job.id)
        job.rq_job_id = rq_job.id
        db.commit()
    except Exception:
        # Worker may not be running in test/dev — job stays PENDING
        pass

    return job


@router.get("", response_model=list[JobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Job]:
    return db.query(Job).filter(Job.user_id == current_user.id).order_by(Job.created_at.desc()).all()


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
