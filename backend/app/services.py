from datetime import datetime, timedelta, date, timezone
import secrets
import uuid
import os
import base64
import hashlib
import hmac
import json
import time
from sqlalchemy.orm import Session
from . import models


PWD_SCHEME = "pbkdf2_sha256"
PWD_ITERS = 210_000
PLAN_DEFINITIONS = {
    "premium_30": {
        "price_cents": 999,
        "duration_days": 30,
    },
}
PLAN_PRICES_CENTS = {k: int(v["price_cents"]) for k, v in PLAN_DEFINITIONS.items()}
ACCESS_TOKEN_TTL_SECONDS = max(900, int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "43200") or 43200))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(str(value or "") + "=" * (-len(str(value or "")) % 4))


def create_access_token(app_secret: str, user_id: int, email_id: str) -> str:
    """Token simples assinado por HMAC-SHA256 (formato: v1.payload.signature)."""
    secret = str(app_secret or "").strip()
    if not secret:
        raise RuntimeError("app_secret_missing")
    now = int(time.time())
    payload = {
        "uid": int(user_id),
        "email": str(email_id or "").strip().lower(),
        "iat": now,
        "exp": now + int(ACCESS_TOKEN_TTL_SECONDS),
        "jti": secrets.token_urlsafe(12),
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"v1.{payload_b64}.{sig_b64}"


def verify_access_token(app_secret: str, token: str) -> dict | None:
    secret = str(app_secret or "").strip()
    value = str(token or "").strip()
    if not secret or not value:
        return None
    parts = value.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        return None
    payload_b64 = parts[1].strip()
    sig_b64 = parts[2].strip()
    if not payload_b64 or not sig_b64:
        return None
    expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    try:
        sig_raw = _b64url_decode(sig_b64)
    except Exception:
        return None
    if not hmac.compare_digest(expected_sig, sig_raw):
        return None
    try:
        payload_raw = _b64url_decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    uid = int(payload.get("uid") or 0)
    exp = int(payload.get("exp") or 0)
    now = int(time.time())
    if uid <= 0 or exp <= now:
        return None
    return payload


def hash_password(raw: str) -> str:
    pwd = str(raw or "").encode("utf-8")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pwd, salt, PWD_ITERS)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    dig_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{PWD_SCHEME}${PWD_ITERS}${salt_b64}${dig_b64}"


def verify_password(raw: str, hashed: str) -> bool:
    value = str(hashed or "").strip()
    pwd = str(raw or "")
    if not value:
        return False
    if value.startswith(f"{PWD_SCHEME}$"):
        try:
            _scheme, iters_s, salt_b64, digest_b64 = value.split("$", 3)
            iters = int(iters_s)
            salt_raw = base64.urlsafe_b64decode(salt_b64 + "=" * (-len(salt_b64) % 4))
            digest_raw = base64.urlsafe_b64decode(digest_b64 + "=" * (-len(digest_b64) % 4))
            probe = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt_raw, max(50_000, iters))
            return hmac.compare_digest(probe, digest_raw)
        except Exception:
            return False

    # Compatibilidade com hashes bcrypt antigos.
    if value.startswith("$2"):
        try:
            from passlib.context import CryptContext  # import tardio para evitar erro de startup
            return CryptContext(schemes=["bcrypt"], deprecated="auto").verify(pwd, value)
        except Exception:
            return False

    # Nao aceitar fallback de texto puro no backend.
    return False


def ensure_plan_row(db: Session, user_id: int):
    row = db.query(models.UserPlan).filter(models.UserPlan.user_id == user_id).first()
    if row:
        return row
    row = models.UserPlan(user_id=user_id, plan_code="free", trial_used=0)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def grant_initial_trial(db: Session, user_id: int):
    row = ensure_plan_row(db, user_id)
    if int(row.trial_used or 0) == 0:
        row.trial_used = 1
        row.plan_code = "trial"
        row.trial_started_at = datetime.now(timezone.utc)
        row.premium_until = datetime.now(timezone.utc) + timedelta(days=1)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return row


def premium_active(row: models.UserPlan | None) -> bool:
    if not row or not row.premium_until:
        return False
    premium_until = row.premium_until
    # Normaliza para timezone-aware (algumas migrações gravam datetime ingênuo).
    if premium_until.tzinfo is None or premium_until.tzinfo.utcoffset(premium_until) is None:
        premium_until = premium_until.replace(tzinfo=timezone.utc)
    return premium_until > datetime.now(timezone.utc)


def plan_duration_days(plan_code: str) -> int:
    plan = str(plan_code or "").strip().lower()
    conf = PLAN_DEFINITIONS.get(plan) or {}
    return int(conf.get("duration_days") or 0)


def activate_premium(db: Session, user_id: int, plan_code: str):
    plan = str(plan_code or "").strip().lower()
    days = plan_duration_days(plan)
    if days <= 0:
        return False, "Plano invalido."
    row = ensure_plan_row(db, user_id)
    base = row.premium_until
    if base and (base.tzinfo is None or base.tzinfo.utcoffset(base) is None):
        base = base.replace(tzinfo=timezone.utc)
    if not base or base <= datetime.now(timezone.utc):
        base = datetime.now(timezone.utc)
    row.plan_code = plan
    row.premium_until = base + timedelta(days=days)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return True, "Plano ativado."


def checkout_price(plan_code: str) -> int:
    return int(PLAN_PRICES_CENTS.get(str(plan_code or "").strip().lower()) or 0)


