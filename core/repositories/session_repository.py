# -*- coding: utf-8 -*-
"""Repositório de sessões — review sessions e mock exam sessions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.database_v2 import Database


class SessionRepository:
    """Agrupa operações de sessões de revisão e simulados."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    # --- Review Sessions ---

    def iniciar_review_session(self, user_id: int, session_type: str, total_items: int) -> int:
        return self.db.iniciar_review_session(user_id, session_type, total_items)

    def registrar_review_session_item(self, session_id: int, item_id: int, acertou: bool,
                                      tempo_ms: int = 0, pulou: bool = False) -> None:
        self.db.registrar_review_session_item(session_id, item_id, acertou, tempo_ms, pulou)

    def finalizar_review_session(self, session_id: int, acertos: int, erros: int,
                                  puladas: int, total_time_ms: int) -> None:
        self.db.finalizar_review_session(session_id, acertos, erros, puladas, total_time_ms)

    # --- Mock Exam Sessions (Simulados) ---

    def criar_mock_exam_session(self, user_id: int, titulo: str, total_questoes: int,
                                 tempo_limite_min: int = 0, filtros: Optional[Dict] = None) -> int:
        return self.db.criar_mock_exam_session(user_id, titulo, total_questoes, tempo_limite_min, filtros)

    def registrar_mock_exam_item(self, session_id: int, questao_idx: int,
                                   questao: Dict, resposta_idx: Optional[int] = None,
                                   correta: Optional[bool] = None, tempo_ms: int = 0) -> None:
        self.db.registrar_mock_exam_item(session_id, questao_idx, questao, resposta_idx, correta, tempo_ms)

    def salvar_mock_exam_progresso(self, session_id: int, current_idx: int,
                                    respostas: Dict[int, Optional[int]]) -> None:
        self.db.salvar_mock_exam_progresso(session_id, current_idx, respostas)

    def finalizar_mock_exam_session(self, session_id: int, acertos: int, total: int,
                                     tempo_total_ms: int = 0, respostas: Optional[Dict] = None) -> None:
        self.db.finalizar_mock_exam_session(session_id, acertos, total, tempo_total_ms, respostas)

    def contar_simulados_hoje(self, user_id: int) -> int:
        return self.db.contar_simulados_hoje(user_id)

    def listar_historico_simulados(self, user_id: int, limite: int = 20) -> List[Dict]:
        return self.db.listar_historico_simulados(user_id, limite)
