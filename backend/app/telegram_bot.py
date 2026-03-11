from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any

import httpx


logger = logging.getLogger(__name__)


DEFAULT_TOPIC_COLORS = {
    "blue": 0x6FB9F0,
    "yellow": 0xFFD67E,
    "purple": 0xCB86DB,
    "green": 0x8EEE98,
    "pink": 0xFF93B2,
    "red": 0xFB6F5F,
}


@dataclass(frozen=True)
class ForumTopicBlueprint:
    key: str
    name: str
    icon_color: int
    starter_text: str
    pin_starter: bool = True


DEFAULT_COMMANDS = [
    {"command": "start", "description": "Abrir menu principal"},
    {"command": "baixar", "description": "Receber o link do app"},
    {"command": "oferta", "description": "Ver oferta beta atual"},
    {"command": "resultados", "description": "Ver prova social"},
    {"command": "faq", "description": "Resolver duvidas rapidas"},
    {"command": "grupo", "description": "Entrar na comunidade"},
    {"command": "suporte", "description": "Falar com o suporte"},
]


MARKETING_MANAGER_DIRECTIVE = """
Voce atua como gerente de marketing e gerente geral da comunidade Quiz Vance no Telegram.
Seu objetivo e atrair usuarios qualificados, aumentar downloads do APK, elevar conversoes
em premium, estimular prova social, captar feedbacks acionaveis e manter o grupo vivo.

Principios:
- vender com clareza, nao com spam;
- responder com senso de dono, energia comercial e utilidade pratica;
- conduzir novos membros para download, teste rapido, comunidade e oferta;
- transformar resultados dos usuarios em prova social;
- transformar duvidas recorrentes em melhorias do produto;
- manter a comunidade organizada por topicos e CTAs objetivos.
""".strip()


DEFAULT_GROUP_BLUEPRINT = [
    ForumTopicBlueprint(
        key="atualizacoes",
        name="Atualizacoes",
        icon_color=DEFAULT_TOPIC_COLORS["green"],
        starter_text=(
            "Canal de anuncios oficiais do Quiz Vance.\n\n"
            "Aqui entram novas versoes do APK, avisos do produto, mudancas de oferta "
            "e campanhas que movem a comunidade."
        ),
    ),
    ForumTopicBlueprint(
        key="comece_aqui",
        name="Comece aqui",
        icon_color=DEFAULT_TOPIC_COLORS["yellow"],
        starter_text=(
            "Seja bem-vindo ao ecossistema Quiz Vance.\n\n"
            "Passo rapido para entrar rodando:\n"
            "1. Use /baixar para instalar o app no Android.\n"
            "2. Use /oferta para ver a proposta beta atual.\n"
            "3. Use /resultados para entender o valor na pratica.\n"
            "4. Use /faq para tirar duvidas rapidas.\n"
            "5. Use /suporte se travar em instalacao, login ou pagamento.\n"
            "6. Por enquanto o app esta disponivel apenas para Android.\n"
            "7. Leia /regras antes de postar."
        ),
    ),
    ForumTopicBlueprint(
        key="bate_papo",
        name="Bate-papo",
        icon_color=DEFAULT_TOPIC_COLORS["blue"],
        starter_text=(
            "Espaco livre para troca entre alunos.\n\n"
            "Compartilhe rotina, metas, conquistas, dificuldades e duvidas mais amplas "
            "sobre estudo. Comunidade viva gera mais retencao e mais confianca."
        ),
    ),
    ForumTopicBlueprint(
        key="resultados",
        name="Resultados",
        icon_color=DEFAULT_TOPIC_COLORS["pink"],
        starter_text=(
            "Use este topico para postar evolucao, aprovacoes, prints de desempenho e "
            "depoimentos sobre a experiencia com o Quiz Vance.\n\n"
            "Prova social forte reduz objecao e acelera a confianca de quem acabou de chegar."
        ),
    ),
    ForumTopicBlueprint(
        key="suporte",
        name="Suporte/Ajuda",
        icon_color=DEFAULT_TOPIC_COLORS["red"],
        starter_text=(
            "Use este topico para problemas tecnicos e suporte rapido.\n\n"
            "Ao pedir ajuda, mande:\n"
            "- modelo do celular\n"
            "- print do erro\n"
            "- passo em que travou"
        ),
    ),
    ForumTopicBlueprint(
        key="feedbacks",
        name="Feedbacks/Inovacoes",
        icon_color=DEFAULT_TOPIC_COLORS["purple"],
        starter_text=(
            "Mande ideias de features, melhorias do onboarding, novos concursos e ajustes "
            "de produto.\n\n"
            "Aqui entra tudo que pode virar inovacao de verdade e melhorar conversao."
        ),
    ),
]


