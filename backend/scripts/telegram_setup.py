from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import telegram_bot  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provisionamento do bot e do grupo comercial no Telegram.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("blueprint", help="Mostra a estrutura recomendada do grupo/forum.")

    webhook = subparsers.add_parser("set-webhook", help="Configura o webhook do bot no backend.")
    webhook.add_argument("--public-base-url", required=True, help="URL publica do backend, sem barra final.")
    webhook.add_argument(
        "--keep-pending",
        action="store_true",
        help="Nao descarta updates pendentes ao configurar o webhook.",
    )

    provision = subparsers.add_parser("provision", help="Cria topicos e mensagens iniciais no grupo/forum.")
    provision.add_argument("--chat-id", required=True, help="ID do supergrupo/forum no Telegram.")
    provision.add_argument("--title", default="", help="Titulo opcional para o grupo.")
    provision.add_argument("--description", default="", help="Descricao opcional para o grupo.")
    provision.add_argument("--dry-run", action="store_true", help="Mostra o plano sem criar nada.")
    provision.add_argument(
        "--skip-commands",
        action="store_true",
        help="Nao atualiza os comandos globais do bot.",
    )
    provision.add_argument(
        "--skip-pins",
        action="store_true",
        help="Nao fixa as mensagens iniciais dos topicos.",
    )

    subparsers.add_parser("me", help="Valida token e mostra informacoes basicas do bot.")
    return parser


def _coerce_chat_id(raw: str) -> int | str:
    value = str(raw or "").strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "blueprint":
        summary = telegram_bot.provision_community_group(
            telegram_bot.TelegramBotClient(token="dry-run"),
            chat_id="preview",
            dry_run=True,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    client = telegram_bot.TelegramBotClient()

    if args.command == "me":
        print(json.dumps(client.get_me(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "set-webhook":
        result = telegram_bot.configure_webhook(
            client,
            args.public_base_url,
            drop_pending_updates=not bool(args.keep_pending),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "provision":
        result = telegram_bot.provision_community_group(
            client,
            _coerce_chat_id(args.chat_id),
            set_commands=not bool(args.skip_commands),
            pin_messages=not bool(args.skip_pins),
            chat_title_override=str(args.title or ""),
            chat_description_override=str(args.description or ""),
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error("Comando invalido.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
