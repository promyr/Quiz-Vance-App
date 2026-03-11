# -*- coding: utf-8 -*-
"""View de perfil — extraída do main_v2.py."""

from __future__ import annotations

import flet as ft

from config import CORES
from core.ui_route_theme import _color


def build_profile_body(state: dict, navigate, dark: bool) -> ft.Control:
    user = state.get("usuario") or {}
    db = state.get("db")
    page = state.get("page")
    xp = int(user.get("xp", 0) or 0)
    nivel = str(user.get("nivel", "Bronze") or "Bronze")
    acertos = int(user.get("acertos", 0) or 0)
    total = int(user.get("total_questoes", 0) or 0)
    taxa = (acertos / total * 100.0) if total > 0 else 0.0
    streak = int(user.get("streak_dias", 0) or 0)
    economia = "Ativo" if bool(user.get("economia_mode")) else "Inativo"
    tema = "Escuro" if state.get("tema_escuro") else "Claro"
    nome = str(user.get("nome", "") or "")
    identificador = str(user.get("email", "") or "")
    id_edit_field = ft.TextField(
        label="ID de acesso",
        value=identificador,
        hint_text="Digite um novo ID",
        expand=True,
    )
    id_feedback = ft.Text("", size=12, color=_color("texto_sec", dark), visible=False)

    def _salvar_id(_):
        if not db or not user.get("id"):
            return
        novo_id = (id_edit_field.value or "").strip().lower()
        if novo_id == (identificador or "").strip().lower():
            id_feedback.value = "Nenhuma alteracao no ID."
            id_feedback.color = _color("texto_sec", dark)
            id_feedback.visible = True
            if page:
                page.update()
            return
        ok, msg = db.atualizar_identificador(user["id"], novo_id)
        id_feedback.value = msg
        id_feedback.color = CORES["sucesso"] if ok else CORES["erro"]
        id_feedback.visible = True
        if ok:
            state["usuario"]["email"] = novo_id
            user["email"] = novo_id
        if page:
            page.update()

    resumo_cards = ft.ResponsiveRow(
        controls=[
            ft.Container(
                col={"sm": 6, "md": 3},
                content=ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text("Nivel", size=12, color=_color("texto_sec", dark)),
                    ft.Text(nivel, size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ], spacing=4))),
            ),
            ft.Container(
                col={"sm": 6, "md": 3},
                content=ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text("XP", size=12, color=_color("texto_sec", dark)),
                    ft.Text(str(xp), size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ], spacing=4))),
            ),
            ft.Container(
                col={"sm": 6, "md": 3},
                content=ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text("Taxa de acerto", size=12, color=_color("texto_sec", dark)),
                    ft.Text(f"{taxa:.1f}%", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ], spacing=4))),
            ),
            ft.Container(
                col={"sm": 6, "md": 3},
                content=ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text("Sequência", size=12, color=_color("texto_sec", dark)),
                    ft.Text(f"{streak} dia(s)", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ], spacing=4))),
            ),
        ],
        spacing=8,
        run_spacing=8,
    )

    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Text("Perfil", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text("Resumo da sua conta e preferencias.", size=14, color=_color("texto_sec", dark)),
                resumo_cards,
                ft.Card(
                    elevation=1,
                    content=ft.Container(padding=12, content=ft.Column([
                        ft.Text("Conta", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ft.ListTile(leading=ft.Icon(ft.Icons.PERSON), title=ft.Text("Nome"), subtitle=ft.Text(nome or "-")),
                        ft.ResponsiveRow(
                            [
                                ft.Container(col={"xs": 12, "md": 9}, content=ft.Row([
                                    ft.Icon(ft.Icons.BADGE, color=_color("texto_sec", dark)),
                                    ft.Container(expand=True, content=id_edit_field),
                                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.END)),
                                ft.Container(col={"xs": 12, "md": 3}, content=ft.ElevatedButton(
                                    "Salvar ID", icon=ft.Icons.SAVE, on_click=_salvar_id, expand=True,
                                )),
                            ],
                            run_spacing=6, spacing=10, vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        id_feedback,
                    ], spacing=4)),
                ),
                ft.Card(
                    elevation=1,
                    content=ft.Container(padding=12, content=ft.Column([
                        ft.Text("Estudo e preferencias", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ft.ListTile(leading=ft.Icon(ft.Icons.SAVINGS), title=ft.Text("Modo economia IA"), trailing=ft.Text(economia, color=_color("texto_sec", dark))),
                        ft.ListTile(leading=ft.Icon(ft.Icons.DARK_MODE), title=ft.Text("Tema"), trailing=ft.Text(tema, color=_color("texto_sec", dark))),
                    ], spacing=4)),
                ),
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
