# -*- coding: utf-8 -*-
"""Helpers de sincronizacao entre fila local e backend."""

from __future__ import annotations

from typing import Any


def resolve_consumed_event_ids(resp: dict[str, Any] | None, events: list[dict[str, Any]]) -> list[str]:
    """
    Resolve quais event_ids podem ser removidos da fila local com seguranca.

    Regras:
    - Se o backend retornar `consumed_event_ids`, usa somente os ids conhecidos do lote.
    - Sem `consumed_event_ids`, so considera "todos consumidos" quando os contadores
      `processed + duplicated` confirmam ACK completo do lote enviado.
    - Em qualquer ambiguidade, nao remove nada.
    """
    batch_ids: list[str] = []
    seen_ids: set[str] = set()
    for ev in list(events or []):
        if not isinstance(ev, dict):
            continue
        eid = str(ev.get("event_id") or "").strip()
        if not eid or eid in seen_ids:
            continue
        seen_ids.add(eid)
        batch_ids.append(eid)
    if not batch_ids:
        return []

    payload = resp if isinstance(resp, dict) else {}

    consumed_raw = payload.get("consumed_event_ids")
    if isinstance(consumed_raw, list):
        out: list[str] = []
        for raw in consumed_raw:
            eid = str(raw or "").strip()
            if eid and eid in seen_ids and eid not in out:
                out.append(eid)
        return out

    try:
        processed = max(0, int(payload.get("processed") or 0))
    except Exception:
        processed = 0
    try:
        duplicated = max(0, int(payload.get("duplicated") or 0))
    except Exception:
        duplicated = 0
    try:
        received = max(0, int(payload.get("received") or 0))
    except Exception:
        received = 0

    expected = len(batch_ids) if received <= 0 else min(received, len(batch_ids))
    acked = processed + duplicated
    if expected > 0 and acked >= expected:
        return list(batch_ids)
    return []

