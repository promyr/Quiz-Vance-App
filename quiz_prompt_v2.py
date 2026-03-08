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
_MAX_OPCAO = 90
_MAX_EXPLIC = 190
_MAX_SUBTEMA = 60
_MAX_TRECHO = 6000
_MIN_CHUNK = 300


_NIVEL: dict[str, tuple[str, str]] = {
    "iniciante": (
        "INICIANTE",
        "Conceito basico e direto; distratores simples erram um detalhe objetivo.",
    ),
    "facil": (
        "FACIL",
        "Conceito central direto; distratores erram um detalhe concreto.",
    ),
    "intermediario": (
        "INTERMEDIARIO",
        "Exija relacao causa-efeito ou aplicacao de conceito; distratores invertem a logica.",
    ),
    "dificil": (
        "DIFICIL",
        "Questao-problema com multiplas etapas; distratores sao parcialmente corretos.",
    ),
    "mestre": (
        "MESTRE",
        "Caso tecnico de alto nivel com interpretacoes plausiveis, sem distratores absurdos.",
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
        "Voce e um elaborador senior de questoes para concursos brasileiros de alto nivel. "
        "Retorne apenas JSON valido, sem markdown e sem texto fora do JSON."
    )


def _normalize_level(dificuldade: str) -> tuple[str, str]:
    key = str(dificuldade or "").strip().lower()
    key = _NIVEL_ALIAS.get(key, key)
    if key not in _NIVEL:
        key = "intermediario"
    return _NIVEL[key]


def _prepare_trecho(chunks: list[str], tema: str, max_chars: int = _MAX_TRECHO) -> str:
    if not chunks:
        return f"Tema: {tema}. Elabore questoes tecnicas sobre este assunto."

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
    return trecho + "\n[...material truncado para caber no contexto...]"


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

    historico_block = ""
    if evitar:
        itens = []
        for q in evitar[:20]:
            txt = " ".join(str(q or "").split()).strip()
            if txt:
                itens.append(f"- {txt[:160]}")
        if itens:
            historico_block = "\nHISTORICO - nao recrie nem parafraseie estas perguntas:\n" + "\n".join(itens) + "\n"

    subtema_block = ""
    if subtemas:
        subtema_block = "\nSUBTEMAS DISPONIVEIS (priorize variedade):\n" + "\n".join(f"- {s}" for s in subtemas) + "\n"

    offset = (pagina_int - 1) % 4
    indices_seq = ", ".join(str((offset + i) % 4) for i in range(quantidade))
    sample_index = (offset + 2) % 4

    prompt = textwrap.dedent(
        f"""
        MATERIAL DE ESTUDO (LOTE {pagina_int}):
        {trecho}

        TEMA: {tema}
        NIVEL: {nivel_label}
        Gere EXATAMENTE {quantidade} questao(oes) novas.
        {subtema_block}{historico_block}
        REGRAS OBRIGATORIAS:
        1. Use somente o material acima. Nunca invente fatos externos.
        2. Perguntas autonomas: proibido usar "segundo o texto", "conforme o trecho" ou similar.
        3. Proibido decoreba ("O que e X?"). Exija raciocinio, comparacao ou aplicacao.
        4. Ignore metadados (autor, ISBN, editora, edicao, datas, sumario, codigos).
        5. Distratores plausiveis: conceito real do material, mas aplicado em contexto errado.
        6. Varie subtemas entre questoes; evite concentrar tudo no mesmo ponto.
        7. Varie correta_index conforme sequencia sugerida: [{indices_seq}].
        8. Se nao houver base suficiente, retorne [].

        INSTRUCAO DE NIVEL:
        {nivel_instrucao}

        LIMITES DE FORMATO:
        - pergunta: max {_MAX_PERGUNTA} chars
        - subtema: max {_MAX_SUBTEMA} chars
        - opcoes: lista com EXATAMENTE 4 itens, max {_MAX_OPCAO} chars cada, sem prefixos "A)", "1."
        - correta_index: inteiro 0-3
        - explicacao: max {_MAX_EXPLIC} chars

        Retorne APENAS JSON valido, sem markdown e sem texto adicional:
        [
          {{
            "pergunta": "Enunciado tecnico e autonomo",
            "subtema": "Conceito-chave",
            "opcoes": ["Opcao correta", "Distrator 1", "Distrator 2", "Distrator 3"],
            "correta_index": {sample_index},
            "explicacao": "Razao objetiva da resposta correta."
          }}
        ]
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
        if not pergunta or len(pergunta) > (_MAX_PERGUNTA + 40):
            return False
        if _REF_MATERIAL_RE.search(pergunta):
            return False
        if _DECOREBA_RE.match(pergunta):
            return False

        opcoes = q.get("opcoes") or []
        if not isinstance(opcoes, list) or len(opcoes) != 4:
            return False

        normalized_options: list[str] = []
        for raw in opcoes[:4]:
            text = _OPTION_PREFIX_RE.sub("", str(raw or "")).strip()
            if not text:
                return False
            if len(text) > (_MAX_OPCAO + 20):
                return False
            normalized_options.append(text.lower())
        if len(set(normalized_options)) != 4:
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
            opcoes.append(text[:_MAX_OPCAO])

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
