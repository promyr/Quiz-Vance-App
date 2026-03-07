"""Runtime helpers for Simulado/Quiz state (stateless utilities).

This module centralizes the minimal, UI‑agnostic logic for:
- creating a new quiz/simulado session state
- resetting runtime fields between tentativas
- tracking tempo por questao

It intentionally avoids any UI objects; callers (views) devem aplicar
efeitos visuais como limpar colunas/containers separadamente.
"""

from __future__ import annotations

import time
from typing import Dict, Any


def _base_estado(simulado_mode_default: bool = False) -> Dict[str, Any]:
    return {
        "respostas": {},
        "corrigido": False,
        "upload_texts": [],
        "upload_names": [],
        "upload_selected_names": [],
        "favoritas": set(),
        "marcadas_erro": set(),
        "current_idx": 0,
        "feedback_imediato": not simulado_mode_default,
        "simulado_mode": bool(simulado_mode_default),
        "modo_continuo": False,
        "start_time": None,
        "confirmados": set(),
        "puladas": set(),
        "ui_stage": "config",
        "show_secondary_tools": False,
        "ultimo_filtro": {},
        "advanced_filters_draft": {},
        "advanced_filters_applied": {},
        "mock_exam_session_id": None,
        "mock_exam_started_at": None,
        "prova_deadline": None,
        "tempo_limite_s": None,
        "simulado_report": None,
        "simulado_items": [],
        "question_time_ms": {},
        "question_last_ts": None,
        "stats_synced_idxs": set(),
        "source_lock_material": False,
        "infinite_batch_size": 5,
        "simulado_infinite": False,
    }


def new_quiz_session(simulado_mode_default: bool = False) -> Dict[str, Any]:
    """Returna um novo dicionário de sessão com estado inicializado."""
    return {
        "questoes": [],
        "estado": _base_estado(simulado_mode_default),
    }


def reset_runtime_state(estado: Dict[str, Any], clear_mode: bool = False) -> None:
    """Limpa campos voláteis do runtime (não toca UI)."""
    if estado is None:
        return
    estado["simulado_report"] = None
    estado["simulado_items"] = []
    estado["mock_exam_session_id"] = None
    estado["mock_exam_started_at"] = None
    estado["prova_deadline"] = None
    estado["question_time_ms"] = {}
    estado["question_last_ts"] = None
    if clear_mode:
        estado["simulado_mode"] = False
        estado["tempo_limite_s"] = None


def track_question_time(estado: Dict[str, Any], questoes: list) -> None:
    """Acumula tempo gasto na questão corrente."""
    if estado is None:
        return
    if not questoes:
        estado["question_last_ts"] = time.monotonic()
        return
    now = time.monotonic()
    last = estado.get("question_last_ts")
    if last is None:
        estado["question_last_ts"] = now
        return
    idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
    delta_ms = int(max(0.0, now - float(last)) * 1000)
    if delta_ms > 0:
        times = dict(estado.get("question_time_ms") or {})
        times[idx] = int(times.get(idx, 0) or 0) + delta_ms
        estado["question_time_ms"] = times
    estado["question_last_ts"] = now

