"""quiz stats sync tables

Revision ID: 20260228_02
Revises: 20260226_01
Create Date: 2026-02-28 00:00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260228_02"
down_revision: Union[str, Sequence[str], None] = "20260226_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_stats_daily (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            day_key DATE NOT NULL,
            questoes INTEGER DEFAULT 0,
            acertos INTEGER DEFAULT 0,
            xp_ganho INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_quiz_stats_daily UNIQUE (user_id, day_key)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_quiz_stats_daily_user_day ON quiz_stats_daily(user_id, day_key DESC);"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_stats_events (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            event_id VARCHAR(120) NOT NULL,
            occurred_at TIMESTAMP DEFAULT NOW(),
            questoes_delta INTEGER DEFAULT 1,
            acertos_delta INTEGER DEFAULT 0,
            xp_delta INTEGER DEFAULT 0,
            correta INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_quiz_stats_event_user UNIQUE (user_id, event_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_quiz_stats_events_user_created ON quiz_stats_events(user_id, created_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quiz_stats_events_user_created;")
    op.execute("DROP TABLE IF EXISTS quiz_stats_events;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_stats_daily_user_day;")
    op.execute("DROP TABLE IF EXISTS quiz_stats_daily;")
