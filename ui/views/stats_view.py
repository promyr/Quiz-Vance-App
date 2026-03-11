# -*- coding: utf-8 -*-
"""View de estatísticas — extraída do main_v2.py."""

from __future__ import annotations

import flet as ft

from config import CORES
from core.error_monitor import log_exception
from core.ui_route_theme import _color
from core.helpers.ui_helpers import (
    close_dialog_compat,
    show_dialog_compat,
)
from ui.design_system import (
    DS,
    ds_badge,
    ds_btn_ghost,
    ds_card,
    ds_section_title,
    ds_stat_card,
)


def build_stats_body(state: dict, navigate, dark: bool) -> ft.Control:
    user = state.get("usuario") or {}
    db = state.get("db")
    page = state.get("page")
    xp = int(user.get("xp", 0) or 0)
    nivel = str(user.get("nivel", "Bronze") or "Bronze")
    acertos = int(user.get("acertos", 0) or 0)
    total = int(user.get("total_questoes", 0) or 0)
    taxa = (acertos / total * 100.0) if total > 0 else 0.0
    progresso_diario = {
        "meta_questoes": int(user.get("meta_questoes_diaria") or 20),
        "questoes_respondidas": 0,
        "streak_dias": int(user.get("streak_dias") or 0),
        "flashcards_revisados": 0,
        "discursivas_corrigidas": 0,
    }
    revisoes_pendentes = 0
    if db and user.get("id"):
        try:
            resumo = db.obter_resumo_estatisticas(int(user["id"]))
            xp = int(resumo.get("xp") or xp)
            nivel = str(resumo.get("nivel") or nivel)
            acertos = int(resumo.get("acertos_total") or acertos)
            total = int(resumo.get("total_questoes") or total)
            taxa = float(resumo.get("taxa_total") or taxa)
            progresso_diario = dict(resumo.get("progresso_diario") or progresso_diario)
            revisoes_pendentes = int(resumo.get("revisoes_pendentes") or 0)
            if state.get("usuario"):
                state["usuario"]["xp"] = xp
                state["usuario"]["nivel"] = nivel
                state["usuario"]["acertos"] = acertos
                state["usuario"]["total_questoes"] = total
                state["usuario"]["streak_dias"] = int(
                    progresso_diario.get("streak_dias", state["usuario"].get("streak_dias", 0))
                )
        except Exception as ex:
            log_exception(ex, "stats_view.build_stats_body.resumo")

    def _open_daily_goal_dialog(_=None):
        if not (db and user.get("id") and page):
            return
        try:
            current_meta = int((db.obter_progresso_diario(int(user["id"])) or {}).get("meta_questoes") or 20)
        except Exception:
            current_meta = int(progresso_diario.get("meta_questoes") or 20)
        meta_field = ft.TextField(
            label="Meta diaria de questoes",
            value=str(current_meta),
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
        )

        def _apply_preset(v: int):
            meta_field.value = str(int(v))
            meta_field.error_text = None
            try:
                meta_field.update()
            except Exception:
                pass

        dialog_ref = {"dlg": None}

        def _save_goal(_evt=None):
            raw = str(meta_field.value or "").strip()
            if not raw.isdigit():
                meta_field.error_text = "Digite um numero entre 5 e 200."
                if page:
                    page.update()
                return
            value = max(5, min(200, int(raw)))
            try:
                db.atualizar_meta_diaria(int(user["id"]), int(value))
                if state.get("usuario"):
                    state["usuario"]["meta_questoes_diaria"] = int(value)
                state.get("view_cache", {}).pop("/home", None)
                state.get("view_cache", {}).pop("/stats", None)
                close_dialog_compat(page, dialog_ref.get("dlg"))
                if page:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Meta diaria atualizada para {value} questoes."),
                        bgcolor=CORES["sucesso"],
                        show_close_icon=True,
                    )
                    page.snack_bar.open = True
                navigate("/stats")
            except Exception as ex_goal:
                log_exception(ex_goal, "stats_view.update_daily_goal")
                meta_field.error_text = "Nao foi possivel salvar a meta agora."
                if page:
                    page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Definir meta diaria"),
            content=ft.Column(
                [
                    ft.Text("Escolha quantas questoes deseja resolver por dia.", size=13, color=_color("texto_sec", dark)),
                    meta_field,
                    ft.Row(
                        [
                            ft.TextButton("10", on_click=lambda _e: _apply_preset(10)),
                            ft.TextButton("20", on_click=lambda _e: _apply_preset(20)),
                            ft.TextButton("30", on_click=lambda _e: _apply_preset(30)),
                            ft.TextButton("50", on_click=lambda _e: _apply_preset(50)),
                        ],
                        spacing=6,
                    ),
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: close_dialog_compat(page, dialog_ref.get("dlg"))),
                ft.TextButton("Salvar", on_click=_save_goal),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialog_ref["dlg"] = dialog
        show_dialog_compat(page, dialog)

    recado = "Constancia > perfeicao: mantenha o ritmo diario."
    if taxa >= 75:
        recado = "Excelente precisao. Vale subir dificuldade em parte das sessoes."
    elif taxa >= 50:
        recado = "Bom caminho. Priorize revisao dos erros para ganhar consistencia."

    resumo_cards = ft.ResponsiveRow(
        controls=[
            ds_stat_card(ft.Icons.STARS_OUTLINED, "XP Total", str(xp), dark=dark, col={"sm": 6, "md": 3}, icon_color=DS.P_500),
            ds_stat_card(ft.Icons.SHIELD_OUTLINED, "Nivel", str(nivel), dark=dark, col={"sm": 6, "md": 3}, icon_color=DS.INFO),
            ds_stat_card(ft.Icons.CHECK_CIRCLE_OUTLINE, "Taxa de acerto", f"{taxa:.1f}%", dark=dark, col={"sm": 6, "md": 3}, icon_color=DS.SUCESSO),
            ds_stat_card(
                ft.Icons.TASK_ALT_OUTLINED,
                "Meta diaria",
                f"{int(progresso_diario.get('questoes_respondidas', 0))}/{int(progresso_diario.get('meta_questoes', 20))}",
                subtitle="Toque para ajustar",
                dark=dark,
                col={"sm": 6, "md": 3},
                icon_color=DS.WARNING,
                on_click=_open_daily_goal_dialog,
            ),
        ],
        spacing=8,
        run_spacing=8,
    )

    atividade_card = ds_card(
        dark=dark,
        padding=12,
        content=ft.Column(
            [
                ft.Text("Atividade de hoje", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Row(
                    [
                        ds_badge(f"{int(progresso_diario.get('flashcards_revisados', 0))} flashcards", color=CORES["primaria"]),
                        ds_badge(f"{int(progresso_diario.get('discursivas_corrigidas', 0))} discursivas", color=CORES["acento"]),
                        ds_badge(f"Sequência {int(progresso_diario.get('streak_dias', 0))} dia(s)", color=CORES["warning"]),
                        ds_badge(f"{int(revisoes_pendentes)} revisoes pendentes", color=CORES["erro"]),
                    ],
                    wrap=True,
                    spacing=8,
                ),
                ft.Text(recado, size=12, color=_color("texto_sec", dark)),
            ],
            spacing=10,
        ),
    )

    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ds_section_title("Estatisticas", dark=dark),
                ft.Text("Resumo rapido do desempenho.", size=14, color=_color("texto_sec", dark)),
                resumo_cards,
                atividade_card,
                ds_btn_ghost("Voltar ao Inicio", icon=ft.Icons.HOME_OUTLINED, on_click=lambda _: navigate("/home"), dark=dark),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
