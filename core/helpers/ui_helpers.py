# -*- coding: utf-8 -*-
"""Helpers de UI extraÃ­dos do main_v2.py â€” diÃ¡logos, banners, temas, file helpers."""

from __future__ import annotations

import asyncio
import os
from typing import Callable, Optional
from urllib.parse import unquote, urlparse

import flet as ft

from config import CORES
from core.error_monitor import log_exception
from core.platform_helper import is_android
from core.ui_route_theme import _color
from core.ui_text_sanitizer import _fix_mojibake_text
from ui.design_system import ds_toast


# ----- Dialog compat -----

def show_dialog_compat(page: Optional[ft.Page], dialog: ft.AlertDialog) -> None:
    if not page:
        return
    if hasattr(page, "show_dialog"):
        page.show_dialog(dialog)
        return
    if hasattr(page, "open"):
        page.open(dialog)
        return
    try:
        page.dialog = dialog
        dialog.open = True
        page.update()
    except Exception:
        pass


def close_dialog_compat(page: Optional[ft.Page], dialog: Optional[ft.AlertDialog] = None) -> None:
    if not page:
        return
    if hasattr(page, "pop_dialog"):
        try:
            page.pop_dialog()
            return
        except Exception:
            pass
    if dialog is not None and hasattr(page, "close"):
        try:
            page.close(dialog)
            return
        except Exception:
            pass
    if dialog is not None:
        try:
            dialog.open = False
            page.update()
        except Exception:
            pass


def launch_url_compat(page: Optional[ft.Page], url: str, ctx: str = "launch_url") -> None:
    if not page:
        return
    link = str(url or "").strip()
    if not link:
        return
    try:
        result = page.launch_url(link)
        if asyncio.iscoroutine(result):
            async def _await_result():
                try:
                    await result
                except Exception as ex:
                    log_exception(ex, f"{ctx}.await")
            page.run_task(_await_result)
    except Exception as ex:
        log_exception(ex, ctx)


# ----- Dialogs -----

def show_quota_dialog(page: Optional[ft.Page], navigate) -> None:
    if not page:
        return
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Cota da IA esgotada"),
        content=ft.Text(
            "As cotas atuais da API acabaram. Voce prefere inserir uma nova API key "
            "ou mudar o modelo/provedor (Gemini/OpenAI/Groq)?"
        ),
    )

    def _to_settings(_):
        close_dialog_compat(page, dialog)
        navigate("/settings")

    def _continue_offline(_):
        close_dialog_compat(page, dialog)

    dialog.actions = [
        ft.TextButton("Continuar offline", on_click=_continue_offline),
        ft.TextButton("Inserir nova API", on_click=_to_settings),
        ft.ElevatedButton("Mudar modelo (Gemini/OpenAI/Groq)", on_click=_to_settings),
    ]
    dialog.actions_alignment = ft.MainAxisAlignment.END
    show_dialog_compat(page, dialog)


def show_upgrade_dialog(page: Optional[ft.Page], navigate, message: str) -> None:
    if not page:
        return
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Recurso Premium"),
        content=ft.Text(message),
    )

    def _go_plans(_):
        close_dialog_compat(page, dialog)
        navigate("/plans")

    dialog.actions = [
        ft.TextButton("Depois", on_click=lambda _: close_dialog_compat(page, dialog)),
        ft.ElevatedButton("Ver planos", on_click=_go_plans),
    ]
    dialog.actions_alignment = ft.MainAxisAlignment.END
    show_dialog_compat(page, dialog)


def show_confirm_dialog(
    page: Optional[ft.Page],
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    confirm_label: str = "Confirmar",
) -> None:
    if not page:
        return
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(str(title or "Confirmacao")),
        content=ft.Text(str(message or "")),
    )

    def _cancel(_):
        close_dialog_compat(page, dialog)

    def _confirm(_):
        close_dialog_compat(page, dialog)
        try:
            on_confirm()
        except Exception as ex:
            log_exception(ex, "ui_helpers.show_confirm_dialog.on_confirm")

    dialog.actions = [
        ft.TextButton("Cancelar", on_click=_cancel),
        ft.ElevatedButton(confirm_label, on_click=_confirm),
    ]
    dialog.actions_alignment = ft.MainAxisAlignment.END
    show_dialog_compat(page, dialog)


