# -*- coding: utf-8 -*-
"""Testes de integracao HTTP para API de billing."""

import os
import unittest
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


if __name__ == "__main__":
    unittest.main()
