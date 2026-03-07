# -*- coding: utf-8 -*-
"""Repositório de quiz — cache de questões, questões do usuário, filtros salvos."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.database_v2 import Database


class QuizRepository:
    """Agrupa operações de quiz: cache, questões do usuário e filtros."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    # --- Cache de questões ---

    def salvar_questao_cache(self, tema: str, dificuldade: str, questao: Dict) -> None:
        self.db.salvar_questao_cache(tema, dificuldade, questao)

    def listar_questoes_cache(self, tema: str, dificuldade: str, limite: int = 10) -> List[Dict]:
        return self.db.listar_questoes_cache(tema, dificuldade, limite)

    # --- Questões do usuário ---

    def registrar_questao_usuario(self, user_id: int, question: Dict, tema: str = "Geral", dificuldade: str = "intermediario", tentativa_correta: Optional[bool] = None, favorita: Optional[bool] = None, marcado_erro: Optional[bool] = None) -> None:
        self.db.registrar_questao_usuario(user_id, question, tema, dificuldade, tentativa_correta, favorita, marcado_erro)

    def listar_questoes_usuario(self, user_id: int, modo: str = "all", limite: int = 20) -> List[Dict]:
        return self.db.listar_questoes_usuario(user_id, modo, limite)

    # --- Filtros ---

    def salvar_filtro_quiz(self, user_id: int, nome: str, filtro: Dict) -> None:
        self.db.salvar_filtro_quiz(user_id, nome, filtro)

    def listar_filtros_quiz(self, user_id: int) -> List[Dict]:
        return self.db.listar_filtros_quiz(user_id)

    def excluir_filtro_quiz(self, filtro_id: int, user_id: int) -> None:
        self.db.excluir_filtro_quiz(filtro_id, user_id)

    def renomear_filtro_quiz(self, filtro_id: int, user_id: int, novo_nome: str) -> None:
        self.db.renomear_filtro_quiz(filtro_id, user_id, novo_nome)

    # --- Revisão ---

    def topicos_revisao(self, user_id: int, limite: int = 3) -> List:
        return self.db.topicos_revisao(user_id, limite)

    def revisoes_pendentes(self, user_id: int) -> Dict:
        return self.db.revisoes_pendentes(user_id)

    def sugerir_estudo_agora(self, user_id: int) -> Dict:
        return self.db.sugerir_estudo_agora(user_id)

    def contadores_revisao(self, user_id: int) -> Dict:
        return self.db.contadores_revisao(user_id)
