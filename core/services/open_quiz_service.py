# -*- coding: utf-8 -*-
"""Serviço auxiliar para dissertativas."""

from __future__ import annotations

from typing import List


class OpenQuizService:
    @staticmethod
    def build_context_input(theme: str, uploads: List[str]) -> List[str]:
        tema = str(theme or "").strip() or "Tema livre"
        return [f"Tema central: {tema}"] + list(uploads or [])

