# -*- coding: utf-8 -*-
"""Normalizacao de texto/mojibake e sanitizacao de controles Flet."""

from __future__ import annotations

from typing import Any, Optional

import flet as ft


_MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00f0", "\u0153", "\u2122", "\ufffd")
_MOJIBAKE_SEQUENCES = ("â€", "â€™", "â€œ", "â€\u009d", "ðŸ")


def _mojibake_score(text: str) -> int:
    if not text:
        return 0
    score = 0
    for marker in _MOJIBAKE_MARKERS:
        score += text.count(marker)
    for seq in _MOJIBAKE_SEQUENCES:
        score += text.count(seq) * 2
    return score


def _fix_mojibake_text(value: str) -> str:
    if not isinstance(value, str) or not value:
        return value
    if not any(marker in value for marker in _MOJIBAKE_MARKERS) and not any(seq in value for seq in _MOJIBAKE_SEQUENCES):
        return value
    current = value
    original_score = _mojibake_score(current)
    candidates = []
    for source_encoding in ("latin-1", "cp1252"):
        try:
            candidate = current.encode(source_encoding).decode("utf-8")
            candidates.append(candidate)
        except Exception:
            continue
    best = current
    best_score = original_score
    for candidate in candidates:
        if not candidate or candidate == current:
            continue
        candidate_score = _mojibake_score(candidate)
        # Evita correcao destrutiva: so aceita se reduzir ruído e preservar quase todo texto.
        length_ok = len(candidate) >= max(3, int(len(current) * 0.92))
        if length_ok and candidate_score < best_score:
            best = candidate
            best_score = candidate_score
    current = best

    sequence_map = {
        "\u00c3\u0192\u00c6\u2019\u00c3\u201a\u00c2\u00b5": "õ",
        "\u00c3\u0192\u00c6\u2019\u00c3\u201a\u00c2\u00a3": "ã",
        "\u00c3\u0192\u00c6\u2019\u00c3\u201a\u00c2\u00a7": "ç",
        "\u00c3\u0192\u00c6\u2019\u00c3\u201a\u00c2\u00a1": "á",
        "\u00c3\u0192\u00c6\u2019\u00c3\u201a\u00c2\u00a9": "é",
        "\u00c3\u0192\u00c6\u2019\u00c3\u201a\u00c2\u00ad": "í",
        "\u00c3\u0192\u00c6\u2019\u00c3\u201a\u00c2\u00ba": "ú",
        "\u00c3\u0192\u00c2\u00b5": "õ",
        "\u00c3\u0192\u00c2\u00a3": "ã",
        "\u00c3\u0192\u00c2\u00a7": "ç",
        "\u00c3\u0192\u00c2\u00a1": "á",
        "\u00c3\u0192\u00c2\u00a9": "é",
        "\u00c3\u0192\u00c2\u00ad": "í",
        "\u00c3\u0192\u00c2\u00ba": "ú",
        "\u00c3\u00b5": "õ",
        "\u00c3\u00a3": "ã",
        "\u00c3\u00a7": "ç",
        "\u00c3\u00a1": "á",
        "\u00c3\u00a9": "é",
        "\u00c3\u00ad": "í",
        "\u00c3\u00ba": "ú",
        "\u00c3\u00aa": "ê",
        "\u00c3\u00b4": "ô",
        "\u00c3\u00b3": "ó",
        "\u00c3\u00a2": "â",
        "\u00c3\u00a0": "à",
        "\u00e2\u20ac\u00a6": "...",
        "\u00e2\u20ac\u201d": "-",
        "\u00e2\u20ac\u201c": "-",
        "\u00e2\u20ac\u00a2": "-",
        "\u00c3\u00a2\u20ac\u201d\u00c2\u2020": "",
        "\u00c2": "",
    }
    for broken, clean in sequence_map.items():
        if broken in current:
            current = current.replace(broken, clean)

    residue_map = {
        "\u00c2": "",
        "\u0192": "",
        "\u00c6": "",
        "\u00a2": "",
        "\u20ac": "",
        "\u2122": "",
        "\ufffd": "",
        "\u25ca": "",
    }
    if any(ch in current for ch in residue_map.keys()):
        current = "".join(residue_map.get(ch, ch) for ch in current)
    return current


