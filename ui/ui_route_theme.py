# -*- coding: utf-8 -*-
"""
Utilitários de tema e rota — compartilhados por views e main_v2.

Exporta:
    _color(key, dark) -> str
    _normalize_route_path(route) -> str
"""

from __future__ import annotations

from config import CORES

# Mapeamento de chaves de cor para seus equivalentes dark
_DARK_SUFFIX_MAP: dict[str, str] = {
    "fundo":     "fundo_escuro",
    "card":      "card_escuro",
    "texto":     "texto_escuro",
    "texto_sec": "texto_sec_escuro",
}


def _color(key: str, dark: bool) -> str:
    """
    Retorna a cor do tema para `key`.

    Se dark=True e existir uma variante _escuro, usa-a;
    caso contrário usa a chave direta de CORES.
    """
    if dark:
        dark_key = _DARK_SUFFIX_MAP.get(key, key + "_escuro")
        if dark_key in CORES:
            return CORES[dark_key]
    return CORES.get(key, "#000000")


def _normalize_route_path(route: str) -> str:
    """
    Normaliza um caminho de rota para comparação consistente.

    - Remove espaços
    - Garante barra inicial
    - Remove barra final (exceto raiz)
    - Lowercase
    """
    if not route:
        return "/home"
    normalized = str(route).strip().lower()
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    if len(normalized) > 1 and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized
