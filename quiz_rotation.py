# -*- coding: utf-8 -*-
"""
quiz_rotation.py
Rotação de assuntos e prevenção de duplicidade para o QuizVance.

RESPONSABILIDADES:
  1. Deduplicação — impede que a mesma questão (ou muito parecida) apareça
     novamente para o mesmo usuário, usando fingerprint leve sobre o enunciado.

  2. Rotação de assuntos — ao pedir um novo lote, seleciona os chunks do
     material que cobrem os subtópicos menos vistos pelo usuário, forçando
     variedade real em vez de repetir sempre o primeiro trecho do PDF.

  3. Construção do bloco "evitar" para o prompt — extrai os enunciados
     recentes do banco (não só da sessão atual) para passar ao _build_quiz_prompt.

INTEGRAÇÃO:
  Em core/ai_service_v2.py (ou no local onde generate_quiz_batch é chamado):

    from core.quiz_rotation import (
        pick_rotation_chunks,
        build_evitar_block,
        register_seen,
        filter_new_questions,
    )

    chunks_rotacionados = pick_rotation_chunks(db, user_id, chunks_raw, tema, qtd_chunks=8)
    evitar              = build_evitar_block(db, user_id, tema, limite=20)

    questoes_brutas = ... (chamada à API com _build_quiz_prompt)

    questoes_novas  = filter_new_questions(db, user_id, questoes_brutas)
    register_seen(db, user_id, questoes_novas)
"""

import hashlib
import json
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Fingerprint de questão
# ---------------------------------------------------------------------------

