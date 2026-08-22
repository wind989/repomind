"""add Ragas context evaluation metrics

Revision ID: 20260822_0010
Revises: 20260822_0009
Create Date: 2026-08-22 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260822_0010"
down_revision = "20260822_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluation_runs", sa.Column("ragas_context_precision", sa.Float(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("ragas_context_recall", sa.Float(), nullable=True))
    op.add_column("evaluation_case_results", sa.Column("ragas_context_precision", sa.Float(), nullable=True))
    op.add_column("evaluation_case_results", sa.Column("ragas_context_recall", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation_case_results", "ragas_context_recall")
    op.drop_column("evaluation_case_results", "ragas_context_precision")
    op.drop_column("evaluation_runs", "ragas_context_recall")
    op.drop_column("evaluation_runs", "ragas_context_precision")
