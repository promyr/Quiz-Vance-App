# -*- coding: utf-8 -*-
"""Fila diária combinada: 3 flashcards -> 2 questões."""

from __future__ import annotations

from typing import Dict, List

from core.repositories.flashcard_repository import FlashcardRepository
from core.repositories.question_progress_repository import QuestionProgressRepository


class DailyReviewService:
    def __init__(self, flash_repo: FlashcardRepository, question_repo: QuestionProgressRepository):
        self.flash_repo = flash_repo
        self.question_repo = question_repo

    def build_daily_queue(self, user_id: int, premium: bool, free_limit: int = 30) -> List[Dict]:
        flashcards = self.flash_repo.list_due(int(user_id), limit=220)
        questions = self.question_repo.list_due(int(user_id), limit=220)

        queue: List[Dict] = []
        fi = 0
        qi = 0
        while fi < len(flashcards) or qi < len(questions):
            for _ in range(3):
                if fi >= len(flashcards):
                    break
                queue.append({"item_type": "flashcard", "payload": dict(flashcards[fi])})
                fi += 1
            for _ in range(2):
                if qi >= len(questions):
                    break
                queue.append({"item_type": "question", "payload": dict(questions[qi])})
                qi += 1
            if not premium and len(queue) >= int(max(1, free_limit)):
                queue = queue[: int(max(1, free_limit))]
                break
        return queue