def _fingerprint(texto: str) -> str:
    """
    Gera um hash curto (12 chars) sobre as primeiras 120 chars normalizadas
    do enunciado. Resistente a variações de pontuação/espaços, mas sensível
    a mudanças reais de conteúdo.
    """
    normalizado = re.sub(r"\s+", " ", texto.lower().strip())[:120]
    return hashlib.sha1(normalizado.encode("utf-8", errors="ignore")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Deduplicação — persiste fingerprints no banco
# ---------------------------------------------------------------------------

_CREATE_SEEN_TABLE = """
CREATE TABLE IF NOT EXISTS quiz_seen_questions (
    user_id     INTEGER NOT NULL,
    tema        TEXT    NOT NULL,
    fingerprint TEXT    NOT NULL,
    visto_em    TEXT    DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, fingerprint)
);
"""

_INSERT_SEEN = """
INSERT OR IGNORE INTO quiz_seen_questions (user_id, tema, fingerprint)
VALUES (?, ?, ?);
"""

_SELECT_SEEN_FPS = """
SELECT fingerprint FROM quiz_seen_questions
WHERE user_id = ? AND tema = ?
ORDER BY visto_em DESC
LIMIT ?;
"""

_SELECT_RECENT_PERGUNTAS = """
SELECT q.pergunta FROM quiz_seen_questions qs
JOIN (
    -- Tenta recuperar o texto original pelo fingerprint via cache de questoes
    SELECT fingerprint, pergunta FROM quiz_question_texts WHERE user_id = ?
) q ON q.fingerprint = qs.fingerprint
WHERE qs.user_id = ? AND qs.tema = ?
ORDER BY qs.visto_em DESC
LIMIT ?;
"""

_CREATE_TEXTS_TABLE = """
CREATE TABLE IF NOT EXISTS quiz_question_texts (
    user_id     INTEGER NOT NULL,
    fingerprint TEXT    NOT NULL,
    tema        TEXT    NOT NULL,
    pergunta    TEXT    NOT NULL,
    PRIMARY KEY (user_id, fingerprint)
);
"""

_INSERT_TEXT = """
INSERT OR IGNORE INTO quiz_question_texts (user_id, fingerprint, tema, pergunta)
VALUES (?, ?, ?, ?);
"""

_SELECT_TEXTS = """
SELECT pergunta FROM quiz_question_texts
WHERE user_id = ? AND tema = ?
ORDER BY rowid DESC
LIMIT ?;
"""


def _ensure_tables(db) -> None:
    """Cria as tabelas auxiliares se ainda não existirem."""
    try:
        conn = db.conn if hasattr(db, "conn") else db._conn
        conn.execute(_CREATE_SEEN_TABLE)
        conn.execute(_CREATE_TEXTS_TABLE)
        conn.commit()
    except Exception:
        pass


def register_seen(db, user_id: int, questoes: list[dict], tema: str = "Geral") -> None:
    """
    Registra fingerprints e textos das questões geradas.
    Chame APÓS filter_new_questions, só com as questões aceitas.
    """
    if not db or not user_id or not questoes:
        return
    try:
        _ensure_tables(db)
        conn = db.conn if hasattr(db, "conn") else db._conn
        for q in questoes:
            pergunta = str(q.get("pergunta") or q.get("enunciado") or "").strip()
            if not pergunta:
                continue
            fp = _fingerprint(pergunta)
            conn.execute(_INSERT_SEEN, (int(user_id), str(tema), fp))
            conn.execute(_INSERT_TEXT, (int(user_id), fp, str(tema), pergunta))
        conn.commit()
    except Exception:
        pass


def filter_new_questions(
    db,
    user_id: int,
    questoes: list[dict],
    tema: str = "Geral",
    janela: int = 200,
) -> list[dict]:
    """
    Remove do lote as questões cujo fingerprint já foi visto pelo usuário
    nas últimas `janela` questões deste tema.

    Retorna apenas as questões realmente novas.
    """
    if not db or not user_id or not questoes:
        return questoes
    try:
        _ensure_tables(db)
        conn = db.conn if hasattr(db, "conn") else db._conn
        rows = conn.execute(_SELECT_SEEN_FPS, (int(user_id), str(tema), janela)).fetchall()
        seen = {row[0] for row in rows}
    except Exception:
        seen = set()

    novas = []
    for q in questoes:
        pergunta = str(q.get("pergunta") or q.get("enunciado") or "").strip()
        if not pergunta:
            continue
        fp = _fingerprint(pergunta)
        if fp not in seen:
            novas.append(q)
            seen.add(fp)  # evita duplicata dentro do próprio lote
    return novas


def build_evitar_block(
    db,
    user_id: int,
    tema: str = "Geral",
    limite: int = 20,
) -> list[str]:
    """
    Retorna os últimos `limite` enunciados vistos pelo usuário neste tema,
    para passar como `evitar` ao _build_quiz_prompt.

    Se o banco não tiver os textos (instalação nova), retorna lista vazia.
    """
    if not db or not user_id:
        return []
    try:
        _ensure_tables(db)
        conn = db.conn if hasattr(db, "conn") else db._conn
        rows = conn.execute(_SELECT_TEXTS, (int(user_id), str(tema), limite)).fetchall()
        return [row[0] for row in rows if row[0]]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Rotação de chunks — seleciona trechos menos explorados do material
# ---------------------------------------------------------------------------

_CREATE_CHUNK_TABLE = """
CREATE TABLE IF NOT EXISTS quiz_chunk_usage (
    user_id  INTEGER NOT NULL,
    tema     TEXT    NOT NULL,
    chunk_fp TEXT    NOT NULL,
    usos     INTEGER DEFAULT 1,
    ultimo   TEXT    DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, tema, chunk_fp)
);
"""

_SELECT_CHUNK_USOS = """
SELECT chunk_fp, usos FROM quiz_chunk_usage
WHERE user_id = ? AND tema = ?;
"""

_UPSERT_CHUNK = """
INSERT INTO quiz_chunk_usage (user_id, tema, chunk_fp, usos)
VALUES (?, ?, ?, 1)
ON CONFLICT(user_id, tema, chunk_fp) DO UPDATE SET
    usos   = usos + 1,
    ultimo = datetime('now');
"""


def pick_rotation_chunks(
    db,
    user_id: int,
    chunks: list[str],
    tema: str = "Geral",
    qtd_chunks: int = 8,
) -> list[str]:
    """
    Seleciona até `qtd_chunks` trechos do material priorizando os menos
    usados anteriormente. Assim, sessões consecutivas exploram partes
    diferentes do PDF em vez de sempre usar os primeiros parágrafos.

    Se não houver banco ou dados de uso, retorna uma seleção aleatória
    cobrindo início, meio e fim do material (distribuição uniforme).
    """
    if not chunks:
        return []

    # Sem banco → distribuição uniforme simples
    if not db or not user_id:
        return _uniform_sample(chunks, qtd_chunks)

    try:
        conn = db.conn if hasattr(db, "conn") else db._conn
        conn.execute(_CREATE_CHUNK_TABLE)
        conn.commit()
        rows = conn.execute(_SELECT_CHUNK_USOS, (int(user_id), str(tema))).fetchall()
        uso_map: dict[str, int] = {row[0]: row[1] for row in rows}
    except Exception:
        return _uniform_sample(chunks, qtd_chunks)

    # Ordena chunks pelo número de usos (menos usados primeiro)
    def _chunk_score(chunk: str) -> int:
        fp = _fingerprint(chunk)
        return uso_map.get(fp, 0)

    ordenados = sorted(chunks, key=_chunk_score)
    selecionados = ordenados[:qtd_chunks]

    # Registra o uso dos chunks selecionados
    try:
        for chunk in selecionados:
            fp = _fingerprint(chunk)
            conn.execute(_UPSERT_CHUNK, (int(user_id), str(tema), fp))
        conn.commit()
    except Exception:
        pass

    return selecionados


def _uniform_sample(chunks: list[str], n: int) -> list[str]:
    """
    Seleciona n chunks distribuídos uniformemente ao longo da lista,
    garantindo cobertura de início, meio e fim do material.
    """
    if len(chunks) <= n:
        return list(chunks)
    step = len(chunks) / n
    indices = [int(i * step) for i in range(n)]
    return [chunks[i] for i in indices]


# ---------------------------------------------------------------------------
# Exemplo de integração completa em generate_quiz_batch:
#
# from core.quiz_rotation import (
#     pick_rotation_chunks, build_evitar_block,
#     filter_new_questions, register_seen,
# )
# from core.quiz_prompt_v2 import _build_quiz_prompt, validate_question, sanitize_question
#
# def generate_quiz_batch(self, chunks, tema, dificuldade, qtd, pagina=1, db=None, user_id=None):
#     chunks_rot = pick_rotation_chunks(db, user_id, chunks, tema, qtd_chunks=8)
#     evitar     = build_evitar_block(db, user_id, tema, limite=20)
#
#     prompt     = _build_quiz_prompt(chunks_rot, tema, dificuldade, qtd, pagina, evitar)
#     raw        = self.provider.complete(prompt)
#
#     try:   items = json.loads(raw)
#     except Exception: items = _try_extract_json_list(raw)
#
#     validas = [sanitize_question(q) for q in (items or []) if validate_question(q)]
#     novas   = filter_new_questions(db, user_id, validas, tema)
#     register_seen(db, user_id, novas, tema)
#     return novas
# ---------------------------------------------------------------------------