def _sanitize_payload_texts(payload: Any) -> Any:
    if isinstance(payload, str):
        return _fix_mojibake_text(payload)
    if isinstance(payload, list):
        return [_sanitize_payload_texts(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_sanitize_payload_texts(item) for item in payload)
    if isinstance(payload, dict):
        return {k: _sanitize_payload_texts(v) for k, v in payload.items()}
    return payload


def _sanitize_control_texts(root: Optional[object], deep: bool = False) -> None:
    if root is None:
        return

    visited = set()
    text_attrs = ("value", "text", "label", "hint_text", "tooltip", "error_text", "helper_text")
    child_attrs = ("content", "title", "subtitle", "leading", "trailing")
    list_attrs = ("controls", "actions", "tabs", "destinations")
    generic_skip = set(text_attrs + child_attrs + list_attrs)

    def _apply_text_layout_defaults(node: object, parent: Optional[object]) -> None:
        if not isinstance(node, ft.Text):
            return
        text_value = str(getattr(node, "value", "") or "")
        is_short = ("\n" not in text_value) and (len(text_value) <= 28)
        responsive_row_cls = getattr(ft, "ResponsiveRow", ft.Row)
        parent_is_row = isinstance(parent, (ft.Row, responsive_row_cls))
        try:
            if parent_is_row and is_short:
                if getattr(node, "max_lines", None) in (None, 0):
                    node.max_lines = 1
                if getattr(node, "overflow", None) is None:
                    node.overflow = ft.TextOverflow.ELLIPSIS
            if not text_value.strip():
                return
            if getattr(node, "no_wrap", None) is None:
                node.no_wrap = False
        except Exception:
            pass

    def _walk(node: Optional[object], parent: Optional[object] = None) -> None:
        if node is None:
            return
        file_picker_cls = getattr(ft, "FilePicker", None)
        if file_picker_cls is not None and isinstance(node, file_picker_cls):
            return
        nid = id(node)
        if nid in visited:
            return
        visited.add(nid)

        _apply_text_layout_defaults(node, parent)

        for attr in text_attrs:
            if not hasattr(node, attr):
                continue
            try:
                current = getattr(node, attr)
            except Exception:
                continue
            if isinstance(current, str):
                fixed = _fix_mojibake_text(current)
                if fixed != current:
                    try:
                        setattr(node, attr, fixed)
                    except Exception:
                        pass

        # Guard rail para erro WrapParentData/FlexParentData:
        # aplicamos apenas em modo deep (recuperacao de erro), para nao quebrar responsividade.
        if deep:
            try:
                if isinstance(node, ft.Row) and bool(getattr(node, "wrap", False)):
                    row_controls = getattr(node, "controls", None)
                    if isinstance(row_controls, (list, tuple)):
                        for child in row_controls:
                            if hasattr(child, "expand") and bool(getattr(child, "expand", False)):
                                try:
                                    setattr(child, "expand", False)
                                except Exception:
                                    pass
            except Exception:
                pass

        for attr in child_attrs:
            if not hasattr(node, attr):
                continue
            try:
                child = getattr(node, attr)
            except Exception:
                continue
            if isinstance(child, str):
                fixed = _fix_mojibake_text(child)
                if fixed != child:
                    try:
                        setattr(node, attr, fixed)
                    except Exception:
                        pass
            else:
                _walk(child, node)

        for attr in list_attrs:
            if not hasattr(node, attr):
                continue
            try:
                items = getattr(node, attr)
            except Exception:
                continue
            if isinstance(items, (list, tuple)):
                for item in items:
                    _walk(item, node)

        if deep:
            # Fallback generico: percorre atributos de controles nao cobertos acima.
            try:
                node_vars = vars(node)
            except Exception:
                node_vars = {}
            for attr, value in node_vars.items():
                if attr.startswith("_") or attr in generic_skip:
                    continue
                if isinstance(value, ft.Control):
                    _walk(value, node)
                elif isinstance(value, (list, tuple, set)):
                    for item in value:
                        if isinstance(item, ft.Control):
                            _walk(item, node)
                elif isinstance(value, dict):
                    for item in value.values():
                        if isinstance(item, ft.Control):
                            _walk(item, node)

    _walk(root, None)


def _sanitize_page_controls(page: Optional[ft.Page]) -> None:
    if page is None:
        return
    try:
        for view in list(getattr(page, "views", []) or []):
            _sanitize_control_texts(view, deep=True)
        dialog = getattr(page, "dialog", None)
        if dialog is not None:
            _sanitize_control_texts(dialog, deep=True)
        bottom_sheet = getattr(page, "bottom_sheet", None)
        if bottom_sheet is not None:
            _sanitize_control_texts(bottom_sheet, deep=True)
        snack_bar = getattr(page, "snack_bar", None)
        if snack_bar is not None:
            _sanitize_control_texts(snack_bar, deep=True)
        file_picker_cls = getattr(ft, "FilePicker", None)
        for overlay in list(getattr(page, "overlay", []) or []):
            if file_picker_cls is not None and isinstance(overlay, file_picker_cls):
                continue
            _sanitize_control_texts(overlay, deep=True)
    except Exception:
        pass


def _debug_scan_wrap_conflicts(root: Optional[object]) -> str:
    """Coleta uma fotografia rapida de Rows com wrap=True e filhos com expand=True."""
    if root is None:
        return ""
    seen = set()
    rows = []

    def _walk(node: Optional[object]):
        if node is None:
            return
        nid = id(node)
        if nid in seen:
            return
        seen.add(nid)
        try:
            if isinstance(node, ft.Row) and bool(getattr(node, "wrap", False)):
                bad = []
                ctrls = getattr(node, "controls", None)
                if isinstance(ctrls, list):
                    for idx, ch in enumerate(ctrls):
                        try:
                            bad.append((idx, ch.__class__.__name__, bool(getattr(ch, "expand", False))))
                        except Exception:
                            bad.append((idx, type(ch).__name__, False))
                rows.append(bad)
        except Exception:
            pass
        for attr in ("content", "leading", "trailing", "title", "subtitle"):
            child = getattr(node, attr, None)
            if child is not None and not isinstance(child, str):
                _walk(child)
        for attr in ("controls", "actions", "tabs", "destinations"):
            items = getattr(node, attr, None)
            if isinstance(items, list):
                for item in items:
                    if item is not None and not isinstance(item, str):
                        _walk(item)

    _walk(root)
    if not rows:
        return "wrap_rows=0"
    parts = [f"wrap_rows={len(rows)}"]
    for i, r in enumerate(rows):
        parts.append(f"row[{i}] children={r}")
    return " | ".join(parts)
