# -*- coding: utf-8 -*-
"""View de plano semanal — extraída do main_v2.py."""

from __future__ import annotations

import asyncio
import datetime
from typing import Optional

import flet as ft

from config import CORES
from core.datetime_utils import _format_exam_date_input, _parse_br_date
from core.error_monitor import log_exception
from core.ui_route_theme import _color
from core.helpers.ai_helpers import create_user_ai_service, schedule_ai_task
from core.helpers.ui_helpers import set_feedback_text


def _screen_width_local(page) -> float:
    """Reimplementação local de _screen_width para evitar import circular."""
    if not page:
        return 1280.0
    width = getattr(page, "width", None)
    if width:
        try:
            v = float(width)
            if v > 0:
                return v
        except Exception:
            pass
    window_width = getattr(page, "window_width", None)
    if window_width:
        try:
            v = float(window_width)
            if v > 0:
                return v
        except Exception:
            pass
    return 1280.0


def _start_prioritized_session_local(state: dict, navigate):
    """Reimplementação local de _start_prioritized_session."""
    user = state.get("usuario") or {}
    db = state.get("db")
    if not db or not user.get("id"):
        navigate("/quiz")
        return
    try:
        preset = db.sugerir_estudo_agora(user["id"])
        state["quiz_preset"] = preset
        navigate("/quiz")
    except Exception as ex:
        log_exception(ex, "study_plan_view._start_prioritized_session")
        navigate("/quiz")


