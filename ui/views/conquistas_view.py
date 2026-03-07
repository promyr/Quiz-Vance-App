# -*- coding: utf-8 -*-
"""View de conquistas — extraída do main_v2.py."""

from __future__ import annotations

import flet as ft

from config import CONQUISTAS, CORES
from core.ui_route_theme import _color
from core.helpers.ui_helpers import soft_border


def build_conquistas_body(state: dict, navigate, dark: bool) -> ft.Control:
    total_conquistas = len(CONQUISTAS)
    total_xp = int(sum(int(c.get("xp_bonus", 0) or 0) for c in CONQUISTAS))
    rows = []
    for c in CONQUISTAS:
        rows.append(
            ft.Container(
                padding=12,
                border_radius=12,
                bgcolor=_color("card", dark),
                border=ft.border.all(1, soft_border(dark, 0.08)),
                content=ft.Row(
                    [
                        ft.Container(
                            width=34,
                            height=34,
                            border_radius=999,
                            alignment=ft.Alignment(0, 0),
                            bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]),
                            content=ft.Icon(ft.Icons.MILITARY_TECH, color=CORES["primaria"], size=18),
                        ),
                        ft.Column(
                            [
                                ft.Text(c["titulo"], weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                ft.Text(c["descricao"], size=12, color=_color("texto_sec", dark)),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=10, vertical=6),
                            border_radius=999,
                            bgcolor=ft.Colors.with_opacity(0.10, CORES["acento"]),
                            content=ft.Text(f"+{c['xp_bonus']} XP", color=CORES["acento"], weight=ft.FontWeight.BOLD),
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )
    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Text("Conquistas", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text("Lista de medalhas disponiveis.", size=14, color=_color("texto_sec", dark)),
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            col={"sm": 6, "md": 4},
                            content=ft.Card(
                                elevation=1,
                                content=ft.Container(
                                    padding=12,
                                    content=ft.Column(
                                        [
                                            ft.Text("Total de conquistas", size=12, color=_color("texto_sec", dark)),
                                            ft.Text(str(total_conquistas), size=20, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                        ],
                                        spacing=4,
                                    ),
                                ),
                            ),
                        ),
                        ft.Container(
                            col={"sm": 6, "md": 4},
                            content=ft.Card(
                                elevation=1,
                                content=ft.Container(
                                    padding=12,
                                    content=ft.Column(
                                        [
                                            ft.Text("XP disponivel", size=12, color=_color("texto_sec", dark)),
                                            ft.Text(f"{total_xp}", size=20, weight=ft.FontWeight.BOLD, color=CORES["acento"]),
                                        ],
                                        spacing=4,
                                    ),
                                ),
                            ),
                        ),
                    ],
                    spacing=8,
                    run_spacing=8,
                ),
                ft.Card(content=ft.Container(padding=10, content=ft.Column(rows, spacing=8)), elevation=1),
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
