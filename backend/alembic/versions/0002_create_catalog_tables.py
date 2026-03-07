"""create catalog tables (domains, datasets)

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-07 00:00:01.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_domains_id"), "domains", ["id"], unique=False)

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("domain_id", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("column_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_cost", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="datasetstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["domain_id"], ["domains.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_datasets_id"), "datasets", ["id"], unique=False)
    op.create_index(op.f("ix_datasets_domain_id"), "datasets", ["domain_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_datasets_domain_id"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_id"), table_name="datasets")
    op.drop_table("datasets")
    op.execute("DROP TYPE IF EXISTS datasetstatus")
    op.drop_index(op.f("ix_domains_id"), table_name="domains")
    op.drop_table("domains")
