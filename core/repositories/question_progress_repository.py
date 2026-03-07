# -*- coding: utf-8 -*-
"""Repository de progresso de questões para fila de revisão."""

from __future__ import annotations

import json
from typing import Dict, List


class QuestionProgressRepository:
    _INTERVALS_DAYS = [1, 2, 4, 7, 14, 30]

    def __init__(self, db):
        self.db = db

    def _row_to_question(self, row) -> Dict:
        try:
            question = json.loads(row["dados_json"] or "{}")
        except Exception:
            question = {}
        meta = question.setdefault("_srs", {})
        meta["nivel"] = int(row["review_level"] or 0)
        meta["tema"] = str(row["tema"] or "Geral")
        meta["marcado_erro"] = bool(row["marcado_erro"] or 0)
        meta["next_review_at"] = row["next_review_at"]
        return question

    def list_due(self, user_id: int, limit: int = 120) -> List[Dict]:
        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dados_json, tema, review_level, marcado_erro, next_review_at
                FROM questoes_usuario
                WHERE user_id = ?
                  AND next_review_at IS NOT NULL
                  AND DATETIME(next_review_at) <= DATETIME('now')
                ORDER BY DATETIME(next_review_at) ASC, ultima_pratica DESC
                LIMIT ?
                """,
                (int(user_id), int(max(1, limit))),
            )
            return [self._row_to_question(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def list_errors(self, user_id: int, limit: int = 120) -> List[Dict]:
        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dados_json, tema, review_level, marcado_erro, next_review_at
                FROM questoes_usuario
                WHERE user_id = ?
                  AND (marcado_erro = 1 OR erros > acertos)
                ORDER BY ultima_pratica DESC
                LIMIT ?
                """,
                (int(user_id), int(max(1, limit))),
            )
            return [self._row_to_question(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def list_marked(self, user_id: int, limit: int = 120) -> List[Dict]:
        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dados_json, tema, review_level, marcado_erro, next_review_at
                FROM questoes_usuario
                WHERE user_id = ?
                  AND (marcado_erro = 1 OR marked_for_review = 1)
                ORDER BY ultima_pratica DESC
                LIMIT ?
                """,
                (int(user_id), int(max(1, limit))),
            )
            return [self._row_to_question(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def register_result(self, user_id: int, question: Dict, action: str) -> None:
        action_norm = str(action or "").strip().lower()
        qhash = self.db._question_hash(question)
        tema = str(question.get("tema") or question.get("_srs", {}).get("tema") or "Geral")
        dificuldade = str(question.get("dificuldade") or "intermediario")
        dados_json = json.dumps(question, ensure_ascii=False)

        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT tentativas, acertos, erros, review_level, marked_for_review, marcado_erro
                FROM questoes_usuario
                WHERE user_id = ? AND qhash = ?
                LIMIT 1
                """,
                (int(user_id), str(qhash)),
            )
            row = cur.fetchone()
            if row is None:
                # base inicial
                cur.execute(
                    """
                    INSERT INTO questoes_usuario
                    (user_id, qhash, dados_json, tema, dificuldade, tentativas, acertos, erros,
                     revisao_nivel, proxima_revisao, ultima_pratica, marked_for_review, next_review_at, review_level, last_attempt_at, last_result)
                    VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, NULL, CURRENT_TIMESTAMP, 0, NULL, 0, CURRENT_TIMESTAMP, NULL)
                    """,
                    (int(user_id), str(qhash), dados_json, tema, dificuldade),
                )
                tentativas = 0
                acertos = 0
                erros = 0
                level = 0
                marked = 0
                marcado_erro = 0
            else:
                tentativas = int(row["tentativas"] or 0)
                acertos = int(row["acertos"] or 0)
                erros = int(row["erros"] or 0)
                level = int(row["review_level"] or 0)
                marked = int(row["marked_for_review"] or 0)
                marcado_erro = int(row["marcado_erro"] or 0)

            next_expr = "NULL"
            if action_norm in {"correct", "acerto"}:
                tentativas += 1
                acertos += 1
                level = max(0, level - 1)
                marcado_erro = 0
                if level <= 0:
                    marked = 0
                    next_expr = "NULL"
                else:
                    days = self._INTERVALS_DAYS[min(level, len(self._INTERVALS_DAYS) - 1)]
                    marked = 1
                    next_expr = f"DATETIME('now', '+{days} days')"
            elif action_norm in {"wrong", "erro"}:
                tentativas += 1
                erros += 1
                level = min(len(self._INTERVALS_DAYS) - 1, level + 1)
                marked = 1
                marcado_erro = 1
                days = self._INTERVALS_DAYS[level]
                next_expr = f"DATETIME('now', '+{days} days')"
            elif action_norm in {"mark", "marcar"}:
                marked = 1
                marcado_erro = 1
                level = max(1, level)
                next_expr = "DATETIME('now')"
            else:
                # skip
                marked = 1
                days = self._INTERVALS_DAYS[min(max(level, 0), len(self._INTERVALS_DAYS) - 1)]
                next_expr = f"DATETIME('now', '+{max(1, int(days))} days')"

            cur.execute(
                f"""
                UPDATE questoes_usuario
                SET dados_json = ?,
                    tema = ?,
                    dificuldade = ?,
                    tentativas = ?,
                    acertos = ?,
                    erros = ?,
                    review_level = ?,
                    revisao_nivel = ?,
                    marked_for_review = ?,
                    marcado_erro = ?,
                    next_review_at = {next_expr},
                    proxima_revisao = {next_expr},
                    ultima_pratica = CURRENT_TIMESTAMP,
                    last_attempt_at = CURRENT_TIMESTAMP,
                    last_result = ?
                WHERE user_id = ? AND qhash = ?
                """,
                (
                    dados_json,
                    tema,
                    dificuldade,
                    int(tentativas),
                    int(acertos),
                    int(erros),
                    int(level),
                    int(level),
                    int(marked),
                    int(marcado_erro),
                    str(action_norm),
                    int(user_id),
                    str(qhash),
                ),
            )
            conn.commit()
        finally:
            conn.close()

