# -*- coding: utf-8 -*-
"""Repository para sessões de revisão."""

from __future__ import annotations

from typing import Optional


class ReviewSessionRepository:
    def __init__(self, db):
        self.db = db

    def start(self, user_id: int, session_type: str, total_items: int) -> int:
        return int(self.db.iniciar_review_session(int(user_id), str(session_type or "daily"), int(max(0, total_items))))

    def add_item(
        self,
        session_id: int,
        item_type: str,
        item_ref: str,
        resultado: str,
        is_correct: Optional[bool],
        response_time_ms: int = 0,
    ) -> None:
        self.db.registrar_review_session_item(
            int(session_id),
            item_type=str(item_type or "question"),
            item_ref=str(item_ref or ""),
            resultado=str(resultado or ""),
            is_correct=is_correct,
            response_time_ms=int(max(0, response_time_ms or 0)),
        )

    def finish(self, session_id: int, acertos: int, erros: int, puladas: int, total_time_ms: int) -> None:
        self.db.finalizar_review_session(
            int(session_id),
            acertos=int(max(0, acertos)),
            erros=int(max(0, erros)),
            puladas=int(max(0, puladas)),
            total_time_ms=int(max(0, total_time_ms)),
        )

