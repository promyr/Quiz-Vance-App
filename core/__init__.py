# -*- coding: utf-8 -*-
"""
Core Package - Quiz Vance V2.0

MÃ³dulos principais da aplicaÃ§Ã£o
"""

from .database_v2 import Database
from .ai_service_v2 import AIService, create_ai_provider
from .auth_service import authenticate_with_google
from .services import (
    DailyReviewService,
    FlashcardsService,
    MockExamReportService,
    MockExamService,
    OpenQuizService,
    QuizFilterService,
    QuestionReviewService,
    ReviewSessionService,
    SpacedRepetitionService,
    StudyPlanService,
    StudySummaryService,
)

__all__ = [
    'Database',
    'AIService',
    'create_ai_provider',
    'authenticate_with_google',
    'DailyReviewService',
    'FlashcardsService',
    'MockExamReportService',
    'MockExamService',
    'OpenQuizService',
    'QuizFilterService',
    'QuestionReviewService',
    'ReviewSessionService',
    'SpacedRepetitionService',
    'StudyPlanService',
    'StudySummaryService',
]

__version__ = '2.0.0'

