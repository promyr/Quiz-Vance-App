# -*- coding: utf-8 -*-
"""Testes de integracao HTTP para API de billing e atividade diaria."""

import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
except Exception:
    TestClient = None
    create_engine = None
    sessionmaker = None
    StaticPool = None

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_BACKEND_SECRET"] = "test-secret-quizvance-1234567890-abcdef"
os.environ["MP_WEBHOOK_TOKEN"] = "test-webhook-token"

try:
    from backend.app.database import Base
    from backend.app import models
    from backend.app import main as backend_main
except Exception:
    Base = None
    models = None
    backend_main = None


class BackendAPIIntegrationTest(unittest.TestCase):
    def setUp(self):
        if TestClient is None or create_engine is None or Base is None or backend_main is None:
            self.skipTest("Dependencias de integracao backend indisponiveis no ambiente atual.")
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=self.engine)
        backend_main._LOGIN_ATTEMPTS.clear()

        def _override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        backend_main.app.dependency_overrides[backend_main.get_db] = _override_get_db
        self.client = TestClient(backend_main.app)

    def tearDown(self):
        if backend_main is not None:
            backend_main.app.dependency_overrides.clear()
        if hasattr(self, "engine"):
            self.engine.dispose()

    def _register_user(self, email: str = "integration@test.local"):
        resp = self.client.post(
            "/auth/register",
            json={
                "name": "Integration User",
                "email_id": email,
                "password": "123456",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        return int(body["user_id"]), str(body["access_token"])

    def _auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _start_manual_checkout(self, user_id: int, token: str) -> dict:
        resp = self.client.post(
            "/billing/checkout/start",
            headers=self._auth_headers(token),
            json={
                "user_id": int(user_id),
                "plan_code": "premium_30",
                "provider": "manual",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def test_plans_endpoint_requires_token_and_blocks_user_mismatch(self):
        uid, token = self._register_user(email="auth@test.local")

        no_auth = self.client.get(f"/plans/me/{uid}")
        self.assertEqual(no_auth.status_code, 401)
        self.assertIn("missing_bearer_token", str(no_auth.json().get("detail") or ""))

        mismatch = self.client.get(f"/plans/me/{uid + 1}", headers=self._auth_headers(token))
        self.assertEqual(mismatch.status_code, 403)
        self.assertIn("token_user_mismatch", str(mismatch.json().get("detail") or ""))

        ok = self.client.get(f"/plans/me/{uid}", headers=self._auth_headers(token))
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(int(ok.json()["user_id"]), uid)

    def test_checkout_confirm_rejects_reused_transaction(self):
        uid, token = self._register_user(email="idempotency@test.local")

        checkout1 = self._start_manual_checkout(uid, token)
        confirm1 = self.client.post(
            "/billing/checkout/confirm",
            headers=self._auth_headers(token),
            json={
                "user_id": uid,
                "checkout_id": checkout1["checkout_id"],
                "auth_token": checkout1["auth_token"],
                "tx_id": "tx-int-001",
                "provider": "manual",
            },
        )
        self.assertEqual(confirm1.status_code, 200, confirm1.text)

        checkout2 = self._start_manual_checkout(uid, token)
        confirm2 = self.client.post(
            "/billing/checkout/confirm",
            headers=self._auth_headers(token),
            json={
                "user_id": uid,
                "checkout_id": checkout2["checkout_id"],
                "auth_token": checkout2["auth_token"],
                "tx_id": "tx-int-001",
                "provider": "manual",
            },
        )
        self.assertEqual(confirm2.status_code, 400)
        self.assertIn("ja utilizada", str(confirm2.json().get("detail") or "").lower())

    def test_mercadopago_webhook_requires_token_and_is_idempotent(self):
        uid, token = self._register_user(email="webhook@test.local")
        checkout = self._start_manual_checkout(uid, token)

        payload = {
            "type": "payment",
            "action": "payment.updated",
            "data": {"id": "987654"},
        }

        forbidden = self.client.post("/billing/webhook/mercadopago", json=payload)
        self.assertEqual(forbidden.status_code, 403)
        self.assertIn("invalid_webhook_token", str(forbidden.json().get("detail") or ""))

        mp_payment = {
            "id": "987654",
            "status": "approved",
            "external_reference": checkout["checkout_id"],
            "currency_id": "BRL",
            "transaction_amount": 9.99,
            "metadata": {
                "checkout_id": checkout["checkout_id"],
                "plan_code": "premium_30",
            },
        }
        with patch("backend.app.main.mercadopago.get_payment", return_value=mp_payment):
            ok1 = self.client.post(
                "/billing/webhook/mercadopago?token=test-webhook-token",
                json=payload,
            )
            self.assertEqual(ok1.status_code, 200, ok1.text)
            self.assertTrue(bool(ok1.json().get("ok")))

            ok2 = self.client.post(
                "/billing/webhook/mercadopago?token=test-webhook-token",
                json=payload,
            )
            self.assertEqual(ok2.status_code, 200, ok2.text)
            self.assertIn("evento ja processado", str(ok2.json().get("message") or "").lower())

        check_plan = self.client.get(f"/plans/me/{uid}", headers=self._auth_headers(token))
        self.assertEqual(check_plan.status_code, 200, check_plan.text)
        self.assertTrue(bool(check_plan.json().get("premium_active")))

        db = self.Session()
        try:
            total = (
                db.query(models.Payment)
                .filter(models.Payment.provider == "mercadopago", models.Payment.provider_tx_id == "987654")
                .count()
            )
            self.assertEqual(total, 1)
        finally:
            db.close()

    def test_daily_activity_ping_updates_summary_streak(self):
        uid, token = self._register_user(email="activity@test.local")
        headers = self._auth_headers(token)
        ontem = (date.today() - timedelta(days=1)).isoformat()
        hoje = date.today().isoformat()

        ping_ontem = self.client.post(
            "/internal/stats/activity/ping",
            headers=headers,
            json={"user_id": uid, "activity_day": ontem, "streak_dias": 4},
        )
        self.assertEqual(ping_ontem.status_code, 200, ping_ontem.text)
        self.assertEqual(int(ping_ontem.json().get("streak_dias") or 0), 4)
        self.assertEqual(str(ping_ontem.json().get("last_activity_day") or ""), ontem)

        ping_hoje = self.client.post(
            "/internal/stats/activity/ping",
            headers=headers,
            json={"user_id": uid, "activity_day": hoje},
        )
        self.assertEqual(ping_hoje.status_code, 200, ping_hoje.text)
        self.assertEqual(int(ping_hoje.json().get("streak_dias") or 0), 5)
        self.assertEqual(str(ping_hoje.json().get("last_activity_day") or ""), hoje)

        summary = self.client.get(
            f"/internal/stats/quiz/summary/{uid}?tz_offset_hours=0",
            headers=headers,
        )
        self.assertEqual(summary.status_code, 200, summary.text)
        body = summary.json()
        self.assertEqual(int(body.get("streak_dias") or 0), 5)
        self.assertEqual(str(body.get("last_activity_day") or ""), hoje)

    def test_summary_prefers_daily_activity_over_stored_streak_hint(self):
        uid, token = self._register_user(email="summary-streak@test.local")
        headers = self._auth_headers(token)
        hoje = date.today()
        ontem = hoje - timedelta(days=1)

        db = self.Session()
        try:
            user = db.query(models.User).filter(models.User.id == uid).first()
            self.assertIsNotNone(user)
            user.streak_days = 9
            user.last_activity_day = hoje
            db.add(models.QuizStatsDaily(user_id=uid, day_key=ontem, questoes=3, acertos=2, xp_ganho=20))
            db.commit()
        finally:
            db.close()

        summary = self.client.get(
            f"/internal/stats/quiz/summary/{uid}?tz_offset_hours=0",
            headers=headers,
        )
        self.assertEqual(summary.status_code, 200, summary.text)
        body = summary.json()
        self.assertEqual(int(body.get("streak_dias") or 0), 0)
        self.assertEqual(str(body.get("last_activity_day") or ""), str(hoje))

    def test_user_settings_preserve_all_provider_keys_and_allow_partial_clear(self):
        uid, token = self._register_user(email="keys@test.local")
        headers = self._auth_headers(token)

        save_all = self.client.post(
            "/internal/user-settings",
            headers=headers,
            json={
                "user_id": uid,
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "api_key": "gem-key-123",
                "api_key_gemini": "gem-key-123",
                "api_key_openai": "open-key-456",
                "api_key_groq": "groq-key-789",
                "economia_mode": False,
                "telemetry_opt_in": False,
            },
        )
        self.assertEqual(save_all.status_code, 200, save_all.text)

        after_save = self.client.get(f"/internal/user-settings/{uid}", headers=headers)
        self.assertEqual(after_save.status_code, 200, after_save.text)
        saved_body = after_save.json()
        self.assertEqual(str(saved_body.get("api_key_gemini") or ""), "gem-key-123")
        self.assertEqual(str(saved_body.get("api_key_openai") or ""), "open-key-456")
        self.assertEqual(str(saved_body.get("api_key_groq") or ""), "groq-key-789")

        clear_openai = self.client.post(
            "/internal/user-settings",
            headers=headers,
            json={
                "user_id": uid,
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "api_key": "gem-key-123",
                "api_key_openai": "",
                "economia_mode": False,
                "telemetry_opt_in": False,
            },
        )
        self.assertEqual(clear_openai.status_code, 200, clear_openai.text)

        after_clear = self.client.get(f"/internal/user-settings/{uid}", headers=headers)
        self.assertEqual(after_clear.status_code, 200, after_clear.text)
        clear_body = after_clear.json()
        self.assertEqual(str(clear_body.get("api_key_gemini") or ""), "gem-key-123")
        self.assertFalse(clear_body.get("api_key_openai"))
        self.assertEqual(str(clear_body.get("api_key_groq") or ""), "groq-key-789")


if __name__ == "__main__":
    unittest.main()
