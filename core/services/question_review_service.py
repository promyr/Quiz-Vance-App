# -*- coding: utf-8 -*-
"""Regras de negócio para revisão de questões."""

from __future__ import annotations

from typing import Dict

from core.repositories.question_progress_repository import QuestionProgressRepository


class QuestionReviewService:
    def __init__(self, repo: QuestionProgressRepository):
        self.repo = repo

    def review_question(self, user_id: int, question: Dict, acertou: bool) -> str:
        action = "correct" if bool(acertou) else "wrong"
        self.repo.register_result(int(user_id), question, action)
        return action

    def mark_for_review(self, user_id: int, question: Dict) -> None:
        self.repo.register_result(int(user_id), question, "mark")

    def skip_question(self, user_id: int, question: Dict) -> None:
        self.repo.register_result(int(user_id), question, "skip")

