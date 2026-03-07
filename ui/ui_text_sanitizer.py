# -*- coding: utf-8 -*-
"""
Sanitizador de texto para UI do Quiz Vance.

Corrige mojibake (UTF-8 lido como latin-1) em textos de payload e controles Flet.

Exporta:
    _fix_mojibake_text(text) -> str
    _sanitize_payload_texts(payload) -> Any
    _sanitize_control_texts(control) -> None
    _sanitize_page_controls(page) -> None
    _debug_scan_wrap_conflicts(root) -> str
"""

from __future__ import annotations

from typing import Any, Optional


# ---------------------------------------------------------------------------
# Correção de mojibake
# ---------------------------------------------------------------------------

def _fix_mojibake_text(text: str) -> str:
    """
    Tenta corrigir texto com mojibake (UTF-8 interpretado como latin-1).

    Estratégia: re-encode como latin-1 e decode como UTF-8.
    Se falhar ou o resultado for igual, retorna o original.
    """
    if not text or not isinstance(text, str):
        return text or ""

    # Heurística rápida: se não contém sequências típicas de mojibake, retorna direto
    if "Ã" not in text and "â€" not in text and "Ã©" not in text:
        return text

    try:
        fixed = text.encode("latin-1").decode("utf-8")
        # Verificar se a correção melhorou o texto (menos caracteres não-ASCII estranhos)
        return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    # Tentar uma segunda passagem (triple-encoded)
    try:
        step1 = text.encode("latin-1")
        step2 = step1.decode("utf-8")
        step3 = step2.encode("latin-1").decode("utf-8")
        return step3
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    return text


# ---------------------------------------------------------------------------
# Sanitização de payloads (dicts, lists, strings)
# ---------------------------------------------------------------------------

def _sanitize_payload_texts(payload: Any) -> Any:
    """
    Percorre recursivamente dicts e lists, aplicando _fix_mojibake_text
    em todos os valores string.
    """
    if payload is None:
        return payload

    if isinstance(payload, str):
        return _fix_mojibake_text(payload)

    if isinstance(payload, dict):
        return {k: _sanitize_payload_texts(v) for k, v in payload.items()}

    if isinstance(payload, list):
        return [_sanitize_payload_texts(item) for item in payload]

    if isinstance(payload, tuple):
        return tuple(_sanitize_payload_texts(item) for item in payload)

    return payload


# ---------------------------------------------------------------------------
# Sanitização de controles Flet
# ---------------------------------------------------------------------------

def _sanitize_control_texts(control: Any, _depth: int = 0) -> None:
    """
    Percorre recursivamente um controle Flet e corrige mojibake em
    atributos de texto (value, label, hint_text, tooltip, text).

    Limite de profundidade: 20 níveis para evitar loops.
    """
    if control is None or _depth > 20:
        return

    _TEXT_ATTRS = ("value", "label", "hint_text", "tooltip", "text", "helper_text",
                   "error_text", "prefix_text", "suffix_text", "content", "title")

    for attr in _TEXT_ATTRS:
        try:
            val = getattr(control, attr, None)
            if isinstance(val, str):
                fixed = _fix_mojibake_text(val)
                if fixed != val:
                    setattr(control, attr, fixed)
        except Exception:
            pass

    # Percorrer filhos
    for child_attr in ("controls", "content", "actions", "leading", "trailing",
                        "title", "subtitle", "header", "footer", "items"):
        try:
            child = getattr(control, child_attr, None)
            if child is None:
                continue
            if isinstance(child, list):
                for item in child:
                    _sanitize_control_texts(item, _depth + 1)
            elif hasattr(child, "__class__") and not isinstance(child, str):
                _sanitize_control_texts(child, _depth + 1)
        except Exception:
            pass


def _sanitize_page_controls(page: Any) -> None:
    """
    Sanitiza todos os controles visíveis na page atual (views[-1] e overlay).
    """
    if page is None:
        return

    try:
        views = getattr(page, "views", None) or []
        if views:
            _sanitize_control_texts(views[-1])
    except Exception:
        pass

    try:
        overlay = getattr(page, "overlay", None) or []
        for ctrl in overlay:
            _sanitize_control_texts(ctrl)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Debug: detectar conflitos de wrap
# ---------------------------------------------------------------------------

def _debug_scan_wrap_conflicts(root: Optional[object]) -> str:
    """
    Escaneia a árvore de controles buscando controles expand=True dentro
    de containers sem dimensão definida (possível causa de erros de layout).

    Retorna string descritiva para logging; string vazia se não encontrou problemas.
    """
    if root is None:
        return ""

    issues: list[str] = []

    def _scan(ctrl: Any, path: str, depth: int) -> None:
        if ctrl is None or depth > 15:
            return

        try:
            expand = getattr(ctrl, "expand", None)
            width = getattr(ctrl, "width", None)
            height = getattr(ctrl, "height", None)
            ctrl_type = type(ctrl).__name__

            if expand and width is None and height is None and depth > 0:
                issues.append(f"{path}/{ctrl_type}[expand=True,no-size]")
        except Exception:
            pass

        for child_attr in ("controls", "content", "actions"):
            try:
                child = getattr(ctrl, child_attr, None)
                if child is None:
                    continue
                label = f"{path}/{type(ctrl).__name__}.{child_attr}"
                if isinstance(child, list):
                    for i, item in enumerate(child):
                        _scan(item, f"{label}[{i}]", depth + 1)
                else:
                    _scan(child, label, depth + 1)
            except Exception:
                pass

    _scan(root, "root", 0)

    if not issues:
        return ""
    return "WRAP_CONFLICTS: " + "; ".join(issues[:10])