class TelegramBotError(RuntimeError):
    pass


def telegram_token() -> str:
    return str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def telegram_enabled() -> bool:
    return bool(telegram_token())


def webhook_secret() -> str:
    return str(os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()


def community_invite_url() -> str:
    return str(os.getenv("TELEGRAM_COMMUNITY_INVITE_URL") or "").strip()


def support_url() -> str:
    return str(os.getenv("TELEGRAM_SUPPORT_URL") or "").strip()


def download_url() -> str:
    return str(os.getenv("TELEGRAM_DOWNLOAD_URL") or "").strip()


def sales_url() -> str:
    return str(os.getenv("TELEGRAM_SALES_URL") or "").strip()


def bot_display_name() -> str:
    return str(os.getenv("TELEGRAM_BOT_DISPLAY_NAME") or "Quiz Vance Bot").strip()


def group_title() -> str:
    return str(os.getenv("TELEGRAM_GROUP_TITLE") or "Quiz Vance | Comunidade Oficial").strip()


def group_description() -> str:
    value = str(
        os.getenv("TELEGRAM_GROUP_DESCRIPTION")
        or "Comunidade oficial do Quiz Vance: atualizacoes, resultados, suporte e oferta do app."
    ).strip()
    return value[:255]


def alert_chat_id() -> int | str | None:
    raw = str(os.getenv("TELEGRAM_ALERT_CHAT_ID") or "").strip()
    if not raw:
        return None
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw


def alert_thread_id() -> int | None:
    raw = str(os.getenv("TELEGRAM_ALERT_THREAD_ID") or "").strip()
    if raw.isdigit():
        return int(raw)
    return None


def _compact_lines(*parts: str) -> str:
    cleaned = [str(part or "").strip() for part in parts if str(part or "").strip()]
    return "\n".join(cleaned)


def marketing_manager_directive() -> str:
    return MARKETING_MANAGER_DIRECTIVE


def build_operational_refresh_pack() -> dict[str, Any]:
    return {
        "positioning": "Comunidade enxuta para onboarding, prova social, suporte e inovacao.",
        "topics": [
            {"name": "Atualizacoes", "message": DEFAULT_GROUP_BLUEPRINT[0].starter_text},
            {"name": "Comece aqui", "message": DEFAULT_GROUP_BLUEPRINT[1].starter_text},
            {"name": "Bate-papo", "message": DEFAULT_GROUP_BLUEPRINT[2].starter_text},
            {"name": "Resultados", "message": DEFAULT_GROUP_BLUEPRINT[3].starter_text},
            {"name": "Suporte/Ajuda", "message": DEFAULT_GROUP_BLUEPRINT[4].starter_text},
            {"name": "Feedbacks/Inovacoes", "message": DEFAULT_GROUP_BLUEPRINT[5].starter_text},
        ],
        "daily_posts": [
            "Dia 1: reforce o Comece aqui com CTA para /baixar e /oferta.",
            "Dia 2: puxe um print ou depoimento em Resultados.",
            "Dia 3: poste melhoria nova em Atualizacoes.",
            "Dia 4: chame a base para compartilhar rotina em Bate-papo.",
            "Dia 5: levante uma pergunta de produto em Feedbacks/Inovacoes.",
            "Dia 6: recircule a oferta beta com CTA curto.",
            "Dia 7: compile melhores resultados da semana.",
        ],
    }


def _menu_keyboard() -> dict[str, list[list[dict[str, str]]]]:
    rows: list[list[dict[str, str]]] = []

    if download_url():
        rows.append([{"text": "Baixar app", "url": download_url()}])
    else:
        rows.append([{"text": "Baixar app", "callback_data": "menu:baixar"}])

    rows.append([{"text": "Oferta beta", "callback_data": "menu:oferta"}])
    rows.append([{"text": "Ver resultados", "callback_data": "menu:resultados"}])

    if community_invite_url():
        rows.append([{"text": "Entrar na comunidade", "url": community_invite_url()}])
    else:
        rows.append([{"text": "Entrar na comunidade", "callback_data": "menu:grupo"}])

    if support_url():
        rows.append([{"text": "Falar com suporte", "url": support_url()}])
    else:
        rows.append([{"text": "Falar com suporte", "callback_data": "menu:suporte"}])

    rows.append([{"text": "FAQ rapido", "callback_data": "menu:faq"}])
    return {"inline_keyboard": rows}


def _offer_message() -> str:
    return _compact_lines(
        "Oferta beta do Quiz Vance",
        "Acesso premium_30 por R$ 9,99.",
        "Ideal para quem quer sair da enrolacao e estudar com questoes, revisao e ritmo diario.",
        "Baixe o APK, teste hoje e, se curtir a experiencia, feche o premium sem friccao.",
        f"Comercial: {sales_url()}" if sales_url() else "",
    )


def _download_message() -> str:
    apk = download_url()
    if apk:
        return _compact_lines(
            "Seu acesso ao app esta por aqui.",
            f"Link do APK: {apk}",
            "Importante: nesta fase o app esta disponivel apenas para Android.",
            "Se estiver no Android, ative instalacao de fontes confiaveis quando o sistema pedir.",
        )
    return _compact_lines(
        "O link do APK ainda nao foi configurado no backend.",
        "Defina TELEGRAM_DOWNLOAD_URL para liberar o download no bot.",
    )


def _results_message() -> str:
    return _compact_lines(
        "Resultados e prova social",
        "Aqui entram prints de evolucao, streaks, acertos, simulados e relatos reais de quem esta usando o Quiz Vance.",
        "Quem chega agora precisa sentir que o app gera constancia, clareza e tracao de estudo na pratica.",
        "Se voce ja testou, poste seu print no topico Resultados e fortalece a comunidade.",
    )


def _faq_message() -> str:
    return _compact_lines(
        "FAQ rapido",
        "1. Como instalar? Use /baixar e habilite a instalacao quando o Android pedir.",
        "2. Tem para iPhone ou desktop? Ainda nao. Por enquanto o app esta disponivel apenas para Android.",
        "3. Como funciona o premium? Use /oferta para ver a proposta atual.",
        "4. Onde tiro duvida tecnica? Use /suporte.",
        "5. Onde vejo prova social? Use /resultados.",
        "6. Onde acompanho a comunidade? Use /grupo.",
    )


def _support_message() -> str:
    return _compact_lines(
        "Suporte Quiz Vance",
        f"Atendimento: {support_url()}" if support_url() else "",
        f"Comercial: {sales_url()}" if sales_url() else "",
        "Se travou na instalacao, login, pagamento ou uso, chama aqui e resolvemos rapido.",
    )


def _group_message() -> str:
    return _compact_lines(
        "Comunidade oficial do Quiz Vance",
        f"Convite: {community_invite_url()}" if community_invite_url() else "",
        "Topicos principais: Atualizacoes, Comece aqui, Bate-papo, Resultados, Suporte/Ajuda e Feedbacks/Inovacoes.",
    )


def _rules_message() -> str:
    return _compact_lines(
        "Regras do grupo",
        "1. Nada de spam ou links soltos.",
        "2. Duvidas tecnicas vao para Suporte/Ajuda.",
        "3. Resultados e depoimentos vao para Resultados.",
        "4. Ideias e melhorias vao para Feedbacks/Inovacoes.",
        "5. Respeito total entre membros.",
        "6. Se entrou agora, comece por /baixar, /oferta e /faq.",
    )


def _strategy_message() -> str:
    return _compact_lines(
        "Estrategia da comunidade Quiz Vance",
        "1. Fazer novos membros baixarem e testarem rapido.",
        "2. Mostrar resultado real cedo para aumentar confianca.",
        "3. Manter conversas e prova social para reter a base.",
        "4. Transformar feedback em inovacao e conteudo de venda.",
        "5. Levar interessados quentes para suporte/comercial sem friccao.",
    )


def _start_message() -> str:
    return _compact_lines(
        f"Bem-vindo ao {bot_display_name()}",
        "Esse bot cuida da entrada comercial e da comunidade oficial do Quiz Vance.",
        "Neste momento, o app esta disponivel apenas para Android.",
        "Se voce quer estudar com mais ritmo e menos dispersao, comece pelo APK, pela oferta beta e pelo FAQ rapido.",
        "Use os botoes abaixo para entrar rapido no ecossistema.",
    )


def _normalize_command(text: str) -> str:
    raw = str(text or "").strip()
    if not raw.startswith("/"):
        return ""
    return raw.split()[0][1:].split("@")[0].strip().lower()


class TelegramBotClient:
    def __init__(self, token: str | None = None, *, timeout_seconds: float = 20.0, base_url: str | None = None):
        self.token = str(token or telegram_token()).strip()
        self.timeout_seconds = float(timeout_seconds)
        api_base = str(base_url or os.getenv("TELEGRAM_API_BASE_URL") or "https://api.telegram.org").strip().rstrip("/")
        self.base_url = api_base

    def _method_url(self, method: str) -> str:
        if not self.token:
            raise TelegramBotError("telegram_bot_token_missing")
        return f"{self.base_url}/bot{self.token}/{method}"

    def request(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self._method_url(method), json=payload or {})
        response.raise_for_status()
        data = response.json()
        if not bool(data.get("ok")):
            raise TelegramBotError(str(data.get("description") or f"telegram_api_error:{method}"))
        return data.get("result")

    def get_me(self) -> dict[str, Any]:
        return dict(self.request("getMe") or {})

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        message_thread_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": str(text or "").strip()[:4096],
            "disable_notification": bool(disable_notification),
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = int(message_thread_id)
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return dict(self.request("sendMessage", payload) or {})

    def answer_callback_query(self, callback_query_id: str, *, text: str = "", show_alert: bool = False) -> bool:
        payload = {
            "callback_query_id": str(callback_query_id or "").strip(),
            "text": str(text or "").strip()[:200],
            "show_alert": bool(show_alert),
        }
        return bool(self.request("answerCallbackQuery", payload))

    def set_my_commands(self, commands: list[dict[str, str]]) -> bool:
        return bool(self.request("setMyCommands", {"commands": commands}))

    def set_chat_title(self, chat_id: int | str, title: str) -> bool:
        return bool(self.request("setChatTitle", {"chat_id": chat_id, "title": str(title or "").strip()[:128]}))

    def set_chat_description(self, chat_id: int | str, description: str) -> bool:
        payload = {"chat_id": chat_id, "description": str(description or "").strip()[:255]}
        return bool(self.request("setChatDescription", payload))

    def create_forum_topic(self, chat_id: int | str, name: str, *, icon_color: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "name": str(name or "").strip()[:128]}
        if icon_color is not None:
            payload["icon_color"] = int(icon_color)
        return dict(self.request("createForumTopic", payload) or {})

    def pin_chat_message(self, chat_id: int | str, message_id: int, *, disable_notification: bool = True) -> bool:
        payload = {"chat_id": chat_id, "message_id": int(message_id), "disable_notification": bool(disable_notification)}
        return bool(self.request("pinChatMessage", payload))

    def set_webhook(self, url: str, *, secret_token: str = "", drop_pending_updates: bool = True) -> bool:
        payload: dict[str, Any] = {
            "url": str(url or "").strip(),
            "drop_pending_updates": bool(drop_pending_updates),
            "allowed_updates": ["message", "callback_query"],
        }
        if secret_token:
            payload["secret_token"] = str(secret_token).strip()
        return bool(self.request("setWebhook", payload))


def provision_community_group(
    client: TelegramBotClient,
    chat_id: int | str,
    *,
    set_commands: bool = True,
    pin_messages: bool = True,
    chat_title_override: str = "",
    chat_description_override: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "chat_id": chat_id,
        "group_title": chat_title_override or group_title(),
        "group_description": chat_description_override or group_description(),
        "commands": list(DEFAULT_COMMANDS),
        "topics": [],
        "dry_run": bool(dry_run),
    }

    for topic in DEFAULT_GROUP_BLUEPRINT:
        summary["topics"].append(
            {
                "key": topic.key,
                "name": topic.name,
                "icon_color": topic.icon_color,
                "starter_text": topic.starter_text,
                "pin_starter": bool(topic.pin_starter),
            }
        )

    if dry_run:
        return summary

    client.set_chat_title(chat_id, chat_title_override or group_title())
    client.set_chat_description(chat_id, chat_description_override or group_description())
    if set_commands:
        client.set_my_commands(DEFAULT_COMMANDS)

    created_topics: list[dict[str, Any]] = []
    for topic in DEFAULT_GROUP_BLUEPRINT:
        created = client.create_forum_topic(chat_id, topic.name, icon_color=topic.icon_color)
        thread_id = int(created.get("message_thread_id") or 0)
        starter = client.send_message(
            chat_id,
            topic.starter_text,
            message_thread_id=thread_id if thread_id > 0 else None,
            reply_markup=_menu_keyboard() if topic.key == "comece_aqui" else None,
            disable_notification=True,
        )
        if pin_messages and topic.pin_starter and starter.get("message_id"):
            client.pin_chat_message(chat_id, int(starter["message_id"]), disable_notification=True)
        created_topics.append(
            {
                "key": topic.key,
                "name": topic.name,
                "message_thread_id": thread_id,
                "starter_message_id": int(starter.get("message_id") or 0),
            }
        )

    summary["topics"] = created_topics
    return summary


def configure_webhook(client: TelegramBotClient, public_base_url: str, *, drop_pending_updates: bool = True) -> dict[str, Any]:
    base = str(public_base_url or "").strip().rstrip("/")
    if not base:
        raise TelegramBotError("public_base_url_missing")
    webhook_url = f"{base}/telegram/webhook"
    secret = webhook_secret()
    ok = client.set_webhook(webhook_url, secret_token=secret, drop_pending_updates=drop_pending_updates)
    return {"ok": bool(ok), "webhook_url": webhook_url, "secret_configured": bool(secret)}


def handle_update(update: dict[str, Any], client: TelegramBotClient | None = None) -> dict[str, Any]:
    tg = client or TelegramBotClient()
    if not telegram_enabled():
        return {"ok": False, "ignored": True, "reason": "telegram_disabled"}
    try:
        callback = update.get("callback_query") if isinstance(update, dict) else None
        if isinstance(callback, dict):
            return _handle_callback_query(tg, callback)

        message = update.get("message") if isinstance(update, dict) else None
        if isinstance(message, dict):
            return _handle_message(tg, message)

        return {"ok": True, "ignored": True, "reason": "unsupported_update"}
    except Exception as ex:
        logger.exception("telegram_update_failed")
        return {"ok": False, "handled": False, "error": str(ex)}


def _handle_callback_query(client: TelegramBotClient, callback: dict[str, Any]) -> dict[str, Any]:
    callback_id = str(callback.get("id") or "").strip()
    data = str(callback.get("data") or "").strip().lower()
    message = callback.get("message") if isinstance(callback.get("message"), dict) else {}
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id")

    if data == "menu:baixar":
        text = _download_message()
    elif data in {"menu:oferta", "menu:planos"}:
        text = _offer_message()
    elif data == "menu:resultados":
        text = _results_message()
    elif data == "menu:grupo":
        text = _group_message()
    elif data == "menu:faq":
        text = _faq_message()
    elif data == "menu:suporte":
        text = _support_message()
    else:
        text = _start_message()

    if callback_id:
        client.answer_callback_query(callback_id)
    if chat_id is not None:
        client.send_message(chat_id, text, reply_markup=_menu_keyboard())
    return {"ok": True, "handled": True, "type": "callback_query", "action": data or "menu:start"}


def _handle_message(client: TelegramBotClient, message: dict[str, Any]) -> dict[str, Any]:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id")
    chat_type = str(chat.get("type") or "").strip().lower()
    text = str(message.get("text") or "").strip()
    command = _normalize_command(text)

    if message.get("new_chat_members") and chat_id is not None and chat_type in {"group", "supergroup"}:
        welcome = _compact_lines(
            "Boas-vindas ao Quiz Vance.",
            "Use o topico Comece aqui para onboarding rapido, /oferta para entender a proposta, /resultados para ver prova social e /suporte se precisar.",
        )
        client.send_message(chat_id, welcome, disable_notification=True)
        return {"ok": True, "handled": True, "type": "group_welcome"}

    alias_responses = {
        "start": _start_message(),
        "menu": _start_message(),
        "baixar": _download_message(),
        "grupo": _group_message(),
        "comunidade": _group_message(),
        "suporte": _support_message(),
        "ajuda": _support_message(),
        "faq": _faq_message(),
        "oferta": _offer_message(),
        "planos": _offer_message(),
        "resultados": _results_message(),
        "regras": _rules_message(),
        "comercial": _offer_message(),
        "estrategia": _strategy_message(),
    }

    if chat_type != "private":
        if command in alias_responses and chat_id is not None:
            client.send_message(chat_id, alias_responses[command], disable_notification=True)
            return {"ok": True, "handled": True, "type": "group_command", "command": command}
        return {"ok": True, "ignored": True, "reason": "group_message_ignored"}

    response = alias_responses.get(command or "start")
    if not response and text:
        response = _compact_lines(
            "Posso te ajudar com download, oferta, resultados, grupo e suporte.",
            "Use os botoes abaixo para seguir.",
        )
    if not response:
        response = _start_message()

    if chat_id is not None:
        client.send_message(chat_id, response, reply_markup=_menu_keyboard())
    return {"ok": True, "handled": True, "type": "private_message", "command": command or "text"}


def notify_admin_event(
    title: str,
    *,
    user_id: int = 0,
    name: str = "",
    email_id: str = "",
    plan_code: str = "",
    amount_cents: int = 0,
    provider: str = "",
    checkout_id: str = "",
    detail: str = "",
) -> bool:
    chat_id = alert_chat_id()
    if chat_id is None or not telegram_enabled():
        return False
    lines = [
        str(title or "").strip(),
        f"Usuario: {name} (#{int(user_id)})" if int(user_id or 0) > 0 else "",
        f"Email: {email_id}" if email_id else "",
        f"Plano: {plan_code}" if plan_code else "",
        f"Valor: R$ {amount_cents / 100:.2f}" if int(amount_cents or 0) > 0 else "",
        f"Provider: {provider}" if provider else "",
        f"Checkout: {checkout_id}" if checkout_id else "",
        detail,
    ]
    text = _compact_lines(*lines)
    client = TelegramBotClient()
    client.send_message(chat_id, text, message_thread_id=alert_thread_id(), disable_notification=False)
    return True
