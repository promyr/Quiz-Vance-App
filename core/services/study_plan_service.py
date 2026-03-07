# -*- coding: utf-8 -*-
"""Serviço auxiliar para planejamento de estudos."""

from __future__ import annotations

from typing import Dict, List


class StudyPlanService:
    @staticmethod
    def choose_topics(seed_topics: List[str], db_topics: List[Dict], default_topic: str = "Geral") -> List[str]:
        topics = [str(t).strip() for t in (seed_topics or []) if str(t).strip()]
        if topics:
            return topics
        from_db = [str((row or {}).get("tema") or "").strip() for row in (db_topics or [])]
        topics = [t for t in from_db if t]
        return topics or [str(default_topic or "Geral")]

