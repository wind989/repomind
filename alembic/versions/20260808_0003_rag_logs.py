"""add retrieval logs and answer citations

Revision ID: 20260808_0003
Revises: 20260808_0002
Create Date: 2026-08-08 13:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260808_0003"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("retrieved_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_logs_knowledge_base_id", "retrieval_logs", ["knowledge_base_id"], unique=False)

    op.create_table(
        "answer_citations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("retrieval_log_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("document_chunk_id", sa.Integer(), nullable=False),
        sa.Column("citation_rank", sa.Integer(), nullable=False),
        sa.Column("distance", sa.Float(), nullable=False),
        sa.Column("document_title", sa.String(length=200), nullable=False),
        sa.Column("content_excerpt", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["retrieval_log_id"], ["retrieval_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_answer_citations_retrieval_log_id", "answer_citations", ["retrieval_log_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_answer_citations_retrieval_log_id", table_name="answer_citations")
    op.drop_table("answer_citations")
    op.drop_index("ix_retrieval_logs_knowledge_base_id", table_name="retrieval_logs")
    op.drop_table("retrieval_logs")
