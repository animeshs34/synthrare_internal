import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, values_callable=lambda obj: [e.value for e in obj],
             name="reportstatus", create_type=False),
        nullable=False,
        default=ReportStatus.PENDING,
    )
    # Overall composite fidelity score: 0.0 – 1.0 (higher is better)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # KS statistic averaged over numeric columns (lower = better)
    ks_statistic: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Absolute mean difference in Pearson correlations (lower = better)
    correlation_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Fraction of real data distribution covered by synthetic (higher = better)
    coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON array: [{column: str, score: float}]
    column_scores: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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

    job: Mapped["Job"] = relationship("Job")
