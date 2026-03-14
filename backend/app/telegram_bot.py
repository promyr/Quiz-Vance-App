from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from zoneinfo import ZoneInfo
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


@dataclass(frozen=True)
class DailyCommunityPost:
    topic_key: str
    text: str
    image_path: str = ""


DEFAULT_COMMANDS = [
    {"command": "start", "description": "Abrir menu principal"},
    {"command": "comecar", "description": "Ver o passo a passo ate o cadastro"},
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
- publicar pelo menos 1 postagem por dia com CTA claro e objetivo unico;
- repetir o caminho ate o APK e o cadastro sem assumir que o usuario entendeu sozinho;
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
            "Fluxo simples para nao se perder:\n"
            "1. Use /comecar para ver o passo a passo.\n"
            "2. Use /baixar para chegar no APK.\n"
            "3. Instale o app no Android.\n"
            "4. Abra o app e toque em Criar conta/Cadastrar.\n"
            "5. Depois veja /oferta, /resultados e /faq.\n"
            "6. Se travar em instalacao, login ou pagamento, use /suporte.\n"
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
        or (
            "Comunidade oficial do Quiz Vance. Entrou agora? Use /comecar, baixe o APK, "
            "instale no Android e crie sua conta. Depois veja resultados, suporte e oferta beta."
        )
    ).strip()
    return value[:255]


def _coerce_chat_id(raw: str) -> int | str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def normalize_chat_id(value: int | str | None) -> str:
    parsed = _coerce_chat_id(str(value or ""))
    return str(parsed or "").strip()


def community_chat_id() -> int | str | None:
    return _coerce_chat_id(str(os.getenv("TELEGRAM_COMMUNITY_CHAT_ID") or "").strip())


def community_updates_thread_id() -> int | None:
    raw = str(
        os.getenv("TELEGRAM_COMMUNITY_UPDATES_THREAD_ID")
        or os.getenv("TELEGRAM_COMMUNITY_DAILY_THREAD_ID")
        or ""
    ).strip()
    if raw.isdigit():
        return int(raw)
    return None


