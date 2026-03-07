# -*- coding: utf-8 -*-
"""Repositório de planos e assinaturas — premium, trial, limites diários."""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.database_v2 import Database


class PlanRepository:
    """Agrupa operações de assinatura, plano premium e limites de uso."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    def sync_subscription_status(self, user_id: int, plan_code: str, premium_until: Optional[str], trial_used: int) -> None:
        self.db.sync_subscription_status(user_id, plan_code, premium_until, trial_used)

    def get_subscription_status(self, user_id: int) -> Dict:
        return self.db.get_subscription_status(user_id)

    def ativar_plano_premium(self, user_id: int, plano: str) -> None:
        self.db.ativar_plano_premium(user_id, plano)

    def consumir_limite_diario(self, user_id: int, feature_key: str, limite: int) -> Dict:
        return self.db.consumir_limite_diario(user_id, feature_key, limite)

    def obter_uso_diario(self, user_id: int, feature_key: str) -> Dict:
        return self.db.obter_uso_diario(user_id, feature_key)
