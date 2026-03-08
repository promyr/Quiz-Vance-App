# -*- coding: utf-8 -*-
"""View de configuraÃ§Ãµes â€” extraÃ­da do main_v2.py."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import flet as ft

from config import AI_PROVIDERS, CORES
from core.error_monitor import log_exception, log_event
from core.ui_route_theme import _color
from core.helpers.ai_helpers import (
    extract_user_api_keys,
    normalize_ai_provider,
    provider_api_field,
)
from core.helpers.ui_helpers import (
    backend_user_id,
    close_dialog_compat,
    launch_url_compat,
    set_feedback_text,
    show_dialog_compat,
)

_AI_KEY_PROVIDERS = ("gemini", "openai", "groq")


def _screen_width_local(page) -> float:
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


def _build_placeholder_body(title, description, navigate, dark):
    return ft.Container(
        expand=True, bgcolor=_color("fundo", dark), padding=20,
        content=ft.Column([
            ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
            ft.Text(description, size=14, color=_color("texto_sec", dark)),
            ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
        ], spacing=10),
    )


def build_settings_body(state: dict, navigate, dark: bool) -> ft.Control:
    user = state.get("usuario") or {}
    db = state["db"]
    page = state.get("page")
    screen_w = _screen_width_local(page)
    compact = screen_w < 1000
    very_compact = screen_w < 760
    form_width = min(520, max(230, int(screen_w - (84 if very_compact else 120))))
    user_id = user.get("id")
    if not user_id:
        return _build_placeholder_body("Configuracoes", "E necessario estar logado para alterar as configuracoes.", navigate, dark)

    def _normalize_provider(value: str) -> str:
        raw = str(value or "").strip().lower()
        if raw in AI_PROVIDERS:
            return raw
        for key, cfg in AI_PROVIDERS.items():
            if raw == str(cfg.get("name", "")).strip().lower():
                return key
        return "gemini"

    provider_links = {
        "gemini": "https://aistudio.google.com/app/apikey",
        "openai": "https://platform.openai.com/api-keys",
        "groq": "https://console.groq.com/keys",
    }

    api_keys = extract_user_api_keys(user)
    current_provider = _normalize_provider(user.get("provider") or "gemini")
    provider_dropdown = ft.Dropdown(
        label="Provider IA",
        options=[ft.dropdown.Option(k, text=v["name"]) for k, v in AI_PROVIDERS.items()],
        value=current_provider,
        width=form_width if compact else 260,
    )
    model_dropdown_ref = {"control": None}

    def _build_model_dropdown(provider_key: str, selected_model: str = None):
        modelos = list(AI_PROVIDERS.get(provider_key, AI_PROVIDERS["gemini"]).get("models") or [])
        if not modelos:
            modelos = [AI_PROVIDERS["gemini"]["default_model"]]
        default_model = AI_PROVIDERS.get(provider_key, AI_PROVIDERS["gemini"]).get("default_model") or modelos[0]
        chosen = selected_model if selected_model in modelos else default_model
        dd = ft.Dropdown(label="Modelo padrao", options=[ft.dropdown.Option(m) for m in modelos], value=chosen, width=form_width if compact else 360)
        model_dropdown_ref["control"] = dd
        return dd

    model_dropdown_slot = ft.Container(content=_build_model_dropdown(current_provider, user.get("model") or AI_PROVIDERS[current_provider]["default_model"]))
    key_status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    key_manage_button = ft.OutlinedButton("Configurar chaves por provider", icon=ft.Icons.KEY, on_click=lambda _: None)
    economia_mode_switch = ft.Switch(value=bool(user.get("economia_mode")))
    telemetry_opt_in_switch = ft.Switch(value=bool(user.get("telemetry_opt_in")))
    save_feedback = ft.Text("", size=12, color=_color("texto_sec", dark), visible=False)

    def _open_external_link(url: str):
        if not page:
            return
        try:
            launch_url_compat(page, url, "settings_open_external_link")
        except Exception as ex:
            log_exception(ex, "settings_open_external_link")

    def _mask_key(value: str) -> str:
        txt = str(value or "").strip()
        if not txt:
            return ""
        if len(txt) <= 8:
            return "*" * len(txt)
        return f"{txt[:4]}...{txt[-4:]}"

    def _update_key_status():
        provider_value = _normalize_provider(provider_dropdown.value or "gemini")
        provider_name = AI_PROVIDERS.get(provider_value, {}).get("name", provider_value)
        key_value = str(api_keys.get(provider_value) or "").strip()
        key_manage_button.text = f"Chaves de API ({provider_name})"
        key_manage_button.icon = ft.Icons.KEY
        if key_value:
            key_status_text.value = f"Chave ativa de {provider_name}: {_mask_key(key_value)}"
            key_status_text.color = _color("sucesso", dark)
        else:
            key_status_text.value = f"Sem chave salva para {provider_name}. Configure para usar IA nesse provider."
            key_status_text.color = _color("warning", dark)
        if page:
            try:
                key_status_text.update()
                key_manage_button.update()
            except Exception:
                pass

    def _open_key_dialog(initial_provider: Optional[str] = None):
        if not page:
            return
        selected_provider_ref = {"value": _normalize_provider(initial_provider or provider_dropdown.value or "gemini")}
        link_ref = {"url": provider_links.get(selected_provider_ref["value"], "")}
        provider_dd = ft.Dropdown(
            label="Provider da chave",
            options=[ft.dropdown.Option(k, text=v["name"]) for k, v in AI_PROVIDERS.items()],
            value=selected_provider_ref["value"],
            width=340 if not compact else min(360, form_width),
        )
        key_field = ft.TextField(label="API key", hint_text="Cole a chave desse provider", width=420 if not compact else min(420, form_width), password=True, can_reveal_password=True, value=str(api_keys.get(selected_provider_ref["value"]) or ""))
        helper_text = ft.Text("", size=12, color=_color("texto_sec", dark))
        open_link_btn = ft.TextButton("Abrir portal de chave", icon=ft.Icons.OPEN_IN_NEW)
        dialog_ref = {"dlg": None}

        def _refresh_dialog_provider(_=None):
            provider_sel = _normalize_provider(provider_dd.value or selected_provider_ref["value"])
            provider_dd.value = provider_sel
            selected_provider_ref["value"] = provider_sel
            provider_name = AI_PROVIDERS.get(provider_sel, {}).get("name", provider_sel)
            link_ref["url"] = provider_links.get(provider_sel, "")
            key_field.value = str(api_keys.get(provider_sel) or "")
            helper_text.value = f"Essa chave sera usada apenas no provider {provider_name}."
            if dialog_ref.get("dlg") is not None:
                try:
                    dialog_ref["dlg"].title = ft.Text(f"API key - {provider_name}")
                    dialog_ref["dlg"].update()
                except Exception:
                    pass

        def _open_selected_portal(_):
            url = str(link_ref.get("url") or "").strip()
            if url:
                _open_external_link(url)

        def _save_key(_):
            provider_sel = _normalize_provider(selected_provider_ref["value"])
            api_keys[provider_sel] = str(key_field.value or "").strip()
            close_dialog_compat(page, dialog_ref.get("dlg"))
            _update_key_status()
            if page:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Chave salva para {AI_PROVIDERS.get(provider_sel, {}).get('name', provider_sel)}"), bgcolor=CORES["sucesso"], show_close_icon=True)
                page.snack_bar.open = True
                page.update()

        def _clear_key(_):
            provider_sel = _normalize_provider(selected_provider_ref["value"])
            api_keys[provider_sel] = ""
            key_field.value = ""
            close_dialog_compat(page, dialog_ref.get("dlg"))
            _update_key_status()
            if page:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Chave removida de {AI_PROVIDERS.get(provider_sel, {}).get('name', provider_sel)}"), bgcolor=CORES["warning"], show_close_icon=True)
                page.snack_bar.open = True
                page.update()

        provider_dd.on_change = _refresh_dialog_provider
        provider_dd.on_select = _refresh_dialog_provider
        open_link_btn.on_click = _open_selected_portal
        _refresh_dialog_provider()

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("API key"),
            content=ft.Container(width=min(460, int(form_width + 40)), content=ft.Column([provider_dd, key_field, helper_text, open_link_btn], spacing=8, tight=True)),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog_compat(page, dialog_ref.get("dlg"))),
                ft.TextButton("Limpar", on_click=_clear_key),
                ft.ElevatedButton("Salvar chave", icon=ft.Icons.SAVE, on_click=_save_key),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialog_ref["dlg"] = dlg
        show_dialog_compat(page, dlg)

    key_manage_button.on_click = lambda _: _open_key_dialog(provider_dropdown.value)

    economia_row = ft.ResponsiveRow([
        ft.Container(col={"xs": 2, "md": 1}, content=economia_mode_switch),
        ft.Container(col={"xs": 10, "md": 11}, content=ft.Text("Modo economia (prioriza modelos mais baratos/estaveis)", size=12 if very_compact else 13, color=_color("texto", dark))),
    ], spacing=8, run_spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    telemetry_row = ft.ResponsiveRow([
        ft.Container(col={"xs": 2, "md": 1}, content=telemetry_opt_in_switch),
        ft.Container(col={"xs": 10, "md": 11}, content=ft.Text("Telemetria anonima (opt-in para melhorias do produto)", size=12 if very_compact else 13, color=_color("texto", dark))),
    ], spacing=8, run_spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _on_provider_change(e):
        selecionado = _normalize_provider(getattr(e.control, "value", None))
        provider_dropdown.value = selecionado
        modelo_atual = model_dropdown_ref.get("control").value if model_dropdown_ref.get("control") else None
        model_dropdown_slot.content = _build_model_dropdown(selecionado, modelo_atual)
        model_dropdown_slot.update()
        _update_key_status()

    provider_dropdown.on_select = _on_provider_change
    if hasattr(provider_dropdown, "on_change"):
        provider_dropdown.on_change = _on_provider_change

    def save(e):
        try:
            provider_value = _normalize_provider(provider_dropdown.value)
            modelos_validos = AI_PROVIDERS.get(provider_value, AI_PROVIDERS["gemini"]).get("models") or []
            selected_model = model_dropdown_ref.get("control").value if model_dropdown_ref.get("control") else None
            model_value = selected_model if selected_model in modelos_validos else AI_PROVIDERS.get(provider_value, {}).get("default_model")
            api_value = str(api_keys.get(provider_value) or "").strip() or None
            db.atualizar_provider_ia(user_id, provider_value, model_value)
            if hasattr(db, "atualizar_api_keys"):
                db.atualizar_api_keys(user_id, api_keys, provider_value)
            else:
                db.atualizar_api_key(user_id, api_value)
            db.atualizar_economia_ia(user_id, bool(economia_mode_switch.value))
            db.atualizar_telemetria_opt_in(user_id, bool(telemetry_opt_in_switch.value))
            state["usuario"]["provider"] = provider_value
            state["usuario"]["model"] = model_value
            state["usuario"]["api_key"] = api_value
            for p in _AI_KEY_PROVIDERS:
                state["usuario"][provider_api_field(p)] = str(api_keys.get(p) or "").strip() or None
            state["usuario"]["economia_mode"] = 1 if economia_mode_switch.value else 0
            state["usuario"]["telemetry_opt_in"] = 1 if telemetry_opt_in_switch.value else 0
            sync_keys = {p: (str(api_keys.get(p) or "").strip() or None) for p in _AI_KEY_PROVIDERS}
            state["settings_sync_signature"] = json.dumps(
                {
                    "provider": provider_value,
                    "model": model_value,
                    "economia_mode": 1 if economia_mode_switch.value else 0,
                    "telemetry_opt_in": 1 if telemetry_opt_in_switch.value else 0,
                    "api_keys": sync_keys,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            state["last_settings_sync_ts"] = time.monotonic()

            backend_ref = state.get("backend")
            b_uid = backend_user_id(state.get("usuario") or {})

            async def _push_settings_remote_async():
                if not (backend_ref and backend_ref.enabled()):
                    return
                if int(b_uid or 0) <= 0:
                    return
                try:
                    await asyncio.to_thread(
                        backend_ref.upsert_user_settings,
                        int(b_uid),
                        provider_value,
                        model_value,
                        api_value,
                        bool(economia_mode_switch.value),
                        bool(telemetry_opt_in_switch.value),
                        api_key_gemini=str(api_keys.get("gemini") or "").strip() or None,
                        api_key_openai=str(api_keys.get("openai") or "").strip() or None,
                        api_key_groq=str(api_keys.get("groq") or "").strip() or None,
                    )
                except Exception as ex_sync:
                    log_exception(ex_sync, "settings_view.save.sync_remote")

            if page and backend_ref and backend_ref.enabled():
                try:
                    page.run_task(_push_settings_remote_async)
                except Exception as ex_task:
                    log_exception(ex_task, "settings_view.save.schedule_remote_sync")

            log_event("settings_save", f"user_id={user_id} provider={provider_value} model={model_value}")
            set_feedback_text(save_feedback, "Configuracoes salvas com sucesso.", "success")
            save_feedback.visible = True
            if page:
                page.snack_bar = ft.SnackBar(content=ft.Text("Configuracoes salvas"), bgcolor=CORES["sucesso"], show_close_icon=True)
                page.snack_bar.open = True
                page.update()
        except Exception as ex:
            log_exception(ex, "settings_view.save")
            set_feedback_text(save_feedback, "Erro ao salvar configuracoes.", "error")
            save_feedback.visible = True
            if page:
                page.snack_bar = ft.SnackBar(content=ft.Text("Erro ao salvar configuracoes", color="white"), bgcolor=CORES["erro"], show_close_icon=True)
                page.snack_bar.open = True
                page.update()

    retorno = ft.Container(
        expand=True, bgcolor=_color("fundo", dark), padding=20,
        content=ft.Column([
            ft.Text("Configuracoes", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
            ft.Text("Ajustes rapidos de IA.", size=14, color=_color("texto_sec", dark)),
            ft.Card(elevation=1, content=ft.Container(padding=12, content=ft.Column([
                ft.Text("IA e preferencia de uso", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                provider_dropdown, model_dropdown_slot, key_manage_button, key_status_text,
                ft.Row([
                    ft.TextButton("Criar chave Gemini", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda _: _open_external_link(provider_links["gemini"])),
                    ft.TextButton("Criar chave OpenAI", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda _: _open_external_link(provider_links["openai"])),
                    ft.TextButton("Criar chave Groq", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda _: _open_external_link(provider_links["groq"])),
                ], wrap=True, spacing=6),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.06, CORES["erro"]),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.35, CORES["erro"])),
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=CORES["erro"]),
                            ft.Text(
                                "Dica: Groq costuma oferecer melhor limite de uso no plano gratuito.",
                                size=11,
                                color=CORES["erro"],
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                economia_row, telemetry_row,
                ft.Text("Cada provider tem sua propria chave. Alterar provider/modelo nao sobrescreve as demais chaves.", size=12, color=_color("texto_sec", dark)),
                ft.ElevatedButton("Salvar", icon=ft.Icons.SAVE, on_click=save),
                save_feedback,
            ], spacing=10))),
            ft.Container(height=12),
            ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
        ], spacing=12, scroll=ft.ScrollMode.AUTO),
    )
    _update_key_status()
    return retorno
