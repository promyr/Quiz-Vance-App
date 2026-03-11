from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import telegram_bot  # noqa: E402


def _get(url: str, *, timeout: float = 15.0) -> tuple[bool, int | None, dict | list | str]:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return resp.is_success, resp.status_code, body
    except Exception as ex:
        return False, None, str(ex)


def _post(url: str, payload: dict, *, timeout: float = 15.0) -> tuple[bool, int | None, dict | list | str]:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.post(url, json=payload)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return resp.is_success, resp.status_code, body
    except Exception as ex:
        return False, None, str(ex)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostico rapido do bot do Telegram.")
    parser.add_argument("--backend-url", default=str(os.getenv("BACKEND_PUBLIC_URL") or "").strip())
    parser.add_argument("--bot-token", default=telegram_bot.telegram_token())
    parser.add_argument("--webhook-secret", default=telegram_bot.webhook_secret())
    args = parser.parse_args()

    token = str(args.bot_token or "").strip()
    backend_url = str(args.backend_url or "").strip().rstrip("/")
    secret = str(args.webhook_secret or "").strip()

    report: dict[str, object] = {
        "backend_url": backend_url,
        "telegram_token_configured": bool(token),
        "webhook_secret_configured": bool(secret),
    }

    if token:
        api_base = f"https://api.telegram.org/bot{token}"
        ok_me, status_me, body_me = _get(f"{api_base}/getMe")
        ok_hook, status_hook, body_hook = _get(f"{api_base}/getWebhookInfo")
        report["telegram_getMe"] = {"ok": ok_me, "status": status_me, "body": body_me}
        report["telegram_getWebhookInfo"] = {"ok": ok_hook, "status": status_hook, "body": body_hook}
    else:
        report["telegram_getMe"] = {"ok": False, "status": None, "body": "bot_token_missing"}
        report["telegram_getWebhookInfo"] = {"ok": False, "status": None, "body": "bot_token_missing"}

    if backend_url:
        ok_health, status_health, body_health = _get(f"{backend_url}/health")
        ok_tg_health, status_tg_health, body_tg_health = _get(f"{backend_url}/telegram/health")
        report["backend_health"] = {"ok": ok_health, "status": status_health, "body": body_health}
        report["backend_telegram_health"] = {"ok": ok_tg_health, "status": status_tg_health, "body": body_tg_health}

        probe_payload = {
            "update_id": 999999,
            "message": {"message_id": 1, "text": "/start", "chat": {"id": 1, "type": "private"}},
        }
        headers = {}
        if secret:
            headers["X-Telegram-Bot-Api-Secret-Token"] = secret
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.post(f"{backend_url}/telegram/webhook", json=probe_payload, headers=headers)
            try:
                probe_body = resp.json()
            except Exception:
                probe_body = resp.text
            report["backend_webhook_probe"] = {"ok": resp.is_success, "status": resp.status_code, "body": probe_body}
        except Exception as ex:
            report["backend_webhook_probe"] = {"ok": False, "status": None, "body": str(ex)}
    else:
        report["backend_health"] = {"ok": False, "status": None, "body": "backend_url_missing"}
        report["backend_telegram_health"] = {"ok": False, "status": None, "body": "backend_url_missing"}
        report["backend_webhook_probe"] = {"ok": False, "status": None, "body": "backend_url_missing"}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
