from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.dataset import Dataset, DatasetStatus
from app.models.domain import Domain
from app.models.user import User
from app.schemas.catalog import DatasetCreate, DatasetListItem, DatasetResponse, DomainResponse
from app.services import storage

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/domains", response_model=list[DomainResponse])
def list_domains(db: Session = Depends(get_db)) -> list[Domain]:
    return db.query(Domain).order_by(Domain.name).all()


@router.get("", response_model=list[DatasetListItem])
def list_datasets(
    domain_slug: str | None = None,
    db: Session = Depends(get_db),
) -> list[Dataset]:
    query = db.query(Dataset).filter(Dataset.status == DatasetStatus.ACTIVE)
    if domain_slug:
        query = query.join(Domain).filter(Domain.slug == domain_slug)
    return query.all()


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.status == DatasetStatus.ACTIVE)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_dataset(
    payload: DatasetCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Dataset:
    domain = db.query(Domain).filter(Domain.id == payload.domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    dataset = Dataset(
        name=payload.name,
        description=payload.description,
        domain_id=payload.domain_id,
        storage_path=payload.storage_path,
        row_count=payload.row_count,
        column_count=payload.column_count,
        credit_cost=payload.credit_cost,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.post("/{dataset_id}/download")
def download_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.status == DatasetStatus.ACTIVE)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    if current_user.credits < dataset.credit_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {dataset.credit_cost}, have {current_user.credits}",
        )

    current_user.credits -= dataset.credit_cost
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Credit deduction failed") from exc

    url = storage.generate_download_url(dataset.storage_path)
    return {"download_url": url, "credits_remaining": str(current_user.credits)}
