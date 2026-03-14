# -*- coding: utf-8 -*-
"""Testes de integracao HTTP para o bot/comercial do Telegram."""

import os
import unittest
from datetime import datetime, timezone
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
os.environ["TELEGRAM_AUTO_POST_ENABLED"] = "0"
os.environ["TELEGRAM_INSTRUCTION_POST_ENABLED"] = "0"

try:
    from backend.app.database import Base
    from backend.app import main as backend_main
    from backend.app import models, telegram_bot
except Exception:
    Base = None
    backend_main = None
    models = None
    telegram_bot = None


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

    def test_operational_refresh_pack_has_daily_posts_with_apk_and_cadastro_cta(self):
        if telegram_bot is None:
            self.skipTest("Modulo do bot indisponivel no ambiente atual.")
        pack = telegram_bot.build_operational_refresh_pack()
        daily_posts = list(pack.get("daily_posts") or [])
        self.assertGreaterEqual(len(daily_posts), 7)
        joined = "\n".join(str(item or "") for item in daily_posts).lower()
        self.assertIn("/comecar", joined)
        self.assertIn("/baixar", joined)
        self.assertIn("cadastrar", joined)

    def test_auto_post_defaults_to_9am_and_promotes_app_usage(self):
        if telegram_bot is None:
            self.skipTest("Modulo do bot indisponivel no ambiente atual.")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TELEGRAM_AUTO_POST_HOUR", None)
            self.assertEqual(int(telegram_bot.auto_post_hour()), 9)
        post = telegram_bot.build_automated_daily_post(datetime(2026, 3, 13, 9, 0, 0).date())
        lowered = str(post.text or "").lower()
        self.assertIn("app", lowered)
        self.assertTrue("hoje" in lowered or "todos os dias" in lowered)

    def test_instruction_post_defaults_to_meio_dia_e_18h_and_guides_api_setup(self):
        if telegram_bot is None:
            self.skipTest("Modulo do bot indisponivel no ambiente atual.")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TELEGRAM_INSTRUCTION_POST_TIMES", None)
            os.environ.pop("TELEGRAM_INSTRUCTION_POST_HOUR", None)
            os.environ.pop("TELEGRAM_INSTRUCTION_POST_MINUTE", None)
            self.assertEqual(list(telegram_bot.instruction_post_times_labels()), ["12:00", "18:00"])
            self.assertEqual(int(telegram_bot.instruction_post_hour()), 12)
            self.assertEqual(int(telegram_bot.instruction_post_minute()), 0)
        midday_post = telegram_bot.build_instructional_post(datetime(2026, 3, 13, 12, 0, 0).date(), "12:00")
        evening_post = telegram_bot.build_instructional_post(datetime(2026, 3, 13, 18, 0, 0).date(), "18:00")
        self.assertTrue(str(midday_post.image_path or "").endswith(".png"))
        self.assertEqual(str(evening_post.image_path or ""), "")
        lowered_midday = str(midday_post.text or "").lower()
        lowered_evening = str(evening_post.text or "").lower()
        self.assertTrue(
            "/baixar" in lowered_midday
            or "configuracao" in lowered_midday
            or "app" in lowered_midday
            or "checklist" in lowered_midday
            or "provider" in lowered_midday
        )
        self.assertTrue("api key" in lowered_evening or "provider" in lowered_evening or "criar conta" in lowered_evening)
        self.assertTrue("erros comuns" in lowered_evening or "topico" in lowered_evening or "material" in lowered_evening or "passo" in lowered_evening)


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

    def test_telegram_group_provision_persists_auto_post_target(self):
        provision_result = {
            "chat_id": -1001234567890,
            "topics": [
                {"key": "atualizacoes", "message_thread_id": 701},
                {"key": "comece_aqui", "message_thread_id": 702},
                {"key": "bate_papo", "message_thread_id": 703},
                {"key": "resultados", "message_thread_id": 704},
                {"key": "suporte", "message_thread_id": 705},
                {"key": "feedbacks", "message_thread_id": 706},
            ],
        }
        with patch("backend.app.telegram_bot.provision_community_group", return_value=provision_result):
            resp = self.client.post(
                "/telegram/group/provision",
                headers={"X-App-Secret": "test-secret-quizvance-1234567890-abcdef"},
                json={
                    "chat_id": -1001234567890,
                    "dry_run": False,
                },
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("auto_post_target_saved")))
        self.assertEqual(str(body.get("community_chat_id") or ""), "-1001234567890")

        db = self.Session()
        try:
            row = db.query(models.TelegramCommunityConfig).first()
            self.assertIsNotNone(row)
            self.assertEqual(str(row.chat_id or ""), "-1001234567890")
            self.assertEqual(int(row.atualizacoes_thread_id or 0), 701)
            self.assertEqual(int(row.comece_aqui_thread_id or 0), 702)
            self.assertEqual(int(row.bate_papo_thread_id or 0), 703)
            self.assertEqual(int(row.resultados_thread_id or 0), 704)
        finally:
            db.close()


    def test_telegram_group_welcome_highlights_apk_and_cadastro(self):
        payload = {
            "update_id": 21,
            "message": {
                "message_id": 31,
                "chat": {"id": -1001234567890, "type": "supergroup"},
                "new_chat_members": [{"id": 501, "first_name": "Novo"}],
            },
        }
        with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 105}) as send_mock:
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(bool(body.get("ok")))
        self.assertEqual(str(body["result"]["type"]), "group_welcome")
        send_mock.assert_called_once()
        _args, kwargs = send_mock.call_args
        sent_text = str(kwargs.get("text") or (_args[1] if len(_args) > 1 else "")).lower()
        self.assertIn("/comecar", sent_text)
        self.assertIn("/baixar", sent_text)
        self.assertIn("cadastrar", sent_text)
        self.assertTrue(bool(kwargs.get("reply_markup")))

    def test_telegram_webhook_observes_group_chat_for_auto_post_target(self):
        payload = {
            "update_id": 22,
            "message": {
                "message_id": 32,
                "text": "/resultados@TestQuizVanceBot",
                "chat": {"id": -1009876543210, "type": "supergroup"},
                "message_thread_id": 912,
            },
        }
        with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 106}):
            resp = self.client.post(
                "/telegram/webhook",
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-token"},
                json=payload,
            )
        self.assertEqual(resp.status_code, 200, resp.text)

        db = self.Session()
        try:
            row = db.query(models.TelegramCommunityConfig).first()
            self.assertIsNotNone(row)
            self.assertEqual(str(row.chat_id or ""), "-1009876543210")
            self.assertEqual(int(row.atualizacoes_thread_id or 0), 912)
        finally:
            db.close()


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


    def test_run_telegram_daily_auto_post_once_is_idempotent_per_day(self):
        db = self.Session()
        try:
            db.add(
                models.TelegramCommunityConfig(
                    chat_id="-1001234567890",
                    atualizacoes_thread_id=811,
                    comece_aqui_thread_id=812,
                    bate_papo_thread_id=813,
                    resultados_thread_id=814,
                    suporte_thread_id=815,
                    feedbacks_thread_id=816,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
        finally:
            db.close()

        scheduled_at = datetime(2026, 3, 12, 9, 5, 0)
        expected_topic = telegram_bot.build_automated_daily_post(scheduled_at.date()).topic_key
        expected_thread_map = {
            "atualizacoes": 811,
            "comece_aqui": 812,
            "bate_papo": 813,
            "resultados": 814,
            "suporte": 815,
            "feedbacks": 816,
        }

        with patch.dict(os.environ, {"TELEGRAM_AUTO_POST_ENABLED": "1"}, clear=False):
            with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 777}) as send_mock:
                ran_first = backend_main._run_telegram_daily_auto_post_once(
                    session_factory=self.Session,
                    now_local=scheduled_at,
                )
                ran_second = backend_main._run_telegram_daily_auto_post_once(
                    session_factory=self.Session,
                    now_local=scheduled_at,
                )

        self.assertTrue(ran_first)
        self.assertFalse(ran_second)
        self.assertEqual(send_mock.call_count, 1)
        args, kwargs = send_mock.call_args
        self.assertEqual(int(args[0]), -1001234567890)
        self.assertEqual(int(kwargs.get("message_thread_id") or 0), expected_thread_map[expected_topic])
        self.assertFalse(bool(kwargs.get("disable_notification")))

        db = self.Session()
        try:
            row = db.query(models.TelegramDailyPostLog).filter(models.TelegramDailyPostLog.day_key == scheduled_at.date()).first()
            self.assertIsNotNone(row)
            self.assertEqual(str(row.status or ""), "sent")
            self.assertEqual(str(row.topic_key or ""), expected_topic)
            self.assertEqual(int(row.attempt_count or 0), 1)
            self.assertIsNotNone(row.sent_at)
        finally:
            db.close()


    def test_run_telegram_instruction_post_once_is_idempotent_per_slot(self):
        db = self.Session()
        try:
            db.add(
                models.TelegramCommunityConfig(
                    chat_id="-1001234567890",
                    atualizacoes_thread_id=911,
                    comece_aqui_thread_id=912,
                    bate_papo_thread_id=913,
                    resultados_thread_id=914,
                    suporte_thread_id=915,
                    feedbacks_thread_id=916,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
        finally:
            db.close()

        scheduled_midday = datetime(2026, 3, 13, 12, 5, 0)
        scheduled_evening = datetime(2026, 3, 13, 18, 5, 0)
        expected_thread_map = {
            "atualizacoes": 911,
            "comece_aqui": 912,
            "bate_papo": 913,
            "resultados": 914,
            "suporte": 915,
            "feedbacks": 916,
        }
        expected_midday_post = telegram_bot.build_instructional_post(scheduled_midday.date(), "12:00")
        expected_evening_post = telegram_bot.build_instructional_post(scheduled_evening.date(), "18:00")

        with patch.dict(os.environ, {"TELEGRAM_INSTRUCTION_POST_ENABLED": "1"}, clear=False):
            with patch("backend.app.telegram_bot.TelegramBotClient.send_photo", return_value={"message_id": 778}) as send_photo_mock:
                with patch("backend.app.telegram_bot.TelegramBotClient.send_message", return_value={"message_id": 779}) as send_message_mock:
                    ran_midday_first = backend_main._run_telegram_instruction_post_once(
                        session_factory=self.Session,
                        now_local=scheduled_midday,
                    )
                    ran_midday_second = backend_main._run_telegram_instruction_post_once(
                        session_factory=self.Session,
                        now_local=scheduled_midday,
                    )
                    ran_evening = backend_main._run_telegram_instruction_post_once(
                        session_factory=self.Session,
                        now_local=scheduled_evening,
                    )

        self.assertTrue(ran_midday_first)
        self.assertFalse(ran_midday_second)
        self.assertTrue(ran_evening)
        self.assertEqual(send_photo_mock.call_count, 1)
        self.assertEqual(send_message_mock.call_count, 1)
        photo_args, photo_kwargs = send_photo_mock.call_args
        message_args, message_kwargs = send_message_mock.call_args
        self.assertEqual(int(photo_args[0]), -1001234567890)
        self.assertEqual(int(message_args[0]), -1001234567890)
        self.assertEqual(int(photo_kwargs.get("message_thread_id") or 0), expected_thread_map[expected_midday_post.topic_key])
        self.assertEqual(int(message_kwargs.get("message_thread_id") or 0), expected_thread_map[expected_evening_post.topic_key])
        self.assertFalse(bool(photo_kwargs.get("disable_notification")))
        self.assertFalse(bool(message_kwargs.get("disable_notification")))
        self.assertEqual(str(photo_kwargs.get("caption") or ""), expected_midday_post.text)
        self.assertEqual(str(message_args[1] or ""), expected_evening_post.text)

        db = self.Session()
        try:
            rows = db.query(models.TelegramInstructionPostLog).filter(models.TelegramInstructionPostLog.day_key == scheduled_midday.date()).order_by(models.TelegramInstructionPostLog.slot_key.asc()).all()
            self.assertEqual(len(rows), 2)
            self.assertEqual([str(row.slot_key or "") for row in rows], ["12:00", "18:00"])
            self.assertTrue(all(str(row.status or "") == "sent" for row in rows))
            self.assertEqual(str(rows[0].topic_key or ""), expected_midday_post.topic_key)
            self.assertEqual(str(rows[1].topic_key or ""), expected_evening_post.topic_key)
            self.assertTrue(all(int(row.attempt_count or 0) == 1 for row in rows))
            self.assertTrue(all(row.sent_at is not None for row in rows))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
