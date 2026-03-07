# -*- coding: utf-8 -*-
"""View de onboarding/boas-vindas — extraída do main_v2.py."""

from __future__ import annotations

import flet as ft

from config import CORES
from core.datetime_utils import _format_datetime_label
from core.error_monitor import log_exception
from core.ui_route_theme import _color
from core.helpers.ai_helpers import resolve_user_api_key


def _screen_width_local(page) -> float:
    if not page:
        return 1280.0
    for attr in ("width", "window_width"):
        v = getattr(page, attr, None)
        if v:
            try:
                fv = float(v)
                if fv > 0:
                    return fv
            except Exception:
                pass
    return 1280.0


def build_onboarding_body(state: dict, navigate, dark: bool) -> ft.Control:
    page = state.get("page")
    user = state.get("usuario") or {}
    db = state.get("db")
    screen_w = _screen_width_local(page)
    compact = screen_w < 960
    mobile = screen_w < 760
    needs_setup = (not user.get("oauth_google")) and (not resolve_user_api_key(user))

    plan_code = str(user.get("plan_code") or "free").lower()
    premium_active = bool(int(user.get("premium_active") or 0))
    premium_until = _format_datetime_label(user.get("premium_until"))
    trial_active = plan_code == "trial" and premium_active

    status_text = ft.Text("", size=12, color=_color("texto_sec", dark))

    def finish_onboarding(_):
        try:
            uid = user.get("id")
            if uid and db:
                db.marcar_onboarding_visto(int(uid))
            if uid and state.get("usuario"):
                state["usuario"]["onboarding_seen"] = 1
            if needs_setup:
                navigate("/settings")
            else:
                navigate("/home")
        except Exception as ex:
            log_exception(ex, "onboarding_view.finish_onboarding")
            status_text.value = "Falha ao concluir boas-vindas. Tente novamente."
            status_text.color = CORES["erro"]
            if page:
                page.update()

    def _feature_line(text: str):
        return ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=CORES["primaria"]), ft.Text(text, size=12, color=_color("texto_sec", dark), expand=True)], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START)

    intro_card = ft.Card(elevation=1, content=ft.Container(padding=14 if mobile else 16, content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.WAVING_HAND, color=CORES["primaria"], size=22), ft.Text("Boas-vindas ao Quiz Vance", size=20 if mobile else 24, weight=ft.FontWeight.BOLD, color=_color("texto", dark))], spacing=8, wrap=True),
        ft.Text("Este painel aparece no login de contas Free para destacar os beneficios Premium.", size=13, color=_color("texto_sec", dark)),
        ft.Container(height=2),
        _feature_line("1) Escolha um modulo: Questoes, Flashcards, Biblioteca ou Dissertativo."),
        _feature_line("2) Gere sua sessao de estudo com IA e acompanhe seu progresso."),
        _feature_line("3) Use o menu para navegar e ajustar tema, perfil e configuracoes."),
    ], spacing=8)))

    free_card = ft.Card(elevation=1, content=ft.Container(padding=14, content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.LOCK_OPEN, size=20, color=CORES["acento"]), ft.Text("Conta Free", size=17, weight=ft.FontWeight.BOLD, color=_color("texto", dark))], spacing=8),
        _feature_line("Questoes e flashcards com modo economico."),
        _feature_line("Correcao de dissertativa: 1 por dia."),
        _feature_line("Acesso completo ao painel e biblioteca."),
    ], spacing=8)))

    premium_card = ft.Card(elevation=1, content=ft.Container(padding=14, content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.WORKSPACE_PREMIUM, size=20, color=CORES["primaria"]), ft.Text("Conta Premium", size=17, weight=ft.FontWeight.BOLD, color=_color("texto", dark))], spacing=8),
        _feature_line("Respostas mais rapidas e qualidade maxima dos modelos."),
        _feature_line("Mais produtividade para sessoes longas."),
        _feature_line("Melhor custo-beneficio para uso diario intenso."),
    ], spacing=8)))

    trial_title = "Cortesia ativa: 1 dia de Premium" if trial_active else "Cortesia de 1 dia para novos usuarios"
    trial_subtitle = (f"Seu periodo de cortesia vai ate {premium_until}." if premium_until else "A cortesia e aplicada automaticamente na criacao da conta.")
    if (not trial_active) and premium_until:
        trial_subtitle = f"Cortesia registrada ate {premium_until}. Veja os planos para continuar."

    trial_card = ft.Card(elevation=1, content=ft.Container(padding=14, content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.CARD_GIFTCARD, size=20, color=CORES["warning"]), ft.Text(trial_title, size=17, weight=ft.FontWeight.BOLD, color=_color("texto", dark))], spacing=8, wrap=True),
        ft.Text(trial_subtitle, size=13, color=_color("texto_sec", dark)),
        ft.Row([
            ft.ElevatedButton("Ver planos", icon=ft.Icons.STARS, on_click=lambda _: navigate("/plans")),
            ft.OutlinedButton("Comecar agora", icon=ft.Icons.ARROW_FORWARD, on_click=finish_onboarding),
        ], spacing=10, wrap=True),
        status_text,
    ], spacing=8)))

    config_hint = ft.Container()
    if needs_setup:
        config_hint = ft.Container(padding=10, border_radius=10, bgcolor=ft.Colors.with_opacity(0.08, CORES["warning"]),
                                   content=ft.Text("Antes de estudar com IA, configure provider, modelo e API key na tela de Configuracoes.", size=12, color=_color("texto", dark)))

    return ft.Container(
        expand=True, bgcolor=_color("fundo", dark), padding=12 if mobile else 18,
        content=ft.Column([
            intro_card,
            ft.ResponsiveRow(controls=[
                ft.Container(col={"sm": 12, "md": 6}, content=free_card),
                ft.Container(col={"sm": 12, "md": 6}, content=premium_card),
            ], spacing=10, run_spacing=10),
            trial_card,
            config_hint,
        ], spacing=10 if compact else 12, scroll=ft.ScrollMode.AUTO, expand=True),
    )