def create_checkout_session(db: Session, user_id: int, plan_code: str, provider: str = "manual"):
    plan = str(plan_code or "").strip().lower()
    amount = checkout_price(plan)
    if amount <= 0:
        return None, "Plano invalido."
    checkout_id = uuid.uuid4().hex
    auth_token = secrets.token_urlsafe(24)
    payment_code = f"QVP-{checkout_id[:8].upper()}"
    row = models.CheckoutSession(
        checkout_id=checkout_id,
        user_id=int(user_id),
        plan_code=plan,
        amount_cents=amount,
        currency="BRL",
        provider=str(provider or "manual"),
        auth_token=auth_token,
        payment_code=payment_code,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, "Checkout criado."


def confirm_checkout_session(
    db: Session,
    user_id: int,
    checkout_id: str,
    auth_token: str,
    tx_id: str,
    provider: str = "manual",
):
    row = (
        db.query(models.CheckoutSession)
        .filter(models.CheckoutSession.checkout_id == str(checkout_id or "").strip())
        .first()
    )
    if not row:
        return False, "Checkout nao encontrado.", None
    if int(row.user_id) != int(user_id):
        return False, "Checkout nao pertence ao usuario.", None
    if str(row.auth_token or "") != str(auth_token or ""):
        return False, "Token de checkout invalido.", None
    if str(row.status or "") != "pending":
        return False, "Checkout ja processado.", None
    expires_at = row.expires_at
    if expires_at.tzinfo is None or expires_at.tzinfo.utcoffset(expires_at) is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        row.status = "expired"
        db.commit()
        return False, "Checkout expirado. Inicie uma nova compra.", None
    tx_clean = str(tx_id or "").strip()
    if not tx_clean:
        return False, "Informe o ID da transacao.", None

    already_paid = (
        db.query(models.Payment)
        .filter(models.Payment.provider == str(provider or "manual"), models.Payment.provider_tx_id == tx_clean)
        .first()
    )
    if already_paid:
        return False, "Transacao ja utilizada.", None

    payment = models.Payment(
        user_id=int(user_id),
        provider=str(provider or "manual"),
        provider_tx_id=tx_clean,
        amount_cents=int(row.amount_cents or 0),
        currency=str(row.currency or "BRL"),
        plan_code=str(row.plan_code or "premium_30"),
        status="paid",
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    row.status = "confirmed"
    row.confirmed_at = datetime.now(timezone.utc)
    ok, msg = activate_premium(db, int(user_id), str(row.plan_code or "premium_30"))
    if not ok:
        db.rollback()
        return False, msg, None
    db.commit()
    return True, "Pagamento confirmado e premium liberado.", row


def finalize_checkout_payment(
    db: Session,
    checkout: models.CheckoutSession,
    *,
    provider: str,
    tx_id: str,
    amount_cents: int,
    currency: str = "BRL",
    plan_code: str = "",
):
    if not checkout:
        return False, "Checkout nao encontrado.", None
    tx_clean = str(tx_id or "").strip()
    if not tx_clean:
        return False, "Transacao sem identificador.", None
    provider_clean = str(provider or "manual").strip().lower() or "manual"
    amount = int(amount_cents or 0)
    if amount <= 0:
        amount = int(checkout.amount_cents or 0)
    curr = str(currency or "").strip().upper() or str(checkout.currency or "BRL")
    paid_plan = str(plan_code or checkout.plan_code or "premium_30").strip().lower()
    now = datetime.now(timezone.utc)

    payment = (
        db.query(models.Payment)
        .filter(models.Payment.provider == provider_clean, models.Payment.provider_tx_id == tx_clean)
        .first()
    )
    if payment and int(payment.user_id) != int(checkout.user_id):
        return False, "Transacao pertence a outro usuario.", payment

    if str(checkout.status or "") == "confirmed":
        if payment:
            return True, "Pagamento ja confirmado e premium sincronizado.", payment
        return False, "Checkout ja confirmado com outra transacao.", None

    expected_amount = int(checkout.amount_cents or 0)
    if expected_amount > 0 and amount < expected_amount:
        return False, "Valor pago menor que o esperado para o plano.", payment
    expected_currency = str(checkout.currency or "BRL").strip().upper()
    if expected_currency and curr != expected_currency:
        return False, "Moeda do pagamento invalida para este checkout.", payment

    if not payment:
        payment = models.Payment(
            user_id=int(checkout.user_id),
            provider=provider_clean,
            provider_tx_id=tx_clean,
            amount_cents=amount,
            currency=curr,
            plan_code=paid_plan,
            status="paid",
            paid_at=now,
        )
        db.add(payment)

    checkout.status = "confirmed"
    checkout.confirmed_at = now
    ok, msg = activate_premium(db, int(checkout.user_id), str(checkout.plan_code or paid_plan))
    if not ok:
        db.rollback()
        return False, msg, payment
    db.commit()
    return True, "Pagamento confirmado e premium sincronizado.", payment


def consume_daily_limit(db: Session, user_id: int, feature_key: str, limit_per_day: int):
    if limit_per_day <= 0:
        return True, 0
    today = date.today()
    row = (
        db.query(models.UsageDaily)
        .filter(
            models.UsageDaily.user_id == user_id,
            models.UsageDaily.feature_key == feature_key,
            models.UsageDaily.day_key == today,
        )
        .first()
    )
    if not row:
        row = models.UsageDaily(user_id=user_id, feature_key=feature_key, day_key=today, used_count=0)
        db.add(row)
        db.commit()
        db.refresh(row)
    if int(row.used_count or 0) >= int(limit_per_day):
        return False, int(row.used_count or 0)
    row.used_count = int(row.used_count or 0) + 1
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True, int(row.used_count or 0)
