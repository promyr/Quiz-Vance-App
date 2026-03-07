# -*- coding: utf-8 -*-
"""Repositories de acesso a dados."""

from .base_repository import BaseRepository
from .flashcard_repository import FlashcardRepository
from .gamification_repository import GamificationRepository
from .plan_repository import PlanRepository
from .question_progress_repository import QuestionProgressRepository
from .quiz_repository import QuizRepository
from .review_session_repository import ReviewSessionRepository
from .session_repository import SessionRepository
from .user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "FlashcardRepository",
    "GamificationRepository",
    "PlanRepository",
    "QuestionProgressRepository",
    "QuizRepository",
    "ReviewSessionRepository",
    "SessionRepository",
    "UserRepository",
]
