from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.api_key import ApiKey, generate_api_key, hash_api_key
from app.models.domain import Domain
from app.models.job import Job
from app.models.user import User
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.schemas.jobs import JobCreate, JobResponse

router = APIRouter(tags=["api_keys"])

limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------

@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    raw_key, key_hash = generate_api_key()
    api_key = ApiKey(user_id=current_user.id, name=payload.name, key_hash=key_hash)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "is_active": api_key.is_active,
        "last_used_at": api_key.last_used_at,
        "created_at": api_key.created_at,
        "raw_key": raw_key,
    }


@router.get("/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ApiKey]:
    return db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id, ApiKey.is_active == True  # noqa: E712
    ).all()


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id, ApiKey.user_id == current_user.id
    ).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Public API v1
# ---------------------------------------------------------------------------

def _authenticate_api_key(request: Request, db: Session) -> User:
    """Resolve 'Authorization: Bearer sr_...' as an API key (not a JWT)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer sr_"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid API key required")
    raw_key = auth.removeprefix("Bearer ")
    key_hash = hash_api_key(raw_key)
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash, ApiKey.is_active == True  # noqa: E712
    ).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return api_key.user


@router.post("/api/v1/generate", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def v1_generate(
    request: Request,
    payload: JobCreate,
    db: Session = Depends(get_db),
) -> Job:
    """Public API: enqueue a synthetic data generation job."""
    import json
    from app.workers.generation_worker import generate_synthetic_data
    from redis import Redis
    from rq import Queue

    current_user = _authenticate_api_key(request, db)

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

    from app.config import settings
    try:
        redis_conn = Redis.from_url(settings.redis_url)
        q = Queue("generation", connection=redis_conn)
        rq_job = q.enqueue(generate_synthetic_data, job.id)
        job.rq_job_id = rq_job.id
        db.commit()
    except Exception:
        pass

    return job


@router.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
@limiter.limit("60/minute")
def v1_get_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Job:
    """Public API: get job status."""
    current_user = _authenticate_api_key(request, db)
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
