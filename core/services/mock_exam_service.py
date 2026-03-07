# -*- coding: utf-8 -*-
"""Regra de dominio do modo prova/simulado (Prompt 6)."""

from __future__ import annotations

from typing import Tuple


class MockExamService:
    FEATURE_KEY = "mock_exam"
    FREE_DAILY_LIMIT = 1
    FREE_MAX_QUESTIONS = 20
    MAX_QUESTIONS = 120
    FREE_PRESET_COUNTS = [10, 20]
    PREMIUM_PRESET_COUNTS = [10, 20, 30, 50]

    def __init__(self, db):
        self.db = db

    @classmethod
    def plan_hint(cls, premium: bool) -> str:
        if premium:
            return "Plano Premium: simulados ilimitados."
        return "Plano Free: 1 simulado/dia e ate 20 questoes."

    @classmethod
    def preset_counts(cls, premium: bool):
        return list(cls.PREMIUM_PRESET_COUNTS if premium else cls.FREE_PRESET_COUNTS)

    @classmethod
    def normalize_question_count(cls, requested_count: int, premium: bool) -> Tuple[int, bool]:
        max_allowed = cls.MAX_QUESTIONS if premium else cls.FREE_MAX_QUESTIONS
        count = int(max(1, min(max_allowed, int(requested_count or 1))))
        capped = count != int(requested_count or 1)
        return count, capped

    def daily_used(self, user_id: int) -> int:
        if not self.db or not user_id:
            return 0
        try:
            return int(self.db.obter_uso_diario(int(user_id), self.FEATURE_KEY))
        except Exception:
            try:
                return int(self.db.contar_simulados_hoje(int(user_id)))
            except Exception:
                return 0

    def can_start_today(self, user_id: int, premium: bool) -> Tuple[bool, int, int]:
        if premium:
            return True, 0, 0
        used = self.daily_used(int(user_id))
        return used < self.FREE_DAILY_LIMIT, used, self.FREE_DAILY_LIMIT

    def consume_start_today(self, user_id: int, premium: bool) -> Tuple[bool, int, int]:
        if premium:
            return True, 0, 0
        if not self.db or not user_id:
            return False, 0, self.FREE_DAILY_LIMIT
        allowed, used_after = self.db.consumir_limite_diario(
            int(user_id),
            self.FEATURE_KEY,
            self.FREE_DAILY_LIMIT,
        )
        return bool(allowed), int(used_after), self.FREE_DAILY_LIMIT

