"""add hybrid retrieval candidates and timing fields

Revision ID: 20260809_0004
Revises: 20260808_0003
Create Date: 2026-08-09 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0004"
down_revision = "20260808_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_logs",
        sa.Column("keyword_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("vector_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("fusion_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("rerank_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.alter_column(
        "answer_citations",
        "distance",
        existing_type=sa.Float(),
        nullable=True,
    )

    op.create_table(
        "retrieval_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("retrieval_log_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("document_chunk_id", sa.Integer(), nullable=False),
        sa.Column("document_title", sa.String(length=200), nullable=False),
        sa.Column("content_excerpt", sa.Text(), nullable=False),
        sa.Column("keyword_rank", sa.Integer(), nullable=True),
        sa.Column("keyword_score", sa.Float(), nullable=True),
        sa.Column("vector_rank", sa.Integer(), nullable=True),
        sa.Column("vector_distance", sa.Float(), nullable=True),
        sa.Column("rrf_score", sa.Float(), nullable=False),
        sa.Column("rerank_score", sa.Float(), nullable=False),
        sa.Column("final_rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["retrieval_log_id"], ["retrieval_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_candidates_retrieval_log_id",
        "retrieval_candidates",
        ["retrieval_log_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_retrieval_candidates_retrieval_log_id", table_name="retrieval_candidates")
    op.drop_table("retrieval_candidates")
    op.execute("UPDATE answer_citations SET distance = 0 WHERE distance IS NULL")
    op.alter_column(
        "answer_citations",
        "distance",
        existing_type=sa.Float(),
        nullable=False,
    )
    op.drop_column("retrieval_logs", "rerank_latency_ms")
    op.drop_column("retrieval_logs", "fusion_latency_ms")
    op.drop_column("retrieval_logs", "vector_latency_ms")
    op.drop_column("retrieval_logs", "keyword_latency_ms")
