# -*- coding: utf-8 -*-
"""
quiz_prompt_v2.py

Prompt and validation helpers for quiz generation.
This module is consumed by:
- core/ai_service_v2.py (prompt builder)
- main_v2.py (post-parse validation/sanitization in some flows)
"""

from __future__ import annotations

import json
import re
import textwrap
from typing import Any, Optional


_MAX_PERGUNTA = 280
_MAX_EXPLIC = 185
_MAX_SUBTEMA = 60
_MAX_TRECHO = 6000
_MIN_CHUNK = 300

_TIPOS_QUESTAO = ("SITUACIONAL", "COMPARATIVA", "APLICACAO", "EXCECAO", "CONCEITUAL")

_CRITICIDADES = ("ALTA", "MEDIA", "BAIXA")


def _distribuicao_criticidade(qtd: int) -> str:
    if qtd <= 2:
        return "ALTA=1, MEDIA=1"
    alta = max(1, qtd // 3)
    media = max(1, qtd // 3)
    baixa = max(0, qtd - alta - media)
    return f"ALTA={alta}, MEDIA={media}, BAIXA={baixa}"


_NIVEL: dict[str, tuple[str, str]] = {
    "iniciante": (
        "INICIANTE",
        "Perguntas diretas sobre conceitos basicos. Alternativas erradas contem erros claros.",
    ),
    "facil": (
        "FACIL",
        "Perguntas sobre conceitos fundamentais. Alternativas erradas trocam um detalhe especifico.",
    ),
    "intermediario": (
        "INTERMEDIARIO",
        "Perguntas que exigem entender relacoes entre conceitos ou aplicar regras a situacoes.",
    ),
    "dificil": (
        "DIFICIL",
        "Perguntas com situacoes praticas que exigem analise. Alternativas erradas sao parcialmente corretas.",
    ),
    "mestre": (
        "MESTRE",
        "Casos complexos com multiplas interpretacoes plausiveis. Exige dominio profundo do tema.",
    ),
}

_NIVEL_ALIAS: dict[str, str] = {
    "fácil": "facil",
    "medio": "intermediario",
    "médio": "intermediario",
    "avancado": "dificil",
    "avançado": "dificil",
    "easy": "iniciante",
    "beginner": "iniciante",
}

_REF_MATERIAL_RE = re.compile(
    r"\b("
    r"segundo o texto|conforme o trecho|de acordo com o texto|de acordo com o autor|"
    r"no texto acima|no texto apresentado|com base no texto|com base no trecho|"
    r"o autor afirma|o autor diz|leia o trecho"
    r")\b",
    re.IGNORECASE,
)

_DECOREBA_RE = re.compile(
    r"^(o que e\b|defina\b|conceitue\b|qual o nome\b|qual a definicao\b|quem foi\b)",
    re.IGNORECASE,
)

_OPTION_PREFIX_RE = re.compile(r"^(?:[A-Ea-e][\)\.\:\-]\s*|\d+[\)\.]\s*)")
_SIGLA_RE = re.compile(r"\b[A-Z]{2,8}(?:/\d{2,4})?\b")
_PROPER_RE = re.compile(r"\b(?:[A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{3,}){0,2})\b")


def _build_system_prompt() -> str:
    return (
        "Voce e o motor de questoes do Quiz Vance, um app brasileiro de estudo para concursos.\n"
        "Seu trabalho: receber um material e gerar questoes objetivas de multipla escolha.\n"
        "Responda SOMENTE com um array JSON. Comece com [ e termine com ].\n"
        "Nunca inclua markdown, explicacoes fora do JSON, ou campos extras.\n"
        "Nunca pergunte sobre autor, editora, ano, ISBN, sumario ou estrutura do documento."
    )


def _normalize_level(dificuldade: str) -> tuple[str, str]:
    key = str(dificuldade or "").strip().lower()
    key = _NIVEL_ALIAS.get(key, key)
    if key not in _NIVEL:
        key = "intermediario"
    return _NIVEL[key]


def _prepare_trecho(chunks: list[str], tema: str, max_chars: int = _MAX_TRECHO) -> str:
    if not chunks:
        return f"Tema: {tema}. Elabore questoes sobre este assunto."

    cleaned = [str(c).strip() for c in chunks if str(c).strip()]
    if not cleaned:
        return f"Tema: {tema}."

    safe_max = max(800, int(max_chars or _MAX_TRECHO))
    chars_per_chunk = max(_MIN_CHUNK, safe_max // max(1, len(cleaned)))
    partes: list[str] = []

    for chunk in cleaned:
        if len(chunk) <= chars_per_chunk:
            partes.append(chunk)
            continue
        cut = chunk[:chars_per_chunk]
        split_at = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(": "))
        if split_at > int(chars_per_chunk * 0.55):
            cut = cut[: split_at + 1]
        partes.append(cut)

    trecho = "\n\n".join(partes)
    if len(trecho) <= safe_max:
        return trecho

    trecho = trecho[:safe_max]
    split_at = max(trecho.rfind(". "), trecho.rfind("; "), trecho.rfind(": "))
    if split_at > int(safe_max * 0.75):
        trecho = trecho[: split_at + 1]
    return trecho + "\n[...truncado...]"


def _extract_subtema_anchors(chunks: list[str], max_items: int = 10) -> list[str]:
    stopwords = {
        "de", "da", "do", "das", "dos", "a", "o", "e", "em", "no", "na", "que", "para", "com",
        "os", "as", "se", "por", "ao", "ou", "uma", "um", "mais", "quando", "como", "mas",
        "isso", "esta", "este", "essa", "esse", "ser", "ter", "foi", "nao", "ja",
    }
    seen: set[str] = set()
    out: list[str] = []

    for raw in chunks or []:
        text = str(raw or "").strip()
        if not text:
            continue
        anchor = ""

        m = _SIGLA_RE.search(text[:220])
        if m:
            anchor = m.group(0).strip()

        if not anchor:
            m2 = _PROPER_RE.search(text[:300])
            if m2:
                anchor = m2.group(0).strip()

        if not anchor:
            tokens = []
            for tok in re.findall(r"[A-Za-z0-9_/-]+", text):
                low = tok.lower()
                if len(low) >= 4 and low not in stopwords:
                    tokens.append(tok)
                if len(tokens) >= 5:
                    break
            anchor = " ".join(tokens).strip()

        if anchor and anchor not in seen:
            seen.add(anchor)
            out.append(anchor[:_MAX_SUBTEMA])
        if len(out) >= max(1, int(max_items or 1)):
            break

    return out


def _build_quiz_prompt(
    chunks: list[str],
    tema: str,
    dificuldade: str,
    qtd: int,
    pagina: int = 1,
    evitar: Optional[list[str]] = None,
) -> str:
    try:
        quantidade = max(1, min(10, int(qtd or 1)))
    except Exception:
        quantidade = 1
    try:
        pagina_int = max(1, int(pagina or 1))
    except Exception:
        pagina_int = 1

    nivel_label, nivel_instrucao = _normalize_level(dificuldade)
    trecho = _prepare_trecho(list(chunks or []), str(tema or ""), _MAX_TRECHO)
    subtemas = _extract_subtema_anchors(list(chunks or []), max_items=min(12, max(4, quantidade * 2)))
    has_content = bool(chunks and any(str(c).strip() for c in chunks))

    # Bloco de questoes a evitar
    evitar_block = ""
    if evitar:
        itens = []
        for q in evitar[:20]:
            txt = " ".join(str(q or "").split()).strip()
            if txt:
                itens.append(f"- {txt[:160]}")
        if itens:
            evitar_block = "\nJa usadas (nao repita):\n" + "\n".join(itens) + "\n"

    # Subtemas extraidos do material
    subtema_block = ""
    if subtemas:
        subtema_block = "Subtemas: " + ", ".join(subtemas) + ".\n"

    # Variacao de posicao da correta
    offset = (pagina_int - 1) % 4
    indices_seq = ", ".join(str((offset + i) % 4) for i in range(quantidade))
    sample_idx = (offset) % 4

    # Retorno vazio so quando tem PDF
    vazio = "\nSe o material nao tiver conteudo tecnico util, retorne []." if has_content else ""

    prompt = textwrap.dedent(
        f"""
        Gere {quantidade} questoes de multipla escolha sobre o conteudo abaixo.

        {trecho}

        Tema: {tema}
        Dificuldade: {nivel_label}
        {nivel_instrucao}
        {subtema_block}{evitar_block}
        Requisitos:
        - Enunciado claro e autonomo (sem mencionar "o texto", "o autor", "o trecho").
        - 4 alternativas plausiveis. A correta deve ser a unica inequivocamente certa.
        - Nao pergunte sobre metadados (autor, editora, ano, capitulo, sumario).
        - Varie a posicao da resposta correta: [{indices_seq}].
        - Cada questao sobre um aspecto diferente do conteudo.{vazio}

        Formato — array JSON, comece direto com [
        Exemplo de 1 item:
        [{{
          "pergunta": "Em caso de posse sem exercicio no prazo, a nomeacao sera:",
          "subtema": "Posse",
          "opcoes": ["Tornada sem efeito", "Anulada", "Convertida", "Suspensa"],
          "correta_index": {sample_idx},
          "explicacao": "A nomeacao e tornada sem efeito por falta de exercicio.",
          "criticidade": "MEDIA",
          "tipo": "APLICACAO"
        }}]
        """
    ).strip()
    return prompt


def _try_extract_json_list(raw: str) -> list[dict]:
    if not raw:
        return []
    text = str(raw).strip().replace("```json", "").replace("```", "")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [p for p in parsed if isinstance(p, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, list):
                return [p for p in parsed if isinstance(p, dict)]
        except Exception:
            pass

    out = []
    for chunk in re.findall(r"\{[\s\S]*?\}", text):
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, dict):
                out.append(parsed)
        except Exception:
            continue
    return out


def validate_question(q: dict) -> bool:
    try:
        if not isinstance(q, dict):
            return False
        pergunta = str(q.get("pergunta") or "").strip()
        if not pergunta or len(pergunta) > (_MAX_PERGUNTA + 120):
            return False
        # Referencia ao material e um sinal ruim, mas nao fatal
        # _REF_MATERIAL_RE agora nao rejeita — sanitize trunca depois

        opcoes = q.get("opcoes") or []
        if not isinstance(opcoes, list) or len(opcoes) < 3:
            return False

        normalized_options: list[str] = []
        for raw in opcoes[:4]:
            text = _OPTION_PREFIX_RE.sub("", str(raw or "")).strip()
            if not text:
                continue
            normalized_options.append(text.lower())
        if len(set(normalized_options)) < 3:
            return False

        try:
            cidx = int(str(q.get("correta_index")).strip())
        except Exception:
            return False
        if cidx < 0 or cidx >= 4:
            return False
        return True
    except Exception:
        return False


def sanitize_question(q: dict) -> dict:
    if not isinstance(q, dict):
        return {"pergunta": "", "subtema": "", "opcoes": [], "correta_index": 0, "explicacao": ""}

    pergunta = str(q.get("pergunta") or "").strip()[:_MAX_PERGUNTA]
    subtema = str(q.get("subtema") or "").strip()[:_MAX_SUBTEMA]
    explicacao = str(q.get("explicacao") or "").strip()[:_MAX_EXPLIC]

    raw_options = q.get("opcoes") or []
    opcoes: list[str] = []
    if isinstance(raw_options, list):
        for raw in raw_options[:4]:
            text = _OPTION_PREFIX_RE.sub("", str(raw or "")).strip()
            opcoes.append(text)

    try:
        cidx = int(str(q.get("correta_index")).strip())
    except Exception:
        cidx = 0
    if opcoes:
        cidx = max(0, min(cidx, len(opcoes) - 1))
    else:
        cidx = 0

    return {
        "pergunta": pergunta,
        "subtema": subtema,
        "opcoes": opcoes,
        "correta_index": cidx,
        "explicacao": explicacao,
    }


def try_parse_questions(raw: str) -> list[dict]:
    result: list[dict] = []
    for item in _try_extract_json_list(raw):
        sanitized = sanitize_question(item)
        if validate_question(sanitized):
            result.append(sanitized)
    return result
