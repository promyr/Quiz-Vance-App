# -*- coding: utf-8 -*-
"""Servico de alto nivel para revisao espacada (Prompt 5)."""

from __future__ import annotations

from typing import Dict, List

from core.repositories.flashcard_repository import FlashcardRepository
from core.repositories.question_progress_repository import QuestionProgressRepository


class SpacedRepetitionService:
    def __init__(self, flash_repo: FlashcardRepository, question_repo: QuestionProgressRepository):
        self.flash_repo = flash_repo
        self.question_repo = question_repo

    @classmethod
    def from_db(cls, db):
        return cls(
            FlashcardRepository(db),
            QuestionProgressRepository(db),
        )

    def due_flashcards(self, user_id: int, limit: int = 120) -> List[Dict]:
        return self.flash_repo.list_due(int(user_id), limit=int(max(1, limit)))

    def due_questions(self, user_id: int, limit: int = 120) -> List[Dict]:
        return self.question_repo.list_due(int(user_id), limit=int(max(1, limit)))

    def review_flashcard(self, user_id: int, card: Dict, action: str) -> None:
        self.flash_repo.register_action(int(user_id), card, str(action or "pular"))

    def review_question(self, user_id: int, question: Dict, acertou: bool) -> None:
        action = "correct" if bool(acertou) else "wrong"
        self.question_repo.register_result(int(user_id), question, action)

    def mark_question(self, user_id: int, question: Dict) -> None:
        self.question_repo.register_result(int(user_id), question, "mark")

    def skip_question(self, user_id: int, question: Dict) -> None:
        self.question_repo.register_result(int(user_id), question, "skip")

