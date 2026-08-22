"""add MRR evaluation metrics

Revision ID: 20260822_0009
Revises: 20260810_0008
Create Date: 2026-08-22 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260822_0009"
down_revision = "20260810_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing runs deliberately remain NULL: they were created before MRR was
    # calculated and must not be presented as if they had been re-evaluated.
    op.add_column("evaluation_runs", sa.Column("mrr", sa.Float(), nullable=True))
    op.add_column("evaluation_case_results", sa.Column("expected_rank", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation_case_results", "expected_rank")
    op.drop_column("evaluation_runs", "mrr")