def show_api_issue_dialog(
    page: Optional[ft.Page],
    navigate,
    kind: str = "generic",
    provider_options: Optional[list[tuple[str, str]]] = None,
    on_select_provider: Optional[Callable[[str], None]] = None,
) -> None:
    if not page:
        return
    mode = str(kind or "generic").strip().lower()
    if mode == "quota":
        title = "Cota da IA esgotada"
        message = (
            "As cotas atuais da API acabaram para o provider atual. "
            "Voce pode continuar agora com outro provider sem sair desta tela, "
            "ou seguir offline/ajustar configuracoes."
        )
    elif mode == "auth":
        title = "API key invalida"
        message = (
            "Nao foi possivel autenticar na IA com a chave atual. "
            "Voce pode continuar agora com outro provider sem sair desta tela, "
            "ou revisar a API key em Configuracoes."
        )
    elif mode == "dependency":
        title = "Provider indisponivel"
        message = (
            "O provider atual nao conseguiu inicializar no dispositivo. "
            "Voce pode continuar agora com outro provider sem sair desta tela."
        )
    else:
        title = "Erro na IA"
        message = "Ocorreu um erro ao usar a IA. Verifique as configuracoes e tente novamente."

    options_raw = provider_options or []
    options: list[tuple[str, str]] = []
    for item in options_raw[:3]:
        try:
            provider_key, provider_name = item
        except Exception:
            continue
        key = str(provider_key or "").strip().lower()
        name = str(provider_name or provider_key or "").strip()
        if key and name:
            options.append((key, name))

    provider_dropdown = None
    if options and callable(on_select_provider):
        provider_dropdown = ft.Dropdown(
            label="Continuar com provider",
            options=[ft.dropdown.Option(k, text=n) for k, n in options],
            value=options[0][0],
            width=320,
        )

    content_control: ft.Control
    if provider_dropdown is not None:
        content_control = ft.Column([
            ft.Text(message),
            provider_dropdown,
        ], spacing=10, tight=True)
    else:
        content_control = ft.Text(message)

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=content_control,
    )

    def _go_settings(_):
        close_dialog_compat(page, dialog)
        navigate("/settings")

    def _switch_provider(provider_key: str):
        close_dialog_compat(page, dialog)
        if not callable(on_select_provider):
            return
        try:
            on_select_provider(str(provider_key or "").strip().lower())
        except Exception as ex:
            log_exception(ex, "ui_helpers.show_api_issue_dialog.switch_provider")

    actions: list[ft.Control] = [
        ft.TextButton("Fechar", on_click=lambda _: close_dialog_compat(page, dialog)),
    ]
    if mode == "quota":
        actions.insert(0, ft.TextButton("Continuar offline", on_click=lambda _: close_dialog_compat(page, dialog)))

    if provider_dropdown is not None:
        actions.append(
            ft.ElevatedButton(
                "Continuar",
                on_click=lambda _: _switch_provider(
                    str(provider_dropdown.value or options[0][0]).strip().lower()
                ),
            )
        )
        actions.append(ft.TextButton("Abrir configuracoes", on_click=_go_settings))
    else:
        actions.append(ft.ElevatedButton("Abrir configuracoes", on_click=_go_settings))

    dialog.actions = actions
    dialog.actions_alignment = ft.MainAxisAlignment.END
    show_dialog_compat(page, dialog)

# ----- Feedback & styling -----

def set_feedback_text(control: ft.Text, message: str, tone: str = "info") -> None:
    palette = {
        "info": CORES.get("texto_sec", "#6B7280"),
        "success": CORES.get("sucesso", "#10B981"),
        "warning": CORES.get("warning", "#F59E0B"),
        "error": CORES.get("erro", "#EF4444"),
    }
    normalized = _fix_mojibake_text(str(message or ""))
    control.value = normalized
    control.color = palette.get(tone, palette["info"])
    host = getattr(control, "_banner_container", None)
    if host is not None:
        try:
            host.visible = bool(str(normalized).strip())
        except Exception:
            pass