def build_study_plan_body(state: dict, navigate, dark: bool) -> ft.Control:
    page = state.get("page")
    screen_w = _screen_width_local(page)
    compact = screen_w < 1000
    very_compact = screen_w < 760
    form_width = max(150, min(360, int(screen_w - 120)))
    user = state.get("usuario") or {}
    db = state.get("db")
    objetivo_field = ft.TextField(label="Objetivo", width=form_width if compact else 360, hint_text="Ex.: Aprovacao TRT, ENEM 2026")
    data_prova_field = ft.TextField(
        label="Data da prova",
        width=max(130, min(180, int(form_width * 0.45))) if compact else 180,
        hint_text="DD/MM/AAAA",
        keyboard_type=ft.KeyboardType.NUMBER,
        max_length=10,
    )
    tempo_diario_field = ft.TextField(label="Tempo diario (min)", width=max(130, min(180, int(form_width * 0.45))) if compact else 180, hint_text="90")
    status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    loading = ft.ProgressRing(width=22, height=22, visible=False)
    itens_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]

    def _on_data_prova_change(e):
        formatted = _format_exam_date_input(getattr(e.control, "value", ""))
        if formatted != getattr(e.control, "value", ""):
            e.control.value = formatted
            e.control.update()

    data_prova_field.on_change = _on_data_prova_change

    def _plan_day_limit(data_prova: str) -> Optional[int]:
        prova_dt = _parse_br_date(data_prova)
        if not prova_dt:
            return None
        today = datetime.date.today()
        delta = (prova_dt - today).days
        if delta < 0:
            return 0
        return max(1, min(7, delta + 1))

    def _normalize_plan_items(raw_items: list, topicos: list[str], tempo_diario: int, limite_dias: int) -> list[dict]:
        itens_norm = []
        for i, item in enumerate(list(raw_items or [])):
            if i >= limite_dias:
                break
            if not isinstance(item, dict):
                continue
            itens_norm.append({
                "dia": str(item.get("dia") or dias_semana[i]),
                "tema": str(item.get("tema") or topicos[i % len(topicos)]),
                "atividade": str(item.get("atividade") or "Questoes + revisao de erros + flashcards"),
                "duracao_min": int(item.get("duracao_min") or tempo_diario),
                "prioridade": int(item.get("prioridade") or (1 if i < 3 else 2)),
            })
        while len(itens_norm) < limite_dias:
            i = len(itens_norm)
            itens_norm.append({
                "dia": dias_semana[i],
                "tema": topicos[i % len(topicos)],
                "atividade": "Questoes + revisao de erros + flashcards",
                "duracao_min": tempo_diario,
                "prioridade": 1 if i < 3 else 2,
            })
        return itens_norm

    def _render_plan():
        itens_column.controls.clear()
        if not db or not user.get("id"):
            itens_column.controls.append(ft.Text("Usuario nao autenticado.", color=CORES["erro"]))
            return
        data = db.obter_plano_ativo(user["id"])
        plan = data.get("plan")
        itens = data.get("itens") or []
        if not plan:
            itens_column.controls.append(ft.Text("Nenhum plano ativo. Gere um novo plano semanal.", color=_color("texto_sec", dark)))
            return
        itens_column.controls.append(ft.Container(
            padding=10, border_radius=8, bgcolor=_color("card", dark),
            content=ft.Row([
                ft.Text(f"Objetivo: {plan.get('objetivo') or '-'}", weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Container(expand=True),
                ft.Text(f"Prova: {plan.get('data_prova') or '-'}", size=12, color=_color("texto_sec", dark)),
            ]),
        ))
        for item in itens:
            def _mk_toggle(iid):
                def _on_change(e):
                    if not db:
                        return
                    db.marcar_item_plano(iid, bool(e.control.value))
                    _render_plan()
                    if page:
                        page.update()
                return _on_change
            itens_column.controls.append(ft.Container(
                padding=10, border_radius=8, bgcolor=_color("card", dark),
                content=ft.Row([
                    ft.Checkbox(value=bool(item.get("concluido")), on_change=_mk_toggle(item["id"])),
                    ft.Column([
                        ft.Text(f"{item.get('dia')} - {item.get('tema')}", weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ft.Text(f"{item.get('atividade')} ({item.get('duracao_min')} min)", size=12, color=_color("texto_sec", dark)),
                    ], spacing=2, expand=True),
                ], spacing=10),
            ))

    async def _gerar_plano_async():
        if not db or not user.get("id") or not page:
            return
        objetivo = (objetivo_field.value or "").strip() or "Aprovacao"
        data_prova = (data_prova_field.value or "").strip() or "-"
        limite_dias = 7
        if data_prova != "-":
            limite_inferido = _plan_day_limit(data_prova)
            if limite_inferido is None:
                set_feedback_text(status_text, "Data invalida. Use DD/MM/AAAA.", "warning")
                page.update()
                return
            if limite_inferido <= 0:
                set_feedback_text(status_text, "A data da prova ja passou. Informe uma data futura.", "warning")
                page.update()
                return
            limite_dias = limite_inferido
        try:
            tempo_diario = max(30, min(360, int((tempo_diario_field.value or "90").strip())))
        except ValueError:
            tempo_diario = 90
        loading.visible = True
        status_text.value = "Gerando plano semanal..."
        page.update()
        topicos = [r.get("tema", "Geral") for r in db.topicos_revisao(user["id"], limite=5)] or ["Geral"]
        service = create_user_ai_service(user)
        itens = []
        try:
            if service:
                itens = await asyncio.to_thread(service.generate_study_plan, objetivo, data_prova, tempo_diario, topicos)
            if not itens:
                itens = [{"dia": d, "tema": topicos[i % len(topicos)], "atividade": "Questoes + revisao de erros + flashcards", "duracao_min": tempo_diario, "prioridade": 1 if i < 3 else 2} for i, d in enumerate(dias_semana[:limite_dias])]
            itens = _normalize_plan_items(itens, topicos, tempo_diario, limite_dias)
            db.salvar_plano_semanal(user["id"], objetivo, data_prova, tempo_diario, itens)
            if limite_dias < 7:
                status_text.value = f"Plano ajustado ao prazo real: {limite_dias} dia(s) ate a prova."
            else:
                status_text.value = "Plano semanal criado."
            _render_plan()
        except Exception as ex:
            log_exception(ex, "study_plan_view._gerar_plano_async")
            status_text.value = "Falha ao gerar plano."
        finally:
            loading.visible = False
            page.update()

    def _gerar_plano_click(_):
        if page:
            schedule_ai_task(page, state, _gerar_plano_async, message="IA gerando plano semanal...", status_control=status_text)

    _render_plan()
    return ft.Container(
        expand=True, bgcolor=_color("fundo", dark), padding=20,
        content=ft.Column([
            ft.Text("Plano Semanal", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
            ft.Text("Gere um plano adaptativo e marque o progresso diario.", size=14, color=_color("texto_sec", dark)),
            ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                ft.Text("Configuracao do plano", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.ResponsiveRow([
                    ft.Container(content=objetivo_field, col={"xs": 12, "md": 6}),
                    ft.Container(content=data_prova_field, col={"xs": 6, "md": 3}),
                    ft.Container(content=tempo_diario_field, col={"xs": 6, "md": 3}),
                ], spacing=12, run_spacing=8),
                ft.ResponsiveRow([
                    ft.Container(col={"xs": 12, "md": 3}, content=ft.ElevatedButton("Gerar plano", icon=ft.Icons.AUTO_AWESOME, on_click=_gerar_plano_click, expand=True)),
                    ft.Container(col={"xs": 12, "md": 6}, content=ft.Row([loading, ft.Container(content=status_text, expand=True)], spacing=10)),
                    ft.Container(col={"xs": 12, "md": 3}, content=ft.ElevatedButton("Estudar agora", icon=ft.Icons.PLAY_ARROW, on_click=lambda _: _start_prioritized_session_local(state, navigate), expand=True)),
                ], run_spacing=6, spacing=8 if very_compact else 10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=8))),
            ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                ft.Text("Itens do plano", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                itens_column,
            ], spacing=8))),
            ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
        ], spacing=12, expand=True, scroll=ft.ScrollMode.AUTO),
    )