def auto_post_enabled() -> bool:
    raw = str(os.getenv("TELEGRAM_AUTO_POST_ENABLED") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def auto_post_timezone_name() -> str:
    value = str(os.getenv("TELEGRAM_AUTO_POST_TIMEZONE") or "America/Sao_Paulo").strip()
    return value or "America/Sao_Paulo"


def auto_post_zoneinfo() -> ZoneInfo:
    try:
        return ZoneInfo(auto_post_timezone_name())
    except Exception:
        return ZoneInfo("UTC")


def auto_post_hour() -> int:
    try:
        return max(0, min(23, int(os.getenv("TELEGRAM_AUTO_POST_HOUR") or 9)))
    except Exception:
        return 9


def auto_post_minute() -> int:
    try:
        return max(0, min(59, int(os.getenv("TELEGRAM_AUTO_POST_MINUTE") or 0)))
    except Exception:
        return 0


def instruction_post_enabled() -> bool:
    raw = str(
        os.getenv("TELEGRAM_INSTRUCTION_POST_ENABLED")
        or os.getenv("TELEGRAM_GUIDE_POST_ENABLED")
        or "1"
    ).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _parse_clock_time(raw: str) -> tuple[int, int] | None:
    token = str(raw or "").strip()
    if not token:
        return None
    parts = token.split(":", 1)
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def instruction_post_times() -> list[tuple[int, int]]:
    raw = str(os.getenv("TELEGRAM_INSTRUCTION_POST_TIMES") or "").strip()
    parsed: list[tuple[int, int]] = []
    if raw:
        for chunk in raw.split(","):
            slot = _parse_clock_time(chunk)
            if slot and slot not in parsed:
                parsed.append(slot)
        if parsed:
            return sorted(parsed)

    legacy_hour = str(os.getenv("TELEGRAM_INSTRUCTION_POST_HOUR") or "").strip()
    legacy_minute = str(os.getenv("TELEGRAM_INSTRUCTION_POST_MINUTE") or "").strip()
    if legacy_hour or legacy_minute:
        slot = _parse_clock_time(f"{legacy_hour or '18'}:{legacy_minute or '0'}")
        if slot:
            return [slot]

    return [(12, 0), (18, 0)]


def instruction_post_times_labels() -> list[str]:
    return [f"{hour:02d}:{minute:02d}" for hour, minute in instruction_post_times()]


def instruction_post_hour() -> int:
    return int(instruction_post_times()[0][0])


def instruction_post_minute() -> int:
    return int(instruction_post_times()[0][1])


def auto_post_poll_seconds() -> int:
    try:
        return max(30, int(os.getenv("TELEGRAM_AUTO_POST_POLL_SECONDS") or 60))
    except Exception:
        return 60


def auto_post_retry_minutes() -> int:
    try:
        return max(5, int(os.getenv("TELEGRAM_AUTO_POST_RETRY_MINUTES") or 20))
    except Exception:
        return 20


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


def _app_asset_path(*parts: str) -> str:
    return str(Path(__file__).resolve().parent.joinpath(*parts))


AUTOMATED_DAILY_POSTS = [
    DailyCommunityPost(
        topic_key="comece_aqui",
        text=_compact_lines(
            "Bom dia. Se voce quer sair da enrolacao hoje, use o Quiz Vance agora.",
            "Comece em /comecar, pegue o APK em /baixar, instale no Android e toque em Criar conta/Cadastrar.",
            "Se travar em qualquer etapa, use /suporte.",
        ),
    ),
    DailyCommunityPost(
        topic_key="resultados",
        text=_compact_lines(
            "Seu estudo de hoje pode comecar em poucos minutos com o app.",
            "Baixe, entre, resolva questoes e depois volte aqui para postar seu print em Resultados.",
        ),
    ),
    DailyCommunityPost(
        topic_key="atualizacoes",
        text=_compact_lines(
            "Quem usa o Quiz Vance todos os dias sente mais ritmo e menos dispersao.",
            "Se voce ainda nao entrou no app, /comecar e /baixar resolvem isso hoje.",
        ),
    ),
    DailyCommunityPost(
        topic_key="bate_papo",
        text=_compact_lines(
            "Meta do dia: abrir o app, fazer algumas questoes e manter o ritmo de estudo vivo.",
            "Quem ja conseguiu usar hoje responde aqui; quem travou em instalacao ou cadastro chama em /suporte.",
        ),
    ),
    DailyCommunityPost(
        topic_key="comece_aqui",
        text=_compact_lines(
            "Nao deixa o grupo virar so leitura. Usa o app hoje e sente a experiencia na pratica.",
            "Fluxo rapido: /comecar, /baixar, instalar o APK, abrir o app e tocar em Criar conta/Cadastrar.",
        ),
    ),
    DailyCommunityPost(
        topic_key="atualizacoes",
        text=_compact_lines(
            "Se voce quer revisar, responder questoes e estudar com direcao, o app foi feito para isso.",
            "Comece agora em /comecar, baixe em /baixar e testa hoje mesmo.",
        ),
    ),
    DailyCommunityPost(
        topic_key="resultados",
        text=_compact_lines(
            "Fechamento da semana: se voce ainda nao usou o Quiz Vance, hoje e o dia de instalar e criar sua conta.",
            "Use /baixar, entra no app e depois conta aqui como foi seu primeiro uso.",
        ),
    ),
]


INSTRUCTIONAL_VISUAL_POSTS = [
    DailyCommunityPost(
        topic_key="comece_aqui",
        text=_compact_lines(
            "Checklist visual de hoje: baixar, instalar e criar a conta.",
            "Use /baixar, instale o APK no Android e toque em Criar conta/Cadastrar assim que abrir o app.",
            "Se travar em instalacao ou cadastro, chame em /suporte.",
        ),
        image_path=_app_asset_path("assets", "telegram_posts", "cadastro_android.png"),
    ),
    DailyCommunityPost(
        topic_key="suporte",
        text=_compact_lines(
            "Configuracao visual da IA em 1 minuto.",
            "Abra Configuracoes, escolha o Provider IA, revise o Modelo padrao e depois entre em Configurar chaves por provider.",
            "Se a chave nao funcionar, mande print em /suporte com o provider ativo.",
        ),
        image_path=_app_asset_path("assets", "telegram_posts", "configuracao_ia.png"),
    ),
    DailyCommunityPost(
        topic_key="comece_aqui",
        text=_compact_lines(
            "Fluxo visual do primeiro uso no app.",
            "Entre, configure provider/modelo/chave e so depois gere questoes ou flashcards.",
            "Quando tiver contexto real, o app rende muito melhor.",
        ),
        image_path=_app_asset_path("assets", "telegram_posts", "primeiro_uso.png"),
    ),
    DailyCommunityPost(
        topic_key="suporte",
        text=_compact_lines(
            "Checklist de suporte para resolver mais rapido.",
            "Se algo falhar, envie print, provider, modelo e o passo exato em que travou.",
            "Com isso a equipe consegue orientar sem adivinhacao.",
        ),
        image_path=_app_asset_path("assets", "telegram_posts", "suporte_checklist.png"),
    ),
]


INSTRUCTIONAL_DETAILED_POSTS = [
    DailyCommunityPost(
        topic_key="comece_aqui",
        text=_compact_lines(
            "Tutorial completo de cadastro no Quiz Vance.",
            "1. Use /baixar para pegar o APK. 2. No Android, autorize a instalacao quando o sistema pedir. 3. Abra o app e toque em Criar conta/Cadastrar.",
            "4. Preencha Nome completo, ID, Senha e Data de nascimento. 5. Finalize e use Fazer login para entrar com os dados que acabou de criar.",
            "Erros comuns: fechar o app antes de concluir o cadastro, esquecer de permitir a instalacao do APK ou achar que entrar no grupo ja cria a conta. O cadastro so termina dentro do app.",
        ),
    ),
    DailyCommunityPost(
        topic_key="suporte",
        text=_compact_lines(
            "Como criar e salvar sua API key sem confusao.",
            "1. Abra Configuracoes. 2. Toque em Configurar chaves por provider. 3. Escolha o provider que voce realmente vai usar. 4. Use Criar chave ou Abrir portal de chave.",
            "5. Copie a chave gerada, cole no campo API key e toque em Salvar chave. Depois volte e confirme se o Provider IA ativo bate com a chave que voce colou.",
            "Erros comuns: colar chave do provider errado, esquecer de salvar, usar chave sem saldo/cota ou trocar o provider e achar que a chave antiga vale para todos.",
        ),
    ),
    DailyCommunityPost(
        topic_key="comece_aqui",
        text=_compact_lines(
            "Operacao geral recomendada para o primeiro estudo no app.",
            "1. Entre na conta. 2. Abra Configuracoes. 3. Ajuste provider, modelo e API key. 4. Volte para Quiz ou Flashcards. 5. Informe um topico real ou anexe material antes de gerar conteudo.",
            "6. Responda as questoes, revise erros e acompanhe a evolucao. Se quiser prova social e dicas, volte para a comunidade e acompanhe os topicos.",
            "Atalho mental: conta criada, IA configurada, contexto definido, estudo liberado.",
        ),
    ),
    DailyCommunityPost(
        topic_key="suporte",
        text=_compact_lines(
            "Como pedir ajuda tecnica de um jeito que acelera a solucao.",
            "Quando algo falhar, mande no topico de suporte: print do erro, provider ativo, modelo selecionado, o que voce estava tentando fazer e em qual tela travou.",
            "Se o problema for geracao de questoes, diga tambem se voce informou topico ou anexou material. Isso evita diagnostico incompleto e reduz muito o vai-e-volta.",
        ),
    ),
]


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
            "Dia 1: Quem entrou hoje e ainda nao instalou: use /comecar e /baixar agora. O caminho e simples: baixar APK, instalar no Android, abrir o app e tocar em Criar conta/Cadastrar.",
            "Dia 2: Poste um print ou depoimento real em Resultados e feche com CTA: quer testar tambem? /baixar e /faq.",
            "Dia 3: Publique uma melhoria nova em Atualizacoes e termine com: se ainda nao entrou no app, comece em /comecar.",
            "Dia 4: Abra um topico no Bate-papo perguntando quem ja instalou e quem ainda travou no cadastro. Direcione os travados para /suporte.",
            "Dia 5: Reforce o passo a passo no Comece aqui: APK, instalacao, cadastro, primeiro login e teste rapido. CTA final: /baixar.",
            "Dia 6: Recircule a oferta beta com uma frase curta de urgencia e lembre que antes da oferta o usuario precisa baixar e criar a conta no app.",
            "Dia 7: Faca resumo da semana com melhores resultados e uma chamada direta: entrou no grupo e ainda nao baixou? /comecar agora.",
        ],
        "instructional_posts": [
            "Cadastro: /baixar, instalar APK, abrir o app, tocar em Criar conta, preencher Nome completo/ID/Senha/Data de nascimento e depois Fazer login.",
            "Configuracoes: antes de estudar com IA, escolher Provider IA, revisar Modelo padrao e abrir Configurar chaves por provider.",
            "API key: usar Criar chave Gemini/OpenAI/Groq, depois colar em API key e finalizar em Salvar chave.",
            "Operacao geral: entrar no app, configurar provider/modelo/chave e entao usar Quiz ou Flashcards pelo menu.",
        ],
    }


