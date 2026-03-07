import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DatasetStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("domains.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[DatasetStatus] = mapped_column(
        Enum(DatasetStatus), nullable=False, default=DatasetStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    domain: Mapped["Domain"] = relationship("Domain", back_populates="datasets")
