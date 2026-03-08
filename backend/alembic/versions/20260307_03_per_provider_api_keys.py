"""add per-provider api key columns to user_settings

Revision ID: 20260307_03
Revises: 20260228_02
Create Date: 2026-03-07 20:30:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260307_03"
down_revision: Union[str, Sequence[str], None] = "20260228_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS api_key_gemini TEXT;"
    )
    op.execute(
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS api_key_openai TEXT;"
    )
    op.execute(
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS api_key_groq TEXT;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS api_key_groq;")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS api_key_openai;")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS api_key_gemini;")
