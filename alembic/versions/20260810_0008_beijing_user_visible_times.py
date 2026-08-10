"""store user-visible DATETIME values as Asia/Shanghai wall-clock time

Revision ID: 20260810_0008
Revises: 20260809_0007
Create Date: 2026-08-10 00:00:00

Existing RepoMind DATETIME values were written as UTC without timezone metadata.
This migration converts each existing non-null value to Beijing wall-clock time
by adding eight hours, then changes MySQL defaults for future direct inserts.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260810_0008"
down_revision = "20260809_0007"
branch_labels = None
depends_on = None


BEIJING_DEFAULT = sa.text("(UTC_TIMESTAMP() + INTERVAL 8 HOUR)")

# Table and column names are static migration metadata, never user input.
TIME_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("knowledge_bases", "created_at", False),
    ("knowledge_bases", "updated_at", False),
    ("documents", "processed_at", True),
    ("documents", "created_at", False),
    ("documents", "updated_at", False),
    ("chat_messages", "created_at", False),
    ("document_chunks", "created_at", False),
    ("document_processing_tasks", "created_at", False),
    ("document_processing_tasks", "started_at", True),
    ("document_processing_tasks", "completed_at", True),
    ("retrieval_logs", "created_at", False),
    ("evaluation_runs", "created_at", False),
    ("answer_feedback", "created_at", False),
    ("answer_feedback", "updated_at", False),
    ("users", "created_at", False),
    ("users", "updated_at", False),
)

DEFAULT_COLUMNS = frozenset(
    {
        ("knowledge_bases", "created_at"),
        ("knowledge_bases", "updated_at"),
        ("documents", "created_at"),
        ("documents", "updated_at"),
        ("chat_messages", "created_at"),
        ("document_chunks", "created_at"),
        ("document_processing_tasks", "created_at"),
        ("retrieval_logs", "created_at"),
        ("evaluation_runs", "created_at"),
        ("answer_feedback", "created_at"),
        ("answer_feedback", "updated_at"),
        ("users", "created_at"),
        ("users", "updated_at"),
    }
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("20260810_0008 requires MySQL because RepoMind DATETIME data is MySQL-backed")

    # Values created before this revision are known UTC wall-clock values. DATETIME
    # has no timezone metadata, so DATE_ADD preserves the instant for user display.
    for table_name, column_name, _nullable in TIME_COLUMNS:
        op.execute(
            sa.text(
                f"UPDATE `{table_name}` "
                f"SET `{column_name}` = DATE_ADD(`{column_name}`, INTERVAL 8 HOUR) "
                f"WHERE `{column_name}` IS NOT NULL"
            )
        )

    # Keep database-side defaults correct for direct SQL inserts. SQLAlchemy ORM
    # writes use app.core.timezone.beijing_now as well.
    for table_name, column_name, nullable in TIME_COLUMNS:
        if (table_name, column_name) in DEFAULT_COLUMNS:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(),
                existing_nullable=nullable,
                server_default=BEIJING_DEFAULT,
            )


def downgrade() -> None:
    raise RuntimeError(
        "20260810_0008 is intentionally irreversible: subtracting eight hours "
        "would corrupt rows created after the timezone migration. Restore a "
        "database backup instead."
    )
