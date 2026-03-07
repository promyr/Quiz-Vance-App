# -*- coding: utf-8 -*-
"""Repositório de gamificação — XP, streak, progresso diário, estatísticas e ranking."""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.database_v2 import Database


class GamificationRepository:
    """Agrupa operações de XP, streak, progresso e ranking."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    # --- XP ---

    def registrar_ganho_xp(self, user_id: int, xp: int, motivo: str = "") -> None:
        self.db.registrar_ganho_xp(user_id, xp, motivo)

    def registrar_resultado_quiz(self, user_id: int, acertos: int, total: int, xp: int) -> None:
        self.db.registrar_resultado_quiz(user_id, acertos, total, xp)

    def registrar_resposta_quiz_tempo_real(self, user_id: int, correta: bool, xp_por_acerto: int = 10) -> Dict:
        return self.db.registrar_resposta_quiz_tempo_real(user_id, correta, xp_por_acerto)

    def sync_cloud_quiz_totals(self, user_id: int, total_questoes: int, total_acertos: int, total_xp: Optional[int] = None, today_questoes: Optional[int] = None, today_acertos: Optional[int] = None) -> None:
        self.db.sync_cloud_quiz_totals(user_id, total_questoes, total_acertos, total_xp, today_questoes, today_acertos)

    # --- Stats sync queue ---

    def enqueue_quiz_stats_event(self, user_id: int, event_id: str, payload: Dict) -> bool:
        return self.db.enqueue_quiz_stats_event(user_id, event_id, payload)

    def list_pending_quiz_stats_events(self, user_id: int, limit: int = 200) -> List[Dict]:
        return self.db.list_pending_quiz_stats_events(user_id, limit)

    def delete_pending_quiz_stats_events(self, ids: List[int]) -> int:
        return self.db.delete_pending_quiz_stats_events(ids)

    # --- Progresso diário ---

    def registrar_progresso_diario(self, user_id: int, questoes: int = 0, acertos: int = 0, flashcards: int = 0, discursivas: int = 0, tempo_segundos: int = 0) -> None:
        self.db.registrar_progresso_diario(user_id, questoes, acertos, flashcards, discursivas, tempo_segundos)

    def obter_progresso_diario(self, user_id: int) -> Dict:
        return self.db.obter_progresso_diario(user_id)

    # --- Estatísticas e ranking ---

    def obter_resumo_estatisticas(self, user_id: int) -> Dict:
        return self.db.obter_resumo_estatisticas(user_id)

    def obter_dados_grafico(self, user_id: int, dias: int = 7) -> List:
        return self.db.obter_dados_grafico(user_id, dias)

    def obter_ranking(self, periodo: str = "Geral") -> List:
        return self.db.obter_ranking(periodo)
