# -*- coding: utf-8 -*-
"""Testes unitarios do fluxo de billing backend."""

import unittest
from datetime import datetime, timedelta, timezone
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("APP_BACKEND_SECRET", "test-secret-quizvance-1234567890-abcdef")
os.environ.setdefault("MP_WEBHOOK_TOKEN", "test-webhook-token")

from backend.app.database import Base
from backend.app import models, services

try:
    from fastapi import HTTPException
    from backend.app.main import health, health_ready, register, _realign_users_id_sequence
    from backend.app import schemas
except Exception:
    HTTPException = None
    health = None
    health_ready = None
    register = None
    _realign_users_id_sequence = None
    schemas = None


class BackendBillingServicesTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _create_user(self, email: str = "user@test.local", name: str = "User") -> models.User:
        user = models.User(
            name=name,
            email_id=email,
            password_hash=services.hash_password("123456"),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_monthly_price_config(self):
        self.assertEqual(services.checkout_price("premium_30"), 999)
        self.assertEqual(services.plan_duration_days("premium_30"), 30)
        self.assertEqual(services.checkout_price("premium_15"), 0)
        self.assertEqual(services.plan_duration_days("premium_15"), 0)

    def test_access_token_roundtrip_and_signature_validation(self):
        secret = "x" * 32
        token = services.create_access_token(secret, 77, "token@test.local")
        payload = services.verify_access_token(secret, token)
        self.assertIsNotNone(payload)
        self.assertEqual(int(payload.get("uid") or 0), 77)
        self.assertIsNone(services.verify_access_token(secret + "1", token))

    def test_create_checkout_monthly(self):
        user = self._create_user()
        row, msg = services.create_checkout_session(self.db, user.id, "premium_30", "mercadopago")
        self.assertIsNotNone(row)
        self.assertEqual(msg, "Checkout criado.")
        self.assertEqual(row.status, "pending")
        self.assertEqual(row.plan_code, "premium_30")
        self.assertEqual(int(row.amount_cents), 999)

    def test_finalize_checkout_payment_creates_payment_and_activates_plan(self):
        user = self._create_user()
        checkout, _msg = services.create_checkout_session(self.db, user.id, "premium_30", "mercadopago")

        ok, msg, payment = services.finalize_checkout_payment(
            self.db,
            checkout,
            provider="mercadopago",
            tx_id="tx-approved-001",
            amount_cents=999,
            currency="BRL",
            plan_code="premium_30",
        )

        self.assertTrue(ok, msg)
        self.assertIn("premium", msg.lower())
        self.assertIsNotNone(payment)

        fresh_checkout = (
            self.db.query(models.CheckoutSession)
            .filter(models.CheckoutSession.checkout_id == checkout.checkout_id)
            .first()
        )
        self.assertEqual(fresh_checkout.status, "confirmed")
        self.assertIsNotNone(fresh_checkout.confirmed_at)

        plan = services.ensure_plan_row(self.db, user.id)
        self.assertEqual(plan.plan_code, "premium_30")
        self.assertTrue(services.premium_active(plan))

        payments = self.db.query(models.Payment).filter(models.Payment.user_id == user.id).all()
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].provider_tx_id, "tx-approved-001")

    def test_finalize_rejects_underpaid_amount(self):
        user = self._create_user(email="underpaid@test.local")
        checkout, _msg = services.create_checkout_session(self.db, user.id, "premium_30", "mercadopago")
        ok, msg, _payment = services.finalize_checkout_payment(
            self.db,
            checkout,
            provider="mercadopago",
            tx_id="tx-underpaid-001",
            amount_cents=100,
            currency="BRL",
            plan_code="premium_30",
        )
        self.assertFalse(ok)
        self.assertIn("menor", msg.lower())

    def test_finalize_is_idempotent_for_existing_payment_and_still_syncs_plan(self):
        user = self._create_user(email="heal@test.local")
        checkout, _ = services.create_checkout_session(self.db, user.id, "premium_30", "mercadopago")

        plan = services.ensure_plan_row(self.db, user.id)
        plan.plan_code = "free"
        plan.premium_until = datetime.now(timezone.utc) - timedelta(days=1)
        self.db.commit()

        payment = models.Payment(
            user_id=user.id,
            provider="mercadopago",
            provider_tx_id="tx-heal-001",
            amount_cents=999,
            currency="BRL",
            plan_code="premium_30",
            status="paid",
            paid_at=datetime.now(timezone.utc),
        )
        self.db.add(payment)
        self.db.commit()

        ok, msg, _payment = services.finalize_checkout_payment(
            self.db,
            checkout,
            provider="mercadopago",
            tx_id="tx-heal-001",
            amount_cents=999,
            currency="BRL",
            plan_code="premium_30",
        )
        self.assertTrue(ok, msg)

        total_payments = (
            self.db.query(models.Payment)
            .filter(models.Payment.provider == "mercadopago", models.Payment.provider_tx_id == "tx-heal-001")
            .count()
        )
        self.assertEqual(total_payments, 1)

        refreshed_plan = services.ensure_plan_row(self.db, user.id)
        self.assertEqual(refreshed_plan.plan_code, "premium_30")
        self.assertTrue(services.premium_active(refreshed_plan))

    def test_confirm_checkout_rejects_reused_transaction(self):
        user = self._create_user(email="reuse@test.local")

        first_checkout, _ = services.create_checkout_session(self.db, user.id, "premium_30", "manual")
        ok, _msg, _ = services.confirm_checkout_session(
            self.db,
            user.id,
            first_checkout.checkout_id,
            first_checkout.auth_token,
            "tx-reused-01",
            "manual",
        )
        self.assertTrue(ok)

        second_checkout, _ = services.create_checkout_session(self.db, user.id, "premium_30", "manual")
        ok2, msg2, _ = services.confirm_checkout_session(
            self.db,
            user.id,
            second_checkout.checkout_id,
            second_checkout.auth_token,
            "tx-reused-01",
            "manual",
        )
        self.assertFalse(ok2)
        self.assertIn("ja utilizada", msg2.lower())

    def test_health_and_ready_endpoints(self):
        if health is None or health_ready is None:
            self.skipTest("fastapi/backend.app.main indisponivel no ambiente atual")
        status = health()
        self.assertTrue(bool(status.get("ok")))
        self.assertIn("ts", status)

        ready = health_ready(self.db)
        self.assertTrue(bool(ready.get("ok")))
        self.assertEqual(str(ready.get("db") or ""), "up")
        self.assertIn("ts", ready)

    def test_health_ready_returns_503_when_db_is_down(self):
        if HTTPException is None or health_ready is None:
            self.skipTest("fastapi/backend.app.main indisponivel no ambiente atual")
        class _BrokenDB:
            def execute(self, *_args, **_kwargs):
                raise RuntimeError("boom")

        with self.assertRaises(HTTPException) as ctx:
            health_ready(_BrokenDB())
        self.assertEqual(int(ctx.exception.status_code), 503)
        self.assertIn("db_down", str(ctx.exception.detail or ""))

    def test_realign_users_sequence_noop_on_sqlite(self):
        if _realign_users_id_sequence is None:
            self.skipTest("backend.app.main indisponivel no ambiente atual")
        _realign_users_id_sequence(self.db)
        self.assertTrue(True)

    def test_register_returns_409_for_duplicate_email(self):
        if HTTPException is None or register is None or schemas is None:
            self.skipTest("backend.app.main indisponivel no ambiente atual")
        self._create_user(email="dup@test.local")
        payload = schemas.RegisterIn(name="Dup", email_id="dup@test.local", password="123456")
        with self.assertRaises(HTTPException) as ctx:
            register(payload, self.db)
        self.assertEqual(int(ctx.exception.status_code), 409)


if __name__ == "__main__":
    unittest.main()
