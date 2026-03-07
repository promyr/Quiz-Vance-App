# -*- coding: utf-8 -*-
"""View de ranking — extraída do main_v2.py."""

from __future__ import annotations

import flet as ft

from config import CORES
from core.ui_route_theme import _color
from core.helpers.ui_helpers import soft_border


def build_ranking_body(state: dict, navigate, dark: bool) -> ft.Control:
    db = state["db"]
    user = state.get("usuario") or {}
    ranking = db.obter_ranking()
    total_participantes = len(ranking)
    top_xp = int((ranking[0]["xp"] if ranking else 0) or 0)
    meu_nome = str(user.get("nome", "") or "").strip().lower()
    minha_posicao = next(
        (idx for idx, r in enumerate(ranking, 1) if str(r.get("nome", "")).strip().lower() == meu_nome),
        None,
    )

    resumo = ft.ResponsiveRow(
        controls=[
            ft.Container(
                col={"sm": 6, "md": 3},
                content=ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Participantes", size=12, color=_color("texto_sec", dark)),
                                ft.Text(str(total_participantes), size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                            ],
                            spacing=4,
                        ),
                    ),
                ),
            ),
            ft.Container(
                col={"sm": 6, "md": 3},
                content=ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Top XP", size=12, color=_color("texto_sec", dark)),
                                ft.Text(str(top_xp), size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                            ],
                            spacing=4,
                        ),
                    ),
                ),
            ),
            ft.Container(
                col={"sm": 12, "md": 6},
                content=ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Sua posicao", size=12, color=_color("texto_sec", dark)),
                                ft.Text(
                                    f"#{minha_posicao}" if minha_posicao else "Fora do ranking",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=CORES["primaria"] if minha_posicao else _color("texto_sec", dark),
                                ),
                            ],
                            spacing=4,
                        ),
                    ),
                ),
            ),
        ],
        spacing=8,
        run_spacing=8,
    )

    medalhas = {1: ("1", CORES["ouro"]), 2: ("2", CORES["prata"]), 3: ("3", CORES["bronze"])}
    ranking_rows = []
    for idx, r in enumerate(ranking, 1):
        medalha_texto, medalha_cor = medalhas.get(idx, (str(idx), _color("texto_sec", dark)))
        destaque_me = str(r.get("nome", "")).strip().lower() == meu_nome
        ranking_rows.append(
            ft.Container(
                padding=12,
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.06, CORES["primaria"]) if destaque_me else _color("card", dark),
                border=ft.border.all(
                    1,
                    ft.Colors.with_opacity(0.20, CORES["primaria"]) if destaque_me else soft_border(dark, 0.08),
                ),
                content=ft.Row(
                    [
                        ft.Container(
                            width=32,
                            height=32,
                            alignment=ft.Alignment(0, 0),
                            border_radius=999,
                            bgcolor=ft.Colors.with_opacity(0.14, medalha_cor),
                            content=ft.Text(medalha_texto, color=medalha_cor, weight=ft.FontWeight.BOLD),
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    r.get("nome", ""),
                                    size=15,
                                    weight=ft.FontWeight.BOLD if destaque_me else ft.FontWeight.W_600,
                                    color=_color("texto", dark),
                                ),
                                ft.Text(
                                    f"Taxa {float(r.get('taxa_acerto', 0) or 0):.1f}%",
                                    size=12,
                                    color=_color("texto_sec", dark),
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=10, vertical=6),
                            border_radius=999,
                            bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]),
                            content=ft.Text(
                                f"{int(r.get('xp', 0) or 0)} XP",
                                color=CORES["primaria"],
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )
    if not ranking_rows:
        ranking_rows.append(ft.Text("Sem dados ainda.", color=_color("texto_sec", dark)))

    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Text("Ranking", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text("Competicao por XP com destaque para seu progresso.", size=14, color=_color("texto_sec", dark)),
                resumo,
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=10,
                        content=ft.Column(ranking_rows, spacing=8),
                    ),
                ),
                ft.Container(height=12),
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
