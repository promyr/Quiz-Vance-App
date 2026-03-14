from datetime import datetime, date, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email_id: Mapped[str] = mapped_column(String(190), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[str] = mapped_column(String(50), default="Bronze")
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_day: Mapped[date | None] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserPlan(Base):
    __tablename__ = "user_plan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    plan_code: Mapped[str] = mapped_column(String(30), default="free")
    premium_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_used: Mapped[int] = mapped_column(Integer, default=0)
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class UsageDaily(Base):
    __tablename__ = "usage_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    feature_key: Mapped[str] = mapped_column(String(80), nullable=False)
    day_key: Mapped[date] = mapped_column(nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "feature_key", "day_key", name="uq_usage_daily"),)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_tx_id: Mapped[str] = mapped_column(String(190), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="BRL")
    plan_code: Mapped[str] = mapped_column(String(30), default="premium_30")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        UniqueConstraint("provider", "provider_tx_id", name="uq_payments_provider_tx"),
        Index("ix_payments_provider_tx", "provider", "provider_tx_id"),
        Index("ix_payments_user_created", "user_id", "created_at"),
    )


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checkout_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plan_code: Mapped[str] = mapped_column(String(30), default="premium_30")
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="BRL")
    provider: Mapped[str] = mapped_column(String(50), default="manual")
    auth_token: Mapped[str] = mapped_column(String(190), nullable=False)
    payment_code: Mapped[str] = mapped_column(String(190), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        Index("ix_checkout_user_created", "user_id", "created_at"),
        Index("ix_checkout_status", "status"),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="gemini")
    model: Mapped[str] = mapped_column(String(120), default="gemini-2.5-flash")
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_gemini: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_openai: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_groq: Mapped[str | None] = mapped_column(Text, nullable=True)
    economia_mode: Mapped[int] = mapped_column(Integer, default=0)
    telemetry_opt_in: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str] = mapped_column(String(190), unique=True, nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class QuizStatsDaily(Base):
    __tablename__ = "quiz_stats_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    day_key: Mapped[date] = mapped_column(nullable=False, index=True)
    questoes: Mapped[int] = mapped_column(Integer, default=0)
    acertos: Mapped[int] = mapped_column(Integer, default=0)
    xp_ganho: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "day_key", name="uq_quiz_stats_daily"),)


class QuizStatsEvent(Base):
    __tablename__ = "quiz_stats_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    questoes_delta: Mapped[int] = mapped_column(Integer, default=0)
    acertos_delta: Mapped[int] = mapped_column(Integer, default=0)
    xp_delta: Mapped[int] = mapped_column(Integer, default=0)
    correta: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_quiz_stats_event_user"),
        Index("ix_quiz_stats_events_user_created", "user_id", "created_at"),
    )



class TelegramCommunityConfig(Base):
    __tablename__ = "telegram_community_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    atualizacoes_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comece_aqui_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bate_papo_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resultados_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suporte_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedbacks_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class TelegramDailyPostLog(Base):
    __tablename__ = "telegram_daily_post_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_key: Mapped[date] = mapped_column(nullable=False, unique=True, index=True)
    topic_key: Mapped[str] = mapped_column(String(40), default="atualizacoes")
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class TelegramInstructionPostLog(Base):
    __tablename__ = "telegram_instruction_post_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_key: Mapped[date] = mapped_column(nullable=False, index=True)
    slot_key: Mapped[str] = mapped_column(String(40), default="18:00", nullable=False)
    topic_key: Mapped[str] = mapped_column(String(40), default="comece_aqui")
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("day_key", "slot_key", name="uq_telegram_instruction_post_log_day_slot"),)
