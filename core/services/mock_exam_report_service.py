# -*- coding: utf-8 -*-
"""Agregacao de relatorio de simulado (Prompt 6)."""

from __future__ import annotations

from typing import Dict, Iterable, List


class MockExamReportService:
    @staticmethod
    def summarize_items(items: Iterable[Dict]) -> Dict:
        total = 0
        acertos = 0
        erros = 0
        puladas = 0
        tempo_total_ms = 0
        by_disciplina: Dict[str, Dict[str, int]] = {}
        by_assunto: Dict[str, Dict[str, int]] = {}

        for item in items or []:
            if not isinstance(item, dict):
                continue
            total += 1
            res = str(item.get("resultado") or "").strip().lower()
            tempo_total_ms += int(max(0, int(item.get("tempo_ms") or 0)))
            if res == "correct":
                acertos += 1
            elif res == "skip":
                puladas += 1
            else:
                erros += 1

            meta = item.get("meta") or {}
            disciplina = str(meta.get("disciplina") or meta.get("tema") or "Geral").strip() or "Geral"
            assunto = str(meta.get("assunto") or "Geral").strip() or "Geral"

            db = by_disciplina.setdefault(disciplina, {"total": 0, "acertos": 0})
            db["total"] += 1
            if res == "correct":
                db["acertos"] += 1

            ab = by_assunto.setdefault(assunto, {"total": 0, "acertos": 0})
            ab["total"] += 1
            if res == "correct":
                ab["acertos"] += 1

        score_pct = (acertos / max(1, total)) * 100.0
        tempo_total_s = int(tempo_total_ms / 1000)
        tempo_medio_s = int(tempo_total_s / max(1, total))
        return {
            "total": total,
            "acertos": acertos,
            "erros": erros,
            "puladas": puladas,
            "score_pct": score_pct,
            "tempo_total_s": tempo_total_s,
            "tempo_medio_s": tempo_medio_s,
            "by_disciplina": by_disciplina,
            "by_assunto": by_assunto,
        }