def automated_daily_posts() -> list[DailyCommunityPost]:
    return list(AUTOMATED_DAILY_POSTS)


def build_automated_daily_post(day_key: date | None = None) -> DailyCommunityPost:
    posts = automated_daily_posts()
    ref_day = day_key or date.today()
    index = (ref_day.toordinal() - 1) % len(posts)
    return posts[index]


def _primary_instruction_slot_label() -> str:
    labels = instruction_post_times_labels()
    return labels[0] if labels else "12:00"


def instructional_posts(slot_key: str = "") -> list[DailyCommunityPost]:
    resolved_slot = str(slot_key or _primary_instruction_slot_label()).strip()
    if resolved_slot == _primary_instruction_slot_label():
        return list(INSTRUCTIONAL_VISUAL_POSTS)
    return list(INSTRUCTIONAL_DETAILED_POSTS)


def build_instructional_post(day_key: date | None = None, slot_key: str = "") -> DailyCommunityPost:
    posts = instructional_posts(slot_key)
    ref_day = day_key or date.today()
    index = (ref_day.toordinal() - 1) % len(posts)
    return posts[index]


def default_reply_markup() -> dict[str, list[list[dict[str, str]]]]:
    return _menu_keyboard()


def _menu_keyboard() -> dict[str, list[list[dict[str, str]]]]:
    rows: list[list[dict[str, str]]] = []
    rows.append([{"text": "Comecar agora", "callback_data": "menu:comecar"}])

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
        "Antes de pensar na oferta, o caminho e: baixe o APK, instale no Android, abra o app e crie sua conta.",
        "Depois disso, teste hoje e, se curtir a experiencia, feche o premium sem friccao.",
        f"Comercial: {sales_url()}" if sales_url() else "",
    )


