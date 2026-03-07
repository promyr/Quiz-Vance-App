# -*- coding: utf-8 -*-
"""Helpers de rota e tema para a UI."""

from __future__ import annotations

from typing import Optional

from config import CORES


ROUTE_ALIASES = {
    "/panel": "/home",
    "/painel": "/home",
    "/inicio": "/home",
    "/questoes": "/quiz",
    "/revisao/caderno-erros": "/revisao/erros",
    "/revisao/caderno_erros": "/revisao/erros",
    "/revisao/marcados": "/revisao/marcadas",
}


def _normalize_route_path(route: Optional[str]) -> str:
    raw = str(route or "").strip()
    if not raw:
        return "/home"
    path = raw.split("?", 1)[0].split("#", 1)[0].strip()
    if not path:
        return "/home"
    if not path.startswith("/"):
        path = f"/{path}"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return ROUTE_ALIASES.get(path.lower(), path)


def _color(name: str, dark: bool):
    if dark:
        mapping = {
            "fundo": CORES["fundo_escuro"],
            "card": CORES["card_escuro"],
            "texto": CORES["texto_escuro"],
            "texto_sec": CORES["texto_sec_escuro"],
        }
        return mapping.get(name, CORES.get(name, "#FFFFFF"))
    return CORES.get(name, "#000000")
