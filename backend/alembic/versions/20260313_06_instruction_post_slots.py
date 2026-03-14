"""instruction post slots at noon and 18h

Revision ID: 20260313_06
Revises: 20260313_05
Create Date: 2026-03-13 00:30:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260313_06"
down_revision: Union[str, Sequence[str], None] = "20260313_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE IF EXISTS telegram_instruction_post_log
        ADD COLUMN IF NOT EXISTS slot_key VARCHAR(40);
        """
    )
    op.execute(
        """
        UPDATE telegram_instruction_post_log
        SET slot_key = '18:00'
        WHERE COALESCE(slot_key, '') = '';
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS telegram_instruction_post_log
        ALTER COLUMN slot_key SET DEFAULT '18:00';
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS telegram_instruction_post_log
        ALTER COLUMN slot_key SET NOT NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS telegram_instruction_post_log
        DROP CONSTRAINT IF EXISTS telegram_instruction_post_log_day_key_key;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_telegram_instruction_post_log_day_slot
        ON telegram_instruction_post_log(day_key, slot_key);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_telegram_instruction_post_log_day_slot;")
    op.execute(
        """
        ALTER TABLE IF EXISTS telegram_instruction_post_log
        DROP COLUMN IF EXISTS slot_key;
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS telegram_instruction_post_log
        ADD CONSTRAINT telegram_instruction_post_log_day_key_key UNIQUE (day_key);
        """
    )
