"""telegram community auto post tables

Revision ID: 20260312_04
Revises: 20260307_03
Create Date: 2026-03-12 00:00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260312_04"
down_revision: Union[str, Sequence[str], None] = "20260307_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_community_config (
            id BIGSERIAL PRIMARY KEY,
            chat_id VARCHAR(64) NOT NULL,
            atualizacoes_thread_id INTEGER NULL,
            comece_aqui_thread_id INTEGER NULL,
            bate_papo_thread_id INTEGER NULL,
            resultados_thread_id INTEGER NULL,
            suporte_thread_id INTEGER NULL,
            feedbacks_thread_id INTEGER NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_daily_post_log (
            id BIGSERIAL PRIMARY KEY,
            day_key DATE NOT NULL UNIQUE,
            topic_key VARCHAR(40) DEFAULT 'atualizacoes',
            chat_id VARCHAR(64) NOT NULL,
            message_thread_id INTEGER NULL,
            post_text TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'pending',
            attempt_count INTEGER DEFAULT 0,
            last_attempt_at TIMESTAMP NULL,
            sent_at TIMESTAMP NULL,
            last_error TEXT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_telegram_daily_post_log_status ON telegram_daily_post_log(status);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_telegram_daily_post_log_status;")
    op.execute("DROP TABLE IF EXISTS telegram_daily_post_log;")
    op.execute("DROP TABLE IF EXISTS telegram_community_config;")
