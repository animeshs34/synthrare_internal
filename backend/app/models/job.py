import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    domain_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("domains.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    parameters: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, values_callable=lambda obj: [e.value for e in obj],
             name="jobstatus", create_type=False),
        nullable=False,
        default=JobStatus.PENDING,
    )
    rq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    dataset: Mapped["Dataset | None"] = relationship("Dataset")
    domain: Mapped["Domain"] = relationship("Domain")
