# -*- coding: utf-8 -*-
"""View da tela inicial (Home) — extraída do main_v2.py."""

from __future__ import annotations

import datetime

import flet as ft

from config import CORES
from core.error_monitor import log_exception
from core.ui_route_theme import _color
from ui.design_system import (
    DS,
    ds_badge,
    ds_btn_primary,
    ds_btn_secondary,
    ds_card,
    ds_progress_bar,
    ds_stat_card,
)


def build_home_body(state: dict, navigate, dark: bool) -> ft.Control:
    usuario = state.get("usuario") or {}
    db = state.get("db")
    nome = usuario.get("nome", "Usuario")

    progresso = {
        "meta_questoes": int(usuario.get("meta_questoes_diaria") or 20),
        "questoes_respondidas": 0,
        "acertos": 0,
        "progresso_meta": 0.0,
        "streak_dias": int(usuario.get("streak_dias") or 0),
        "pct_acerto_7d": 0.0,
        "pct_acerto_30d": 0.0,
        "revisoes_pendentes": 0,
        "ultima_sessao_rota": None,
        "ultima_sessao_label": None,
    }
    if db and usuario.get("id"):
        try:
            resumo = db.obter_resumo_estatisticas(int(usuario["id"]))
            pd = dict(resumo.get("progresso_diario") or {})
            if pd:
                progresso.update(pd)
            progresso["revisoes_pendentes"] = int(resumo.get("revisoes_pendentes") or 0)
            if state.get("usuario"):
                state["usuario"]["xp"] = int(resumo.get("xp") or state["usuario"].get("xp", 0))
                state["usuario"]["nivel"] = str(resumo.get("nivel") or state["usuario"].get("nivel", "Bronze"))
                state["usuario"]["acertos"] = int(resumo.get("acertos_total") or state["usuario"].get("acertos", 0))
                state["usuario"]["total_questoes"] = int(resumo.get("total_questoes") or state["usuario"].get("total_questoes", 0))
                state["usuario"]["streak_dias"] = int(progresso.get("streak_dias", state["usuario"].get("streak_dias", 0)))
        except Exception as ex:
            log_exception(ex, "home_view.progresso_diario")

    streak = int(progresso.get("streak_dias") or 0)
    respondidas = int(progresso.get("questoes_respondidas") or 0)
    meta = int(progresso.get("meta_questoes") or 20)
    acertos = int(progresso.get("acertos") or 0)
    pct_acerto = round((acertos / respondidas * 100) if respondidas > 0 else 0)
    revisoes_pend = int(progresso.get("revisoes_pendentes") or 0)
    progresso_meta = min(1.0, respondidas / max(meta, 1))

    hora = datetime.datetime.now().hour
    if hora < 12:
        saudacao_label = "Bom dia"
    elif hora < 18:
        saudacao_label = "Boa tarde"
    else:
        saudacao_label = "Boa noite"

    streak_emoji = "\U0001f525" if streak > 0 else "\U0001f4aa"
    streak_text = f"{streak} dia{'s' if streak != 1 else ''} de sequencia" if streak > 0 else "Comece sua sequencia hoje!"

    saudacao = ft.Column(
        [
            ft.Text(f"{saudacao_label}, {nome.split()[0]}!", size=DS.FS_H2, weight=DS.FW_BOLD, color=DS.text_color(dark)),
            ft.Row(
                [ft.Text(streak_emoji, size=18), ft.Text(streak_text, size=DS.FS_BODY_S, color=DS.text_sec_color(dark))],
                spacing=DS.SP_4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        spacing=DS.SP_4,
    )

    stat_cards = [
        ds_stat_card(col={"xs": 6, "sm": 6, "md": 3}, height=172, icon=ft.Icons.TODAY_OUTLINED, label="Questoes hoje", value=f"{respondidas}/{meta}", subtitle=f"{int(progresso_meta*100)}% da meta", dark=dark, icon_color=DS.P_500, on_click=lambda _: navigate("/stats")),
        ds_stat_card(col={"xs": 6, "sm": 6, "md": 3}, height=172, icon=ft.Icons.TRACK_CHANGES_OUTLINED, label="% Acerto (hoje)", value=f"{pct_acerto}%", subtitle=f"{acertos} de {respondidas} certas", dark=dark, icon_color=DS.SUCESSO if pct_acerto >= 70 else DS.WARNING, trend_up=pct_acerto >= 70 if respondidas > 0 else None),
        ds_stat_card(col={"xs": 6, "sm": 6, "md": 3}, height=172, icon=ft.Icons.REPLAY_OUTLINED, label="Revisoes pendentes", value=str(revisoes_pend), subtitle="Clique para revisar", dark=dark, icon_color=DS.ERRO if revisoes_pend > 5 else DS.A_500, on_click=lambda _: navigate("/revisao")),
        ds_stat_card(col={"xs": 6, "sm": 6, "md": 3}, height=172, icon=ft.Icons.LOCAL_FIRE_DEPARTMENT_OUTLINED, label="Sequencia", value=f"{streak}" if streak > 0 else "0", subtitle="dias consecutivos", dark=dark, icon_color=DS.WARNING),
    ]

    meta_card = ds_card(
        dark=dark,
        content=ft.Column([
            ft.Row([
                ft.Text("Meta Diaria", size=DS.FS_BODY, weight=DS.FW_SEMI, color=DS.text_color(dark)),
                ft.Text(f"{respondidas}/{meta} questoes", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ds_progress_bar(progresso_meta, dark=dark, height=10, color=DS.P_500),
            ft.ResponsiveRow([
                ft.Container(col={"xs": 12, "md": 6}, content=ds_btn_primary(
                    "Continuar estudando" if respondidas > 0 else "Comecar agora",
                    on_click=lambda _: navigate("/quiz"), icon=ft.Icons.PLAY_ARROW_ROUNDED, dark=dark, height=44, expand=True,
                )),
                ft.Container(col={"xs": 12, "md": 6}, content=ds_btn_secondary(
                    "Ver revisoes", on_click=lambda _: navigate("/revisao"), icon=ft.Icons.REPLAY_OUTLINED, dark=dark, height=44, expand=True,
                ), visible=revisoes_pend > 0),
            ], spacing=DS.SP_12, run_spacing=DS.SP_8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=DS.SP_12),
    )

    tema_input = ft.TextField(hint_text="Ex.: Direito Constitucional, Calculo I", border_radius=DS.R_MD, expand=True, dense=True, on_submit=lambda e: _iniciar_tema(e.control.value))

    def _iniciar_tema(tema_valor: str = None):
        tema = (tema_valor or tema_input.value or "").strip()
        if not tema:
            return
        state["quiz_preset"] = {"topic": tema, "count": "10", "difficulty": "intermediario"}
        navigate("/quiz")

    tema_card = ds_card(
        dark=dark,
        content=ft.Column([
            ft.Row([
                ft.Container(content=ft.Icon(ft.Icons.AUTO_AWESOME, size=22, color=DS.P_500), bgcolor=f"{DS.P_500}1A", border_radius=DS.R_MD, padding=DS.SP_12),
                ft.Column([
                    ft.Text("Estudar um tema com IA", size=DS.FS_BODY, weight=DS.FW_SEMI, color=DS.text_color(dark)),
                    ft.Text("Gere questoes personalizadas em segundos", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                ], spacing=DS.SP_4, expand=True),
            ], spacing=DS.SP_12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.ResponsiveRow([
                ft.Container(col={"xs": 12, "md": 9}, content=tema_input),
                ft.Container(col={"xs": 12, "md": 3}, content=ds_btn_primary("Gerar", on_click=lambda _: _iniciar_tema(), icon=ft.Icons.ARROW_FORWARD_ROUNDED, dark=dark, height=DS.TAP_MIN, expand=True)),
            ], spacing=DS.SP_8, run_spacing=DS.SP_8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=DS.SP_12),
        border_color=DS.P_300 if not dark else DS.P_900,
    )

    return ft.Container(
        expand=True,
        content=ft.Column([saudacao, ft.Container(height=DS.SP_4), ft.ResponsiveRow(controls=stat_cards, columns=12, spacing=DS.SP_12, run_spacing=DS.SP_12), meta_card, tema_card, ft.Container(height=DS.SP_32)], spacing=DS.SP_16, scroll=ft.ScrollMode.AUTO, expand=True),
        padding=DS.SP_16,
    )
