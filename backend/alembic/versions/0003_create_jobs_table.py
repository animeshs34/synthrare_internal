"""create jobs table

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-07 00:00:02.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("domain_id", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("parameters", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="jobstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("rq_job_id", sa.String(length=255), nullable=True),
        sa.Column("result_path", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["domain_id"], ["domains.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_id"), "jobs", ["id"], unique=False)
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"], unique=False)
    op.create_index(op.f("ix_jobs_dataset_id"), "jobs", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_jobs_domain_id"), "jobs", ["domain_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_domain_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_dataset_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_user_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_id"), table_name="jobs")
    op.drop_table("jobs")
    op.execute("DROP TYPE IF EXISTS jobstatus")