def soft_border(dark: bool, alpha: float = 0.10):
    return ft.Colors.with_opacity(alpha, _color("texto", dark))


def style_form_controls(control: ft.Control, dark: bool) -> None:
    if control is None:
        return
    try:
        if isinstance(control, ft.TextField):
            control.filled = True
            control.fill_color = ft.Colors.with_opacity(0.05, _color("texto", dark))
            control.border_color = soft_border(dark, 0.12)
            control.focused_border_color = CORES["primaria"]
            control.border_radius = 12
            if getattr(control, "text_size", None) is None:
                control.text_size = 15
        elif isinstance(control, ft.Dropdown):
            control.filled = True
            control.fill_color = ft.Colors.with_opacity(0.05, _color("texto", dark))
            control.border_color = soft_border(dark, 0.12)
            control.focused_border_color = CORES["primaria"]
            control.border_radius = 12
            if getattr(control, "text_size", None) is None:
                control.text_size = 15
        elif isinstance(control, ft.Switch):
            control.active_color = CORES["primaria"]
            control.inactive_track_color = soft_border(dark, 0.20)
            control.inactive_thumb_color = soft_border(dark, 0.45)
    except Exception:
        pass

    for child_attr in ("controls", "content", "leading", "title", "subtitle", "trailing"):
        if not hasattr(control, child_attr):
            continue
        child = getattr(control, child_attr)
        if child is None:
            continue
        if isinstance(child, list):
            for item in child:
                style_form_controls(item, dark)
        else:
            style_form_controls(child, dark)


def status_banner(control: ft.Text, dark: bool):
    box = ft.Container(
        visible=bool(str(getattr(control, "value", "") or "").strip()),
        bgcolor=ft.Colors.with_opacity(0.06, _color("texto", dark)),
        border_radius=10,
        border=ft.border.all(1, soft_border(dark, 0.10)),
        padding=10,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=_color("texto_sec", dark)),
                ft.Container(expand=True, content=control),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    try:
        setattr(control, "_banner_container", box)
    except Exception:
        pass
    return box


def wrap_study_content(content: ft.Control, dark: bool):
    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=12,
        alignment=ft.Alignment(0, -1),
        content=content,
    )


# ----- Layout & Dimensions -----

def screen_width(page: ft.Page) -> float:
    def _normalize_mobile_dimension(raw_value: float) -> float:
        value = float(raw_value or 0.0)
        if value <= 0:
            return value
        page_platform = str(getattr(page, "platform", "") or "").lower()
        mobile_runtime = bool(is_android() or ("android" in page_platform) or ("ios" in page_platform))
        if not mobile_runtime:
            return value
        dpr_value = 0.0
        media = getattr(page, "media", None)
        if media is not None:
            try:
                dpr_value = float(getattr(media, "device_pixel_ratio", 0.0) or 0.0)
            except Exception:
                dpr_value = 0.0
        if dpr_value <= 0:
            try:
                dpr_value = float(getattr(page, "device_pixel_ratio", 0.0) or 0.0)
            except Exception:
                dpr_value = 0.0
        if dpr_value > 1.1 and value > 760:
            value = value / dpr_value
        elif value > 900:
            value = value / 2.5
        return max(240.0, value)

    width = getattr(page, "width", None)
    if width:
        try:
            width_value = float(width)
            if width_value > 0:
                return _normalize_mobile_dimension(width_value)
        except Exception:
            pass

    window_width = getattr(page, "window_width", None)
    if window_width:
        try:
            window_value = float(window_width)
            if window_value > 0:
                return _normalize_mobile_dimension(window_value)
        except Exception:
            pass

    return 1280.0

