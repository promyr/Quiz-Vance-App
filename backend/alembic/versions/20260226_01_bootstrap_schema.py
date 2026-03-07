"""bootstrap schema

Revision ID: 20260226_01
Revises:
Create Date: 2026-02-26 00:00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260226_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            email_id VARCHAR(190) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            xp INTEGER DEFAULT 0,
            level VARCHAR(50) DEFAULT 'Bronze',
            streak_days INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email_id ON users(email_id);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_plan (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL REFERENCES users(id),
            plan_code VARCHAR(30) DEFAULT 'free',
            premium_until TIMESTAMP NULL,
            trial_used INTEGER DEFAULT 0,
            trial_started_at TIMESTAMP NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_daily (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            feature_key VARCHAR(80) NOT NULL,
            day_key DATE NOT NULL,
            used_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_usage_daily UNIQUE (user_id, feature_key, day_key)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            provider VARCHAR(50) NOT NULL,
            provider_tx_id VARCHAR(190) NOT NULL,
            amount_cents INTEGER DEFAULT 0,
            currency VARCHAR(12) DEFAULT 'BRL',
            plan_code VARCHAR(30) DEFAULT 'premium_30',
            status VARCHAR(30) DEFAULT 'pending',
            paid_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_provider_tx ON payments(provider, provider_tx_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_provider_tx ON payments(provider, provider_tx_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_created ON payments(user_id, created_at DESC);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkout_sessions (
            id BIGSERIAL PRIMARY KEY,
            checkout_id VARCHAR(64) UNIQUE NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id),
            plan_code VARCHAR(30) DEFAULT 'premium_30',
            amount_cents INTEGER DEFAULT 0,
            currency VARCHAR(12) DEFAULT 'BRL',
            provider VARCHAR(50) DEFAULT 'manual',
            auth_token VARCHAR(190) NOT NULL,
            payment_code VARCHAR(190) NOT NULL,
            status VARCHAR(30) DEFAULT 'pending',
            expires_at TIMESTAMP NOT NULL,
            confirmed_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_user_created ON checkout_sessions(user_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_status ON checkout_sessions(status);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL REFERENCES users(id),
            provider VARCHAR(40) DEFAULT 'gemini',
            model VARCHAR(120) DEFAULT 'gemini-2.5-flash',
            api_key TEXT NULL,
            economia_mode INTEGER DEFAULT 0,
            telemetry_opt_in INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_events (
            id BIGSERIAL PRIMARY KEY,
            provider VARCHAR(50) NOT NULL,
            event_id VARCHAR(190) UNIQUE NOT NULL,
            payload_json TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_webhook_events_event_id ON webhook_events(event_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS webhook_events;")
    op.execute("DROP TABLE IF EXISTS user_settings;")
    op.execute("DROP TABLE IF EXISTS checkout_sessions;")
    op.execute("DROP TABLE IF EXISTS payments;")
    op.execute("DROP TABLE IF EXISTS usage_daily;")
    op.execute("DROP TABLE IF EXISTS user_plan;")
    op.execute("DROP TABLE IF EXISTS users;")
