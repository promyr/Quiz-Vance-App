# -*- coding: utf-8 -*-
"""
StatsRepository — Progresso diário, resumo de estatísticas, ranking e sync de stats.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from core.database_v2 import Database


class StatsRepository:
    """Gerencia estatísticas de estudo: progresso diário, streak, XP e sync cloud."""

    def __init__(self, db: "Database") -> None:
        self._db = db

    def _conectar(self) -> sqlite3.Connection:
        return self._db.conectar()

    # ------------------------------------------------------------------
    # Streak
    # ------------------------------------------------------------------

    def _calcular_streak(self, cursor: sqlite3.Cursor, user_id: int) -> int:
        cursor.execute(
            "SELECT streak_dias, ultima_atividade FROM usuarios WHERE id = ?", (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return 1
        streak_atual = int(row[0] or 0)
        ultima = row[1]
        hoje = datetime.date.today()
        if not ultima:
            return max(1, streak_atual)
        try:
            ultima_data = datetime.datetime.strptime(str(ultima), "%Y-%m-%d").date()
        except ValueError:
            return max(1, streak_atual)
        if ultima_data == hoje:
            return max(1, streak_atual)
        if ultima_data == (hoje - datetime.timedelta(days=1)):
            return max(1, streak_atual + 1)
        return 1

    # ------------------------------------------------------------------
    # Progresso diário
    # ------------------------------------------------------------------

    def _registrar_progresso_diario_cursor(
        self,
        cursor: sqlite3.Cursor,
        user_id: int,
        questoes: int = 0,
        acertos: int = 0,
        flashcards: int = 0,
        discursivas: int = 0,
        tempo_segundos: int = 0,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO estudo_progresso_diario
                (user_id, dia, questoes_respondidas, acertos, flashcards_revisados,
                 discursivas_corrigidas, tempo_segundos, updated_at)
            VALUES (?, DATE('now','localtime'), ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, dia) DO UPDATE SET
                questoes_respondidas = estudo_progresso_diario.questoes_respondidas + excluded.questoes_respondidas,
                acertos = estudo_progresso_diario.acertos + excluded.acertos,
                flashcards_revisados = estudo_progresso_diario.flashcards_revisados + excluded.flashcards_revisados,
                discursivas_corrigidas = estudo_progresso_diario.discursivas_corrigidas + excluded.discursivas_corrigidas,
                tempo_segundos = estudo_progresso_diario.tempo_segundos + excluded.tempo_segundos,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                max(0, int(questoes or 0)),
                max(0, int(acertos or 0)),
                max(0, int(flashcards or 0)),
                max(0, int(discursivas or 0)),
                max(0, int(tempo_segundos or 0)),
            ),
        )

    def registrar_progresso_diario(
        self,
        user_id: int,
        questoes: int = 0,
        acertos: int = 0,
        flashcards: int = 0,
        discursivas: int = 0,
        tempo_segundos: int = 0,
    ) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        self._registrar_progresso_diario_cursor(
            cursor, user_id,
            questoes=questoes, acertos=acertos,
            flashcards=flashcards, discursivas=discursivas,
            tempo_segundos=tempo_segundos,
        )
        novo_streak = self._calcular_streak(cursor, user_id)
        cursor.execute(
            "UPDATE usuarios SET streak_dias = ?, ultima_atividade = DATE('now','localtime') WHERE id = ?",
            (novo_streak, user_id),
        )
        conn.commit()
        conn.close()

    def obter_progresso_diario(self, user_id: int) -> Dict:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT meta_questoes_diaria, streak_dias FROM usuarios WHERE id = ?", (user_id,)
        )
        user_row = cursor.fetchone()
        meta = int((user_row["meta_questoes_diaria"] if user_row else 20) or 20)
        streak = int((user_row["streak_dias"] if user_row else 0) or 0)
        cursor.execute(
            """
            SELECT questoes_respondidas, acertos, flashcards_revisados, discursivas_corrigidas, tempo_segundos
            FROM estudo_progresso_diario
            WHERE user_id = ? AND dia = DATE('now','localtime')
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        feitos = int((row["questoes_respondidas"] if row else 0) or 0)
        acertos = int((row["acertos"] if row else 0) or 0)
        return {
            "meta_questoes": max(5, meta),
            "questoes_respondidas": feitos,
            "acertos": acertos,
            "pct_acerto_7d": 0.0,
            "pct_acerto_30d": 0.0,
            "progresso_meta": min(1.0, feitos / max(1, meta)),
            "streak_dias": streak,
        }

    # ------------------------------------------------------------------
    # Gamificação & XP
    # ------------------------------------------------------------------

    def registrar_ganho_xp(self, user_id: int, xp: int, motivo: str = "") -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO historico_xp (user_id, xp_ganho, motivo) VALUES (?, ?, ?)",
            (user_id, xp, motivo),
        )
        cursor.execute(
            "UPDATE usuarios SET xp = xp + ?, ultima_atividade = DATE('now','localtime') WHERE id = ?",
            (xp, user_id),
        )
        conn.commit()
        conn.close()

    def registrar_resultado_quiz(self, user_id: int, acertos: int, total: int, xp: int) -> None:
        """Atualiza estatísticas de quiz e XP (chamado ao final de um quiz/simulado)."""
        conn = self._conectar()
        cursor = conn.cursor()
        novo_streak = self._calcular_streak(cursor, user_id)
        cursor.execute(
            """
            UPDATE usuarios
            SET xp = xp + ?, acertos = acertos + ?, total_questoes = total_questoes + ?,
                streak_dias = ?, ultima_atividade = DATE('now','localtime')
            WHERE id = ?
            """,
            (xp, acertos, total, novo_streak, user_id),
        )
        cursor.execute(
            "INSERT INTO historico_xp (user_id, xp_ganho, motivo) VALUES (?, ?, ?)",
            (user_id, xp, f"Quiz {acertos}/{total}"),
        )
        self._registrar_progresso_diario_cursor(
            cursor, user_id,
            questoes=max(0, int(total or 0)),
            acertos=max(0, int(acertos or 0)),
        )
        conn.commit()
        conn.close()

    def registrar_resposta_quiz_tempo_real(
        self, user_id: int, correta: bool, xp_por_acerto: int = 10
    ) -> Dict:
        """Persistência incremental por resposta confirmada em modo treino."""
        conn = self._conectar()
        cursor = conn.cursor()
        acertos_delta = 1 if bool(correta) else 0
        xp_delta = int(max(0, xp_por_acerto)) if acertos_delta else 0
        novo_streak = self._calcular_streak(cursor, int(user_id))
        cursor.execute(
            """
            UPDATE usuarios
            SET xp = xp + ?, acertos = acertos + ?, total_questoes = total_questoes + 1,
                streak_dias = ?, ultima_atividade = DATE('now','localtime')
            WHERE id = ?
            """,
            (xp_delta, acertos_delta, novo_streak, int(user_id)),
        )
        if xp_delta > 0:
            cursor.execute(
                "INSERT INTO historico_xp (user_id, xp_ganho, motivo) VALUES (?, ?, ?)",
                (int(user_id), xp_delta, "Quiz tempo real"),
            )
        self._registrar_progresso_diario_cursor(
            cursor, int(user_id), questoes=1, acertos=acertos_delta,
        )
        conn.commit()
        conn.close()
        return {
            "xp_ganho": xp_delta,
            "acertos_delta": acertos_delta,
            "questoes_delta": 1,
            "streak_dias": int(novo_streak),
        }

    # ------------------------------------------------------------------
    # Sync cloud
    # ------------------------------------------------------------------

    def sync_cloud_quiz_totals(
        self,
        user_id: int,
        total_questoes: int,
        total_acertos: int,
        total_xp: Optional[int] = None,
        today_questoes: Optional[int] = None,
        today_acertos: Optional[int] = None,
    ) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT xp, acertos, total_questoes FROM usuarios WHERE id = ?", (int(user_id),)
            )
            row = cursor.fetchone()
            if not row:
                return
            xp_local = int(row[0] or 0)
            acertos_local = int(row[1] or 0)
            total_local = int(row[2] or 0)
            xp_cloud = int(total_xp or 0) if total_xp is not None else xp_local
            cursor.execute(
                "UPDATE usuarios SET xp = ?, acertos = ?, total_questoes = ? WHERE id = ?",
                (
                    max(0, max(xp_local, xp_cloud)),
                    max(0, max(acertos_local, int(total_acertos or 0))),
                    max(0, max(total_local, int(total_questoes or 0))),
                    int(user_id),
                ),
            )
            if today_questoes is not None or today_acertos is not None:
                cloud_q = max(0, int(today_questoes or 0))
                cloud_a = min(cloud_q, max(0, int(today_acertos or 0)))
                cursor.execute(
                    "SELECT questoes_respondidas, acertos FROM estudo_progresso_diario WHERE user_id = ? AND dia = DATE('now','localtime')",
                    (int(user_id),),
                )
                daily_row = cursor.fetchone()
                if daily_row:
                    local_q = int(daily_row[0] or 0)
                    local_a = int(daily_row[1] or 0)
                    merged_q = max(local_q, cloud_q)
                    merged_a = min(merged_q, max(local_a, cloud_a))
                    cursor.execute(
                        "UPDATE estudo_progresso_diario SET questoes_respondidas = ?, acertos = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND dia = DATE('now','localtime')",
                        (merged_q, merged_a, int(user_id)),
                    )
                elif cloud_q > 0 or cloud_a > 0:
                    cursor.execute(
                        "INSERT INTO estudo_progresso_diario (user_id, dia, questoes_respondidas, acertos, flashcards_revisados, discursivas_corrigidas, tempo_segundos, updated_at) VALUES (?, DATE('now','localtime'), ?, ?, 0, 0, 0, CURRENT_TIMESTAMP)",
                        (int(user_id), cloud_q, min(cloud_q, cloud_a)),
                    )
            conn.commit()
        finally:
            conn.close()

    def enqueue_quiz_stats_event(self, user_id: int, event_id: str, payload: Dict[str, Any]) -> bool:
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO stats_sync_queue (user_id, event_id, payload_json) VALUES (?, ?, ?)",
                (int(user_id), str(event_id or "").strip(), json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()
            return bool(cursor.rowcount)
        finally:
            conn.close()

    def list_pending_quiz_stats_events(self, user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        conn = self._conectar()
        cursor = conn.cursor()
        lim = max(1, min(int(limit or 200), 1000))
        try:
            cursor.execute(
                "SELECT id, event_id, payload_json FROM stats_sync_queue WHERE user_id = ? ORDER BY id ASC LIMIT ?",
                (int(user_id), lim),
            )
            out: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                try:
                    payload = json.loads(str(row[2] or "{}"))
                except Exception:
                    payload = {}
                out.append({"id": int(row[0]), "event_id": str(row[1] or ""), "event": payload})
            return out
        finally:
            conn.close()

    def delete_pending_quiz_stats_events(self, ids: List[int]) -> int:
        ids_norm = [int(i) for i in (ids or []) if int(i or 0) > 0]
        if not ids_norm:
            return 0
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            placeholders = ",".join("?" for _ in ids_norm)
            cursor.execute(f"DELETE FROM stats_sync_queue WHERE id IN ({placeholders})", tuple(ids_norm))
            deleted = int(cursor.rowcount or 0)
            conn.commit()
            return deleted
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Resumo e ranking
    # ------------------------------------------------------------------

    def obter_resumo_estatisticas(self, user_id: int) -> Dict:
        """Retorna resumo consolidado para Home/Estatísticas."""
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT xp, nivel, acertos, total_questoes, streak_dias, meta_questoes_diaria FROM usuarios WHERE id = ? LIMIT 1",
                (int(user_id),),
            )
            row = cursor.fetchone()
        finally:
            conn.close()
        progresso = self.obter_progresso_diario(int(user_id))
        revisoes = self._db.revisoes_pendentes(int(user_id))
        xp = int((row["xp"] if row else 0) or 0)
        nivel = str((row["nivel"] if row else "Bronze") or "Bronze")
        acertos_total = int((row["acertos"] if row else 0) or 0)
        total_questoes = int((row["total_questoes"] if row else 0) or 0)
        streak = int((row["streak_dias"] if row else 0) or 0)
        meta = int((row["meta_questoes_diaria"] if row else 20) or 20)
        taxa_total = (acertos_total / total_questoes * 100.0) if total_questoes > 0 else 0.0
        return {
            "xp": xp,
            "nivel": nivel,
            "acertos_total": acertos_total,
            "total_questoes": total_questoes,
            "taxa_total": taxa_total,
            "streak_dias": streak,
            "meta_questoes": max(5, meta),
            "progresso_diario": progresso,
            "revisoes_pendentes": int(revisoes or 0),
        }

    def obter_dados_grafico(self, user_id: int, dias: int = 7) -> Tuple[List[Dict], int]:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DATE(data_hora) as dia, SUM(xp_ganho) as xp
            FROM historico_xp
            WHERE user_id = ? AND data_hora >= DATE('now','localtime', '-' || ? || ' days')
            GROUP BY DATE(data_hora)
            ORDER BY dia ASC
            """,
            (user_id, dias),
        )
        resultados = cursor.fetchall()
        conn.close()
        data_dict = {r[0]: r[1] for r in resultados}
        hoje = datetime.date.today()
        dados: List[Dict] = []
        total_xp = 0
        for i in range(dias - 1, -1, -1):
            dia = (hoje - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            xp = data_dict.get(dia, 0)
            total_xp += xp
            if dias <= 7:
                label = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][
                    datetime.datetime.strptime(dia, "%Y-%m-%d").weekday()
                ]
            else:
                label = f"{dia.split('-')[2]}/{dia.split('-')[1]}"
            dados.append({"dia": label, "xp": xp})
        return dados, total_xp

    def obter_ranking(self, periodo: str = "Geral") -> List[Dict]:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if periodo == "Hoje":
            cursor.execute(
                """
                SELECT u.nome, u.avatar, u.nivel, u.xp, u.acertos, u.total_questoes,
                    COALESCE((SELECT SUM(epd.tempo_segundos) FROM estudo_progresso_diario epd
                              WHERE epd.user_id = u.id AND epd.dia = DATE('now','localtime')), 0) AS segundos_estudo
                FROM usuarios u
                WHERE u.ultima_atividade = DATE('now','localtime')
                ORDER BY u.xp DESC LIMIT 50
                """
            )
        else:
            cursor.execute(
                """
                SELECT u.nome, u.avatar, u.nivel, u.xp, u.acertos, u.total_questoes,
                    COALESCE((SELECT SUM(epd.tempo_segundos) FROM estudo_progresso_diario epd
                              WHERE epd.user_id = u.id), 0) AS segundos_estudo
                FROM usuarios u ORDER BY u.xp DESC LIMIT 50
                """
            )
        rows = cursor.fetchall()
        conn.close()
        ranking: List[Dict] = []
        for row in rows:
            ud = dict(row)
            total = int(ud.get("total_questoes") or 0)
            acertos = int(ud.get("acertos") or 0)
            segundos = int(ud.pop("segundos_estudo", 0) or 0)
            ud["taxa_acerto"] = (acertos / total * 100) if total else 0
            ud["horas_estudo"] = round(segundos / 3600.0, 2)
            ud["pontuacao"] = int(ud.get("xp") or 0)
            ranking.append(ud)
        return ranking
