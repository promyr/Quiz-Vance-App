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

CREATE TABLE IF NOT EXISTS user_plan (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL REFERENCES users(id),
    plan_code VARCHAR(30) DEFAULT 'free',
    premium_until TIMESTAMP NULL,
    trial_used INTEGER DEFAULT 0,
    trial_started_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usage_daily (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    feature_key VARCHAR(80) NOT NULL,
    day_key DATE NOT NULL,
    used_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_usage_daily UNIQUE (user_id, feature_key, day_key)
);

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
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_provider_tx ON payments(provider, provider_tx_id);
CREATE INDEX IF NOT EXISTS idx_payments_provider_tx ON payments(provider, provider_tx_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_created ON payments(user_id, created_at DESC);

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
CREATE INDEX IF NOT EXISTS idx_checkout_user_created ON checkout_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkout_status ON checkout_sessions(status);

CREATE TABLE IF NOT EXISTS user_settings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL REFERENCES users(id),
    provider VARCHAR(40) DEFAULT 'gemini',
    model VARCHAR(120) DEFAULT 'gemini-2.5-flash',
    api_key TEXT,
    economia_mode INTEGER DEFAULT 0,
    telemetry_opt_in INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    event_id VARCHAR(190) UNIQUE NOT NULL,
    payload_json TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW()
);

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
CREATE INDEX IF NOT EXISTS idx_quiz_stats_daily_user_day ON quiz_stats_daily(user_id, day_key DESC);

CREATE TABLE IF NOT EXISTS quiz_stats_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    event_id VARCHAR(120) NOT NULL,
    occurred_at TIMESTAMP DEFAULT NOW(),
    questoes_delta INTEGER DEFAULT 0,
    acertos_delta INTEGER DEFAULT 0,
    xp_delta INTEGER DEFAULT 0,
    correta INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_quiz_stats_event_user UNIQUE (user_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_quiz_stats_events_user_created ON quiz_stats_events(user_id, created_at DESC);
