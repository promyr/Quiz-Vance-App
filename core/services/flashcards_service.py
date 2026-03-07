# -*- coding: utf-8 -*-
"""Serviço auxiliar para fluxo de flashcards."""

from __future__ import annotations

from typing import Dict, List


class FlashcardsService:
    @staticmethod
    def normalize_seed_cards(items: List[Dict]) -> List[Dict]:
        out = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            frente = str(item.get("frente") or item.get("front") or "").strip()
            verso = str(item.get("verso") or item.get("back") or "").strip()
            if frente and verso:
                out.append({"frente": frente, "verso": verso})
        return out