def _quickstart_message() -> str:
    apk = download_url()
    return _compact_lines(
        "Comece agora no Quiz Vance",
        "Passo 1. Use /baixar ou o botao Baixar app para chegar no APK.",
        "Passo 2. Instale o APK no Android e permita a instalacao quando o sistema pedir.",
        "Passo 3. Abra o app e toque em Criar conta/Cadastrar para fazer seu registro.",
        "Passo 4. Depois de entrar, volte aqui e use /oferta, /resultados e /faq.",
        f"Link direto do APK: {apk}" if apk else "",
        "Se travar em qualquer etapa, use /suporte.",
    )


def _download_message() -> str:
    apk = download_url()
    if apk:
        return _compact_lines(
            "Seu acesso ao app esta por aqui.",
            f"Link do APK: {apk}",
            "Importante: nesta fase o app esta disponivel apenas para Android.",
            "Se estiver no Android, ative instalacao de fontes confiaveis quando o sistema pedir.",
            "Depois de instalar, abra o app e toque em Criar conta/Cadastrar para concluir o registro.",
            "Se entrou no grupo mas ainda nao se registrou, esse e o proximo passo.",
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
        "1. Como chego no APK? Use /baixar.",
        "2. Como instalo? Baixe o APK e habilite a instalacao quando o Android pedir.",
        "3. Como me cadastro? Depois de instalar, abra o app e toque em Criar conta/Cadastrar.",
        "4. Tem para iPhone ou desktop? Ainda nao. Por enquanto o app esta disponivel apenas para Android.",
        "5. Como funciona o premium? Use /oferta para ver a proposta atual.",
        "6. Onde tiro duvida tecnica? Use /suporte.",
        "7. Onde vejo prova social? Use /resultados.",
        "8. Onde acompanho a comunidade? Use /grupo.",
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
        "Se voce entrou no grupo agora, nao pare aqui: use /comecar, pegue o APK em /baixar e faca seu cadastro no app.",
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
        "Se voce quer estudar com mais ritmo e menos dispersao, siga esta ordem: /comecar, /baixar, instalar, criar sua conta e depois ver /oferta.",
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

    def send_photo(
        self,
        chat_id: int | str,
        photo: str,
        *,
        caption: str = "",
        message_thread_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        photo_value = str(photo or "").strip()
        if not photo_value:
            raise TelegramBotError("telegram_photo_missing")

        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "caption": str(caption or "").strip()[:1024],
            "disable_notification": str(bool(disable_notification)).lower(),
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = str(int(message_thread_id))
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

        photo_path = Path(photo_value)
        if photo_path.is_file():
            with photo_path.open("rb") as fh:
                files = {"photo": (photo_path.name, fh, "image/png")}
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(self._method_url("sendPhoto"), data=payload, files=files)
        else:
            payload["photo"] = photo_value
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self._method_url("sendPhoto"), json=payload)

        response.raise_for_status()
        data = response.json()
        if not bool(data.get("ok")):
            raise TelegramBotError(str(data.get("description") or "telegram_api_error:sendPhoto"))
        return dict(data.get("result") or {})

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
    elif data == "menu:comecar":
        text = _quickstart_message()
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
            "Entrou agora? Faca isso sem pensar muito: /comecar, /baixar, instale o APK no Android, abra o app e toque em Criar conta/Cadastrar.",
            "Depois use /oferta para entender a proposta, /resultados para ver prova social e /suporte se precisar.",
        )
        client.send_message(chat_id, welcome, reply_markup=_menu_keyboard(), disable_notification=True)
        return {"ok": True, "handled": True, "type": "group_welcome"}

    alias_responses = {
        "start": _start_message(),
        "menu": _start_message(),
        "comecar": _quickstart_message(),
        "instalar": _quickstart_message(),
        "cadastro": _quickstart_message(),
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
            "Posso te ajudar com APK, cadastro, oferta, resultados, grupo e suporte.",
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
