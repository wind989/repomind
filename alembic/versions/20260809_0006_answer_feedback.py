"""add answer feedback

Revision ID: 20260809_0006
Revises: 20260809_0005
Create Date: 2026-08-09 02:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0006"
down_revision = "20260809_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("retrieval_log_id", sa.Integer(), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["retrieval_log_id"], ["retrieval_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("retrieval_log_id", name="uq_answer_feedback_retrieval_log_id"),
    )
    op.create_index("ix_answer_feedback_retrieval_log_id", "answer_feedback", ["retrieval_log_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_answer_feedback_retrieval_log_id", table_name="answer_feedback")
    op.drop_table("answer_feedback")
