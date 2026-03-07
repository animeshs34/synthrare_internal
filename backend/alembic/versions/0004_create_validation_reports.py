"""create validation_reports table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-07 00:00:03.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="reportstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("ks_statistic", sa.Float(), nullable=True),
        sa.Column("correlation_delta", sa.Float(), nullable=True),
        sa.Column("coverage_score", sa.Float(), nullable=True),
        sa.Column("column_scores", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(op.f("ix_validation_reports_id"), "validation_reports", ["id"], unique=False)
    op.create_index(op.f("ix_validation_reports_job_id"), "validation_reports", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_validation_reports_job_id"), table_name="validation_reports")
    op.drop_index(op.f("ix_validation_reports_id"), table_name="validation_reports")
    op.drop_table("validation_reports")
    op.execute("DROP TYPE IF EXISTS reportstatus")