def screen_height(page: ft.Page) -> float:
    def _normalize_mobile_dimension(raw_value: float) -> float:
        value = float(raw_value or 0.0)
        if value <= 0:
            return value
        page_platform = str(getattr(page, "platform", "") or "").lower()
        mobile_runtime = bool(is_android() or ("android" in page_platform) or ("ios" in page_platform))
        if not mobile_runtime:
            return value
        dpr_value = 0.0
        media = getattr(page, "media", None)
        if media is not None:
            try:
                dpr_value = float(getattr(media, "device_pixel_ratio", 0.0) or 0.0)
            except Exception:
                dpr_value = 0.0
        if dpr_value <= 0:
            try:
                dpr_value = float(getattr(page, "device_pixel_ratio", 0.0) or 0.0)
            except Exception:
                dpr_value = 0.0
        if dpr_value > 1.1 and value > 1280:
            value = value / dpr_value
        elif value > 1400:
            value = value / 2.5
        return max(360.0, value)

    height = getattr(page, "height", None)
    if height:
        try:
            height_value = float(height)
            if height_value > 0:
                return _normalize_mobile_dimension(height_value)
        except Exception:
            pass

    window_height = getattr(page, "window_height", None)
    if window_height:
        try:
            window_value = float(window_height)
            if window_value > 0:
                return _normalize_mobile_dimension(window_value)
        except Exception:
            pass

    return 820.0

def build_focus_header(title: str, flow: str, etapa_control: ft.Control, dark: bool):
    stage_chip = ft.Container(
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=999,
        bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]),
        content=etapa_control,
    )
    return ft.Container(
        padding=ft.padding.only(bottom=6),
        content=ft.Column(
            [
                ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text(flow, size=14, color=_color("texto_sec", dark)),
                stage_chip,
            ],
            spacing=6,
        ),
    )


# ----- Theme -----

def apply_global_theme(page: ft.Page) -> None:
    page.theme = ft.Theme(
        use_material3=True,
        color_scheme_seed=CORES["primaria"],
        card_bgcolor=CORES["card"],
        scaffold_bgcolor=CORES["fundo"],
        divider_color=ft.Colors.with_opacity(0.08, CORES["texto"]),
    )
    page.dark_theme = ft.Theme(
        use_material3=True,
        color_scheme_seed=CORES["texto_sec_escuro"],
        card_bgcolor=CORES["card_escuro"],
        scaffold_bgcolor=CORES["fundo_escuro"],
        divider_color=ft.Colors.with_opacity(0.10, CORES["texto_escuro"]),
    )


# ----- Logo -----

def logo_control(dark: bool):
    logo_path = os.path.join("assets", "logo_quizvance.png")
    if os.path.exists(logo_path):
        return ft.Image(src=logo_path, width=220, height=220, fit="contain"), True
    return ft.Text("Quiz Vance", size=32, weight=ft.FontWeight.BOLD, color=_color("texto", dark)), False


def logo_small(dark: bool):
    logo_path = os.path.join("assets", "logo_quizvance.png")
    if os.path.exists(logo_path):
        return ft.Image(src=logo_path, width=110, height=110, fit="contain")
    return ft.Text("Quiz Vance", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark))


# ----- Premium -----

def is_premium_active(usuario: dict) -> bool:
    return bool(usuario and int(usuario.get("premium_active") or 0) == 1)


def should_show_welcome_offer(usuario: Optional[dict]) -> bool:
    return not is_premium_active(usuario or {})


def backend_user_id(usuario: dict) -> int:
    try:
        uid = int(usuario.get("backend_user_id") or 0)
        return uid if uid > 0 else 0
    except Exception:
        return 0


# ----- File helpers -----

def normalize_uploaded_file_path(file_path: str) -> str:
    raw = str(file_path or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("file://"):
        try:
            parsed = urlparse(raw)
            uri_path = unquote(parsed.path or "")
            if os.name == "nt" and len(uri_path) >= 3 and uri_path[0] == "/" and uri_path[2] == ":":
                uri_path = uri_path[1:]
            return uri_path or raw
        except Exception:
            return raw
    return raw


# ----- Toast safe wrapper -----

def ds_toast_safe(page: Optional[ft.Page], msg: str, tipo: str = "info") -> None:
    try:
        ds_toast(page, msg, tipo=tipo)
    except Exception:
        pass


