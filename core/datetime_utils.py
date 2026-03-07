# -*- coding: utf-8 -*-
"""Formatacao e parsing de datas para UI."""

from __future__ import annotations

import datetime
from typing import Optional


def _format_datetime_label(value: Optional[str]) -> str:
    if not value:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    try:
        dt_iso = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt_iso.strftime("%d/%m/%Y %H:%M")
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            continue
    return raw


def _format_exam_date_input(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())[:8]
    if len(digits) <= 2:
        return digits
    if len(digits) <= 4:
        return f"{digits[:2]}/{digits[2:]}"
    return f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"


def _parse_br_date(value: str) -> Optional[datetime.date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.datetime.strptime(raw, "%d/%m/%Y").date()
    except Exception:
        return None
