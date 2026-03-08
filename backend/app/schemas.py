from datetime import datetime
from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    name: str
    email_id: str
    password: str = Field(min_length=6)


class LoginIn(BaseModel):
    email_id: str
    password: str


class AuthOut(BaseModel):
    user_id: int
    name: str
    email_id: str
    plan_code: str
    premium_active: bool
    premium_until: datetime | None = None
    access_token: str | None = None
    token_type: str = "bearer"


class ActivatePlanIn(BaseModel):
    user_id: int
    plan_code: str


class CheckoutStartIn(BaseModel):
    user_id: int
    plan_code: str
    provider: str = "mercadopago"
    name: str = ""
    email_id: str = ""


class CheckoutConfirmIn(BaseModel):
    user_id: int
    checkout_id: str
    auth_token: str
    tx_id: str
    provider: str = "mercadopago"


class CheckoutReconcileIn(BaseModel):
    user_id: int
    checkout_id: str


class ConsumeUsageIn(BaseModel):
    user_id: int
    feature_key: str
    limit_per_day: int


class WebhookPaymentIn(BaseModel):
    provider: str
    event_id: str
    event_type: str
    user_id: int
    tx_id: str
    amount_cents: int = 0
    currency: str = "BRL"
    plan_code: str = "premium_30"


class UpsertUserIn(BaseModel):
    user_id: int
    name: str
    email_id: str


class UserSettingsOut(BaseModel):
    user_id: int
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    api_key: str | None = None
    api_key_gemini: str | None = None
    api_key_openai: str | None = None
    api_key_groq: str | None = None
    economia_mode: bool = False
    telemetry_opt_in: bool = False


class UpsertUserSettingsIn(BaseModel):
    user_id: int
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    api_key: str | None = None
    api_key_gemini: str | None = None
    api_key_openai: str | None = None
    api_key_groq: str | None = None
    economia_mode: bool = False
    telemetry_opt_in: bool = False


class QuizStatsEventIn(BaseModel):
    event_id: str
    questoes_delta: int = 0
    acertos_delta: int = 0
    xp_delta: int = 0
    correta: bool = False
    occurred_at: datetime | None = None


class QuizStatsBatchIn(BaseModel):
    user_id: int
    events: list[QuizStatsEventIn] = []


class QuizStatsSummaryOut(BaseModel):
    user_id: int
    total_questoes: int = 0
    total_acertos: int = 0
    total_xp: int = 0
    today_questoes: int = 0
    today_acertos: int = 0
    today_xp: int = 0
    streak_dias: int = 0
