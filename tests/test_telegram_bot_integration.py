# -*- coding: utf-8 -*-
"""Testes de integracao HTTP para o bot/comercial do Telegram."""

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
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:test-telegram-token"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "telegram-secret-token"
os.environ["TELEGRAM_DOWNLOAD_URL"] = "https://downloads.quizvance.local/app.apk"
os.environ["TELEGRAM_COMMUNITY_INVITE_URL"] = "https://t.me/quizvancegrupo"
os.environ["TELEGRAM_SUPPORT_URL"] = "https://t.me/quizvancesuporte"

try:
    from backend.app.database import Base
    from backend.app import main as backend_main
except Exception:
    Base = None
    backend_main = None


class TelegramBotIntegrationTest(unittest.TestCase):
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

    def test_telegram_webhook_rejects_invalid_secret(self):
        resp = self.client.post("/telegram/webhook", json={"message": {"chat": {"id": 1, "type": "private"}}})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("invalid_telegram_secret", str(resp.json().get("detail") or ""))

    def test_telegram_webhook_handles_private_start(self):
        payload = {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "text": "/start",
                "chat": {"id": 777, "type": "private"},
            },
        }
        with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 99}) as send_mock:
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertEqual(str(body["result"]["type"]), "private_message")
        send_mock.assert_called_once()

    def test_telegram_group_provision_supports_dry_run(self):
        resp = self.client.post(
            "/telegram/group/provision",
            headers={"X-App-Secret": "test-secret-quizvance-1234567890-abcdef"},
            json={
                "chat_id": -1001234567890,
                "dry_run": True,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("dry_run")))
        self.assertGreaterEqual(len(body.get("topics") or []), 6)

    def test_telegram_webhook_handles_group_baixar_command(self):
        payload = {
            "update_id": 2,
            "message": {
                "message_id": 11,
                "text": "/baixar@TestQuizVanceBot",
                "chat": {"id": -1001234567890, "type": "supergroup"},
            },
        }
        with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 101}) as send_mock:
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertEqual(str(body["result"]["type"]), "group_command")
        self.assertEqual(str(body["result"]["command"]), "baixar")
        send_mock.assert_called_once()

    def test_telegram_webhook_handles_private_oferta_command(self):
        payload = {
            "update_id": 3,
            "message": {
                "message_id": 12,
                "text": "/oferta",
                "chat": {"id": 888, "type": "private"},
            },
        }
        with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 102}) as send_mock:
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertEqual(str(body["result"]["type"]), "private_message")
        self.assertEqual(str(body["result"]["command"]), "oferta")
        send_mock.assert_called_once()

    def test_telegram_webhook_handles_private_faq_command(self):
        payload = {
            "update_id": 30,
            "message": {
                "message_id": 14,
                "text": "/faq",
                "chat": {"id": 889, "type": "private"},
            },
        }
        with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 104}) as send_mock:
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertEqual(str(body["result"]["type"]), "private_message")
        self.assertEqual(str(body["result"]["command"]), "faq")
        send_mock.assert_called_once()

    def test_telegram_webhook_handles_group_resultados_command(self):
        payload = {
            "update_id": 4,
            "message": {
                "message_id": 13,
                "text": "/resultados@TestQuizVanceBot",
                "chat": {"id": -1001234567890, "type": "supergroup"},
            },
        }
        with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 103}) as send_mock:
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertEqual(str(body["result"]["type"]), "group_command")
        self.assertEqual(str(body["result"]["command"]), "resultados")
        send_mock.assert_called_once()

    def test_telegram_webhook_does_not_raise_when_send_message_fails(self):
        payload = {
            "update_id": 40,
            "message": {
                "message_id": 15,
                "text": "/start",
                "chat": {"id": 999, "type": "private"},
            },
        }
        with patch(
            "backend.app.telegram_bot.TelegramBotClient.send_message",
            side_effect=RuntimeError("send_failed"),
        ):
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertFalse(bool(body["result"].get("ok")))
        self.assertIn("send_failed", str(body["result"].get("error") or ""))

    def test_telegram_webhook_configure_calls_set_webhook(self):
        with patch("backend.app.telegram_bot.TelegramBotClient.set_webhook", return_value=True) as webhook_mock:
            resp = self.client.post(
                "/telegram/webhook/configure",
                headers={"X-App-Secret": "test-secret-quizvance-1234567890-abcdef"},
                json={
                    "public_base_url": "https://quiz-vance-backend.fly.dev",
                    "drop_pending_updates": True,
                },
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertEqual(str(body.get("webhook_url") or ""), "https://quiz-vance-backend.fly.dev/telegram/webhook")
        webhook_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
