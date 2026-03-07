# -*- coding: utf-8 -*-
"""Regras de filtro avancado do Quiz (Prompt 2)."""

from __future__ import annotations

from typing import Dict, Iterable, List

from core.filter_taxonomy import get_quiz_filter_taxonomy


class QuizFilterService:
    SECTIONS = ("disciplinas", "assuntos", "bancas", "cargos", "anos", "status")

    @classmethod
    def empty_filters(cls) -> Dict[str, List[str]]:
        return {k: [] for k in cls.SECTIONS}

    @classmethod
    def normalize_filters(cls, raw: Dict) -> Dict[str, List[str]]:
        out = cls.empty_filters()
        if not isinstance(raw, dict):
            return out
        for key in cls.SECTIONS:
            value = raw.get(key) or []
            if isinstance(value, (list, tuple, set)):
                out[key] = [str(v).strip() for v in value if str(v).strip()]
        return out

    @classmethod
    def selection_count(cls, filters: Dict) -> int:
        data = cls.normalize_filters(filters)
        return sum(len(data.get(k) or []) for k in cls.SECTIONS)

    @classmethod
    def section_count_map(cls, filters: Dict) -> Dict[str, int]:
        data = cls.normalize_filters(filters)
        return {k: len(data.get(k) or []) for k in cls.SECTIONS}

    @classmethod
    def is_equal(cls, a: Dict, b: Dict) -> bool:
        aa = cls.normalize_filters(a)
        bb = cls.normalize_filters(b)
        for key in cls.SECTIONS:
            if sorted(aa.get(key) or []) != sorted(bb.get(key) or []):
                return False
        return True

    @classmethod
    def has_any(cls, filters: Dict) -> bool:
        return cls.selection_count(filters) > 0

    @classmethod
    def taxonomy_options(cls) -> Dict[str, List[Dict[str, str]]]:
        taxonomy = get_quiz_filter_taxonomy() or {}
        sections_raw = taxonomy.get("sections") or {}

        # sections pode ser dict {key: [...]} ou list [{key, label, options}]
        if isinstance(sections_raw, list):
            sections: Dict[str, list] = {}
            for sec in sections_raw:
                if not isinstance(sec, dict):
                    continue
                sec_key = str(sec.get("key") or "").strip()
                if not sec_key:
                    continue
                opts = sec.get("options") or sec.get("items") or []
                sections[sec_key] = opts
        else:
            sections = sections_raw  # type: ignore[assignment]

        out = {}
        for key in cls.SECTIONS:
            opts = sections.get(key) or []
            normalized = []
            for item in opts:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "").strip()
                label = str(item.get("label") or item_id).strip()
                if item_id and label:
                    normalized.append({"id": item_id, "label": label})
            out[key] = normalized
        return out

    @classmethod
    def option_label(cls, section: str, option_id: str) -> str:
        sec = str(section or "").strip()
        oid = str(option_id or "").strip()
        if not sec or not oid:
            return oid
        for item in cls.taxonomy_options().get(sec, []):
            if str(item.get("id")) == oid:
                return str(item.get("label") or oid)
        return oid

    @classmethod
    def summary(cls, filters: Dict, max_items: int = 6) -> str:
        data = cls.normalize_filters(filters)
        parts: List[str] = []
        for section in cls.SECTIONS:
            values = data.get(section) or []
            for vid in values:
                parts.append(cls.option_label(section, vid))
        if not parts:
            return "Sem filtros avancados"
        if len(parts) <= max_items:
            return ", ".join(parts)
        head = ", ".join(parts[:max_items])
        return f"{head} +{len(parts) - max_items}"

    @classmethod
    def to_generation_hint(cls, filters: Dict) -> str:
        data = cls.normalize_filters(filters)
        tokens: List[str] = []
        for section in cls.SECTIONS:
            values = data.get(section) or []
            if not values:
                continue
            labels = [cls.option_label(section, v) for v in values]
            tokens.append(f"{section}: {', '.join(labels)}")
        if not tokens:
            return ""
        return "Filtros avancados ativos: " + " | ".join(tokens)

    @classmethod
    def toggle_value(cls, filters: Dict, section: str, value: str) -> Dict[str, List[str]]:
        data = cls.normalize_filters(filters)
        sec = str(section or "").strip()
        val = str(value or "").strip()
        if sec not in cls.SECTIONS or not val:
            return data
        bucket = list(data.get(sec) or [])
        if val in bucket:
            bucket = [x for x in bucket if x != val]
        else:
            bucket.append(val)
        data[sec] = bucket
        return data

    @classmethod
    def filtered_options(cls, section: str, query: str) -> List[Dict[str, str]]:
        base = list(cls.taxonomy_options().get(str(section or "").strip(), []))
        q = str(query or "").strip().lower()
        if not q:
            return base
        return [item for item in base if q in str(item.get("label") or "").lower()]

    @classmethod
    def primary_topic(cls, filters: Dict) -> str:
        data = cls.normalize_filters(filters)
        disciplinas = data.get("disciplinas") or []
        if not disciplinas:
            return ""
        return cls.option_label("disciplinas", disciplinas[0])

