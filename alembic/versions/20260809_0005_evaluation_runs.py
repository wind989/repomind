"""add retrieval evaluation runs

Revision ID: 20260809_0005
Revises: 20260809_0004
Create Date: 2026-08-09 01:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0005"
down_revision = "20260809_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("top1_hit_count", sa.Integer(), nullable=False),
        sa.Column("recall_hit_count", sa.Integer(), nullable=False),
        sa.Column("average_keyword_latency_ms", sa.Integer(), nullable=False),
        sa.Column("average_vector_latency_ms", sa.Integer(), nullable=False),
        sa.Column("average_fusion_latency_ms", sa.Integer(), nullable=False),
        sa.Column("average_rerank_latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_knowledge_base_id", "evaluation_runs", ["knowledge_base_id"], unique=False)

    op.create_table(
        "evaluation_case_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_run_id", sa.Integer(), nullable=False),
        sa.Column("case_key", sa.String(length=100), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_document_title", sa.String(length=200), nullable=False),
        sa.Column("top1_document_title", sa.String(length=200), nullable=True),
        sa.Column("top1_hit", sa.Boolean(), nullable=False),
        sa.Column("recall_hit", sa.Boolean(), nullable=False),
        sa.Column("retrieved_count", sa.Integer(), nullable=False),
        sa.Column("candidate_titles_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_run_id", "case_key", name="uq_evaluation_case_results_run_case"),
    )
    op.create_index(
        "ix_evaluation_case_results_evaluation_run_id",
        "evaluation_case_results",
        ["evaluation_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_case_results_evaluation_run_id", table_name="evaluation_case_results")
    op.drop_table("evaluation_case_results")
    op.drop_index("ix_evaluation_runs_knowledge_base_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
