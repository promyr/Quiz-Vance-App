# -*- coding: utf-8 -*-
"""View 'Mais' (hub) â€” extraÃ­da do main_v2.py."""

from __future__ import annotations

import os

import flet as ft

from config import CORES, get_level_info
from core.error_monitor import log_exception
from core.ui_route_theme import _color
from core.helpers.ui_helpers import launch_url_compat, show_dialog_compat, close_dialog_compat
from core.legal_texts import TERMOS_DE_USO, POLITICA_PRIVACIDADE, POLITICA_REEMBOLSO
from ui.design_system import (
    DS,
    ds_badge,
    ds_card,
    ds_progress_bar,
    ds_section_title,
)


def build_mais_body(state: dict, navigate, dark: bool, on_logout, toggle_dark) -> ft.Control:
    """Tela Mais: hub com perfil + grid de atalhos para rotas secundarias."""
    usuario = state.get("usuario") or {}
    db = state.get("db")
    page = state.get("page")
    nome = usuario.get("nome", "Usuario")
    email = usuario.get("email", "")

    if db and usuario.get("id"):
        try:
            resumo = db.obter_resumo_estatisticas(int(usuario["id"]))
            if state.get("usuario"):
                state["usuario"]["xp"] = int(resumo.get("xp") or state["usuario"].get("xp", 0))
                state["usuario"]["nivel"] = str(resumo.get("nivel") or state["usuario"].get("nivel", "Bronze"))
                state["usuario"]["acertos"] = int(resumo.get("acertos_total") or state["usuario"].get("acertos", 0))
                state["usuario"]["total_questoes"] = int(resumo.get("total_questoes") or state["usuario"].get("total_questoes", 0))
                state["usuario"]["streak_dias"] = int(resumo.get("streak_dias") or state["usuario"].get("streak_dias", 0))
        except Exception as ex:
            log_exception(ex, "mais_view.progresso_diario")

    xp = int(usuario.get("xp") or 0)
    nivel_info = get_level_info(xp)
    nivel_atual = dict(nivel_info.get("atual") or {})
    nivel_nome = str(nivel_atual.get("nome") or usuario.get("nivel") or "Bronze")
    nivel_cor_key = str(nivel_atual.get("cor") or "primaria").strip().lower()
    nivel_cor = CORES.get(nivel_cor_key, DS.A_500)
    faixa_min = int(nivel_atual.get("xp_min") or 0)
    faixa_max_raw = nivel_atual.get("xp_max")
    if faixa_max_raw == float("inf"):
        nivel_next = "MAX"
        nivel_prog = 1.0
    else:
        faixa_max = int(faixa_max_raw or max(500, xp))
        nivel_next = str(faixa_max)
        nivel_prog = max(0.0, min(1.0, (xp - faixa_min) / max(1, faixa_max - faixa_min)))

    perfil_header = ds_card(
        dark=dark,
        content=ft.Column([
            ft.Row([
                ft.Container(content=ft.Text(nome[0].upper() if nome else "U", size=DS.FS_H2, weight=DS.FW_BOLD, color=DS.WHITE), bgcolor=DS.P_500, border_radius=DS.R_PILL, width=56, height=56, alignment=ft.Alignment(0, 0)),
                ft.Column([
                    ft.Text(nome, size=DS.FS_BODY, weight=DS.FW_SEMI, color=DS.text_color(dark)),
                    ft.Text(email, size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                    ds_badge(nivel_nome, color=nivel_cor),
                ], spacing=DS.SP_4, expand=True),
                ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Editar perfil", icon_color=DS.text_sec_color(dark), icon_size=20, on_click=lambda _: navigate("/profile")),
            ], spacing=DS.SP_16, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=DS.SP_8),
            ft.Row([
                ft.Text(f"{xp} XP", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                ft.Container(expand=True),
                ft.Text((f"{nivel_next} XP" if str(nivel_next) != "MAX" else "MAX"), size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
            ]),
            ds_progress_bar(nivel_prog, dark=dark, color=nivel_cor),
        ], spacing=DS.SP_8),
    )

    def _atalho(icon, label, rota, cor=DS.P_500):
        return ft.Container(
            content=ft.Column([
                ft.Container(content=ft.Icon(icon, size=24, color=cor), bgcolor=f"{cor}1A", border_radius=DS.R_LG, padding=DS.SP_16),
                ft.Text(label, size=DS.FS_CAPTION, color=DS.text_color(dark), text_align=ft.TextAlign.CENTER, max_lines=2),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=DS.SP_8),
            on_click=lambda _, r=rota: navigate(r),
            border_radius=DS.R_LG, bgcolor=DS.card_color(dark), border=ft.border.all(1, DS.border_color(dark, 0.08)),
            padding=DS.SP_16, ink=True,
        )

    grid_items = [
        _atalho(ft.Icons.STYLE_OUTLINED, "Flashcards", "/flashcards", DS.A_500),
        _atalho(ft.Icons.EDIT_NOTE_OUTLINED, "Dissertativo", "/open-quiz", DS.INFO),
        _atalho(ft.Icons.LOCAL_LIBRARY_OUTLINED, "Biblioteca", "/library", DS.P_500),
        _atalho(ft.Icons.INSIGHTS_OUTLINED, "Estatisticas", "/stats", DS.WARNING),
        _atalho(ft.Icons.TIMER_OUTLINED, "Simulado", "/simulado", DS.WARNING),
        _atalho(ft.Icons.EMOJI_EVENTS_OUTLINED, "Ranking", "/ranking", DS.WARNING),
        _atalho(ft.Icons.MILITARY_TECH_OUTLINED, "Conquistas", "/conquistas", DS.SUCESSO),
        _atalho(ft.Icons.STARS_OUTLINED, "Planos", "/plans", DS.P_400),
        _atalho(ft.Icons.SETTINGS_OUTLINED, "Configuracoes", "/settings", DS.G_500),
    ]

    grid = ft.ResponsiveRow(
        controls=[ft.Container(col={"xs": 6, "sm": 4, "md": 3}, content=item) for item in grid_items],
        run_spacing=DS.SP_12, spacing=DS.SP_12,
    )

    conta_section = ds_card(
        dark=dark,
        content=ft.Column([
            ft.Row([
                ft.Row([ft.Icon(ft.Icons.DARK_MODE_OUTLINED, size=18, color=DS.text_sec_color(dark)), ft.Text("Modo escuro", size=DS.FS_BODY_S, color=DS.text_color(dark))], spacing=DS.SP_8),
                ft.Switch(value=dark, on_change=toggle_dark, active_color=DS.P_500, scale=0.9),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1, color=DS.border_color(dark, 0.08)),
            ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.LOGOUT, size=18, color=DS.ERRO), ft.Text("Sair", size=DS.FS_BODY_S, color=DS.ERRO, weight=DS.FW_MED)], spacing=DS.SP_8),
                on_click=on_logout, ink=True, border_radius=DS.R_MD, padding=ft.padding.symmetric(vertical=DS.SP_4),
            ),
        ], spacing=DS.SP_12),
    )

    support_email = str(os.getenv("QUIZVANCE_SUPPORT_EMAIL") or "quizvance@gmail.com").strip()

    def _show_legal_dialog(title: str, content_text: str):
        if not page:
            return

        dlg = ft.AlertDialog(
            title=ft.Text(title, size=DS.FS_H3, weight=DS.FW_BOLD, color=DS.text_color(dark)),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(content_text, size=DS.FS_BODY, color=DS.text_color(dark), selectable=True)
                ], scroll=ft.ScrollMode.AUTO),
                width=600,
                height=400,
            ),
            actions=[ft.TextButton("Fechar", on_click=lambda _: close_dialog_compat(page, dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=DS.card_color(dark),
            shape=ft.RoundedRectangleBorder(radius=DS.R_LG)
        )
        show_dialog_compat(page, dlg)

    def _open_support_email(_):
        if not page:
            return
        mailto_link = f"mailto:{support_email}?subject=Suporte%20Quiz%20Vance"
        launch_url_compat(page, mailto_link, "mais.open_support")

    legal_section = ds_card(
        dark=dark,
        content=ft.Column([
            ft.Text("Termos e suporte", size=DS.FS_BODY, weight=DS.FW_SEMI, color=DS.text_color(dark)),
            ft.Text("Clique nos botoes abaixo para ler as politicas no proprio aplicativo.", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
            ft.Row([
                ft.OutlinedButton("Termos de uso", icon=ft.Icons.DESCRIPTION_OUTLINED, on_click=lambda _: _show_legal_dialog("Termos de Uso", TERMOS_DE_USO)),
                ft.OutlinedButton("Privacidade", icon=ft.Icons.POLICY_OUTLINED, on_click=lambda _: _show_legal_dialog("Politica de Privacidade", POLITICA_PRIVACIDADE)),
                ft.OutlinedButton("Reembolso", icon=ft.Icons.ASSIGNMENT_RETURN_OUTLINED, on_click=lambda _: _show_legal_dialog("Politica de Reembolso", POLITICA_REEMBOLSO)),
            ], wrap=True, spacing=DS.SP_8),
            ft.Row([
                ft.Text("Contato:", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                ft.Text(support_email, size=DS.FS_CAPTION, color=DS.text_color(dark), weight=DS.FW_MED),
                ft.TextButton("Abrir suporte", icon=ft.Icons.SUPPORT_AGENT_OUTLINED, on_click=_open_support_email),
            ], wrap=True, spacing=DS.SP_8),
        ], spacing=DS.SP_8),
    )

    return ft.Container(
        expand=True,
        content=ft.Column([perfil_header, ds_section_title("Ferramentas", dark=dark), grid, ds_section_title("Conta", dark=dark), conta_section, ds_section_title("Legal", dark=dark), legal_section, ft.Container(height=DS.SP_32)], spacing=DS.SP_16, scroll=ft.ScrollMode.AUTO),
        padding=DS.SP_16,
    )
