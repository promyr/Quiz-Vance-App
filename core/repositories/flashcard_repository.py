# -*- coding: utf-8 -*-
"""Repository de flashcards para revisão inteligente."""

from __future__ import annotations

import datetime
import json
from typing import Dict, List, Optional


class FlashcardRepository:
    _INTERVALS_DAYS = [1, 2, 4, 7, 14, 30, 60, 120, 180]

    def __init__(self, db):
        self.db = db

    def list_due(self, user_id: int, limit: int = 120) -> List[Dict]:
        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT frente, verso, tema, dificuldade, revisao_nivel, proxima_revisao
                FROM flashcards
                WHERE user_id = ?
                  AND proxima_revisao IS NOT NULL
                  AND DATETIME(proxima_revisao) <= DATETIME('now')
                ORDER BY DATETIME(proxima_revisao) ASC
                LIMIT ?
                """,
                (int(user_id), int(max(1, limit))),
            )
            rows = cur.fetchall()
            out = []
            for row in rows:
                out.append(
                    {
                        "frente": str(row["frente"] or ""),
                        "verso": str(row["verso"] or ""),
                        "tema": str(row["tema"] or "Geral"),
                        "dificuldade": str(row["dificuldade"] or "intermediario"),
                        "_srs": {
                            "nivel": int(row["revisao_nivel"] or 0),
                            "proxima_revisao": row["proxima_revisao"],
                        },
                    }
                )
            return out
        finally:
            conn.close()

    def _next_schedule_expr(self, action: str, current_level: int) -> tuple[int, str]:
        action_norm = str(action or "").strip().lower()
        level = int(max(0, current_level or 0))
        if action_norm in {"lembrei", "remembered", "correct"}:
            level = min(len(self._INTERVALS_DAYS) - 1, level + 1)
            days = self._INTERVALS_DAYS[level]
            return level, f"DATETIME('now', '+{days} days')"
        if action_norm in {"rever", "again", "wrong"}:
            level = max(0, level - 1)
            return level, "DATETIME('now', '+1 day')"
        # pular/skip
        return level, "DATETIME('now', '+12 hours')"

    def register_action(self, user_id: int, card: Dict, action: str) -> None:
        frente = str(card.get("frente") or "").strip()
        verso = str(card.get("verso") or "").strip()
        tema = str(card.get("tema") or "Geral").strip() or "Geral"
        dificuldade = str(card.get("dificuldade") or "intermediario").strip() or "intermediario"
        if not frente or not verso:
            return

        # garante existência
        self.db.salvar_flashcards_gerados(int(user_id), tema, [{"frente": frente, "verso": verso}], dificuldade)
        card_hash = self.db._flashcard_hash({"frente": frente, "verso": verso, "tema": tema})

        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, revisao_nivel, total_revisoes, total_acertos, total_erros
                FROM flashcards
                WHERE user_id = ? AND card_hash = ?
                LIMIT 1
                """,
                (int(user_id), str(card_hash)),
            )
            row = cur.fetchone()
            if not row:
                return

            current_level = int(row["revisao_nivel"] or 0)
            next_level, next_expr = self._next_schedule_expr(action, current_level)
            total_rev = int(row["total_revisoes"] or 0) + 1
            total_hits = int(row["total_acertos"] or 0) + (1 if str(action).lower() in {"lembrei", "remembered", "correct"} else 0)
            total_miss = int(row["total_erros"] or 0) + (1 if str(action).lower() in {"rever", "again", "wrong"} else 0)

            cur.execute(
                f"""
                UPDATE flashcards
                SET revisao_nivel = ?,
                    proxima_revisao = {next_expr},
                    ultima_revisao_em = CURRENT_TIMESTAMP,
                    total_revisoes = ?,
                    total_acertos = ?,
                    total_erros = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(next_level), int(total_rev), int(total_hits), int(total_miss), int(row["id"])),
            )
            conn.commit()
        finally:
            conn.close()

