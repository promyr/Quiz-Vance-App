# -*- coding: utf-8 -*-
"""Orquestração de sessão de revisão."""

from __future__ import annotations

from typing import Optional

from core.repositories.review_session_repository import ReviewSessionRepository


class ReviewSessionService:
    def __init__(self, repo: ReviewSessionRepository):
        self.repo = repo

    def start(self, user_id: int, session_type: str, total_items: int) -> int:
        return self.repo.start(int(user_id), str(session_type or "daily"), int(max(0, total_items)))

    def record(
        self,
        session_id: int,
        item_type: str,
        item_ref: str,
        resultado: str,
        is_correct: Optional[bool],
        response_time_ms: int = 0,
    ) -> None:
        self.repo.add_item(
            int(session_id),
            item_type=str(item_type or "question"),
            item_ref=str(item_ref or ""),
            resultado=str(resultado or ""),
            is_correct=is_correct,
            response_time_ms=int(max(0, response_time_ms)),
        )

    def finish(self, session_id: int, acertos: int, erros: int, puladas: int, total_time_ms: int) -> None:
        self.repo.finish(
            int(session_id),
            acertos=int(max(0, acertos)),
            erros=int(max(0, erros)),
            puladas=int(max(0, puladas)),
            total_time_ms=int(max(0, total_time_ms)),
        )

