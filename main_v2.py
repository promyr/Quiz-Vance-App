# -*- coding: utf-8 -*-
"""
Quiz Vance V2.0 - Arquivo principal.
"""

import flet as ft
import os
import asyncio
import inspect
import random
import time
import datetime
import hashlib
import unicodedata
import json
import re
import textwrap
from collections.abc import Mapping
from typing import Optional, Callable, Any
from urllib.parse import unquote, urlparse

from config import CORES, AI_PROVIDERS, DIFICULDADES, get_level_info
from core.database_v2 import Database
from core.backend_client import BackendClient
from core.error_monitor import log_exception, log_event
from core.app_paths import ensure_runtime_dirs, get_db_path, get_data_dir
from core.ai_service_v2 import AIService, create_ai_provider
from core.sounds import create_sound_manager
from core.library_service import LibraryService
from core.platform_helper import is_android, is_desktop, get_platform
from core.filter_taxonomy import get_quiz_filter_taxonomy
from core.ui_async_guard import AsyncActionGuard
from core.datetime_utils import _format_datetime_label, _format_exam_date_input, _parse_br_date
from core.ui_route_theme import _normalize_route_path, _color
from core.ui_text_sanitizer import (
    _fix_mojibake_text,
    _sanitize_payload_texts,
    _sanitize_control_texts,
    _sanitize_page_controls,
    _debug_scan_wrap_conflicts,
)
from core.repositories.question_progress_repository import QuestionProgressRepository
from core.services.mock_exam_report_service import MockExamReportService
from core.services.mock_exam_service import MockExamService
from core.services.quiz_filter_service import QuizFilterService
from ui.views.login_view_v2 import LoginView
from ui.views.review_session_view_v2 import build_review_session_body
from ui.views.ranking_view import build_ranking_body as _ext_build_ranking_body
from ui.views.conquistas_view import build_conquistas_body as _ext_build_conquistas_body
from ui.views.profile_view import build_profile_body as _ext_build_profile_body
from ui.views.stats_view import build_stats_body as _ext_build_stats_body
from ui.views.plans_view import build_plans_body as _ext_build_plans_body
from ui.views.study_plan_view import build_study_plan_body as _ext_build_study_plan_body
from ui.views.settings_view import build_settings_body as _ext_build_settings_body
from ui.views.home_view import build_home_body as _ext_build_home_body
from ui.views.library_view import build_library_body as _ext_build_library_body
from ui.views.onboarding_view import build_onboarding_body as _ext_build_onboarding_body
from ui.views.mais_view import build_mais_body as _ext_build_mais_body
from ui.views.flashcards_view import build_flashcards_body as _ext_build_flashcards_body
from ui.views.open_quiz_view import build_open_quiz_body as _ext_build_open_quiz_body
from ui.views.quiz_view import build_quiz_body as _ext_build_quiz_body
from ui.design_system import DS, AppText, ds_card, ds_btn_primary, ds_btn_ghost, ds_empty_state, ds_toast, ds_bottom_sheet, ds_section_title, ds_stat_card, ds_badge, ds_divider, ds_skeleton, ds_skeleton_card, ds_chip, ds_btn_secondary, ds_progress_bar, ds_icon_btn, ds_page_scaffold, ds_action_bar, ds_content_text

# Compat: alguns testes/rotas esperam este wrapper local
def _build_quiz_body(state, navigate, dark: bool):
    return _ext_build_quiz_body(state, navigate, dark)

# --- Rotação de assuntos e deduplicação de questões ---
try:
    from quiz_rotation import (
        pick_rotation_chunks as _pick_rotation_chunks,
        build_evitar_block as _build_evitar_block,
        filter_new_questions as _filter_new_questions,
        register_seen as _register_seen,
    )
    from quiz_prompt_v2 import validate_question as _validate_question, sanitize_question as _sanitize_question
    _QUIZ_ROTATION_ENABLED = True
except ImportError:
    _QUIZ_ROTATION_ENABLED = False

# --- Helpers extraídos (Fase 2 refatoração) ---
from core.helpers.ai_helpers import (
    normalize_ai_provider as _normalize_ai_provider,
    provider_api_field as _provider_api_field,
    extract_user_api_keys as _extract_user_api_keys,
    resolve_user_api_key as _resolve_user_api_key,
    create_user_ai_service as _create_user_ai_service,
    emit_opt_in_event as _emit_opt_in_event,
    is_ai_quota_exceeded as _is_ai_quota_exceeded,
    is_ai_processing as _is_ai_processing,
    sync_ai_indicator_controls as _sync_ai_indicator_controls,
    begin_ai_processing as _begin_ai_processing,
    end_ai_processing as _end_ai_processing,
    schedule_ai_task as _schedule_ai_task,
    generation_profile as _generation_profile,
)
from core.helpers.ui_helpers import (
    show_dialog_compat as _show_dialog_compat,
    close_dialog_compat as _close_dialog_compat,
    launch_url_compat as _launch_url_compat,
    show_quota_dialog as _show_quota_dialog,
    show_upgrade_dialog as _show_upgrade_dialog,
    show_confirm_dialog as _show_confirm_dialog,
    show_api_issue_dialog as _show_api_issue_dialog,
    set_feedback_text as _set_feedback_text,
    soft_border as _soft_border,
    style_form_controls as _style_form_controls,
    status_banner as _status_banner,
    wrap_study_content as _wrap_study_content,
    apply_global_theme as _apply_global_theme,
    logo_control as _logo_control,
    logo_small as _logo_small,
    is_premium_active as _is_premium_active,
    should_show_welcome_offer as _should_show_welcome_offer,
    backend_user_id as _backend_user_id,
    normalize_uploaded_file_path as _normalize_uploaded_file_path,
)

# Rotas da bottom bar (Android) / sidebar principal (Desktop) - maximo 5
APP_ROUTES = [
    ("/home",       "Inicio",    ft.Icons.HOME_OUTLINED),
    ("/quiz",       "Questoes",  ft.Icons.QUIZ_OUTLINED),
    ("/revisao",    "Revisao",   ft.Icons.STYLE_OUTLINED),
    ("/flashcards", "Cards",     ft.Icons.STYLE_OUTLINED),
    ("/mais",       "Mais",      ft.Icons.GRID_VIEW_OUTLINED),
]

# Rotas secundarias - acessiveis via /mais (hub)
APP_ROUTES_SECONDARY = [
    ("/flashcards",  "Flashcards",    ft.Icons.STYLE_OUTLINED),
    ("/open-quiz",   "Dissertativo",  ft.Icons.EDIT_NOTE_OUTLINED),
    ("/library",     "Biblioteca",    ft.Icons.LOCAL_LIBRARY_OUTLINED),
    ("/stats",       "Estatisticas",  ft.Icons.INSIGHTS_OUTLINED),
    ("/profile",     "Perfil",        ft.Icons.PERSON_OUTLINE),
    ("/ranking",     "Ranking",       ft.Icons.EMOJI_EVENTS_OUTLINED),
    ("/conquistas",  "Conquistas",    ft.Icons.MILITARY_TECH_OUTLINED),
    ("/plans",       "Planos",        ft.Icons.STARS_OUTLINED),
    ("/settings",    "Configuracoes", ft.Icons.SETTINGS_OUTLINED),
]

_AI_KEY_PROVIDERS = ("gemini", "openai", "groq")


def _read_env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    txt = str(raw).strip()
    if not txt:
        return float(default)
    try:
        return float(txt)
    except Exception:
        return float(default)


_QUIZ_STATS_SYNC_INTERVAL_S = max(
    8.0,
    _read_env_float(
        "QUIZVANCE_STATS_SYNC_INTERVAL_S",
        _read_env_float("QUIZVANCE_CLOUD_SYNC_INTERVAL_S", 20.0),
    ),
)
_SETTINGS_SYNC_INTERVAL_S = max(8.0, _read_env_float("QUIZVANCE_SETTINGS_SYNC_INTERVAL_S", 20.0))
_ROUTE_SYNC_MIN_GAP_S = max(2.0, _read_env_float("QUIZVANCE_ROUTE_SYNC_MIN_GAP_S", 6.0))


def _normalize_ai_provider(value: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in _AI_KEY_PROVIDERS else "gemini"


def _provider_api_field(provider: str) -> str:
    return f"api_key_{_normalize_ai_provider(provider)}"


def _extract_user_api_keys(usuario: Optional[dict]) -> dict[str, str]:
    user = usuario or {}
    keys: dict[str, str] = {}
    for p in _AI_KEY_PROVIDERS:
        keys[p] = str(user.get(_provider_api_field(p)) or "").strip()
    legacy = str(user.get("api_key") or "").strip()
    if legacy and not any(bool(v) for v in keys.values()):
        provider = _normalize_ai_provider(user.get("provider") or "gemini")
        keys[provider] = legacy
    return keys


def _resolve_user_api_key(usuario: Optional[dict], provider: Optional[str] = None) -> str:
    user = usuario or {}
    provider_key = _normalize_ai_provider(provider or user.get("provider") or "gemini")
    keys = _extract_user_api_keys(user)
    active = str(keys.get(provider_key) or "").strip()
    if active:
        return active
    if not any(bool(v) for v in keys.values()):
        return str(user.get("api_key") or "").strip()
    return ""


def _settings_signature(
    provider: str,
    model: str,
    economia_mode: bool,
    telemetry_opt_in: bool,
    api_keys: dict[str, Optional[str]],
) -> str:
    payload = {
        "provider": _normalize_ai_provider(provider),
        "model": str(model or "").strip(),
        "economia_mode": 1 if bool(economia_mode) else 0,
        "telemetry_opt_in": 1 if bool(telemetry_opt_in) else 0,
        "api_keys": {p: (str((api_keys or {}).get(p) or "").strip() or None) for p in _AI_KEY_PROVIDERS},
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _create_user_ai_service(usuario: dict, force_economic: bool = False) -> Optional[AIService]:
    if not usuario:
        return None
    provider_type = _normalize_ai_provider(usuario.get("provider") or "gemini")
    api_key = _resolve_user_api_key(usuario, provider_type)
    if not api_key:
        return None
    provider_config = AI_PROVIDERS.get(provider_type, AI_PROVIDERS["gemini"])
    model_value = usuario.get("model") or provider_config.get("default_model")
    economia_mode = bool(usuario.get("economia_mode"))
    if economia_mode or force_economic:
        if provider_type == "gemini":
            model_value = "gemini-2.5-flash-lite"
        elif provider_type == "openai":
            model_value = "gpt-5-nano"
        elif provider_type == "groq":
            model_value = "llama-3.1-8b-instant"
    anon_raw = str(usuario.get("id") or usuario.get("email") or "anon")
    user_anon = hashlib.sha256(anon_raw.encode("utf-8", errors="ignore")).hexdigest()[:16]
    telemetry_opt_in = bool(usuario.get("telemetry_opt_in"))
    try:
        return AIService(
            create_ai_provider(provider_type, api_key, model_value),
            telemetry_opt_in=telemetry_opt_in,
            user_anon=user_anon,
        )
    except Exception as ex:
        log_exception(ex, "main._create_user_ai_service")
        return None


def _emit_opt_in_event(
    usuario: Optional[dict],
    event_name: str,
    feature_name: str,
    latency_ms: int = 0,
    error_code: str = "",
):
    if not usuario or not bool(usuario.get("telemetry_opt_in")):
        return
    anon_raw = str(usuario.get("id") or usuario.get("email") or "anon")
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") + "Z",
        "feature_name": str(feature_name or "app"),
        "provider": str(usuario.get("provider") or ""),
        "model": str(usuario.get("model") or ""),
        "latency_ms": int(max(0, latency_ms or 0)),
        "error_code": str(error_code or ""),
        "user_anon": hashlib.sha256(anon_raw.encode("utf-8", errors="ignore")).hexdigest()[:16],
    }
    try:
        log_event(event_name, json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


def _build_focus_header(title: str, flow: str, etapa_control: ft.Control, dark: bool):
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


def _is_ai_quota_exceeded(service: Optional[AIService]) -> bool:
    if not service:
        return False
    provider = getattr(service, "provider", None)
    kind = str(getattr(provider, "last_error_kind", "") or "").lower()
    if kind in {"quota_hard", "quota_soft"}:
        return True
    msg = str(getattr(provider, "last_error_message", "") or "").lower()
    return ("quota exceeded" in msg) or ("429" in msg) or ("rate limit" in msg)


def _show_dialog_compat(page: Optional[ft.Page], dialog: ft.AlertDialog):
    if not page:
        return
    # Flet 0.80+ API
    if hasattr(page, "show_dialog"):
        page.show_dialog(dialog)
        return
    # Legacy fallback
    if hasattr(page, "open"):
        page.open(dialog)
        return
    # Last-resort fallback for older runtimes
    try:
        page.dialog = dialog
        dialog.open = True
        page.update()
    except Exception:
        pass


def _close_dialog_compat(page: Optional[ft.Page], dialog: Optional[ft.AlertDialog] = None):
    if not page:
        return
    # Flet 0.80+ API
    if hasattr(page, "pop_dialog"):
        try:
            page.pop_dialog()
            return
        except Exception:
            pass
    # Legacy fallback
    if dialog is not None and hasattr(page, "close"):
        try:
            page.close(dialog)
            return
        except Exception:
            pass
    # Last-resort fallback
    if dialog is not None:
        try:
            dialog.open = False
            page.update()
        except Exception:
            pass


def _launch_url_compat(page: Optional[ft.Page], url: str, ctx: str = "launch_url"):
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


def _show_quota_dialog(page: Optional[ft.Page], navigate):
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
        _close_dialog_compat(page, dialog)
        navigate("/settings")

    def _continue_offline(_):
        _close_dialog_compat(page, dialog)

    dialog.actions = [
        ft.TextButton("Continuar offline", on_click=_continue_offline),
        ft.TextButton("Inserir nova API", on_click=_to_settings),
        ft.ElevatedButton("Mudar modelo (Gemini/OpenAI/Groq)", on_click=_to_settings),
    ]
    dialog.actions_alignment = ft.MainAxisAlignment.END
    _show_dialog_compat(page, dialog)


def _is_premium_active(usuario: dict) -> bool:
    return bool(usuario and int(usuario.get("premium_active") or 0) == 1)


def _should_show_welcome_offer(usuario: Optional[dict]) -> bool:
    """Tela de vantagens deve aparecer no login para quem nao esta premium ativo."""
    return not _is_premium_active(usuario or {})


def _backend_user_id(usuario: dict) -> int:
    try:
        backend_uid = int(usuario.get("backend_user_id") or 0)
        return backend_uid if backend_uid > 0 else 0
    except Exception:
        return 0


def _build_quiz_stats_event_payload(correta: bool, delta: dict) -> dict:
    now_iso = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat() + "Z"
    raw = f"{now_iso}|{int(delta.get('questoes_delta', 0) or 0)}|{int(delta.get('acertos_delta', 0) or 0)}|{int(delta.get('xp_ganho', 0) or 0)}|{1 if bool(correta) else 0}|{random.random()}"
    event_id = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:40]
    return {
        "event_id": event_id,
        "questoes_delta": int(delta.get("questoes_delta", 0) or 0),
        "acertos_delta": int(delta.get("acertos_delta", 0) or 0),
        "xp_delta": int(delta.get("xp_ganho", 0) or 0),
        "correta": bool(correta),
        "occurred_at": now_iso,
    }


def _generation_profile(usuario: dict, feature_key: str) -> dict:
    if _is_premium_active(usuario):
        return {"force_economic": False, "delay_s": 0.0, "label": "premium"}
    if feature_key in {"quiz", "flashcards"}:
        return {"force_economic": True, "delay_s": 0.0, "label": "free_fast"}
    return {"force_economic": False, "delay_s": 0.0, "label": "free"}


def _show_upgrade_dialog(page: Optional[ft.Page], navigate, message: str):
    if not page:
        return
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Recurso Premium"),
        content=ft.Text(message),
    )

    def _go_plans(_):
        _close_dialog_compat(page, dialog)
        navigate("/plans")

    dialog.actions = [
        ft.TextButton("Depois", on_click=lambda _: _close_dialog_compat(page, dialog)),
        ft.ElevatedButton("Ver planos", on_click=_go_plans),
    ]
    dialog.actions_alignment = ft.MainAxisAlignment.END
    _show_dialog_compat(page, dialog)


def _show_confirm_dialog(
    page: Optional[ft.Page],
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    confirm_label: str = "Confirmar",
):
    if not page:
        return
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(str(title or "Confirmacao")),
        content=ft.Text(str(message or "")),
    )

    def _cancel(_):
        _close_dialog_compat(page, dialog)

    def _confirm(_):
        _close_dialog_compat(page, dialog)
        try:
            on_confirm()
        except Exception as ex:
            log_exception(ex, "main._show_confirm_dialog.on_confirm")

    dialog.actions = [
        ft.TextButton("Cancelar", on_click=_cancel),
        ft.ElevatedButton(confirm_label, on_click=_confirm),
    ]
    dialog.actions_alignment = ft.MainAxisAlignment.END
    _show_dialog_compat(page, dialog)


def _show_api_issue_dialog(page: Optional[ft.Page], navigate, kind: str = "generic"):
    if not page:
        return
    mode = str(kind or "generic").strip().lower()
    if mode == "quota":
        _show_quota_dialog(page, navigate)
        return
    if mode == "auth":
        title = "API key invalida"
        message = (
            "Nao foi possivel autenticar na IA com a chave atual. "
            "Revise a API key em Configuracoes."
        )
    else:
        title = "Erro na IA"
        message = "Ocorreu um erro ao usar a IA. Verifique as configuracoes e tente novamente."

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=ft.Text(message),
    )

    def _go_settings(_):
        _close_dialog_compat(page, dialog)
        navigate("/settings")

    dialog.actions = [
        ft.TextButton("Fechar", on_click=lambda _: _close_dialog_compat(page, dialog)),
        ft.ElevatedButton("Abrir configuracoes", on_click=_go_settings),
    ]
    dialog.actions_alignment = ft.MainAxisAlignment.END
    _show_dialog_compat(page, dialog)


def _set_feedback_text(control: ft.Text, message: str, tone: str = "info"):
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


def _wrap_study_content(content: ft.Control, dark: bool):
    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=12,
        alignment=ft.Alignment(0, -1),
        content=content,
    )


def _status_banner(control: ft.Text, dark: bool):
    box = ft.Container(
        visible=bool(str(getattr(control, "value", "") or "").strip()),
        bgcolor=ft.Colors.with_opacity(0.06, _color("texto", dark)),
        border_radius=10,
        border=ft.border.all(1, _soft_border(dark, 0.10)),
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


def _is_ai_processing(state: Optional[dict]) -> bool:
    try:
        return int((state or {}).get("ai_busy_count") or 0) > 0
    except Exception:
        return False


def _sync_ai_indicator_controls(state: Optional[dict]) -> None:
    if not isinstance(state, dict):
        return
    busy_count = max(0, int(state.get("ai_busy_count") or 0))
    busy = bool(busy_count > 0)
    message = str(state.get("ai_busy_message") or "").strip() or "Processando com IA..."
    box = state.get("_ai_busy_box_ctl")
    text = state.get("_ai_busy_text_ctl")
    bar = state.get("_ai_busy_bar_ctl")
    try:
        if text is not None:
            text.value = message
        if bar is not None:
            bar.visible = busy
        if box is not None:
            box.visible = busy
    except Exception:
        pass


def _begin_ai_processing(state: Optional[dict], page: Optional[ft.Page], message: str = "") -> None:
    if not isinstance(state, dict):
        return
    count = max(0, int(state.get("ai_busy_count") or 0)) + 1
    state["ai_busy_count"] = count
    if str(message or "").strip():
        state["ai_busy_message"] = str(message).strip()
    elif not str(state.get("ai_busy_message") or "").strip():
        state["ai_busy_message"] = "Processando com IA..."
    _sync_ai_indicator_controls(state)
    if page:
        try:
            page.update()
        except Exception:
            pass


def _end_ai_processing(state: Optional[dict], page: Optional[ft.Page]) -> None:
    if not isinstance(state, dict):
        return
    count = max(0, int(state.get("ai_busy_count") or 0) - 1)
    state["ai_busy_count"] = count
    if count == 0:
        state["ai_busy_message"] = ""
    _sync_ai_indicator_controls(state)
    if count == 0 and bool(state.get("pending_theme_refresh")):
        state["pending_theme_refresh"] = False
        refresh_cb = state.get("_theme_refresh_cb")
        if callable(refresh_cb):
            try:
                refresh_cb(None)
            except TypeError:
                try:
                    refresh_cb()
                except Exception:
                    pass
            except Exception:
                pass
    if page:
        try:
            page.update()
        except Exception:
            pass


def _schedule_ai_task(
    page: Optional[ft.Page],
    state: Optional[dict],
    coro_fn: Callable[..., Any],
    *args,
    message: str = "Processando com IA...",
    status_control: Optional[ft.Text] = None,
) -> bool:
    if not page:
        return False
    if _is_ai_processing(state):
        if status_control is not None:
            _set_feedback_text(status_control, "Aguarde: a IA ainda esta processando a solicitacao anterior.", "info")
        else:
            try:
                ds_toast(page, "IA em processamento. Aguarde concluir.", tipo="info")
            except Exception:
                pass
        try:
            page.update()
        except Exception:
            pass
        return False

    _begin_ai_processing(state, page, message=message)
    if status_control is not None and str(message or "").strip():
        _set_feedback_text(status_control, str(message).strip(), "info")
        try:
            page.update()
        except Exception:
            pass

    async def _runner():
        try:
            await coro_fn(*args)
        finally:
            _end_ai_processing(state, page)

    try:
        page.run_task(_runner)
        return True
    except Exception:
        _end_ai_processing(state, page)
        return False


def _soft_border(dark: bool, alpha: float = 0.10):
    return ft.Colors.with_opacity(alpha, _color("texto", dark))


def _style_form_controls(control: ft.Control, dark: bool):
    if control is None:
        return
    try:
        if isinstance(control, ft.TextField):
            control.filled = True
            control.fill_color = ft.Colors.with_opacity(0.05, _color("texto", dark))
            control.border_color = _soft_border(dark, 0.12)
            control.focused_border_color = CORES["primaria"]
            control.border_radius = 12
            if getattr(control, "text_size", None) is None:
                control.text_size = 15
        elif isinstance(control, ft.Dropdown):
            control.filled = True
            control.fill_color = ft.Colors.with_opacity(0.05, _color("texto", dark))
            control.border_color = _soft_border(dark, 0.12)
            control.focused_border_color = CORES["primaria"]
            control.border_radius = 12
            if getattr(control, "text_size", None) is None:
                control.text_size = 15
        elif isinstance(control, ft.Switch):
            control.active_color = CORES["primaria"]
            control.inactive_track_color = _soft_border(dark, 0.20)
            control.inactive_thumb_color = _soft_border(dark, 0.45)
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
                _style_form_controls(item, dark)
        else:
            _style_form_controls(child, dark)


def _apply_global_theme(page: ft.Page):
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


def _logo_control(dark: bool):
    logo_path = os.path.join("assets", "logo_quizvance.png")
    if os.path.exists(logo_path):
        return ft.Image(src=logo_path, width=220, height=220, fit="contain"), True
    return ft.Text("Quiz Vance", size=32, weight=ft.FontWeight.BOLD, color=_color("texto", dark)), False

def _logo_small(dark: bool):
    logo_path = os.path.join("assets", "logo_quizvance.png")
    if os.path.exists(logo_path):
        return ft.Image(src=logo_path, width=110, height=110, fit="contain")
    return ft.Text("Quiz Vance", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark))


def _normalize_uploaded_file_path(file_path: str) -> str:
    raw = str(file_path or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("file://"):
        try:
            parsed = urlparse(raw)
            uri_path = unquote(parsed.path or "")
            # file:///C:/... em Windows chega com barra inicial.
            if os.name == "nt" and len(uri_path) >= 3 and uri_path[0] == "/" and uri_path[2] == ":":
                uri_path = uri_path[1:]
            return uri_path or raw
        except Exception:
            return raw
    return raw


def _read_uploaded_study_text(file_path: str) -> str:
    normalized_path = _normalize_uploaded_file_path(file_path)
    if not normalized_path or normalized_path.lower().startswith("content://"):
        return ""
    ext = os.path.splitext(normalized_path)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception as ex:
            log_exception(ex, "main._read_uploaded_study_text.import_pdf")
            return ""
        try:
            with open(normalized_path, "rb") as fh:
                reader = PdfReader(fh, strict=False)
                try:
                    if bool(getattr(reader, "is_encrypted", False)):
                        # Tentativa padrao para PDFs protegidos sem senha efetiva.
                        reader.decrypt("")
                except Exception:
                    pass
                pages = []
                for page_obj in reader.pages[:20]:
                    try:
                        pages.append((page_obj.extract_text() or "").strip())
                    except Exception:
                        continue
                return "\n".join([p for p in pages if p])[:24000]
        except Exception as ex:
            log_exception(ex, "main._read_uploaded_study_text.read_pdf")
            return ""

    if ext in {".txt", ".md", ".csv", ".json", ".log"}:
        for encoding in ("utf-8", "latin-1"):
            try:
                with open(normalized_path, "r", encoding=encoding, errors="ignore") as f:
                    return (f.read() or "").strip()[:24000]
            except Exception:
                continue
    return ""


def _start_prioritized_session(state: dict, navigate):
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
        log_exception(ex, "main._start_prioritized_session")
        navigate("/quiz")


def _pick_study_files_native() -> list[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as ex:
        log_exception(ex, "main._pick_study_files_native.import")
        return []

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilenames(
            title="Selecione material para estudo",
            filetypes=[
                ("Documentos", "*.pdf *.txt *.md"),
                ("PDF", "*.pdf"),
                ("Texto", "*.txt"),
                ("Markdown", "*.md"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        return list(selected or [])
    except Exception as ex:
        log_exception(ex, "main._pick_study_files_native.dialog")
        return []
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def _get_or_create_file_picker(page: ft.Page) -> Optional[ft.FilePicker]:
    if not hasattr(ft, "FilePicker"):
        return None

    picker = getattr(page, "_quizvance_file_picker", None)
    services = getattr(page, "services", None)
    overlay = getattr(page, "overlay", None)

    def _remove_from_container(container, ctrl):
        if container is None or ctrl is None:
            return
        try:
            if ctrl in container:
                container.remove(ctrl)
        except Exception:
            pass

    def _attach_picker(ctrl: ft.FilePicker):
        attached = False
        if services is not None:
            try:
                if ctrl not in services:
                    services.append(ctrl)
                attached = True
            except Exception:
                pass
        if not attached and overlay is not None:
            try:
                if ctrl not in overlay:
                    overlay.append(ctrl)
                attached = True
            except Exception:
                pass
        return attached

    try:
        for ctrl in list(services or []):
            if isinstance(ctrl, ft.FilePicker) and ctrl is not picker:
                _remove_from_container(services, ctrl)
        for ctrl in list(overlay or []):
            if isinstance(ctrl, ft.FilePicker) and ctrl is not picker:
                _remove_from_container(overlay, ctrl)
    except Exception:
        pass

    if picker is not None:
        if _attach_picker(picker):
            try:
                page.update()
            except Exception:
                pass
            return picker

    try:
        picker = ft.FilePicker()
        if not _attach_picker(picker):
            return None
        setattr(page, "_quizvance_file_picker", picker)
        page.update()
        return picker
    except Exception as ex:
        log_exception(ex, "main._get_or_create_file_picker")
        return None


async def _pick_study_files(page: Optional[ft.Page]) -> list[str]:
    if not page:
        return []

    picker = _get_or_create_file_picker(page)
    if picker is None:
        if is_android():
            return []
        return await asyncio.to_thread(_pick_study_files_native)

    loop = asyncio.get_running_loop()
    result_future: asyncio.Future[list[str]] = loop.create_future()
    has_on_result = hasattr(picker, "on_result")
    previous_handler = getattr(picker, "on_result", None) if has_on_result else None

    def _extract_paths(files_payload) -> list[str]:
        selected_paths: list[str] = []
        seen: set[str] = set()

        def _push(candidate):
            if candidate is None:
                return
            try:
                text = str(candidate).strip()
            except Exception:
                return
            if not text:
                return
            lowered = text.lower()
            if lowered in {"none", "null"}:
                return
            if text in seen:
                return
            seen.add(text)
            selected_paths.append(text)

        for file_obj in files_payload or []:
            if isinstance(file_obj, (list, tuple)):
                for item in file_obj:
                    _push(item)
                continue
            if isinstance(file_obj, str):
                _push(file_obj)
                continue
            if isinstance(file_obj, Mapping):
                for key in ("path", "full_path", "absolute_path", "local_path", "file_path", "uri"):
                    value = file_obj.get(key)
                    if isinstance(value, (list, tuple)):
                        for item in value:
                            _push(item)
                    else:
                        _push(value)
                continue
            for attr in ("path", "full_path", "absolute_path", "local_path", "file_path", "uri"):
                value = getattr(file_obj, attr, None)
                if isinstance(value, (list, tuple)):
                    for item in value:
                        _push(item)
                else:
                    _push(value)
        return selected_paths

    def _on_result(e):
        try:
            files = getattr(e, "files", None) or []
            selected_paths = _extract_paths(files)
            if not selected_paths:
                selected_paths = _extract_paths(
                    [
                        getattr(e, "path", None),
                        getattr(e, "file", None),
                        getattr(e, "paths", None),
                        getattr(e, "data", None),
                    ]
                )
            if not result_future.done():
                result_future.set_result(selected_paths)
        except Exception as ex_inner:
            if not result_future.done():
                result_future.set_exception(ex_inner)

    async def _call_pick_files_with_compat(**kwargs):
        """
        Compat para Flet sync/async:
        - versoes antigas: pick_files retorna valor direto
        - versoes novas: pick_files pode retornar coroutine/awaitable
        """
        pick_fn = getattr(picker, "pick_files", None)
        if inspect.iscoroutinefunction(pick_fn):
            return await pick_fn(**kwargs)
        result = pick_fn(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    try:
        # Mantem callback para compatibilidade entre APIs do Flet.
        if has_on_result:
            picker.on_result = _on_result
        try:
            pick_result = await _call_pick_files_with_compat(
                allow_multiple=True,
                file_type=ft.FilePickerFileType.ANY,
                allowed_extensions=["pdf", "txt", "md", "csv", "json", "log"],
            )
        except Exception:
            # fallback generico
            try:
                pick_result = await _call_pick_files_with_compat(allow_multiple=True)
            except Exception as ex:
                log_exception(ex, "main._pick_study_files.pick_files")
                if is_android():
                    return []
                return await asyncio.to_thread(_pick_study_files_native)

        direct_payload = pick_result if isinstance(pick_result, (list, tuple)) else [pick_result]
        direct_paths = _extract_paths(direct_payload)
        if not direct_paths and pick_result is not None:
            direct_paths = _extract_paths(
                [
                    getattr(pick_result, "files", None),
                    getattr(pick_result, "path", None),
                    getattr(pick_result, "paths", None),
                    getattr(pick_result, "data", None),
                ]
            )
        # Em desktop, retorno direto vazio normalmente ja indica cancelamento.
        # Em Android, alguns runtimes retornam vazio e so depois disparam callback.
        if direct_paths or (pick_result is not None and not is_android()):
            return direct_paths

        if not has_on_result:
            if is_android():
                return []
            try:
                return await asyncio.to_thread(_pick_study_files_native)
            except Exception:
                return []

        timed_out = False
        try:
            selected = await asyncio.wait_for(result_future, timeout=30 if is_android() else 45)
        except asyncio.TimeoutError:
            selected = []
            timed_out = True
        if timed_out and (not is_android()):
            try:
                return await asyncio.to_thread(_pick_study_files_native)
            except Exception:
                return []
        return selected
    except Exception as ex:
        log_exception(ex, "main._pick_study_files")
        if is_android():
            return []
        return await asyncio.to_thread(_pick_study_files_native)
    finally:
        if has_on_result:
            picker.on_result = previous_handler


def _state_async_guard(state: Optional[dict]) -> AsyncActionGuard:
    if not isinstance(state, dict):
        return AsyncActionGuard()
    guard = state.get("async_guard")
    if isinstance(guard, AsyncActionGuard):
        return guard
    guard = AsyncActionGuard()
    state["async_guard"] = guard
    return guard


def _extract_uploaded_material(file_paths: list[str]) -> tuple[list[str], list[str], list[str]]:
    upload_texts = []
    upload_names = []
    failed_names = []
    for file_path in file_paths:
        safe_path = _normalize_uploaded_file_path(file_path)
        basename = os.path.basename(safe_path or str(file_path or "")) or "arquivo"
        ext = os.path.splitext(safe_path)[1].lower()
        extracted = _read_uploaded_study_text(file_path)
        if extracted.strip():
            upload_texts.append(extracted)
            upload_names.append(basename)
            continue
        failed_names.append(basename)
        reason = "sem_texto"
        if not safe_path:
            reason = "caminho_invalido"
        elif str(safe_path).lower().startswith("content://"):
            reason = "uri_content_nao_suportada"
        elif ext not in {".pdf", ".txt", ".md", ".csv", ".json", ".log"}:
            reason = f"extensao_nao_suportada:{ext or 'desconhecida'}"
        elif (not str(safe_path).lower().startswith("content://")) and (not os.path.exists(safe_path)):
            reason = "arquivo_inexistente"
        elif ext == ".pdf":
            reason = "pdf_sem_texto_selecionavel_ou_leitura_falhou"
        log_event("upload_material_skip", f"{reason}|{safe_path or file_path}")
    return upload_texts, upload_names, failed_names


def _format_upload_info_label(names: list[str], max_names: int = 3, max_preview_chars: int = 80) -> str:
    if not names:
        return "Nenhum material enviado."
    preview = ", ".join(str(n or "") for n in names[:max_names]).strip()
    if len(preview) > max_preview_chars:
        preview = f"{preview[: max_preview_chars - 1]}..."
    if len(names) > max_names:
        preview += f" +{len(names) - max_names}"
    return f"{len(names)} arquivo(s): {preview}"


from core.quiz_defaults import DEFAULT_QUIZ_QUESTIONS



def _build_sidebar(current_route: str, navigate, dark: bool, screen_w: float = 1280, collapsed: bool = False):
    items = []
    for route, label, icon in APP_ROUTES:
        selected = route == current_route
        row_controls = [
            ft.Icon(icon, size=18, color=CORES["primaria"] if selected else _color("texto_sec", dark)),
        ]
        if not collapsed:
            row_controls.append(
                ft.Text(
                    label,
                    color=CORES["primaria"] if selected else _color("texto", dark),
                    weight=ft.FontWeight.BOLD if selected else ft.FontWeight.W_500,
                )
            )
        items.append(
            ft.TextButton(
                content=ft.Row(
                    row_controls,
                    spacing=0 if collapsed else 10,
                    alignment=ft.MainAxisAlignment.CENTER if collapsed else ft.MainAxisAlignment.START,
                ),
                tooltip=label if collapsed else None,
                width=56 if collapsed else None,
                on_click=lambda _, r=route: navigate(r),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]) if selected else "transparent",
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=10 if collapsed else 12,
                ),
            )
        )

    sidebar_width = 84 if collapsed else (210 if screen_w < 1440 else 230)
    logo_height = 84 if collapsed else (120 if screen_w < 1280 else 150)
    logo_path = os.path.join("assets", "logo_quizvance.png")
    logo_content = (
        ft.Image(src=logo_path, width=44, height=44, fit="contain")
        if collapsed and os.path.exists(logo_path)
        else (
            ft.Icon(ft.Icons.SCHOOL, size=34, color=CORES["primaria"])
            if collapsed
            else (
                ft.Image(src=logo_path, width=160, height=86, fit="contain")
                if os.path.exists(logo_path)
                else ft.Text("Quiz Vance", size=30, weight=ft.FontWeight.BOLD, color=_color("texto", dark))
            )
        )
    )
    logo_top = ft.Container(
        height=logo_height,
        border=ft.border.only(bottom=ft.BorderSide(1, _soft_border(dark, 0.10))),
        alignment=ft.Alignment(0, 0),
        content=logo_content,
    )

    return ft.Container(
        width=sidebar_width,
        padding=0,
        bgcolor=_color("card", dark),
        border=ft.border.only(right=ft.BorderSide(1, _soft_border(dark, 0.10))),
        content=ft.Column(
            controls=[
                logo_top,
                ft.Container(
                    expand=True,
                    padding=10 if collapsed else 16,
                    content=ft.ListView(
                        controls=items,
                        spacing=6,
                        expand=True,
                    ),
                ),
            ],
            spacing=0,
            expand=True,
        ),
    )

def _screen_width(page: ft.Page) -> float:
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
        # Em muitos runtimes Flutter/Flet a largura ja vem em dp; so normaliza
        # quando o valor esta claramente em pixels fisicos.
        if dpr_value > 1.1 and value > 760:
            value = value / dpr_value
        elif value > 900:
            # Heuristica para devices que reportam largura fisica em pixels.
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


def _screen_height(page: ft.Page) -> float:
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
        # Altura em dp nao deve ser reescalada; normaliza apenas se vier fisica.
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

def _build_compact_nav(current_route: str, navigate, dark: bool):
    buttons = []
    for route, label, icon in APP_ROUTES:
        selected = route == current_route
        buttons.append(
            ft.TextButton(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=16, color=CORES["primaria"] if selected else _color("texto_sec", dark)),
                        ft.Text(
                            label,
                            size=12,
                            color=CORES["primaria"] if selected else _color("texto", dark),
                            weight=ft.FontWeight.BOLD if selected else ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=6,
                ),
                on_click=lambda _, r=route: navigate(r),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]) if selected else "transparent",
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(10, 8, 10, 8),
                ),
            )
        )

    return ft.Container(
        bgcolor=_color("card", dark),
        border=ft.border.only(bottom=ft.BorderSide(1, _soft_border(dark, 0.10))),
        padding=ft.padding.symmetric(horizontal=8, vertical=6),
        content=ft.Row(
            controls=buttons,
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
        ),
    )


def _build_home_body(state: dict, navigate, dark: bool):
    usuario = state.get("usuario") or {}
    db = state.get("db")
    nome = usuario.get("nome", "Usuario")

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Dados do progresso ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
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
            log_exception(ex, "home.progresso_diario")

    streak = int(progresso.get("streak_dias") or 0)
    respondidas = int(progresso.get("questoes_respondidas") or 0)
    meta = int(progresso.get("meta_questoes") or 20)
    acertos = int(progresso.get("acertos") or 0)
    pct_acerto = round((acertos / respondidas * 100) if respondidas > 0 else 0)
    revisoes_pend = int(progresso.get("revisoes_pendentes") or 0)
    progresso_meta = min(1.0, respondidas / max(meta, 1))

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ SaudaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    hora = datetime.datetime.now().hour
    if hora < 12:
        saudacao_label = "Bom dia"
    elif hora < 18:
        saudacao_label = "Boa tarde"
    else:
        saudacao_label = "Boa noite"

    streak_emoji = "🔥" if streak > 0 else "💪"
    streak_text = f"{streak} dia{'s' if streak != 1 else ''} de sequencia" if streak > 0 else "Comece sua sequencia hoje!"

    saudacao = ft.Column(
        [
            ft.Text(f"{saudacao_label}, {nome.split()[0]}!", size=DS.FS_H2, weight=DS.FW_BOLD, color=DS.text_color(dark)),
            ft.Row(
                [
                    ft.Text(streak_emoji, size=18),
                    ft.Text(streak_text, size=DS.FS_BODY_S, color=DS.text_sec_color(dark)),
                ],
                spacing=DS.SP_4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        spacing=DS.SP_4,
    )

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Stat cards ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    stat_cards = [
        ds_stat_card(
            col={"xs": 6, "sm": 6, "md": 3},
            height=172,
            icon=ft.Icons.TODAY_OUTLINED,
            label="Questoes hoje",
            value=f"{respondidas}/{meta}",
            subtitle=f"{int(progresso_meta*100)}% da meta",
            dark=dark,
            icon_color=DS.P_500,
            on_click=lambda _: navigate("/stats"),
        ),
        ds_stat_card(
            col={"xs": 6, "sm": 6, "md": 3},
            height=172,
            icon=ft.Icons.TRACK_CHANGES_OUTLINED,
            label="% Acerto (hoje)",
            value=f"{pct_acerto}%",
            subtitle=f"{acertos} de {respondidas} certas",
            dark=dark,
            icon_color=DS.SUCESSO if pct_acerto >= 70 else DS.WARNING,
            trend_up=pct_acerto >= 70 if respondidas > 0 else None,
        ),
        ds_stat_card(
            col={"xs": 6, "sm": 6, "md": 3},
            height=172,
            icon=ft.Icons.REPLAY_OUTLINED,
            label="Revisoes pendentes",
            value=str(revisoes_pend),
            subtitle="Clique para revisar",
            dark=dark,
            icon_color=DS.ERRO if revisoes_pend > 5 else DS.A_500,
            on_click=lambda _: navigate("/revisao"),
        ),
        ds_stat_card(
            col={"xs": 6, "sm": 6, "md": 3},
            height=172,
            icon=ft.Icons.LOCAL_FIRE_DEPARTMENT_OUTLINED,
            label="Sequencia",
            value=f"{streak}" if streak > 0 else "0",
            subtitle="dias consecutivos",
            dark=dark,
            icon_color=DS.WARNING,
        ),
    ]

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Meta diÃƒÆ’Ã‚Â¡ria com barra de progresso ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    meta_card = ds_card(
        dark=dark,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Meta Diaria", size=DS.FS_BODY, weight=DS.FW_SEMI, color=DS.text_color(dark)),
                        ft.Text(f"{respondidas}/{meta} questoes", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ds_progress_bar(progresso_meta, dark=dark, height=10, color=DS.P_500),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "md": 6},
                            content=ds_btn_primary(
                                "Continuar estudando" if respondidas > 0 else "Comecar agora",
                                on_click=lambda _: navigate("/quiz"),
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                dark=dark,
                                height=44,
                                expand=True,
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "md": 6},
                            content=ds_btn_secondary(
                                "Ver revisoes",
                                on_click=lambda _: navigate("/revisao"),
                                icon=ft.Icons.REPLAY_OUTLINED,
                                dark=dark,
                                height=44,
                                expand=True,
                            ),
                            visible=revisoes_pend > 0,
                        ),
                    ],
                    spacing=DS.SP_12,
                    run_spacing=DS.SP_8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=DS.SP_12,
        ),
    )

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ Card: Estudar um tema (stub para Commit 8) ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    # Campo de tema inline - funcional (Commit 8)
    tema_input = ft.TextField(
        hint_text="Ex.: Direito Constitucional, Calculo I",
        border_radius=DS.R_MD,
        expand=True,
        dense=True,
        on_submit=lambda e: _iniciar_tema(e.control.value),
    )

    def _iniciar_tema(tema_valor: str = None):
        tema = (tema_valor or tema_input.value or "").strip()
        if not tema:
            return
        state["quiz_preset"] = {"topic": tema, "count": "10", "difficulty": "intermediario"}
        navigate("/quiz")

    tema_card = ds_card(
        dark=dark,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.AUTO_AWESOME, size=22, color=DS.P_500),
                            bgcolor=f"{DS.P_500}1A",
                            border_radius=DS.R_MD,
                            padding=DS.SP_12,
                        ),
                        ft.Column(
                            [
                                ft.Text("Estudar um tema com IA", size=DS.FS_BODY, weight=DS.FW_SEMI, color=DS.text_color(dark)),
                                ft.Text("Gere questoes personalizadas em segundos", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                            ],
                            spacing=DS.SP_4,
                            expand=True,
                        ),
                    ],
                    spacing=DS.SP_12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 9}, content=tema_input),
                        ft.Container(
                            col={"xs": 12, "md": 3},
                            content=ds_btn_primary(
                                "Gerar",
                                on_click=lambda _: _iniciar_tema(),
                                icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                                dark=dark,
                                height=DS.TAP_MIN,
                                expand=True,
                            ),
                        ),
                    ],
                    spacing=DS.SP_8,
                    run_spacing=DS.SP_8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=DS.SP_12,
        ),
        border_color=DS.P_300 if not dark else DS.P_900,
    )

    return ft.Container(
        expand=True,
        content=ft.Column(
            [
                saudacao,
                ft.Container(height=DS.SP_4),
                ft.ResponsiveRow(controls=stat_cards, columns=12, spacing=DS.SP_12, run_spacing=DS.SP_12),
                meta_card,
                tema_card,
                ft.Container(height=DS.SP_32),
            ],
            spacing=DS.SP_16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=DS.SP_16,
    )



def _build_onboarding_body(state: dict, navigate, dark: bool):
    page = state.get("page")
    user = state.get("usuario") or {}
    db = state.get("db")
    screen_w = _screen_width(page) if page else 1280
    compact = screen_w < 960
    mobile = screen_w < 760
    needs_setup = (not user.get("oauth_google")) and (not _resolve_user_api_key(user))

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
            log_exception(ex, "main.finish_onboarding")
            status_text.value = "Falha ao concluir boas-vindas. Tente novamente."
            status_text.color = CORES["erro"]
            if page:
                page.update()

    def _feature_line(text: str):
        return ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=CORES["primaria"]),
                ft.Text(text, size=12, color=_color("texto_sec", dark), expand=True),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    intro_card = ft.Card(
        elevation=1,
        content=ft.Container(
            padding=14 if mobile else 16,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.WAVING_HAND, color=CORES["primaria"], size=22),
                            ft.Text("Boas-vindas ao Quiz Vance", size=20 if mobile else 24, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ],
                        spacing=8,
                        wrap=True,
                    ),
                    ft.Text(
                        "Este painel aparece no login de contas Free para destacar os beneficios Premium.",
                        size=13,
                        color=_color("texto_sec", dark),
                    ),
                    ft.Container(height=2),
                    _feature_line("1) Escolha um modulo: Questoes, Flashcards, Biblioteca ou Dissertativo."),
                    _feature_line("2) Gere sua sessao de estudo com IA e acompanhe seu progresso."),
                    _feature_line("3) Use o menu para navegar e ajustar tema, perfil e configuracoes."),
                ],
                spacing=8,
            ),
        ),
    )

    free_card = ft.Card(
        elevation=1,
        content=ft.Container(
            padding=14,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LOCK_OPEN, size=20, color=CORES["acento"]),
                            ft.Text("Conta Free", size=17, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ],
                        spacing=8,
                    ),
                    _feature_line("Questoes e flashcards com modo economico."),
                    _feature_line("Correcao de dissertativa: 1 por dia."),
                    _feature_line("Acesso completo ao painel e biblioteca."),
                ],
                spacing=8,
            ),
        ),
    )

    premium_card = ft.Card(
        elevation=1,
        content=ft.Container(
            padding=14,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.WORKSPACE_PREMIUM, size=20, color=CORES["primaria"]),
                            ft.Text("Conta Premium", size=17, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ],
                        spacing=8,
                    ),
                    _feature_line("Respostas mais rapidas e qualidade maxima dos modelos."),
                    _feature_line("Mais produtividade para sessoes longas."),
                    _feature_line("Melhor custo-beneficio para uso diario intenso."),
                ],
                spacing=8,
            ),
        ),
    )

    trial_title = "Cortesia ativa: 1 dia de Premium" if trial_active else "Cortesia de 1 dia para novos usuarios"
    trial_subtitle = (
        f"Seu periodo de cortesia vai ate {premium_until}."
        if premium_until
        else "A cortesia e aplicada automaticamente na criacao da conta."
    )
    if (not trial_active) and premium_until:
        trial_subtitle = f"Cortesia registrada ate {premium_until}. Veja os planos para continuar."

    trial_card = ft.Card(
        elevation=1,
        content=ft.Container(
            padding=14,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CARD_GIFTCARD, size=20, color=CORES["warning"]),
                            ft.Text(trial_title, size=17, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ],
                        spacing=8,
                        wrap=True,
                    ),
                    ft.Text(trial_subtitle, size=13, color=_color("texto_sec", dark)),
                    ft.Row(
                        [
                            ft.ElevatedButton("Ver planos", icon=ft.Icons.STARS, on_click=lambda _: navigate("/plans")),
                            ft.OutlinedButton("Comecar agora", icon=ft.Icons.ARROW_FORWARD, on_click=finish_onboarding),
                        ],
                        spacing=10,
                        wrap=True,
                    ),
                    status_text,
                ],
                spacing=8,
            ),
        ),
    )

    config_hint = ft.Container()
    if needs_setup:
        config_hint = ft.Container(
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, CORES["warning"]),
            content=ft.Text(
                "Antes de estudar com IA, configure provider, modelo e API key na tela de Configuracoes.",
                size=12,
                color=_color("texto", dark),
            ),
        )

    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=12 if mobile else 18,
        content=ft.Column(
            [
                intro_card,
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(col={"sm": 12, "md": 6}, content=free_card),
                        ft.Container(col={"sm": 12, "md": 6}, content=premium_card),
                    ],
                    spacing=10,
                    run_spacing=10,
                ),
                trial_card,
                config_hint,
            ],
            spacing=10 if compact else 12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
    )


def _build_placeholder_body(title: str, description: str, navigate, dark: bool):
    tips = {
        "Questoes": [
            "Escolha categoria e dificuldade para gerar questoes.",
            "Cada rodada traz 5 questoes com feedback imediato.",
            "Use 'Reforco' para ver explicacoes detalhadas."
        ],
        "Flashcards": [
            "Selecione tema e gere baralho com IA.",
            "Marque como 'Lembrei' ou 'Rever' para espacamento.",
            "Exporte pacotes de estudo em Markdown pela Biblioteca."
        ],
        "Dissertativo": [
            "Digite a pergunta ou cole o enunciado.",
            "Receba estrutura de resposta, pontos-chave e referencia.",
            "Peca reescrita por clareza ou concisao."
        ],
        "Estatisticas": [
            "Painel mostra XP diario e taxa de acerto por tema.",
            "Ranking interno por XP acumulado.",
            "Filtros por periodo e categoria (coming soon)."
        ],
        "Perfil": [
            "Atualize nome, avatar e preferencia de tema.",
            "Configure provider/modelo de IA por default.",
            "Gerencie chaves de API de forma segura."
        ],
        "Ranking": [
            "Comparacao com outros usuarios por XP.",
            "Exibe nivel, taxa de acerto e horas de estudo.",
            "Resets semanais opcionais (beta)."
        ],
        "Conquistas": [
            "Desbloqueie medalhas por metas de estudo.",
            "Bonus de XP ao concluir marcos.",
            "Streaks diarias contam para conquistas especiais."
        ],
        "Configuracoes": [
            "Troque tema, idioma e notificacoes.",
            "Selecione provider/modelo principal.",
            "Backup e restauracao de dados (em breve)."
        ],
    }

    rows = [
        ft.ListTile(
            leading=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=CORES["primaria"]),
            title=ft.Text(t, color=_color("texto", dark)),
        ) for t in tips.get(title, [description])
    ]

    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text(description, size=14, color=_color("texto_sec", dark)),
                ft.Container(height=12),
                ft.Card(content=ft.Column(rows, spacing=0), elevation=2),
                ft.Container(height=16),
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=10,
        ),
    )



def _build_library_body(state, navigate, dark: bool):
    page = state.get("page")
    user = state.get("usuario") or {}
    db = state.get("db")
    if not db or not user:
        return ft.Text("Erro: Usuario nao autenticado")
        
    library_service = LibraryService(db)
    from core.services.study_summary_service import StudySummaryService
    summary_service = StudySummaryService()
    
    # Estado local
    file_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=False)
    package_list = ft.Column(spacing=6)
    status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    upload_ring = ft.ProgressRing(width=20, height=20, visible=False)
    files_count_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=_color("texto", dark))
    packs_count_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=CORES["primaria"])

    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    def _start_quiz_from_package(dados: dict):
        dados = _as_dict(dados)
        questions = dados.get("questoes") or []
        if not questions:
            status_text.value = "Pacote sem questoes."
            status_text.color = CORES["warning"]
            if page:
                page.update()
            return
        state["quiz_package_questions"] = questions
        navigate("/quiz")

    def _start_flashcards_from_package(dados: dict):
        dados = _as_dict(dados)
        cards = dados.get("flashcards") or []
        if not cards:
            summary = _as_dict(dados.get("summary_v2"))
            cards = summary.get("sugestoes_flashcards") or []
        seed_cards = []
        for item in cards:
            if not isinstance(item, dict):
                continue
            frente = str(item.get("frente") or item.get("front") or "").strip()
            verso = str(item.get("verso") or item.get("back") or "").strip()
            if frente and verso:
                seed_cards.append({"frente": frente, "verso": verso})
        if not seed_cards:
            status_text.value = "Pacote sem flashcards."
            status_text.color = CORES["warning"]
            if page:
                page.update()
            return
        state["flashcards_seed_cards"] = seed_cards
        navigate("/flashcards")

    def _start_plan_from_package(pkg: dict):
        pkg = _as_dict(pkg)
        dados = _as_dict(pkg.get("dados"))
        summary = _as_dict(dados.get("summary_v2"))
        topicos = summary.get("topicos_principais") or summary.get("topicos") or dados.get("topicos") or []
        topicos = [str(t).strip() for t in topicos if str(t).strip()][:10]
        state["study_plan_seed"] = {
            "objetivo": str(pkg.get("titulo") or "Plano de estudo"),
            "data_prova": "",
            "tempo_diario": 90,
            "topicos": topicos,
        }
        navigate("/study-plan")

    def _safe_file_stub(value: str) -> str:
        return summary_service.safe_file_stub(value)

    def _build_package_markdown(pkg: dict) -> str:
        return summary_service.build_package_markdown(pkg)

    def _build_package_plain_text(pkg: dict) -> str:
        return summary_service.build_package_plain_text(pkg)

    def _write_simple_pdf(path, title: str, text: str):
        _ = title
        summary_service.write_simple_pdf(path, text)

    def _export_package_markdown(pkg: dict):
        try:
            export_dir = get_data_dir() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_base = _safe_file_stub(pkg.get("titulo") or "pacote_estudo")
            out_path = export_dir / f"{nome_base}_{stamp}.md"
            markdown = _build_package_markdown(pkg)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(markdown)
            status_text.value = f"Resumo exportado: {out_path}"
            status_text.color = CORES["sucesso"]
            if page:
                ds_toast(page, "Exportado em Markdown.", tipo="sucesso")
                page.update()
        except Exception as ex:
            log_exception(ex, "_export_package_markdown")
            status_text.value = "Falha ao exportar Markdown."
            status_text.color = CORES["erro"]
            if page:
                ds_toast(page, "Erro ao exportar Markdown.", tipo="erro")
                page.update()

    def _export_package_pdf(pkg: dict):
        try:
            export_dir = get_data_dir() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_base = _safe_file_stub(pkg.get("titulo") or "pacote_estudo")
            out_path = export_dir / f"{nome_base}_{stamp}.pdf"
            plain_text = _build_package_plain_text(pkg)
            _write_simple_pdf(out_path, str(pkg.get("titulo") or "Pacote de Estudo"), plain_text)
            status_text.value = f"PDF exportado: {out_path}"
            status_text.color = CORES["sucesso"]
            if page:
                ds_toast(page, "Exportado em PDF.", tipo="sucesso")
                page.update()
        except Exception as ex:
            log_exception(ex, "_export_package_pdf")
            status_text.value = "Falha ao exportar PDF."
            status_text.color = CORES["erro"]
            if page:
                ds_toast(page, "Erro ao exportar PDF.", tipo="erro")
                page.update()

    def _refresh_packages():
        package_list.controls.clear()
        try:
            packs = db.listar_study_packages(user["id"], limite=8)
        except Exception as ex:
            log_exception(ex, "_refresh_packages")
            packs = []
        packs_count_text.value = str(len(packs))
        if not packs:
            package_list.controls.append(
                ft.Text("Nenhum pacote gerado ainda.", size=11, color=_color("texto_sec", dark))
            )
            return
        for p in packs:
            p = _as_dict(p)
            dados = _as_dict(p.get("dados"))
            qcount = len(dados.get("questoes") or [])
            fcount = len(dados.get("flashcards") or [])
            package_list.controls.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=_color("card", dark),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(p.get("titulo", "Pacote"), weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                            ft.Text(f"{qcount} questoes - {fcount} flashcards", size=11, color=_color("texto_sec", dark)),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                ],
                            ),
                            ft.ResponsiveRow(
                                [
                                    ft.Container(
                                        col={"xs": 12, "md": 4},
                                        content=ft.TextButton(
                                            "Quiz",
                                            icon=ft.Icons.PLAY_ARROW,
                                            on_click=lambda _, d=dados: _start_quiz_from_package(d),
                                        ),
                                    ),
                                    ft.Container(
                                        col={"xs": 12, "md": 4},
                                        content=ft.TextButton(
                                            "Cards",
                                            icon=ft.Icons.STYLE_OUTLINED,
                                            on_click=lambda _, d=dados: _start_flashcards_from_package(d),
                                        ),
                                    ),
                                    ft.Container(
                                        col={"xs": 12, "md": 4},
                                        content=ft.TextButton(
                                            "Plano",
                                            icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                                            on_click=lambda _, item=p: _start_plan_from_package(item),
                                        ),
                                    ),
                                    ft.Container(
                                        col={"xs": 12, "md": 12},
                                        alignment=ft.Alignment(1, 0),
                                        content=ft.PopupMenuButton(
                                            icon=ft.Icons.MORE_HORIZ,
                                            tooltip="Mais acoes",
                                            items=[
                                                ft.PopupMenuItem(
                                                    text="Exportar .md",
                                                    icon=ft.Icons.DOWNLOAD_OUTLINED,
                                                    on_click=lambda _, item=p: _export_package_markdown(item),
                                                ),
                                                ft.PopupMenuItem(
                                                    text="Exportar .pdf",
                                                    icon=ft.Icons.PICTURE_AS_PDF,
                                                    on_click=lambda _, item=p: _export_package_pdf(item),
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                                run_spacing=6,
                                spacing=6,
                            ),
                        ],
                        spacing=6,
                    ),
                )
            )

    async def _generate_package_async(file_id: int, file_name: str):
        if not page:
            return
        status_text.value = f"Gerando pacote: {file_name}..."
        status_text.color = _color("texto_sec", dark)
        upload_ring.visible = True
        page.update()
        try:
            content_txt = await asyncio.to_thread(library_service.get_conteudo_arquivo, file_id)
            if not content_txt.strip():
                status_text.value = "Arquivo sem texto para pacote."
                status_text.color = CORES["warning"]
                return
            chunks = [line.strip() for line in content_txt.splitlines() if line.strip()]
            source_hash = hashlib.sha256(
                f"{file_name}\n{content_txt[:180000]}".encode("utf-8", errors="ignore")
            ).hexdigest()
            service = _create_user_ai_service(user)
            summary = {
                "titulo": f"Resumo de {file_name}",
                "resumo_curto": "Resumo indisponivel.",
                "resumo_estruturado": [],
                "topicos_principais": [],
                "definicoes": [],
                "exemplos": [],
                "pegadinhas": [],
                "checklist_de_estudo": [],
                "sugestoes_flashcards": [],
                "sugestoes_questoes": [],
                "resumo": "Resumo indisponivel.",
                "topicos": [],
            }
            summary_from_cache = False
            if db and user.get("id"):
                cached = db.obter_resumo_por_hash(int(user["id"]), source_hash)
                if isinstance(cached, dict) and cached:
                    summary = cached
                    summary_from_cache = True
                    status_text.value = "Resumo reutilizado do cache. Gerando questoes..."
            questoes = []
            flashcards = []
            if service:
                if not summary_from_cache:
                    if (not _is_premium_active(user)) and db and user.get("id"):
                        allowed, _used = db.consumir_limite_diario(int(user["id"]), "study_summary", 2)
                        if not allowed:
                            status_text.value = "Plano Free: limite de 2 resumos/dia atingido."
                            status_text.color = CORES["warning"]
                            _show_upgrade_dialog(page, navigate, "No Premium voce gera resumos ilimitados por dia.")
                            return
                    summary = await asyncio.to_thread(service.generate_study_summary, chunks, file_name, 1)
                    if db and user.get("id"):
                        try:
                            db.salvar_resumo_por_hash(int(user["id"]), source_hash, file_name, summary)
                        except Exception as ex:
                            log_exception(ex, "_generate_package_async.save_summary_cache")
                # Rotação: seleciona chunks menos vistos; monta lista de perguntas a evitar
                _uid = int(user["id"]) if user.get("id") else None
                _chunks_rot = _pick_rotation_chunks(db, _uid, chunks, file_name, qtd_chunks=8) if _QUIZ_ROTATION_ENABLED else chunks
                _evitar = _build_evitar_block(db, _uid, file_name, limite=20) if _QUIZ_ROTATION_ENABLED else []
                lote_quiz = await asyncio.to_thread(
                    service.generate_quiz_batch,
                    _chunks_rot,
                    file_name,
                    "Intermediario",
                    3,
                    1,
                    _evitar,
                )
                # Valida estrutura e remove duplicatas antes de entregar para a UI
                lote_quiz_filtrado = []
                for _q in (lote_quiz or []):
                    if _QUIZ_ROTATION_ENABLED and not _validate_question(_q):
                        continue
                    if _QUIZ_ROTATION_ENABLED:
                        _q = _sanitize_question(_q)
                    lote_quiz_filtrado.append(_q)
                if _QUIZ_ROTATION_ENABLED and _uid:
                    lote_quiz_filtrado = _filter_new_questions(db, _uid, lote_quiz_filtrado, file_name)
                    _register_seen(db, _uid, lote_quiz_filtrado, file_name)
                lote_quiz = lote_quiz_filtrado
                for q in lote_quiz or []:
                    questoes.append(
                        _sanitize_payload_texts({
                            "enunciado": q.get("pergunta", ""),
                            "alternativas": q.get("opcoes", []),
                            "correta_index": q.get("correta_index", 0),
                        })
                    )
                flashcards = await asyncio.to_thread(service.generate_flashcards, chunks, 5, 1)
            if not questoes:
                questoes = random.sample(DEFAULT_QUIZ_QUESTIONS, min(3, len(DEFAULT_QUIZ_QUESTIONS)))
            if db and user.get("id"):
                try:
                    if flashcards:
                        db.salvar_flashcards_gerados(int(user["id"]), str(file_name or "Geral"), flashcards, "intermediario")
                    if questoes:
                        from core.repositories.question_progress_repository import QuestionProgressRepository
                        qrepo = QuestionProgressRepository(db)
                        for q in questoes:
                            if isinstance(q, dict):
                                qrepo.register_result(int(user["id"]), q, "mark")
                except Exception as ex:
                    log_exception(ex, "_generate_package_async.integrate_review_flow")
            resumo_curto = str(summary.get("resumo_curto") or summary.get("resumo") or "").strip()
            topicos_principais = summary.get("topicos_principais") or summary.get("topicos") or []
            if not isinstance(topicos_principais, list):
                topicos_principais = []
            pacote = {
                "resumo": resumo_curto,
                "topicos": [str(t).strip() for t in topicos_principais if str(t).strip()][:12],
                "summary_v2": summary,
                "questoes": questoes,
                "flashcards": flashcards,
            }
            db.salvar_study_package(user["id"], f"Pacote - {file_name}", file_name, pacote)
            status_text.value = "Pacote gerado e salvo."
            status_text.color = CORES["sucesso"]
            _refresh_packages()
        except Exception as ex:
            log_exception(ex, "_generate_package_async")
            msg = str(ex).lower()
            if "401" in msg or "key" in msg or "auth" in msg:
                 status_text.value = "Erro: API Key invalida!"
                 ds_toast(page, "Chave de API invalida. Verifique Configuracoes.", tipo="erro")
                 _show_api_issue_dialog(page, navigate, "auth")
            elif "429" in msg or "quota" in msg:
                 status_text.value = "Erro: Cota excedida!"
                 ds_toast(page, "Limite gratuito da API excedido.", tipo="erro")
                 _show_api_issue_dialog(page, navigate, "quota")
            else:
                 status_text.value = "Falha tecnica na geracao."
                 ds_toast(page, f"Erro na IA: {msg[:40]}...", tipo="erro")
            status_text.color = CORES["erro"]
        finally:
            upload_ring.visible = False
            page.update()

    def _refresh_list():
        try:
            file_list.controls.clear()
            arquivos = library_service.listar_arquivos(user["id"])
            log_event("library_refresh", f"found {len(arquivos)} files")
            files_count_text.value = str(len(arquivos))
            
            if not arquivos:
                file_list.controls.append(
                    ft.Container(
                        padding=20,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Icon(ft.Icons.LIBRARY_ADD, size=48, color=_color("texto_sec", dark)),
                            ft.Text("Sua biblioteca esta vazia", color=_color("texto_sec", dark)),
                            ft.Text("Faca upload de PDFs para usar nos quizzes", size=12, color=_color("texto_sec", dark))
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                    )
                )
            else:
                for arq in arquivos:
                    nome = arq["nome_arquivo"]
                    date_str = arq.get("data_upload", "")[:10]
                    fid = arq["id"]
                    
                    # Botao de excluir
                    btn_delete = ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, 
                        icon_color=CORES["erro"],
                        tooltip="Excluir",
                        on_click=lambda _, i=fid: _delete_file(i)
                    )
                    btn_package = ft.IconButton(
                        icon=ft.Icons.AUTO_AWESOME,
                        tooltip="Gerar pacote",
                        on_click=lambda _, i=fid, n=nome: _schedule_ai_task(
                            page,
                            state,
                            _generate_package_async,
                            i,
                            n,
                            message=f"IA gerando pacote: {n}...",
                            status_control=status_text,
                        ),
                    )
                    
                    file_list.controls.append(
                        ft.Container(
                            padding=8,
                            border_radius=8,
                            bgcolor=_color("card", dark),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.PICTURE_AS_PDF if nome.endswith(".pdf") else ft.Icons.DESCRIPTION, color=CORES["primaria"]),
                                            ft.Column([
                                                ft.Text(nome, weight=ft.FontWeight.BOLD, color=_color("texto", dark), max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                ft.Text(f"{date_str} - {arq.get('total_paginas', 0)} paginas", size=11, color=_color("texto_sec", dark))
                                            ], expand=True, spacing=2),
                                            btn_package,
                                            btn_delete,
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                spacing=4,
                            )
                        )
                    )
            
            if page: page.update()
        except Exception as e:
            log_exception(e, "_refresh_list")

    def _delete_file(file_id):
        def _confirmed_delete():
            try:
                library_service.excluir_arquivo(file_id, user["id"])
                status_text.value = "Arquivo removido."
                status_text.color = CORES["sucesso"]
                if page:
                    ds_toast(page, "Arquivo removido com sucesso.", tipo="sucesso")
                _refresh_list()
            except Exception as e:
                status_text.value = f"Erro: {e}"
                status_text.color = CORES["erro"]
                log_exception(e, "_delete_file")
                if page:
                    ds_toast(page, "Falha ao remover arquivo.", tipo="erro")
                    page.update()

        _show_confirm_dialog(
            page,
            "Excluir arquivo",
            "Deseja excluir este arquivo da biblioteca?",
            _confirmed_delete,
            confirm_label="Excluir",
        )

    async def _upload_files_async():
        guard = _state_async_guard(state)

        def _on_start():
            upload_ring.visible = True
            status_text.value = "Abrindo seletor de arquivos..."
            status_text.color = _color("texto_sec", dark)
            page.update()

        def _on_timeout():
            status_text.value = "Tempo esgotado ao buscar arquivos. Tente novamente."
            status_text.color = CORES["warning"]

        def _on_error(ex: Exception):
            log_exception(ex, "_upload_files_async")
            status_text.value = f"Erro no upload: {ex}"
            status_text.color = CORES["erro"]

        def _on_finish():
            upload_ring.visible = False
            page.update()

        async def _run_upload():
            file_paths = await _pick_study_files(page)
            if not file_paths:
                status_text.value = ""
                return

            if (not _is_premium_active(user)) and len(file_paths) > 1:
                status_text.value = "Plano Free: envie apenas 1 arquivo por vez na Biblioteca."
                status_text.color = CORES["warning"]
                _show_upgrade_dialog(page, navigate, "No Premium, o upload na Biblioteca e ilimitado por envio.")
                return

            count = 0
            failed = []
            for path in file_paths:
                try:
                    library_service.adicionar_arquivo(user["id"], path)
                    count += 1
                except Exception as ex_file:
                    failed.append(os.path.basename(_normalize_uploaded_file_path(path) or str(path)))
                    log_exception(ex_file, "_upload_files_async.add_file")
            if count <= 0:
                status_text.value = "Falha ao adicionar arquivo(s). Verifique o caminho/permissao do PDF."
                status_text.color = CORES["erro"]
                if page:
                    ds_toast(page, "Nao foi possivel adicionar os PDFs selecionados.", tipo="erro")
                return
            if failed:
                status_text.value = f"{count} arquivo(s) adicionados. Ignorados: {len(failed)}."
                status_text.color = CORES["warning"]
                if page:
                    ds_toast(page, f"{count} arquivo(s) adicionados; {len(failed)} falharam.", tipo="warning")
            else:
                status_text.value = f"{count} arquivo(s) adicionado(s) com sucesso!"
                status_text.color = CORES["sucesso"]
                if page:
                    ds_toast(page, f"{count} arquivo(s) adicionado(s) com sucesso!", tipo="sucesso")
            _refresh_list()

        await guard.run(
            "library.upload.files",
            _run_upload,
            timeout_s=300,
            on_start=_on_start,
            on_timeout=_on_timeout,
            on_error=_on_error,
            on_finish=_on_finish,
        )

    def _upload_click(_):
        if page:
            page.run_task(_upload_files_async)

    _refresh_list()
    _refresh_packages()
    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column([
            ds_section_title("Minha Biblioteca", dark=dark),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        col={"sm": 6, "md": 3},
                        content=ds_card(
                            dark=dark,
                            padding=12,
                            content=ft.Column(
                                [ft.Text("Arquivos", size=12, color=_color("texto_sec", dark)), files_count_text],
                                spacing=4,
                            ),
                        ),
                    ),
                    ft.Container(
                        col={"sm": 6, "md": 3},
                        content=ds_card(
                            dark=dark,
                            padding=12,
                            content=ft.Column(
                                [ft.Text("Pacotes", size=12, color=_color("texto_sec", dark)), packs_count_text],
                                spacing=4,
                            ),
                        ),
                    ),
                ],
                spacing=8,
                run_spacing=8,
            ),
            ds_card(
                dark=dark,
                padding=12,
                content=ft.Column(
                    [
                        ft.ResponsiveRow(
                            [
                                ft.Container(
                                    col={"xs": 12, "md": 6},
                                    content=ft.Text("Acoes", size=15, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                                ),
                                ft.Container(
                                    col={"xs": 12, "md": 6},
                                    alignment=ft.Alignment(1, 0),
                                    content=ds_btn_primary(
                                        "Adicionar PDF",
                                        icon=ft.Icons.UPLOAD_FILE,
                                        on_click=_upload_click,
                                        dark=dark,
                                    ),
                                ),
                            ],
                            run_spacing=8,
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            [ft.Container(expand=True, content=status_text), upload_ring],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=8,
                ),
            ),
            ds_card(
                dark=dark,
                padding=12,
                content=ft.Column(
                    [
                        ft.Text("Pacotes de Estudo", size=15, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                        ft.Container(
                            height=208,
                            content=ft.Column([package_list], scroll=ft.ScrollMode.AUTO),
                        ),
                    ],
                    spacing=8,
                ),
            ),
            ds_card(
                dark=dark,
                padding=12,
                content=ft.Column(
                    [
                        ft.Text("Arquivos", size=15, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                        ft.Container(
                            height=286,
                            content=file_list,
                        ),
                    ],
                    spacing=8,
                ),
            ),
        ], expand=True, spacing=10, scroll=ft.ScrollMode.AUTO),
    )


def _build_splash(page: ft.Page, navigate, dark: bool):
    # Splash usa fundo escuro fixo para realÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â§ar a logo
    splash_bg = "#1c1c1c"
    logo, has_image = _logo_control(True)

    logo_box = ft.Container(
        content=logo,
        width=180,
        height=180,
        alignment=ft.Alignment(0, 0),
        animate_size=ft.Animation(350, ft.AnimationCurve.EASE_IN_OUT),
        opacity=0,
        animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
    )

    tagline = ft.Text("Vamos avancar hoje", size=16, color="#cbd5e1", opacity=0,
                      animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT))

    view = ft.View(
        route="/splash",
        controls=[
            ft.Container(
                expand=True,
                bgcolor=splash_bg,
        content=ft.Container(
            expand=True,
            opacity=1,
            animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
                    content=ft.Column(
                        [
                            logo_box,
                            ft.Text("Quiz Vance", size=32, weight=ft.FontWeight.BOLD, color=CORES["fundo"]) if not has_image else ft.Container(),
                            ft.Text("Estude com foco. Avance com pratica.", color="#cbd5e1"),
                            tagline,
                        ],
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.Alignment(0, 0),
                    ),
                ),
            )
        ],
        bgcolor=splash_bg,
    )
    return view, logo_box, tagline




def _build_flashcards_body(state, navigate, dark: bool):
    page = state.get("page")
    screen_w = _screen_width(page) if page else 1280
    compact = screen_w < 1000
    very_compact = screen_w < 760
    field_w_small = max(140, min(220, int(screen_w - 120)))
    user = state.get("usuario") or {}
    db = state.get("db")
    library_service = LibraryService(db) if db else None
    seed_cards = state.pop("flashcards_seed_cards", None)
    session = state.get("flashcards_session")
    if not isinstance(session, dict):
        session = {
            "flashcards": [],
            "estado": {
                "upload_texts": [],
                "upload_names": [],
                "upload_selected_names": [],
                "current_idx": 0,
                "mostrar_verso": False,
                "lembrei": 0,
                "rever": 0,
                "modo_continuo": False,
                "cont_theme": "Conceito",
                "cont_base_content": [],
                "cont_prefetching": False,
                "cont_source_lock_material": False,
                "ui_stage": "config",
                "tema_input": "",
                "referencia_input": "",
                "quantidade_value": "5",
            },
        }
        state["flashcards_session"] = session
    if not isinstance(session.get("flashcards"), list):
        session["flashcards"] = []
    if not isinstance(session.get("estado"), dict):
        session["estado"] = {}
    flashcards = session["flashcards"]
    estado = session["estado"]
    estado.setdefault("upload_texts", [])
    estado.setdefault("upload_names", [])
    estado.setdefault("upload_selected_names", [])
    estado.setdefault("current_idx", 0)
    estado.setdefault("mostrar_verso", False)
    estado.setdefault("lembrei", 0)
    estado.setdefault("rever", 0)
    estado.setdefault("modo_continuo", False)
    estado.setdefault("cont_theme", "Conceito")
    estado.setdefault("cont_base_content", [])
    estado.setdefault("cont_prefetching", False)
    estado.setdefault("cont_source_lock_material", False)
    estado.setdefault("ui_stage", "study" if flashcards else "config")
    estado.setdefault("tema_input", "")
    estado.setdefault("referencia_input", "")
    estado.setdefault("quantidade_value", "5")
    if isinstance(seed_cards, list) and seed_cards:
        try:
            from core.services.flashcards_service import FlashcardsService
            seed_normalized = FlashcardsService.normalize_seed_cards(seed_cards)
        except Exception:
            seed_normalized = []
        seed_normalized = _sanitize_payload_texts(list(seed_normalized or []))
        seed_normalized = [dict(card) for card in seed_normalized if isinstance(card, dict)]
        if seed_normalized:
            flashcards[:] = seed_normalized
            estado["current_idx"] = 0
            estado["mostrar_verso"] = False
            estado["lembrei"] = 0
            estado["rever"] = 0
            estado["ui_stage"] = "study"
    flashcards[:] = _sanitize_payload_texts([dict(card) for card in flashcards if isinstance(card, dict)])
    cards_column = ft.Column(
        spacing=12,
        expand=False,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    cards_host = ft.Container(
        content=cards_column,
        opacity=1.0,
        scale=1.0,
        animate_opacity=ft.Animation(160, ft.AnimationCurve.EASE_IN_OUT),
        animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_IN_OUT),
    )
    carregando = ft.ProgressRing(width=28, height=28, visible=False)
    status_text = ft.Text("", size=12, weight=ft.FontWeight.W_400, color=_color("texto_sec", dark))
    status_estudo = ft.Text("", size=12, weight=ft.FontWeight.W_400, color=_color("texto_sec", dark))
    contador_flashcards = ft.Text("0 flashcards prontos", size=12, color=_color("texto_sec", dark))
    desempenho_text = ft.Text("Lembrei: 0 | Rever: 0", size=12, color=_color("texto_sec", dark))
    etapa_text = ft.Text("Etapa 1 de 2: configure e gere", size=13, weight=ft.FontWeight.W_500, color=_color("texto_sec", dark))
    upload_info = ft.Text(
        "Nenhum material enviado.",
        size=12,
        weight=ft.FontWeight.W_400,
        color=_color("texto_sec", dark),
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
        visible=False,
    )
    material_source_hint = ft.Text(
        "",
        size=11,
        color=_color("texto_sec", dark),
        visible=False,
    )
    ai_enabled = bool(_create_user_ai_service(user))

    tema_field = ft.TextField(
        label="Tema principal",
        hint_text="Ex.: Direito Administrativo",
        expand=True,
        value=str(estado.get("tema_input") or ""),
    )
    referencia_field = ft.TextField(
        label="Referencia ou briefing",
        hint_text="Resumo, texto ou instrucoes para guiar a IA.",
        expand=True,
        min_lines=3,
        max_lines=5,
        multiline=True,
        value=str(estado.get("referencia_input") or ""),
    )
    quantidade_value = str(estado.get("quantidade_value") or "5").strip()
    if quantidade_value not in {"5", "10", "cont"}:
        quantidade_value = "5"
    quantidade_dropdown = ft.Dropdown(
        label="Quantidade",
        width=field_w_small if compact else 160,
        options=[
            ft.dropdown.Option(key="5", text="5 cards"),
            ft.dropdown.Option(key="10", text="10 cards"),
            ft.dropdown.Option(key="cont", text="Continuo"),
        ],
        value=quantidade_value,
    )
    library_files = []
    if library_service and user.get("id"):
        try:
            library_files = library_service.listar_arquivos(user["id"])
        except Exception as ex:
            log_exception(ex, "main._build_flashcards_body.listar_arquivos")
    library_dropdown = ft.Dropdown(
        label="Adicionar da Biblioteca",
        width=field_w_small if compact else 300,
        options=[ft.dropdown.Option(str(f["id"]), text=str(f["nome_arquivo"])) for f in library_files],
        disabled=not library_files,
    )

    def _persist_form_inputs(_=None):
        estado["tema_input"] = str(tema_field.value or "").strip()
        estado["referencia_input"] = str(referencia_field.value or "")
        qtd_val = str(quantidade_dropdown.value or "5").strip()
        if qtd_val not in {"5", "10", "cont"}:
            qtd_val = "5"
        estado["quantidade_value"] = qtd_val

    tema_field.on_change = _persist_form_inputs
    referencia_field.on_change = _persist_form_inputs
    quantidade_dropdown.on_change = _persist_form_inputs

    def _set_upload_info():
        names = estado["upload_names"] or estado.get("upload_selected_names") or []
        upload_info.value = _format_upload_info_label(names)
        upload_info.visible = bool(names)
        if estado.get("upload_texts"):
            material_source_hint.value = "Fonte ativa: material anexado. Os flashcards serao gerados desse conteudo."
            material_source_hint.visible = True
        elif names:
            material_source_hint.value = "Arquivo selecionado, mas sem texto extraido. Gere apenas apos carregar texto do PDF."
            material_source_hint.visible = True
        else:
            material_source_hint.value = ""
            material_source_hint.visible = False

    def _guess_topic_from_name(raw_name: str) -> str:
        nome = str(raw_name or "").strip()
        if nome.startswith("[LIB]"):
            nome = nome[5:].strip()
        nome = os.path.basename(nome)
        guess = os.path.splitext(nome)[0].replace("_", " ").replace("-", " ").strip()
        return " ".join(guess.split())[:64]

    def _resolve_theme_value() -> str:
        manual = str(tema_field.value or "").strip()
        if manual:
            return manual
        names = list(estado.get("upload_names") or estado.get("upload_selected_names") or [])
        for raw_name in names:
            guessed = _guess_topic_from_name(raw_name)
            if guessed:
                return guessed
        return "Tema livre"

    def _on_library_select(e):
        fid = getattr(e.control, "value", None)
        if not fid or not library_service:
            return
        nome = next((str(f.get("nome_arquivo") or "Arquivo Biblioteca") for f in library_files if str(f.get("id")) == str(fid)), "Arquivo Biblioteca")
        nome_tag = f"[LIB] {nome}"
        estado["upload_selected_names"] = [nome_tag]
        try:
            texto = library_service.get_conteudo_arquivo(int(fid))
        except Exception as ex:
            log_exception(ex, "main._build_flashcards_body.library_select")
            texto = ""
            if texto:
                # Biblioteca selecionada vira a fonte principal (sem misturar com anexos antigos).
                estado["upload_texts"] = [texto]
                estado["upload_names"] = [nome_tag]
                if not str(tema_field.value or "").strip():
                    guessed = _guess_topic_from_name(nome_tag)
                    if guessed:
                        tema_field.value = guessed
                _persist_form_inputs()
                _set_upload_info()
                _set_feedback_text(status_text, f"Adicionado da biblioteca: {nome}", "success")
        else:
            estado["upload_texts"] = []
            estado["upload_names"] = []
            _set_upload_info()
            _set_feedback_text(status_text, "Arquivo da biblioteca sem texto extraivel.", "warning")
        e.control.value = None
        try:
            e.control.update()
        except Exception:
            pass
        if page:
            page.update()

    library_dropdown.on_change = _on_library_select

    async def _pick_files_async():
        if not page:
            return
        guard = _state_async_guard(state)

        def _on_start():
            _set_feedback_text(status_text, "Abrindo seletor de arquivos...", "info")
            page.update()

        def _on_timeout():
            _set_feedback_text(status_text, "Tempo esgotado ao buscar arquivos.", "warning")

        def _on_error(ex: Exception):
            log_exception(ex, "main._build_flashcards_body._pick_files_async")
            _set_feedback_text(status_text, "Falha ao abrir arquivos.", "error")

        async def _run_pick():
            file_paths = await _pick_study_files(page)
            if not file_paths:
                _set_feedback_text(status_text, "", "info")
                return
            estado["upload_selected_names"] = [
                (os.path.basename(_normalize_uploaded_file_path(fp) or str(fp or "")) or "arquivo")
                for fp in file_paths
            ]
            upload_texts, upload_names, failed_names = _extract_uploaded_material(file_paths)
            estado["upload_texts"] = upload_texts
            estado["upload_names"] = upload_names
            if not upload_texts:
                _set_feedback_text(
                    status_text,
                    (
                        "Nao foi possivel extrair texto dos arquivos. "
                        "Para PDF, confirme que nao e imagem escaneada ou protegido por senha."
                    ),
                    "warning",
                )
            else:
                if failed_names:
                    _set_feedback_text(
                        status_text,
                        f"Material carregado: {len(upload_texts)} arquivo(s). Ignorados: {len(failed_names)}.",
                        "warning",
                    )
                else:
                    _set_feedback_text(status_text, f"Material carregado: {len(upload_texts)} arquivo(s).", "success")
            _set_upload_info()

        await guard.run(
            "flashcards.upload.files",
            _run_pick,
            timeout_s=180,
            on_start=_on_start,
            on_timeout=_on_timeout,
            on_error=_on_error,
            on_finish=lambda: page.update(),
        )

    def _upload_material(_):
        if not page:
            return
        page.run_task(_pick_files_async)

    def _limpar_material(_):
        if not estado["upload_texts"] and not estado["upload_names"]:
            _set_feedback_text(status_text, "Nao ha material para remover.", "info")
            if page:
                page.update()
            return

        def _confirmed_clear():
            estado["upload_texts"] = []
            estado["upload_names"] = []
            estado["upload_selected_names"] = []
            estado["cont_source_lock_material"] = False
            _set_upload_info()
            _set_feedback_text(status_text, "Material removido.", "info")
            if page:
                ds_toast(page, "Material removido.", tipo="info")
                page.update()

        _show_confirm_dialog(
            page,
            "Limpar material",
            "Deseja remover todo material anexado desta sessao?",
            _confirmed_clear,
            confirm_label="Limpar",
        )

    def _mostrar_etapa_config():
        estado["ui_stage"] = "config"
        etapa_text.value = "Etapa 1 de 2: configure e gere"
        config_section.visible = True
        study_section.visible = False

    def _mostrar_etapa_estudo():
        estado["ui_stage"] = "study"
        etapa_text.value = "Etapa 2 de 2: revise os flashcards"
        config_section.visible = False
        study_section.visible = True

    def _render_flashcards():
        cards_column.controls.clear()
        screen = (_screen_width(page) if page else 1280)
        screen_h = (_screen_height(page) if page else 820)
        is_compact = screen < 1000
        very_compact_local = screen < 760
        title_font = 20 if screen < 900 else (24 if screen < 1280 else 28)
        card_w = min(560, max(280, int(screen * (0.90 if screen < 760 else (0.58 if is_compact else 0.50)))))
        if not flashcards:
            cards_column.controls.append(
                ft.Container(
                    width=card_w,
                    padding=14,
                    border_radius=10,
                    bgcolor=_color("card", dark),
                    content=ft.Text("Nenhum flashcard carregado.", color=_color("texto_sec", dark)),
                )
            )
            contador_flashcards.value = "0 flashcards prontos"
            desempenho_text.value = "Lembrei: 0 | Rever: 0"
            return

        idx = int(max(0, min(len(flashcards) - 1, estado["current_idx"])))
        estado["current_idx"] = idx
        card = dict(flashcards[idx]) if isinstance(flashcards[idx], dict) else {}
        frente = _fix_mojibake_text(str(card.get("frente", "")))
        verso = _fix_mojibake_text(str(card.get("verso", "")))
        front_len = len(frente or "")
        front_lines = max(1, str(frente or "").count("\n") + 1)
        front_font = (
            14 if front_len > 820 else
            15 if front_len > 620 else
            16 if front_len > 420 else
            17 if front_len > 300 else
            (18 if very_compact_local else title_font)
        )
        chars_per_line = 26 if card_w < 360 else (32 if card_w < 460 else 38)
        wrapped_lines = max(front_lines, max(1, int((front_len + chars_per_line - 1) / chars_per_line)))
        min_h = 240 if very_compact_local else (260 if is_compact else 280)
        max_h = max(340, min(620, int(screen_h * 0.76)))
        front_block_h = 140 + (wrapped_lines * max(18, front_font + 7))
        verso_block_h = 0
        if bool(estado.get("mostrar_verso")):
            verso_len = len(verso or "")
            verso_lines = max(2, int((verso_len + (chars_per_line + 4) - 1) / (chars_per_line + 4)))
            verso_block_h = 72 + min(180, verso_lines * 16)
        card_h = min(max_h, max(min_h, front_block_h + verso_block_h))
        revelou = bool(estado["mostrar_verso"])
        if dark:
            card_bg = "#111827" if not revelou else "#1F2937"
            inner_bg = "#0F172A" if not revelou else "#111827"
        else:
            card_bg = "#DDE2EC" if not revelou else "#FFFFFF"
            inner_bg = "#D1D7E3" if not revelou else "#F3F4F6"

        cards_column.controls.append(
            ds_card(
                dark=dark,
                width=card_w,
                height=card_h,
                padding=14,
                border_radius=DS.R_XXL,
                bgcolor=card_bg,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"Card {idx + 1}/{len(flashcards)}", size=12, color=_color("texto_sec", dark)),
                                ds_badge("Verso" if revelou else "Frente", color=CORES["primaria"]),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Container(
                            expand=True,
                            padding=14,
                            border_radius=DS.R_LG,
                            bgcolor=inner_bg,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        expand=True,
                                        alignment=ft.Alignment(-1, -1),
                                        content=ft.ListView(
                                            controls=[
                                                ds_content_text(
                                                    frente,
                                                    dark=dark,
                                                    variant="h3",
                                                    size=front_font,
                                                    weight=ft.FontWeight.BOLD,
                                                    text_align=ft.TextAlign.LEFT,
                                                )
                                            ],
                                            spacing=0,
                                            expand=True,
                                            auto_scroll=False,
                                        ),
                                    ),
                                    ft.Container(
                                        visible=bool(estado["mostrar_verso"]),
                                        padding=12,
                                        border_radius=DS.R_MD,
                                        bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]),
                                        content=ft.Column(
                                            [
                                                ft.Text("Resposta", size=11, weight=ft.FontWeight.W_600, color=CORES["primaria"]),
                                                ds_content_text(
                                                    verso,
                                                    dark=dark,
                                                    variant="body",
                                                    text_align=ft.TextAlign.LEFT,
                                                ),
                                            ],
                                            spacing=6,
                                            horizontal_alignment=ft.CrossAxisAlignment.START,
                                        ),
                                    ),
                                ],
                                spacing=10,
                                expand=True,
                            ),
                        ),
                    ],
                    spacing=12,
                    expand=True,
                ),
            )
        )
        if estado.get("modo_continuo"):
            contador_flashcards.value = f"Prontos: {len(flashcards)} (continuo)"
        else:
            contador_flashcards.value = f"Prontos: {len(flashcards)}"
        desempenho_text.value = f"Lembrei {estado['lembrei']} | Rever {estado['rever']}"
        _sanitize_control_texts(cards_column)

    async def _animate_card_transition(mutator):
        if page:
            cards_host.opacity = 0.0
            cards_host.scale = 0.97
            page.update()
            await asyncio.sleep(0.10)
        mutator()
        _render_flashcards()
        if page:
            cards_host.opacity = 1.0
            cards_host.scale = 1.0
            page.update()

    def _prev_card(_=None):
        if not flashcards:
            return
        if estado.get("modo_continuo"):
            estado["current_idx"] = (estado["current_idx"] - 1) % max(1, len(flashcards))
        else:
            estado["current_idx"] = max(0, estado["current_idx"] - 1)
        estado["mostrar_verso"] = False
        _render_flashcards()
        if page:
            page.update()

    def _next_card(_=None):
        if not flashcards:
            return
        if estado.get("modo_continuo"):
            estado["current_idx"] = (estado["current_idx"] + 1) % max(1, len(flashcards))
        else:
            estado["current_idx"] = min(len(flashcards) - 1, estado["current_idx"] + 1)
        estado["mostrar_verso"] = False
        _render_flashcards()
        _maybe_prefetch_more()
        if page:
            page.update()

    def _mostrar_resposta(_=None):
        estado["mostrar_verso"] = True
        _render_flashcards()
        if page:
            page.update()

    def _registrar_avaliacao(lembrei: bool):
        if not flashcards:
            return
        if lembrei:
            estado["lembrei"] += 1
        else:
            estado["rever"] += 1
        if db and user.get("id"):
            try:
                db.registrar_progresso_diario(user["id"], flashcards=1)
            except Exception as ex:
                log_exception(ex, "main._build_flashcards_body._registrar_avaliacao")
        if estado.get("modo_continuo"):
            estado["current_idx"] = (estado["current_idx"] + 1) % max(1, len(flashcards))
        elif estado["current_idx"] < len(flashcards) - 1:
            estado["current_idx"] += 1
        estado["mostrar_verso"] = False
        status_estudo.value = "Card marcado como dominado." if lembrei else "Card marcado para revisar."
        _render_flashcards()
        _maybe_prefetch_more()
        if page:
            page.update()

    def _mark_lembrei(_=None):
        _registrar_avaliacao(True)

    def _mark_rever(_=None):
        _registrar_avaliacao(False)

    async def _prev_card_animated():
        if not flashcards:
            return
        await _animate_card_transition(lambda: (
            estado.__setitem__("current_idx", max(0, estado["current_idx"] - 1)),
            estado.__setitem__("mostrar_verso", False),
        ))

    async def _next_card_animated():
        if not flashcards:
            return
        if estado.get("modo_continuo"):
            await _animate_card_transition(lambda: (
                estado.__setitem__("current_idx", (estado["current_idx"] + 1) % max(1, len(flashcards))),
                estado.__setitem__("mostrar_verso", False),
            ))
        else:
            await _animate_card_transition(lambda: (
                estado.__setitem__("current_idx", min(len(flashcards) - 1, estado["current_idx"] + 1)),
                estado.__setitem__("mostrar_verso", False),
            ))
        _maybe_prefetch_more()

    async def _prefetch_more_flashcards_async():
        if not page:
            return
        if not estado.get("modo_continuo") or estado.get("cont_prefetching"):
            return
        estado["cont_prefetching"] = True
        strict_material_source = bool(estado.get("cont_source_lock_material"))
        tema = str(estado.get("cont_theme") or "Conceito").strip() or "Conceito"
        base_content = list(estado.get("cont_base_content") or [])
        if not base_content and tema:
            base_content = [tema]
        prefetch_qtd = 5
        profile = _generation_profile(user, "flashcards")
        service = _create_user_ai_service(user, force_economic=bool(profile.get("force_economic")))
        novos = []
        try:
            if service and base_content:
                try:
                    novos = await asyncio.to_thread(service.generate_flashcards, base_content, prefetch_qtd)
                except Exception as ex:
                    log_exception(ex, "main._build_flashcards_body.prefetch")
            if not novos and strict_material_source:
                _set_feedback_text(status_estudo, "Modo continuo: sem novos cards do material anexado no momento.", "warning")
                if page:
                    page.update()
                return
            if not novos:
                base_idx = len(flashcards)
                novos = [
                    {
                        "frente": f"{tema} {base_idx + i + 1}",
                        "verso": f"Resumo ou dica sobre {tema} ({base_idx + i + 1}).",
                    }
                    for i in range(prefetch_qtd)
                ]
            novos = _sanitize_payload_texts(list(novos or []))
            novos = [dict(card) for card in novos if isinstance(card, dict)]
            if novos:
                flashcards.extend(novos)
                _render_flashcards()
                if page:
                    page.update()
        finally:
            estado["cont_prefetching"] = False

    def _maybe_prefetch_more():
        if not (page and estado.get("modo_continuo")):
            return
        if estado.get("cont_prefetching"):
            return
        total = len(flashcards)
        idx = int(estado.get("current_idx") or 0)
        if total > 0 and (total - idx) <= 3:
            page.run_task(_prefetch_more_flashcards_async)

    async def _mostrar_resposta_animated():
        if not flashcards or estado["mostrar_verso"]:
            return
        await _animate_card_transition(lambda: estado.__setitem__("mostrar_verso", True))

    def _prev_card_click(_):
        if page:
            page.run_task(_prev_card_animated)
        else:
            _prev_card()

    def _next_card_click(_):
        if page:
            page.run_task(_next_card_animated)
        else:
            _next_card()

    def _mostrar_resposta_click(_):
        if page:
            page.run_task(_mostrar_resposta_animated)
        else:
            _mostrar_resposta()

    async def _gerar_flashcards_async():
        if not page:
            return
        _persist_form_inputs()
        gerar_button.disabled = True
        carregando.visible = True
        pre_profile = _generation_profile(user, "flashcards")
        if pre_profile.get("label") == "free_slow":
            _set_feedback_text(status_text, "Modo Free: gerando flashcards (economico e mais lento)...", "info")
        else:
            _set_feedback_text(status_text, "Gerando flashcards...", "info")
        page.update()

        try:
            modo_continuo = (quantidade_dropdown.value == "cont")
            quantidade = 20 if modo_continuo else max(1, min(10, int(quantidade_dropdown.value or "5")))
        except ValueError:
            quantidade = 5
            modo_continuo = False
        estado["modo_continuo"] = bool(modo_continuo)

        tema = (tema_field.value or "Conceito").strip()
        selected_library_id = str(getattr(library_dropdown, "value", "") or "").strip()
        if selected_library_id and library_service:
            nome = next(
                (str(f.get("nome_arquivo") or "Arquivo Biblioteca") for f in (library_files or []) if str(f.get("id")) == selected_library_id),
                "Arquivo Biblioteca",
            )
            nome_tag = f"[LIB] {nome}"
            estado["upload_selected_names"] = [nome_tag]
            try:
                texto_lib = library_service.get_conteudo_arquivo(int(selected_library_id))
            except Exception:
                texto_lib = ""
            if texto_lib:
                estado["upload_texts"] = [texto_lib]
                estado["upload_names"] = [nome_tag]
                if not tema.strip():
                    tema = _guess_topic_from_name(nome_tag)
                    tema_field.value = tema
                    _persist_form_inputs()
            else:
                estado["upload_texts"] = []
                estado["upload_names"] = []
            _set_upload_info()
        material_selected = bool(estado.get("upload_selected_names")) or bool(estado.get("upload_names"))
        material_text_ready = bool(estado.get("upload_texts"))
        if material_selected and (not material_text_ready):
            _set_feedback_text(
                status_text,
                "PDF selecionado, mas sem texto extraido. Use um PDF com texto selecionavel (nao escaneado) ou adicione referencia.",
                "warning",
            )
            carregando.visible = False
            gerar_button.disabled = False
            page.update()
            return
        material_source_locked = bool(material_selected and material_text_ready)
        if material_source_locked and not tema:
            first_pool = (estado.get("upload_names") or estado.get("upload_selected_names") or [""])
            first_name = str(first_pool[0] or "").strip()
            if first_name.startswith("[LIB]"):
                first_name = first_name[5:].strip()
            first_name = os.path.basename(first_name)
            guess_topic = os.path.splitext(first_name)[0].replace("_", " ").replace("-", " ").strip()
            guess_topic = " ".join(guess_topic.split())
            if guess_topic:
                tema = guess_topic[:64]
                tema_field.value = tema
                _persist_form_inputs()
        referencia = [line.strip() for line in (referencia_field.value or "").splitlines() if line.strip()]
        base_content = list(estado["upload_texts"]) + referencia
        if material_source_locked:
            base_content.append(
                "INSTRUCAO DE FOCO: Gere os flashcards com base principal no material anexado, sem sair do assunto."
            )
        if not base_content and tema:
            base_content = [tema]
        estado["cont_theme"] = tema or "Conceito"
        estado["cont_base_content"] = list(base_content)
        estado["cont_prefetching"] = False
        estado["cont_source_lock_material"] = material_source_locked
        gen_profile = pre_profile
        service = _create_user_ai_service(user, force_economic=bool(gen_profile.get("force_economic")))
        gerados = []
        if material_source_locked and not service:
            _set_feedback_text(status_text, "Para gerar flashcards do PDF, configure a IA em Configuracoes.", "warning")
            carregando.visible = False
            gerar_button.disabled = False
            page.update()
            return

        if gen_profile.get("delay_s", 0) > 0:
            await asyncio.sleep(float(gen_profile["delay_s"]))
        if service and base_content:
            try:
                gerados = await asyncio.to_thread(service.generate_flashcards, base_content, quantidade)
            except Exception as ex:
                log_exception(ex, "main._build_flashcards_body")
        if not gerados:
            if material_source_locked:
                _set_feedback_text(
                    status_text,
                    "Nao consegui gerar flashcards do material anexado. Revise o PDF/referencia e tente novamente.",
                    "warning",
                )
                if _is_ai_quota_exceeded(service):
                    _show_quota_dialog(page, navigate)
                carregando.visible = False
                gerar_button.disabled = False
                page.update()
                return
            base = tema or "Conceito"
            gerados = [
                {"frente": f"{base} {i+1}", "verso": f"Resumo ou dica do {base} {i+1}."}
                for i in range(quantidade)
            ]
            if _is_ai_quota_exceeded(service):
                _set_feedback_text(status_text, "Cotas da IA esgotadas. Flashcards offline prontos.", "warning")
                _show_quota_dialog(page, navigate)
            else:
                _set_feedback_text(status_text, "Flashcards offline prontos.", "info")
        else:
            _set_feedback_text(status_text, f"{len(gerados)} flashcards gerados com IA.", "success")
        gerados = _sanitize_payload_texts(list(gerados or []))
        flashcards[:] = [dict(card) for card in gerados if isinstance(card, dict)]
        estado["current_idx"] = 0
        estado["mostrar_verso"] = False
        estado["lembrei"] = 0
        estado["rever"] = 0
        _render_flashcards()
        _maybe_prefetch_more()
        if estado.get("modo_continuo"):
            status_estudo.value = f"{status_text.value} Modo continuo ativo: novos cards serao adicionados automaticamente."
        else:
            status_estudo.value = status_text.value
        _mostrar_etapa_estudo()
        carregando.visible = False
        gerar_button.disabled = False
        page.update()

    def _on_gerar(e):
        if not page:
            return
        _schedule_ai_task(
            page,
            state,
            _gerar_flashcards_async,
            message="IA gerando flashcards...",
            status_control=status_text,
        )

    gerar_button = ds_btn_primary(
        "Gerar e iniciar revisao",
        icon=ft.Icons.BOLT,
        on_click=_on_gerar,
        dark=dark,
        expand=True,
    )

    def _voltar_config(_):
        _mostrar_etapa_config()
        if page:
            page.update()

    config_section = ft.Column(
        [
            ds_card(
                dark=dark,
                padding=14,
                content=ft.Column(
                    [
                        ft.Text("Gere seus flashcards", size=17, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                        ft.ResponsiveRow(
                            [
                                ft.Container(content=tema_field, col={"sm": 12, "md": 8}),
                                ft.Container(content=quantidade_dropdown, col={"sm": 12, "md": 4}),
                            ],
                            spacing=12,
                            run_spacing=8,
                        ),
                        referencia_field,
                        ft.ResponsiveRow(
                            [
                                ft.Container(
                                    col={"xs": 12, "md": 4},
                                    content=ds_btn_secondary("Anexar material", icon=ft.Icons.UPLOAD_FILE, on_click=_upload_material, dark=dark, expand=True),
                                ),
                                ft.Container(
                                    col={"xs": 12, "md": 5},
                                    content=library_dropdown,
                                ),
                                ft.Container(
                                    col={"xs": 12, "md": 3},
                                    content=ds_btn_ghost("Limpar material", on_click=_limpar_material, dark=dark),
                                ),
                                ft.Container(col={"xs": 12, "md": 12}, content=upload_info),
                                ft.Container(col={"xs": 12, "md": 12}, content=material_source_hint),
                            ],
                            run_spacing=6,
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.ResponsiveRow(
                            [
                                ft.Container(col={"xs": 12, "md": 4}, content=gerar_button),
                                ft.Container(
                                    col={"xs": 12, "md": 8},
                                    content=ft.Column([carregando, _status_banner(status_text, dark)], spacing=6),
                                ),
                            ],
                            run_spacing=6,
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=8,
                ),
            ),
        ],
        spacing=10,
        visible=True,
    )

    study_section = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Revisao de flashcards", size=17, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                    ft.Row([contador_flashcards, desempenho_text], spacing=10, wrap=True),
                ],
                wrap=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            _status_banner(status_estudo, dark),
            ft.Container(
                alignment=ft.Alignment(0, 0),
                content=cards_host,
            ),
            ds_action_bar(
                [
                    {"label": "Mostrar resposta", "icon": ft.Icons.VISIBILITY, "on_click": _mostrar_resposta_click, "kind": "primary"},
                    {"label": "Lembrei", "icon": ft.Icons.CHECK_CIRCLE, "on_click": _mark_lembrei, "kind": "primary"},
                    {"label": "Rever", "icon": ft.Icons.REFRESH, "on_click": _mark_rever, "kind": "warning"},
                ],
                dark=dark,
            ),
            ft.ResponsiveRow(
                [
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ds_btn_secondary("Anterior", icon=ft.Icons.CHEVRON_LEFT, on_click=_prev_card_click, dark=dark, expand=True),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ds_btn_secondary("Proximo", icon=ft.Icons.CHEVRON_RIGHT, on_click=_next_card_click, dark=dark, expand=True),
                    ),
                ],
                run_spacing=6,
                spacing=10,
            ),
            ft.ResponsiveRow(
                [
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ds_btn_ghost("Voltar para configuracao", icon=ft.Icons.ARROW_BACK, on_click=_voltar_config, dark=dark),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ds_btn_ghost("Voltar ao Inicio", icon=ft.Icons.HOME_OUTLINED, on_click=lambda _: navigate("/home"), dark=dark),
                    ),
                ],
                run_spacing=6,
                spacing=10,
            ),
        ],
        spacing=10,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        visible=False,
    )

    _set_upload_info()
    _render_flashcards()
    if estado.get("ui_stage") == "study" and flashcards:
        _mostrar_etapa_estudo()
    else:
        _mostrar_etapa_config()

    retorno = _wrap_study_content(
        ft.Column(
            [
                _build_focus_header("Flashcards", "Fluxo: 1) Configure  2) Gere  3) Revise ativamente", etapa_text, dark),
                config_section,
                study_section,
            ],
            spacing=12,
            expand=True,
        ),
        dark,
    )
    if not ai_enabled:
        status_text.value = "Configure uma API key em Configuracoes para liberar a IA."
    return retorno


def _build_open_quiz_body(state, navigate, dark: bool):
    page = state.get("page")
    screen_h = _screen_height(page) if page else 820
    screen_w = _screen_width(page) if page else 1280
    user = state.get("usuario") or {}
    db = state.get("db")
    library_service = LibraryService(db) if db else None
    backend = state.get("backend")
    service = _create_user_ai_service(user)
    runtime = state.setdefault("open_quiz_runtime", {}) if isinstance(state, dict) else {}
    if not isinstance(runtime, dict):
        runtime = {}
        if isinstance(state, dict):
            state["open_quiz_runtime"] = runtime
    status = ft.Text("", size=12, color=_color("texto_sec", dark))
    pergunta_text = ft.Text("", size=18, weight=ft.FontWeight.W_600, color=_color("texto", dark), text_align=ft.TextAlign.LEFT)
    gabarito_text = ft.Text("", size=13, color=_color("texto_sec", dark), visible=False)
    resposta_field = ft.TextField(
        label="Sua resposta",
        multiline=True,
        min_lines=12,
        max_lines=20,
        expand=True,
        hint_text="Escreva sua resposta dissertativa aqui...",
    )
    study_card_width = max(280, min(1320, int(min(screen_w, 1360) - 24)))
    tema_field = ft.TextField(label="Tema", hint_text="Ex.: Direito Constitucional", expand=True, value=str(runtime.get("tema") or ""))
    loading = ft.ProgressRing(width=24, height=24, visible=False)
    estado = {
        "pergunta": str(runtime.get("pergunta") or ""),
        "gabarito": str(runtime.get("gabarito") or ""),
        "contexto_gerado": str(runtime.get("contexto_gerado") or ""),
        "upload_texts": list(runtime.get("upload_texts") or []),
        "upload_names": list(runtime.get("upload_names") or []),
        "upload_selected_names": list(runtime.get("upload_selected_names") or []),
        "etapa": int(runtime.get("etapa") or 1),
    }
    secao_texto = ft.Text(str(runtime.get("secao_texto") or "Aguardando pergunta..."), size=12, color=_color("texto_sec", dark))
    contexto_gerado_text = ft.Text(
        str(runtime.get("contexto_text") or (f"Contexto: {estado['contexto_gerado']}" if estado.get("contexto_gerado") else "")),
        size=13,
        color=_color("texto_sec", dark),
        text_align=ft.TextAlign.LEFT,
    )
    escala_text = ft.Text(
        "Escala: nota 0-100 | Aprovado >= 70. Criterios: aderencia ao tema, estrutura, clareza e fundamentacao.",
        size=12,
        color=_color("texto_sec", dark),
    )
    pergunta_text.value = str(runtime.get("pergunta_text") or estado.get("pergunta") or "")
    resposta_field.value = str(runtime.get("resposta") or "")
    gabarito_text.value = str(runtime.get("gabarito_text") or "")
    gabarito_text.visible = bool(runtime.get("gabarito_visible"))
    if str(runtime.get("status") or "").strip():
        status.value = str(runtime.get("status") or "")
        saved_color = str(runtime.get("status_color") or "").strip()
        if saved_color:
            status.color = saved_color

    def _persist_open_quiz_runtime():
        if not isinstance(state, dict):
            return
        state["open_quiz_runtime"] = {
            "tema": str(tema_field.value or ""),
            "resposta": str(resposta_field.value or ""),
            "status": str(status.value or ""),
            "status_color": str(status.color or ""),
            "etapa": int(estado.get("etapa") or 1),
            "pergunta": str(estado.get("pergunta") or ""),
            "gabarito": str(estado.get("gabarito") or ""),
            "contexto_gerado": str(estado.get("contexto_gerado") or ""),
            "gabarito_text": str(gabarito_text.value or ""),
            "gabarito_visible": bool(gabarito_text.visible),
            "upload_texts": list(estado.get("upload_texts") or []),
            "upload_names": list(estado.get("upload_names") or []),
            "upload_selected_names": list(estado.get("upload_selected_names") or []),
            "secao_texto": str(secao_texto.value or ""),
            "contexto_text": str(contexto_gerado_text.value or ""),
            "pergunta_text": str(pergunta_text.value or ""),
        }
    upload_info = ft.Text(
        "Nenhum material enviado.",
        size=12,
        color=_color("texto_sec", dark),
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    etapa_text = ft.Text("Etapa 1 de 2: defina o tema", size=13, color=_color("texto_sec", dark))
    library_files = []
    if library_service and user.get("id"):
        try:
            library_files = library_service.listar_arquivos(user["id"])
        except Exception as ex:
            log_exception(ex, "main._build_open_quiz_body.listar_arquivos")
    library_dropdown = ft.Dropdown(
        label="Adicionar da Biblioteca",
        options=[ft.dropdown.Option(str(f["id"]), text=str(f["nome_arquivo"])) for f in library_files],
        disabled=not library_files,
        expand=True,
    )

    def _set_upload_info():
        names = estado["upload_names"] or estado.get("upload_selected_names") or []
        upload_info.value = _format_upload_info_label(names)
        _persist_open_quiz_runtime()

    def _guess_topic_from_name(raw_name: str) -> str:
        nome = str(raw_name or "").strip()
        if nome.startswith("[LIB]"):
            nome = nome[5:].strip()
        nome = os.path.basename(nome)
        guess = os.path.splitext(nome)[0].replace("_", " ").replace("-", " ").strip()
        return " ".join(guess.split())[:64]

    def _resolve_theme_value() -> str:
        manual = str(tema_field.value or "").strip()
        if manual:
            return manual
        names = list(estado.get("upload_names") or estado.get("upload_selected_names") or [])
        for raw_name in names:
            guessed = _guess_topic_from_name(raw_name)
            if guessed:
                return guessed
        return ""

    def _on_library_select(e):
        fid = getattr(e.control, "value", None)
        if not fid or not library_service:
            return
        nome = next((str(f.get("nome_arquivo") or "Arquivo Biblioteca") for f in library_files if str(f.get("id")) == str(fid)), "Arquivo Biblioteca")
        nome_tag = f"[LIB] {nome}"
        estado["upload_selected_names"] = [nome_tag]
        try:
            texto = library_service.get_conteudo_arquivo(int(fid))
        except Exception as ex:
            log_exception(ex, "main._build_open_quiz_body.library_select")
            texto = ""
        if texto:
            # Biblioteca selecionada vira a fonte principal desta sessao.
            estado["upload_texts"] = [texto]
            estado["upload_names"] = [nome_tag]
            if not str(tema_field.value or "").strip():
                guessed = _guess_topic_from_name(nome_tag)
                if guessed:
                    tema_field.value = guessed
            _set_upload_info()
            _set_feedback_text(status, f"Adicionado da biblioteca: {nome}", "success")
        else:
            estado["upload_texts"] = []
            estado["upload_names"] = []
            _set_upload_info()
            _set_feedback_text(status, "Arquivo da biblioteca sem texto extraivel.", "warning")
        e.control.value = None
        try:
            e.control.update()
        except Exception:
            pass
        if page:
            page.update()
        _persist_open_quiz_runtime()

    library_dropdown.on_change = _on_library_select

    async def _pick_files_async():
        if not page:
            return
        guard = _state_async_guard(state)

        def _on_start():
            _set_feedback_text(status, "Abrindo seletor de arquivos...", "info")
            page.update()

        def _on_timeout():
            _set_feedback_text(status, "Tempo esgotado ao buscar arquivos.", "warning")

        def _on_error(ex: Exception):
            log_exception(ex, "main._build_open_quiz_body._pick_files_async")
            _set_feedback_text(status, "Falha ao abrir arquivos.", "error")

        async def _run_pick():
            file_paths = await _pick_study_files(page)
            if not file_paths:
                _set_feedback_text(status, "", "info")
                return
            upload_texts, upload_names, failed_names = _extract_uploaded_material(file_paths)
            estado["upload_texts"] = upload_texts
            estado["upload_names"] = upload_names
            estado["upload_selected_names"] = list(upload_names)
            if not upload_texts:
                _set_feedback_text(
                    status,
                    (
                        "Nao foi possivel extrair texto dos arquivos. "
                        "Para PDF, confirme que nao e imagem escaneada ou protegido por senha."
                    ),
                    "warning",
                )
            else:
                if failed_names:
                    _set_feedback_text(
                        status,
                        f"Material carregado: {len(upload_texts)} arquivo(s). Ignorados: {len(failed_names)}.",
                        "warning",
                    )
                else:
                    _set_feedback_text(status, f"Material carregado: {len(upload_texts)} arquivo(s).", "success")
            _set_upload_info()
            _persist_open_quiz_runtime()

        await guard.run(
            "open_quiz.upload.files",
            _run_pick,
            timeout_s=180,
            on_start=_on_start,
            on_timeout=_on_timeout,
            on_error=_on_error,
            on_finish=lambda: page.update(),
        )

    def _upload_material(_):
        if not page:
            return
        page.run_task(_pick_files_async)

    def _limpar_material(_):
        if not estado["upload_texts"] and not estado["upload_names"]:
            _set_feedback_text(status, "Nao ha material para remover.", "info")
            if page:
                page.update()
            return

        def _confirmed_clear():
            estado["upload_texts"] = []
            estado["upload_names"] = []
            estado["upload_selected_names"] = []
            _set_upload_info()
            _set_feedback_text(status, "Material removido.", "info")
            _persist_open_quiz_runtime()
            if page:
                ds_toast(page, "Material removido.", tipo="info")
                page.update()

        _show_confirm_dialog(
            page,
            "Limpar material",
            "Deseja remover todo material anexado desta sessao?",
            _confirmed_clear,
            confirm_label="Limpar",
        )

    def _mostrar_etapa_geracao():
        estado["etapa"] = 1
        etapa_text.value = "Etapa 1 de 2: defina o tema"
        config_section.visible = True
        study_section.visible = False
        _persist_open_quiz_runtime()

    def _mostrar_etapa_resposta():
        estado["etapa"] = 2
        etapa_text.value = "Etapa 2 de 2: responda com base no contexto"
        config_section.visible = False
        study_section.visible = True
        _persist_open_quiz_runtime()

    def _voltar_geracao(_=None):
        _mostrar_etapa_geracao()
        if page:
            page.update()

    def _show_open_quiz_grade_dialog(feedback: dict):
        if not page:
            return
        nota = int(feedback.get("nota", 0) or 0)
        aprovado = bool(feedback.get("correto"))
        criterios = feedback.get("criterios") if isinstance(feedback.get("criterios"), dict) else {}
        aderencia = int(criterios.get("aderencia", 0) or 0)
        estrutura = int(criterios.get("estrutura", 0) or 0)
        clareza = int(criterios.get("clareza", 0) or 0)
        fundamentacao = int(criterios.get("fundamentacao", 0) or 0)

        def _as_lines(value, limit: int = 3):
            if isinstance(value, list):
                items = [str(x).strip() for x in value if str(x).strip()]
            else:
                raw = str(value or "").strip()
                items = [p.strip(" -•\t") for p in re.split(r"[\n;]+", raw) if p.strip(" -•\t")]
            return items[: max(1, int(limit or 1))]

        fortes = _as_lines(feedback.get("pontos_fortes"), limit=3)
        melhorar = _as_lines(feedback.get("pontos_melhorar"), limit=3)
        feedback_txt = _fix_mojibake_text(str(feedback.get("feedback", "") or "").strip())

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Correcao da dissertativa"),
            content=ft.Container(
                width=max(320, min(760, int((_screen_width(page) if page else 1280) - 80))),
                content=ft.Column(
                    [
                        ft.Text(
                            f"Nota: {nota} | {'Aprovado' if aprovado else 'Revisar'}",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=CORES["sucesso"] if aprovado else CORES["warning"],
                        ),
                        ft.Text(
                            f"Criterios - Aderencia: {aderencia} | Estrutura: {estrutura} | "
                            f"Clareza: {clareza} | Fundamentacao: {fundamentacao}",
                            size=13,
                            color=_color("texto_sec", dark),
                        ),
                        ft.Divider(height=14),
                        ft.Text("Pontos fortes", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text("• " + ("\n• ".join(fortes) if fortes else "Sem destaques registrados."), size=13),
                        ft.Text("Pontos para melhorar", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text("• " + ("\n• ".join(melhorar) if melhorar else "Sem observacoes adicionais."), size=13),
                        ft.Text("Feedback geral", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text(feedback_txt or "Sem feedback detalhado.", size=13),
                        ft.Text(
                            "Obs.: a avaliacao nao exige copia literal da resposta esperada.",
                            size=12,
                            color=_color("texto_sec", dark),
                        ),
                    ],
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
            ),
        )
        dlg.actions = [ft.ElevatedButton("Fechar", on_click=lambda _: _close_dialog_compat(page, dlg))]
        dlg.actions_alignment = ft.MainAxisAlignment.END
        _show_dialog_compat(page, dlg)

    async def gerar(_):
        if not page:
            return
        loading.visible = True
        _set_feedback_text(status, "Gerando contexto e pergunta-estopim...", "info")
        page.update()
        selected_library_id = str(getattr(library_dropdown, "value", "") or "").strip()
        if selected_library_id and library_service and not estado.get("upload_texts"):
            nome = next(
                (str(f.get("nome_arquivo") or "Arquivo Biblioteca") for f in library_files if str(f.get("id")) == selected_library_id),
                "Arquivo Biblioteca",
            )
            nome_tag = f"[LIB] {nome}"
            estado["upload_selected_names"] = [nome_tag]
            try:
                texto_lib = library_service.get_conteudo_arquivo(int(selected_library_id))
            except Exception as ex:
                log_exception(ex, "main._build_open_quiz_body.generate.library_select")
                texto_lib = ""
            if texto_lib:
                estado["upload_texts"] = [texto_lib]
                estado["upload_names"] = [nome_tag]
                _set_upload_info()
            else:
                estado["upload_texts"] = []
                estado["upload_names"] = []
                _set_upload_info()

        selected_names = list(estado.get("upload_names") or estado.get("upload_selected_names") or [])
        if selected_names and not estado.get("upload_texts"):
            loading.visible = False
            _set_feedback_text(
                status,
                "O PDF selecionado nao teve texto extraido. Use um PDF com texto pesquisavel ou anexe outro arquivo.",
                "warning",
            )
            page.update()
            return

        tema = _resolve_theme_value()
        if not tema:
            if estado.get("upload_texts"):
                tema = "Conteudo principal do material anexado"
            else:
                loading.visible = False
                _set_feedback_text(
                    status,
                    "Defina o tema antes de gerar ou selecione um PDF com texto extraivel.",
                    "warning",
                )
                page.update()
                return
        if not str(tema_field.value or "").strip():
            tema_field.value = tema

        contexto = [f"Tema central: {tema}"]
        source_lock = bool(estado["upload_texts"])
        if estado["upload_texts"]:
            source_label = ", ".join(selected_names[:2]) if selected_names else "material anexado"
            contexto.append(
                f"INSTRUCAO DE FOCO: Gere contexto e pergunta usando apenas o material selecionado ({source_label})."
            )
            contexto.extend(list(estado["upload_texts"]))
        content_for_open_question = list(estado["upload_texts"]) if estado["upload_texts"] else list(contexto)
        pergunta = None
        if service:
            try:
                pergunta = await asyncio.to_thread(
                    service.generate_open_question,
                    content_for_open_question,
                    tema,
                    source_lock,
                    "Medio",
                )
            except Exception as ex:
                log_exception(ex, "main._build_open_quiz_body.generate")
        if not pergunta:
            contexto_gerado = f"Você está analisando o tema '{tema}' em um cenário prático, exigindo argumento claro, exemplos e conclusão."
            pergunta = {
                "pergunta": f"Explique os pontos principais sobre {tema}.",
                "resposta_esperada": f"Resposta esperada com fundamentos, estrutura clara e exemplos sobre {tema}.",
                "contexto": contexto_gerado,
            }
            if _is_ai_quota_exceeded(service):
                _set_feedback_text(status, "Cotas da IA esgotadas. Contexto/pergunta gerados no modo offline.", "warning")
                _show_quota_dialog(page, navigate)
            else:
                _set_feedback_text(status, "Contexto e pergunta gerados no modo offline.", "info")
        else:
            _set_feedback_text(status, "Contexto e pergunta gerados com IA.", "success")
        estado["contexto_gerado"] = (
            pergunta.get("contexto")
            or pergunta.get("cenario")
            or f"Cenário gerado para o tema '{tema}'."
        )
        estado["contexto_gerado"] = _fix_mojibake_text(str(estado["contexto_gerado"] or ""))
        sw = _screen_width(page) if page else 1280
        pergunta_text.size = 16 if sw < 900 else (18 if sw < 1280 else 20)
        estado["pergunta"] = _fix_mojibake_text(str(pergunta.get("pergunta", "") or ""))
        estado["gabarito"] = _fix_mojibake_text(str(pergunta.get("resposta_esperada", "") or ""))
        contexto_gerado_text.value = f"Contexto: {estado['contexto_gerado']}"
        pergunta_text.value = estado["pergunta"]
        gabarito_text.value = "Gabarito oculto ate a correcao."
        gabarito_text.visible = False
        secao_texto.value = "Contexto e pergunta prontos."
        resposta_field.value = ""
        _mostrar_etapa_resposta()
        _persist_open_quiz_runtime()
        loading.visible = False
        page.update()

    async def corrigir(_):
        if not page:
            return
        if not estado["pergunta"] or not resposta_field.value:
            status.value = "Gere uma pergunta e responda antes de corrigir."
            page.update()
            return
        if (not _is_premium_active(user)) and user.get("id"):
            allowed = True
            _used = 0
            consumed_online = False
            if backend and backend.enabled():
                try:
                    backend_uid = _backend_user_id(user)
                    if int(backend_uid or 0) > 0:
                        usage = await asyncio.to_thread(backend.consume_usage, int(backend_uid), "open_quiz_grade", 1)
                        allowed = bool(usage.get("allowed"))
                        _used = int(usage.get("used") or 0)
                        consumed_online = True
                except Exception as ex:
                    log_exception(ex, "main._build_open_quiz_body.consume_usage_backend")
            if (not consumed_online) and db:
                allowed, _used = db.consumir_limite_diario(user["id"], "open_quiz_grade", 1)
            if not allowed:
                _set_feedback_text(
                    status,
                    "Free: limite diario da dissertativa atingido (1/dia).",
                    "warning",
                )
                _show_upgrade_dialog(page, navigate, "No plano Free voce pode corrigir 1 dissertativa por dia.")
                page.update()
                return
        loading.visible = True
        _set_feedback_text(status, "Corrigindo resposta...", "info")
        page.update()
        feedback = None
        if service:
            try:
                feedback = await asyncio.to_thread(
                    service.grade_open_answer,
                    estado["pergunta"],
                    resposta_field.value,
                    estado["gabarito"],
                )
            except Exception as ex:
                log_exception(ex, "main._build_open_quiz_body.grade")
        if not feedback:
            nota = 80 if len(resposta_field.value.split()) > 40 else 55
            feedback = {
                "nota": nota,
                "correto": nota >= 70,
                "criterios": {
                    "aderencia": nota,
                    "estrutura": max(45, nota - 8),
                    "clareza": max(45, nota - 5),
                    "fundamentacao": max(40, nota - 10),
                },
                "pontos_fortes": ["Resposta objetiva e conectada ao tema proposto."],
                "pontos_melhorar": ["Aprofunde argumentos com exemplos e conclusao mais forte."],
                "feedback": "Estruture melhor em introducao, desenvolvimento e conclusao para melhorar a nota.",
            }
            if _is_ai_quota_exceeded(service):
                _show_quota_dialog(page, navigate)
        if db and user.get("id"):
            try:
                db.registrar_progresso_diario(user["id"], discursivas=1)
            except Exception as ex:
                log_exception(ex, "main._build_open_quiz_body.registrar_progresso_diario")
        _set_feedback_text(
            status,
            f"Nota: {feedback.get('nota', 0)} | {'Aprovado' if feedback.get('correto') else 'Revisar'}",
            "success" if feedback.get("correto") else "warning",
        )
        gabarito_text.value = ""
        gabarito_text.visible = False
        _show_open_quiz_grade_dialog(feedback)
        _persist_open_quiz_runtime()
        loading.visible = False
        page.update()

    def _on_gerar_click(e):
        if not page:
            return
        _schedule_ai_task(
            page,
            state,
            gerar,
            e,
            message="IA gerando contexto e pergunta...",
            status_control=status,
        )

    def _on_corrigir_click(_):
        if not page:
            return
        _schedule_ai_task(
            page,
            state,
            corrigir,
            _,
            message="IA corrigindo resposta dissertativa...",
            status_control=status,
        )

    def limpar(_):
        estado["pergunta"] = ""
        estado["gabarito"] = ""
        estado["contexto_gerado"] = ""
        contexto_gerado_text.value = ""
        pergunta_text.value = ""
        gabarito_text.value = ""
        gabarito_text.visible = False
        resposta_field.value = ""
        status.value = "Campos limpos."
        secao_texto.value = "Aguardando pergunta..."
        _mostrar_etapa_geracao()
        _persist_open_quiz_runtime()
        if page:
            page.update()

    config_section = ds_card(
        dark=dark,
        padding=14,
        content=ft.Column(
            [
                ft.Text("1) Defina o tema", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.ResponsiveRow(
                    [
                        ft.Container(content=tema_field, col={"sm": 12, "md": 6}),
                    ]
                ),
                ft.Text(
                    "A IA vai gerar automaticamente o contexto e a pergunta-estopim para sua dissertacao.",
                    size=12,
                    color=_color("texto_sec", dark),
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "md": 4},
                            content=ds_btn_secondary("Anexar material", icon=ft.Icons.UPLOAD_FILE, on_click=_upload_material, dark=dark, expand=True),
                        ),
                        ft.Container(col={"xs": 12, "md": 5}, content=library_dropdown),
                        ft.Container(col={"xs": 12, "md": 3}, content=ds_btn_ghost("Limpar material", on_click=_limpar_material, dark=dark)),
                        ft.Container(col={"xs": 12, "md": 12}, content=upload_info),
                    ],
                    run_spacing=6,
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "md": 4},
                            content=ds_btn_primary(
                                "Gerar contexto e pergunta",
                                icon=ft.Icons.BOLT,
                                on_click=_on_gerar_click,
                                expand=True,
                                dark=dark,
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "md": 8},
                            content=ft.Row(
                                [loading, ft.Container(expand=True, content=_status_banner(status, dark))],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ],
                    run_spacing=6,
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=10,
        ),
    )

    study_section = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("2) Sua resposta", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                    secao_texto,
                ],
                wrap=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.ResponsiveRow(
                [
                    ft.Container(
                        col={"xs": 12, "md": 12},
                        content=ds_card(
                            dark=dark,
                            padding=12,
                            expand=True,
                            width=study_card_width,
                            content=ft.Container(
                                height=max(200, min(340, int(screen_h * 0.38))),
                                content=ft.Column(
                                    [
                                        ft.Text("Contexto", size=12, weight=ft.FontWeight.W_600, color=_color("texto_sec", dark)),
                                        ft.Container(alignment=ft.Alignment(-1, 0), content=contexto_gerado_text),
                                        ds_divider(dark),
                                        ft.Text("Pergunta", size=12, weight=ft.FontWeight.W_600, color=_color("texto_sec", dark)),
                                        ft.Container(alignment=ft.Alignment(-1, 0), content=pergunta_text),
                                    ],
                                    spacing=8,
                                    scroll=ft.ScrollMode.AUTO,
                                ),
                            ),
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 12},
                        content=ds_card(
                            dark=dark,
                            padding=12,
                            expand=True,
                            width=study_card_width,
                            content=ft.Column(
                                [
                                    ft.Text("Sua resposta", size=12, weight=ft.FontWeight.W_600, color=_color("texto_sec", dark)),
                                    ft.Container(expand=True, content=resposta_field),
                                ],
                                spacing=8,
                            ),
                        ),
                    ),
                ],
                spacing=10,
                run_spacing=10,
            ),
            escala_text,
            ds_action_bar(
                [
                    {"label": "3) Corrigir", "icon": ft.Icons.CHECK, "on_click": _on_corrigir_click, "kind": "primary"},
                    {"label": "Limpar", "icon": ft.Icons.RESTART_ALT, "on_click": limpar, "kind": "ghost"},
                    {
                        "label": "Voltar para geracao",
                        "icon": ft.Icons.ARROW_BACK,
                        "on_click": _voltar_geracao,
                        "kind": "ghost",
                    },
                    {"label": "Voltar ao Inicio", "icon": ft.Icons.HOME_OUTLINED, "on_click": lambda _: navigate("/home"), "kind": "ghost"},
                ],
                dark=dark,
            ),
            gabarito_text,
        ],
        spacing=10,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        visible=False,
    )

    if estado.get("etapa") == 2 and str(estado.get("pergunta") or "").strip():
        _mostrar_etapa_resposta()
    else:
        _mostrar_etapa_geracao()

    _set_upload_info()
    tema_field.on_change = lambda _: _persist_open_quiz_runtime()
    resposta_field.on_change = lambda _: _persist_open_quiz_runtime()

    return _wrap_study_content(
        ft.Column(
            [
                _build_focus_header("Dissertativo", "Fluxo: 1) Tema  2) Contexto e pergunta  3) Resposta e correcao", etapa_text, dark),
                config_section,
                study_section,
            ],
            spacing=10,
            expand=True,
        ),
        dark,
    )


def _build_study_plan_body(state, navigate, dark: bool):
    page = state.get("page")
    screen_w = _screen_width(page) if page else 1280
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
            itens_norm.append(
                {
                    "dia": str(item.get("dia") or dias_semana[i]),
                    "tema": str(item.get("tema") or topicos[i % len(topicos)]),
                    "atividade": str(item.get("atividade") or "Questoes + revisao de erros + flashcards"),
                    "duracao_min": int(item.get("duracao_min") or tempo_diario),
                    "prioridade": int(item.get("prioridade") or (1 if i < 3 else 2)),
                }
            )
        while len(itens_norm) < limite_dias:
            i = len(itens_norm)
            itens_norm.append(
                {
                    "dia": dias_semana[i],
                    "tema": topicos[i % len(topicos)],
                    "atividade": "Questoes + revisao de erros + flashcards",
                    "duracao_min": tempo_diario,
                    "prioridade": 1 if i < 3 else 2,
                }
            )
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
        itens_column.controls.append(
            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=_color("card", dark),
                content=ft.Row(
                    [
                        ft.Text(f"Objetivo: {plan.get('objetivo') or '-'}", weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ft.Container(expand=True),
                        ft.Text(f"Prova: {plan.get('data_prova') or '-'}", size=12, color=_color("texto_sec", dark)),
                    ]
                ),
            )
        )
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
            itens_column.controls.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=_color("card", dark),
                    content=ft.Row(
                        [
                            ft.Checkbox(value=bool(item.get("concluido")), on_change=_mk_toggle(item["id"])),
                            ft.Column(
                                [
                                    ft.Text(f"{item.get('dia')} - {item.get('tema')}", weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                    ft.Text(f"{item.get('atividade')} ({item.get('duracao_min')} min)", size=12, color=_color("texto_sec", dark)),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )

    async def _gerar_plano_async():
        if not db or not user.get("id") or not page:
            return
        objetivo = (objetivo_field.value or "").strip() or "Aprovacao"
        data_prova = (data_prova_field.value or "").strip() or "-"
        limite_dias = 7
        if data_prova != "-":
            limite_inferido = _plan_day_limit(data_prova)
            if limite_inferido is None:
                _set_feedback_text(status_text, "Data invalida. Use DD/MM/AAAA.", "warning")
                page.update()
                return
            if limite_inferido <= 0:
                _set_feedback_text(status_text, "A data da prova ja passou. Informe uma data futura.", "warning")
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
        service = _create_user_ai_service(user)
        itens = []
        try:
            if service:
                itens = await asyncio.to_thread(service.generate_study_plan, objetivo, data_prova, tempo_diario, topicos)
            if not itens:
                itens = [
                    {
                        "dia": d,
                        "tema": topicos[i % len(topicos)],
                        "atividade": "Questoes + revisao de erros + flashcards",
                        "duracao_min": tempo_diario,
                        "prioridade": 1 if i < 3 else 2,
                    }
                    for i, d in enumerate(dias_semana[:limite_dias])
                ]
            itens = _normalize_plan_items(itens, topicos, tempo_diario, limite_dias)
            db.salvar_plano_semanal(user["id"], objetivo, data_prova, tempo_diario, itens)
            if limite_dias < 7:
                status_text.value = f"Plano ajustado ao prazo real: {limite_dias} dia(s) ate a prova."
            else:
                status_text.value = "Plano semanal criado."
            _render_plan()
        except Exception as ex:
            log_exception(ex, "main._build_study_plan_body._gerar_plano_async")
            status_text.value = "Falha ao gerar plano."
        finally:
            loading.visible = False
            page.update()

    def _gerar_plano_click(_):
        if page:
            _schedule_ai_task(
                page,
                state,
                _gerar_plano_async,
                message="IA gerando plano semanal...",
                status_control=status_text,
            )

    _render_plan()
    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Text("Plano Semanal", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text("Gere um plano adaptativo e marque o progresso diario.", size=14, color=_color("texto_sec", dark)),
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Configuracao do plano", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(content=objetivo_field, col={"xs": 12, "md": 6}),
                                        ft.Container(content=data_prova_field, col={"xs": 6, "md": 3}),
                                        ft.Container(content=tempo_diario_field, col={"xs": 6, "md": 3}),
                                    ],
                                    spacing=12,
                                    run_spacing=8,
                                ),
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(
                                            col={"xs": 12, "md": 3},
                                            content=ft.ElevatedButton("Gerar plano", icon=ft.Icons.AUTO_AWESOME, on_click=_gerar_plano_click, expand=True),
                                        ),
                                        ft.Container(
                                            col={"xs": 12, "md": 6},
                                            content=ft.Row([loading, ft.Container(content=status_text, expand=True)], spacing=10),
                                        ),
                                        ft.Container(
                                            col={"xs": 12, "md": 3},
                                            content=ft.ElevatedButton(
                                                "Estudar agora",
                                                icon=ft.Icons.PLAY_ARROW,
                                                on_click=lambda _: _start_prioritized_session(state, navigate),
                                                expand=True,
                                            ),
                                        ),
                                    ],
                                    run_spacing=6,
                                    spacing=8 if very_compact else 10,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=8,
                        ),
                    ),
                ),
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Itens do plano", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                itens_column,
                            ],
                            spacing=8,
                        ),
                    ),
                ),
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=12,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
    )


def _build_stats_body(state, navigate, dark: bool):
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
            log_exception(ex, "main._build_stats_body.resumo")

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
                _close_dialog_compat(page, dialog_ref.get("dlg"))
                if page:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Meta diaria atualizada para {value} questoes."),
                        bgcolor=CORES["sucesso"],
                        show_close_icon=True,
                    )
                    page.snack_bar.open = True
                navigate("/stats")
            except Exception as ex_goal:
                log_exception(ex_goal, "main._build_stats_body.update_daily_goal")
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
                ft.TextButton("Cancelar", on_click=lambda _e: _close_dialog_compat(page, dialog_ref.get("dlg"))),
                ft.TextButton("Salvar", on_click=_save_goal),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialog_ref["dlg"] = dialog
        _show_dialog_compat(page, dialog)

    recado = "Constancia > perfeicao: mantenha o ritmo diario."
    if taxa >= 75:
        recado = "Excelente precisao. Vale subir dificuldade em parte das sessoes."
    elif taxa >= 50:
        recado = "Bom caminho. Priorize revisao dos erros para ganhar consistencia."

    resumo_cards = ft.ResponsiveRow(
        controls=[
            ds_stat_card(
                ft.Icons.STARS_OUTLINED,
                "XP Total",
                str(xp),
                dark=dark,
                col={"sm": 6, "md": 3},
                icon_color=DS.P_500,
            ),
            ds_stat_card(
                ft.Icons.SHIELD_OUTLINED,
                "Nivel",
                str(nivel),
                dark=dark,
                col={"sm": 6, "md": 3},
                icon_color=DS.INFO,
            ),
            ds_stat_card(
                ft.Icons.CHECK_CIRCLE_OUTLINE,
                "Taxa de acerto",
                f"{taxa:.1f}%",
                dark=dark,
                col={"sm": 6, "md": 3},
                icon_color=DS.SUCESSO,
            ),
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
                        ds_badge(f"Streak {int(progresso_diario.get('streak_dias', 0))} dia(s)", color=CORES["warning"]),
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


def _build_profile_body(state, navigate, dark: bool):
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
                content=ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Nivel", size=12, color=_color("texto_sec", dark)),
                                ft.Text(nivel, size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
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
                                ft.Text("XP", size=12, color=_color("texto_sec", dark)),
                                ft.Text(str(xp), size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
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
                                ft.Text("Taxa de acerto", size=12, color=_color("texto_sec", dark)),
                                ft.Text(f"{taxa:.1f}%", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
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
                                ft.Text("Streak", size=12, color=_color("texto_sec", dark)),
                                ft.Text(f"{streak} dia(s)", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
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
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Conta", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.PERSON),
                                    title=ft.Text("Nome"),
                                    subtitle=ft.Text(nome or "-"),
                                ),
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(
                                            col={"xs": 12, "md": 9},
                                            content=ft.Row(
                                                [
                                                    ft.Icon(ft.Icons.BADGE, color=_color("texto_sec", dark)),
                                                    ft.Container(expand=True, content=id_edit_field),
                                                ],
                                                spacing=10,
                                                vertical_alignment=ft.CrossAxisAlignment.END,
                                            ),
                                        ),
                                        ft.Container(
                                            col={"xs": 12, "md": 3},
                                            content=ft.ElevatedButton(
                                                "Salvar ID",
                                                icon=ft.Icons.SAVE,
                                                on_click=_salvar_id,
                                                expand=True,
                                            ),
                                        ),
                                    ],
                                    run_spacing=6,
                                    spacing=10,
                                    vertical_alignment=ft.CrossAxisAlignment.END,
                                ),
                                id_feedback,
                            ],
                            spacing=4,
                        ),
                    ),
                ),
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Estudo e preferencias", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.SAVINGS),
                                    title=ft.Text("Modo economia IA"),
                                    trailing=ft.Text(economia, color=_color("texto_sec", dark)),
                                ),
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.DARK_MODE),
                                    title=ft.Text("Tema"),
                                    trailing=ft.Text(tema, color=_color("texto_sec", dark)),
                                ),
                            ],
                            spacing=4,
                        ),
                    ),
                ),
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )


def _build_ranking_body(state, navigate, dark: bool):
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
                    ft.Colors.with_opacity(0.20, CORES["primaria"]) if destaque_me else _soft_border(dark, 0.08),
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


def _build_conquistas_body(state, navigate, dark: bool):
    from config import CONQUISTAS
    total_conquistas = len(CONQUISTAS)
    total_xp = int(sum(int(c.get("xp_bonus", 0) or 0) for c in CONQUISTAS))
    rows = []
    for c in CONQUISTAS:
        rows.append(
            ft.Container(
                padding=12,
                border_radius=12,
                bgcolor=_color("card", dark),
                border=ft.border.all(1, _soft_border(dark, 0.08)),
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


def _build_plans_body(state, navigate, dark: bool):
    user = state.get("usuario") or {}
    db = state.get("db")
    backend = state.get("backend")
    page = state.get("page")
    if not db or not user.get("id"):
        return _build_placeholder_body("Planos", "E necessario login para gerenciar assinatura.", navigate, dark)

    # Render inicial instantaneo com cache local; sincronizacao online ocorre em background.
    sub = db.get_subscription_status(user["id"])
    plan_code = str(sub.get("plan_code") or "free")
    premium_active = bool(sub.get("premium_active"))
    premium_until = sub.get("premium_until")
    trial_used = int(sub.get("trial_used") or 0)

    status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    plan_value_text = ft.Text("", size=20, weight=ft.FontWeight.BOLD, color=_color("texto", dark))
    validade_value_text = ft.Text("", size=16, weight=ft.FontWeight.W_600, color=_color("texto", dark))
    operation_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    op_busy = {"value": False}
    checkout_state = {
        "checkout_id": "",
        "auth_token": "",
        "payment_code": "",
        "amount_cents": 0,
        "currency": "BRL",
        "plan_code": "",
        "provider": "",
        "checkout_url": "",
    }
    tx_id_field = ft.TextField(
        label="ID da transacao",
        hint_text="Cole o identificador do pagamento",
        width=280,
        visible=False,
    )
    payment_code_field = ft.TextField(label="Codigo de pagamento", read_only=True, width=280, visible=False)
    confirm_payment_button = ft.ElevatedButton("Confirmar pagamento", icon=ft.Icons.VERIFIED, visible=False)
    open_checkout_button = ft.ElevatedButton("Abrir pagamento", icon=ft.Icons.OPEN_IN_NEW, visible=False)
    refresh_payment_button = ft.OutlinedButton("Ja paguei, verificar status", icon=ft.Icons.REFRESH, visible=False)
    cancel_checkout_button = ft.TextButton("Cancelar checkout", icon=ft.Icons.CLOSE, visible=False)
    subscribe_monthly_button = ft.ElevatedButton("Assinar Mensal", icon=ft.Icons.PAYMENT)
    checkout_info_text = ft.Text("", size=12, color=_color("texto_sec", dark), visible=False)
    PAID_PLAN_CODES = {"premium_30"}

    def _set_status(message: str, tone: str = "info"):
        tone_map = {
            "info": _color("texto_sec", dark),
            "success": CORES["sucesso"],
            "warning": CORES["warning"],
            "error": CORES["erro"],
        }
        status_text.value = str(message or "")
        status_text.color = tone_map.get(tone, tone_map["info"])

    def _set_busy(value: bool):
        busy = bool(value)
        op_busy["value"] = busy
        operation_ring.visible = busy
        subscribe_monthly_button.disabled = busy
        confirm_payment_button.disabled = busy
        open_checkout_button.disabled = busy
        refresh_payment_button.disabled = busy
        cancel_checkout_button.disabled = busy
        if page:
            page.update()

    def _is_paid_plan_active() -> bool:
        code = str(plan_code or "").strip().lower()
        return bool(premium_active and code in PAID_PLAN_CODES)

    def _refresh_labels():
        if str(plan_code or "").strip().lower() == "trial" and premium_active:
            plano_atual = "Trial"
        elif _is_paid_plan_active():
            plano_atual = "Premium"
        else:
            plano_atual = "Free (trial usado)" if trial_used else "Free"
        validade_fmt = _format_datetime_label(str(premium_until or "")) if premium_until and premium_active else ""
        if premium_active and str(plan_code or "").strip().lower() == "trial":
            validade = f"Cortesia ate {validade_fmt}" if validade_fmt else "Cortesia ativa"
        elif premium_active:
            validade = f"Ate {validade_fmt}" if validade_fmt else "Premium ativo"
        else:
            validade = "Sem premium ativo"
        plan_value_text.value = plano_atual
        validade_value_text.value = validade
        validade_value_text.color = CORES["primaria"] if premium_active else _color("texto", dark)

    def _apply_status(s: dict):
        state["usuario"].update(s)
        nonlocal plan_code, premium_active, premium_until, trial_used
        plan_code = str(s.get("plan_code") or "free")
        premium_active = bool(s.get("premium_active"))
        premium_until = s.get("premium_until")
        trial_used = int(s.get("trial_used") or 0)
        _refresh_labels()
        if page:
            page.update()

    async def _fetch_backend_status_async() -> Optional[dict]:
        if not (backend and backend.enabled()):
            return None
        try:
            backend_uid = _backend_user_id(user)
            if int(backend_uid or 0) <= 0:
                return None
            if int(user.get("backend_user_id") or 0) <= 0:
                await asyncio.to_thread(backend.upsert_user, backend_uid, user.get("nome", ""), user.get("email", ""))
            b = await asyncio.to_thread(backend.get_plan, backend_uid)
            return {
                "plan_code": b.get("plan_code", "free"),
                "premium_active": 1 if b.get("premium_active") else 0,
                "premium_until": b.get("premium_until"),
                "trial_used": 1 if b.get("plan_code") == "trial" else int(user.get("trial_used", 0) or 0),
            }
        except Exception as ex:
            log_exception(ex, "main._build_plans_body._fetch_backend_status_async")
            return None

    async def _refresh_status_async():
        remote = await _fetch_backend_status_async()
        if remote is not None:
            try:
                await asyncio.to_thread(
                    db.sync_subscription_status,
                    int(user["id"]),
                    str(remote.get("plan_code") or "free"),
                    remote.get("premium_until"),
                    int(remote.get("trial_used") or 0),
                )
            except Exception as ex:
                log_exception(ex, "main._build_plans_body._refresh_status_async.persist")
            _apply_status(remote)
            return
        _apply_status(db.get_subscription_status(user["id"]))

    def _refresh_status(_=None):
        if not page:
            return
        page.run_task(_refresh_status_async)

    def _set_checkout_visibility(visible: bool):
        manual_confirm = bool(visible and not checkout_state.get("checkout_url"))
        tx_id_field.visible = manual_confirm
        payment_code_field.visible = bool(visible)
        confirm_payment_button.visible = manual_confirm
        open_checkout_button.visible = bool(visible and checkout_state.get("checkout_url"))
        refresh_payment_button.visible = bool(visible)
        cancel_checkout_button.visible = bool(visible)
        checkout_info_text.visible = bool(visible)

    def _show_checkout_popup():
        if not page:
            return
        url = str(checkout_state.get("checkout_url") or "").strip()
        if not url:
            return
        link_field = ft.TextField(label="Link de pagamento", value=url, read_only=True, multiline=True, min_lines=2, max_lines=3)
        msg = ft.Text(
            f"Finalize o pagamento de {checkout_state.get('currency', 'BRL')} "
            f"{(int(checkout_state.get('amount_cents') or 0) / 100):.2f} no Mercado Pago."
        )

        def _copy_link(_=None):
            try:
                page.set_clipboard(url)
                page.snack_bar = ft.SnackBar(content=ft.Text("Link copiado."), bgcolor=CORES["sucesso"], show_close_icon=True)
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Checkout Mensal"),
            content=ft.Column([msg, link_field], tight=True, spacing=8),
            actions=[
                ft.TextButton("Copiar link", on_click=_copy_link),
                ft.TextButton("Fechar", on_click=lambda _: _close_dialog_compat(page, dlg)),
                ft.ElevatedButton("Abrir pagamento", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda _: (_launch_url_compat(page, url, "plans.checkout_popup"), _close_dialog_compat(page, dlg))),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        _show_dialog_compat(page, dlg)

    def _clear_checkout():
        checkout_state.update(
            {
                "checkout_id": "",
                "auth_token": "",
                "payment_code": "",
                "amount_cents": 0,
                "currency": "BRL",
                "plan_code": "",
                "provider": "",
                "checkout_url": "",
            }
        )
        tx_id_field.value = ""
        payment_code_field.value = ""
        checkout_info_text.value = ""
        _set_checkout_visibility(False)

    async def _start_checkout_async(plano: str):
        if op_busy["value"]:
            return
        if not (backend and backend.enabled()):
            _set_status("Compra premium exige backend online. Configure BACKEND_URL.", "error")
            if page:
                page.update()
            return
        backend_uid = _backend_user_id(user)
        if int(backend_uid or 0) <= 0:
            _set_status("Conta ainda nao vinculada ao backend. Faça login online novamente.", "error")
            if page:
                page.update()
            return
        _set_busy(True)
        try:
            resp = await asyncio.to_thread(
                backend.start_checkout,
                int(backend_uid),
                plano,
                "mercadopago",
                str(user.get("nome") or ""),
                str(user.get("email") or ""),
            )
            if not bool(resp.get("ok")):
                _set_status(str(resp.get("message") or "Falha ao iniciar checkout."), "error")
                if page:
                    page.update()
                return
            checkout_state["checkout_id"] = str(resp.get("checkout_id") or "")
            checkout_state["auth_token"] = str(resp.get("auth_token") or "")
            checkout_state["payment_code"] = str(resp.get("payment_code") or "")
            checkout_state["amount_cents"] = int(resp.get("amount_cents") or 0)
            checkout_state["currency"] = str(resp.get("currency") or "BRL")
            checkout_state["plan_code"] = str(resp.get("plan_code") or plano)
            checkout_state["provider"] = str(resp.get("provider") or "")
            checkout_state["checkout_url"] = str(resp.get("checkout_url") or "").strip()
            payment_code_field.value = checkout_state["payment_code"]
            if checkout_state["checkout_url"]:
                checkout_info_text.value = (
                    f"Checkout iniciado para {checkout_state['plan_code']}. "
                    f"Valor: {checkout_state['currency']} {checkout_state['amount_cents'] / 100:.2f}. "
                    "Abra o pagamento, conclua no Mercado Pago e depois toque em verificar status."
                )
            else:
                checkout_info_text.value = (
                    f"Checkout iniciado para {checkout_state['plan_code']}. "
                    f"Valor: {checkout_state['currency']} {checkout_state['amount_cents'] / 100:.2f}. "
                    "Apos pagar, informe o ID da transacao e confirme."
                )
            _set_checkout_visibility(True)
            _set_status("Checkout criado. Complete o pagamento para liberar premium.", "warning")
            if checkout_state["checkout_url"]:
                _show_checkout_popup()
                try:
                    _launch_url_compat(page, checkout_state["checkout_url"], "plans.start_checkout")
                except Exception:
                    pass
        except Exception as ex:
            log_exception(ex, "main._build_plans_body._start_checkout")
            _set_status(f"Falha ao iniciar checkout: {ex}", "error")
        finally:
            _set_busy(False)
        if page:
            page.update()

    async def _confirm_checkout_async(_=None):
        if op_busy["value"]:
            return
        checkout_id = str(checkout_state.get("checkout_id") or "")
        auth_token = str(checkout_state.get("auth_token") or "")
        tx_id = str(tx_id_field.value or "").strip()
        if not checkout_id or not auth_token:
            _set_status("Nenhum checkout pendente.", "error")
            if page:
                page.update()
            return
        if not tx_id:
            _set_status("Informe o ID da transacao para confirmar.", "error")
            if page:
                page.update()
            return
        if not (backend and backend.enabled()):
            _set_status("Backend offline. Nao e possivel confirmar pagamento.", "error")
            if page:
                page.update()
            return
        backend_uid = _backend_user_id(user)
        if int(backend_uid or 0) <= 0:
            _set_status("Conta ainda nao vinculada ao backend. Faça login online novamente.", "error")
            if page:
                page.update()
            return
        _set_busy(True)
        ok = False
        msg = "Falha ao confirmar pagamento."
        try:
            resp = await asyncio.to_thread(
                backend.confirm_checkout,
                int(backend_uid),
                checkout_id,
                auth_token,
                tx_id,
            )
            ok = bool(resp.get("ok"))
            msg = str(resp.get("message") or ("Pagamento confirmado." if ok else msg))
        except Exception as ex:
            log_exception(ex, "main._build_plans_body._confirm_checkout")
            ok = False
            msg = f"Falha ao confirmar pagamento: {ex}"
        _set_status(msg, "success" if ok else "error")
        if ok:
            await _refresh_status_async()
            _clear_checkout()
        _set_busy(False)
        if page:
            page.update()

    def _open_checkout(_=None):
        url = str(checkout_state.get("checkout_url") or "").strip()
        if not url:
            _set_status("Checkout sem link de pagamento.", "error")
            if page:
                page.update()
            return
        if page:
            _show_checkout_popup()
            try:
                _launch_url_compat(page, url, "plans.open_checkout")
            except Exception:
                pass

    async def _refresh_after_payment_async(_=None):
        if op_busy["value"]:
            return
        _set_busy(True)
        checkout_id = str(checkout_state.get("checkout_id") or "").strip()
        reconcile_msg = ""
        if checkout_id and backend and backend.enabled():
            try:
                backend_uid = _backend_user_id(user)
                if int(backend_uid or 0) <= 0:
                    raise RuntimeError("conta_nao_vinculada_backend")
                # Evita travar a UI por muito tempo quando o provedor de pagamento estiver lento.
                rec = await asyncio.wait_for(
                    asyncio.to_thread(backend.reconcile_checkout, int(backend_uid), checkout_id),
                    timeout=5.5,
                )
                reconcile_msg = str(rec.get("message") or "").strip()
            except Exception as ex:
                log_exception(ex, "main._build_plans_body._refresh_after_payment.reconcile")
                reconcile_msg = str(ex or "").strip()
        await _refresh_status_async()
        if _is_paid_plan_active():
            _set_status(reconcile_msg or "Pagamento confirmado. Premium ativo.", "success")
            _clear_checkout()
        else:
            if str(plan_code or "").strip().lower() == "trial":
                _set_status(reconcile_msg or "Seu trial esta ativo, mas pagamento ainda nao foi confirmado.", "warning")
            else:
                _set_status(reconcile_msg or "Pagamento ainda nao confirmado. Aguarde alguns segundos e tente novamente.", "warning")
        _set_busy(False)
        if page:
            page.update()

    def _start_checkout(_=None):
        if page:
            page.run_task(_start_checkout_async, "premium_30")

    def _confirm_checkout(_=None):
        if page:
            page.run_task(_confirm_checkout_async)

    def _refresh_after_payment(_=None):
        if page:
            page.run_task(_refresh_after_payment_async)

    confirm_payment_button.on_click = _confirm_checkout
    open_checkout_button.on_click = _open_checkout
    refresh_payment_button.on_click = _refresh_after_payment
    cancel_checkout_button.on_click = lambda _=None: (_clear_checkout(), page.update() if page else None)
    subscribe_monthly_button.on_click = _start_checkout

    _refresh_labels()

    backend_status_text = "Online ativo" if (backend and backend.enabled()) else "Offline local"
    backend_status_color = CORES["acento"] if (backend and backend.enabled()) else _color("texto_sec", dark)

    result = ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Text("Planos", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text("Gerencie seu acesso Free/Premium.", size=14, color=_color("texto_sec", dark)),
                ft.Text(f"Sincronizacao: {backend_status_text}", size=12, color=backend_status_color),
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Fluxo de compra premium", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                payment_code_field,
                                tx_id_field,
                                checkout_info_text,
                                ft.Row([operation_ring], alignment=ft.MainAxisAlignment.START),
                                ft.Row(
                                    [open_checkout_button, refresh_payment_button, confirm_payment_button, cancel_checkout_button],
                                    wrap=True,
                                    spacing=8,
                                ),
                            ],
                            spacing=8,
                        ),
                    ),
                ),
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
                                            ft.Text("Plano atual", size=12, color=_color("texto_sec", dark)),
                                            plan_value_text,
                                        ],
                                        spacing=4,
                                    ),
                                ),
                            ),
                        ),
                        ft.Container(
                            col={"sm": 6, "md": 8},
                            content=ft.Card(
                                elevation=1,
                                content=ft.Container(
                                    padding=12,
                                    content=ft.Column(
                                        [
                                            ft.Text("Validade", size=12, color=_color("texto_sec", dark)),
                                            validade_value_text,
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
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Free", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                ft.Text("Questoes e flashcards ilimitados em modo economico/lento.", size=12, color=_color("texto_sec", dark)),
                                ft.Text("Biblioteca: upload de 1 arquivo por vez.", size=12, color=_color("texto_sec", dark)),
                                ft.Text("Dissertativa: 1 correcao por dia.", size=12, color=_color("texto_sec", dark)),
                            ],
                            spacing=4,
                        ),
                    ),
                ),
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            col={"sm": 12, "md": 12},
                            content=ft.Card(
                                elevation=1,
                                content=ft.Container(
                                    padding=12,
                                    content=ft.Column(
                                        [
                                            ft.Text("Mensal", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                            ft.Text("Mesmo recurso, melhor custo-beneficio.", size=12, color=_color("texto_sec", dark)),
                                            ft.Text("Biblioteca: upload ilimitado por envio.", size=12, color=_color("texto_sec", dark)),
                                            subscribe_monthly_button,
                                        ],
                                        spacing=8,
                                    ),
                                ),
                            ),
                        ),
                    ],
                    spacing=8,
                    run_spacing=8,
                ),
                status_text,
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
    # Sincronizacao online em background para nao travar a abertura da tela.
    if backend and backend.enabled() and page:
        try:
            page.run_task(_refresh_status_async)
        except Exception:
            pass
    return result




def _build_settings_body(state, navigate, dark: bool):
    user = state.get("usuario") or {}
    db = state["db"]
    page = state.get("page")
    screen_w = _screen_width(page) if page else 1280
    compact = screen_w < 1000
    very_compact = screen_w < 760
    form_width = min(520, max(230, int(screen_w - (84 if very_compact else 120))))
    user_id = user.get("id")
    if not user_id:
        return _build_placeholder_body(
            "Configuracoes",
            "E necessario estar logado para alterar as configuracoes.",
            navigate,
            dark,
        )

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

    api_keys = _extract_user_api_keys(user)

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
        dd = ft.Dropdown(
            label="Modelo padrao",
            options=[ft.dropdown.Option(m) for m in modelos],
            value=chosen,
            width=form_width if compact else 360,
        )
        model_dropdown_ref["control"] = dd
        return dd

    model_dropdown_slot = ft.Container(
        content=_build_model_dropdown(
            current_provider,
            user.get("model") or AI_PROVIDERS[current_provider]["default_model"],
        )
    )

    key_status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    key_manage_button = ft.OutlinedButton(
        "Configurar chaves por provider",
        icon=ft.Icons.KEY,
        on_click=lambda _: None,
    )
    economia_mode_switch = ft.Switch(
        value=bool(user.get("economia_mode")),
    )
    telemetry_opt_in_switch = ft.Switch(
        value=bool(user.get("telemetry_opt_in")),
    )
    save_feedback = ft.Text("", size=12, color=_color("texto_sec", dark), visible=False)

    def _open_external_link(url: str):
        if not page:
            return
        try:
            _launch_url_compat(page, url, "settings_open_external_link")
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
        key_field = ft.TextField(
            label="API key",
            hint_text="Cole a chave desse provider",
            width=420 if not compact else min(420, form_width),
            password=True,
            can_reveal_password=True,
            value=str(api_keys.get(selected_provider_ref["value"]) or ""),
        )
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
            _close_dialog_compat(page, dialog_ref.get("dlg"))
            _update_key_status()
            if page:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Chave salva para {AI_PROVIDERS.get(provider_sel, {}).get('name', provider_sel)}"),
                    bgcolor=CORES["sucesso"],
                    show_close_icon=True,
                )
                page.snack_bar.open = True
                page.update()

        def _clear_key(_):
            provider_sel = _normalize_provider(selected_provider_ref["value"])
            api_keys[provider_sel] = ""
            key_field.value = ""
            _close_dialog_compat(page, dialog_ref.get("dlg"))
            _update_key_status()
            if page:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Chave removida de {AI_PROVIDERS.get(provider_sel, {}).get('name', provider_sel)}"),
                    bgcolor=CORES["warning"],
                    show_close_icon=True,
                )
                page.snack_bar.open = True
                page.update()

        provider_dd.on_change = _refresh_dialog_provider
        provider_dd.on_select = _refresh_dialog_provider
        open_link_btn.on_click = _open_selected_portal

        _refresh_dialog_provider()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("API key"),
            content=ft.Container(
                width=min(460, int(form_width + 40)),
                content=ft.Column(
                    [
                        provider_dd,
                        key_field,
                        helper_text,
                        open_link_btn,
                    ],
                    spacing=8,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: _close_dialog_compat(page, dialog_ref.get("dlg"))),
                ft.TextButton("Limpar", on_click=_clear_key),
                ft.ElevatedButton("Salvar chave", icon=ft.Icons.SAVE, on_click=_save_key),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialog_ref["dlg"] = dlg
        _show_dialog_compat(page, dlg)

    key_manage_button.on_click = lambda _: _open_key_dialog(provider_dropdown.value)

    economia_row = ft.ResponsiveRow(
        [
            ft.Container(col={"xs": 2, "md": 1}, content=economia_mode_switch),
            ft.Container(
                col={"xs": 10, "md": 11},
                content=ft.Text(
                    "Modo economia (prioriza modelos mais baratos/estaveis)",
                    size=12 if very_compact else 13,
                    color=_color("texto", dark),
                ),
            ),
        ],
        spacing=8,
        run_spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    telemetry_row = ft.ResponsiveRow(
        [
            ft.Container(col={"xs": 2, "md": 1}, content=telemetry_opt_in_switch),
            ft.Container(
                col={"xs": 10, "md": 11},
                content=ft.Text(
                    "Telemetria anonima (opt-in para melhorias do produto)",
                    size=12 if very_compact else 13,
                    color=_color("texto", dark),
                ),
            ),
        ],
        spacing=8,
        run_spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def _on_provider_change(e):
        selecionado = _normalize_provider(getattr(e.control, "value", None))
        provider_dropdown.value = selecionado
        modelo_atual = (model_dropdown_ref.get("control").value if model_dropdown_ref.get("control") else None)
        model_dropdown_slot.content = _build_model_dropdown(selecionado, modelo_atual)
        model_dropdown_slot.update()
        _update_key_status()

    # Flet 0.80.x usa on_select no Dropdown (on_change nao existe).
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
                state["usuario"][_provider_api_field(p)] = str(api_keys.get(p) or "").strip() or None
            state["usuario"]["economia_mode"] = 1 if economia_mode_switch.value else 0
            state["usuario"]["telemetry_opt_in"] = 1 if telemetry_opt_in_switch.value else 0

            backend_ref = state.get("backend")
            backend_uid = _backend_user_id(state.get("usuario") or {})

            async def _push_settings_remote_async():
                if not (backend_ref and backend_ref.enabled()):
                    return
                if int(backend_uid or 0) <= 0:
                    return
                try:
                    await asyncio.to_thread(
                        backend_ref.upsert_user_settings,
                        int(backend_uid),
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
                    log_exception(ex_sync, "settings_save.sync_remote")

            if page and backend_ref and backend_ref.enabled():
                try:
                    page.run_task(_push_settings_remote_async)
                except Exception as ex_task:
                    log_exception(ex_task, "settings_save.schedule_remote_sync")

            log_event("settings_save", f"user_id={user_id} provider={provider_value} model={model_value}")
            _set_feedback_text(save_feedback, "Configuracoes salvas com sucesso.", "success")
            save_feedback.visible = True
            if page:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Configuracoes salvas"),
                    bgcolor=CORES["sucesso"],
                    show_close_icon=True,
                )
                page.snack_bar.open = True
                page.update()
        except Exception as ex:
            log_exception(ex, "settings_save")
            _set_feedback_text(save_feedback, "Erro ao salvar configuracoes.", "error")
            save_feedback.visible = True
            if page:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Erro ao salvar configuracoes", color="white"),
                    bgcolor=CORES["erro"],
                    show_close_icon=True,
                )
                page.snack_bar.open = True
                page.update()

    retorno = ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Text("Configuracoes", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.Text("Ajustes rapidos de IA.", size=14, color=_color("texto_sec", dark)),
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("IA e preferencia de uso", size=16, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                                provider_dropdown,
                                model_dropdown_slot,
                                key_manage_button,
                                key_status_text,
                                ft.Row(
                                    [
                                        ft.TextButton(
                                            "Criar chave Gemini",
                                            icon=ft.Icons.OPEN_IN_NEW,
                                            on_click=lambda _: _open_external_link(provider_links["gemini"]),
                                        ),
                                        ft.TextButton(
                                            "Criar chave OpenAI",
                                            icon=ft.Icons.OPEN_IN_NEW,
                                            on_click=lambda _: _open_external_link(provider_links["openai"]),
                                        ),
                                        ft.TextButton(
                                            "Criar chave Groq",
                                            icon=ft.Icons.OPEN_IN_NEW,
                                            on_click=lambda _: _open_external_link(provider_links["groq"]),
                                        ),
                                    ],
                                    wrap=True,
                                    spacing=6,
                                ),
                                economia_row,
                                telemetry_row,
                                ft.Text(
                                    "Cada provider tem sua propria chave. Alterar provider/modelo nao sobrescreve as demais chaves.",
                                    size=12,
                                    color=_color("texto_sec", dark),
                                ),
                                ft.ElevatedButton("Salvar", icon=ft.Icons.SAVE, on_click=save),
                                save_feedback,
                            ],
                            spacing=10,
                        ),
                    ),
                ),
                ft.Container(height=12),
                ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: navigate("/home")),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
    _update_key_status()
    return retorno


def _open_menu_dialog(page: ft.Page, state: dict, current_route: str, dark: bool, navigate, on_logout, toggle_dark):
    user = state.get("usuario") or {}
    selected_index = 0
    for idx, (route, _, _) in enumerate(APP_ROUTES):
        if route == current_route:
            selected_index = idx
            break

    def _close_drawer_safe():
        try:
            if hasattr(page, "close_drawer"):
                page.close_drawer()
                return
        except Exception:
            pass
        try:
            if getattr(page, "drawer", None):
                page.drawer.open = False
                page.update()
        except Exception:
            pass

    def _on_menu_change(e):
        idx = getattr(e.control, "selected_index", None)
        try:
            idx = int(idx)
        except Exception:
            return
        if idx < 0 or idx >= len(APP_ROUTES):
            return
        target_route = APP_ROUTES[idx][0]
        _close_drawer_safe()
        if target_route != current_route:
            navigate(target_route)

    def _logout_and_close(e):
        _close_drawer_safe()
        on_logout(e)

    destinations = [
        ft.NavigationDrawerDestination(
            icon=icon,
            selected_icon=ft.Icons.CHECK_CIRCLE,
            label=label,
        )
        for _, label, icon in APP_ROUTES
    ]

    drawer = ft.NavigationDrawer(
        selected_index=selected_index,
        on_change=_on_menu_change,
        bgcolor=_color("card", dark),
        controls=[
            ft.Container(
                padding=ft.padding.only(left=16, right=12, top=12, bottom=8),
                content=ft.Column(
                    [
                        ft.Text("Menu", size=20, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ft.Text(
                            f"{user.get('nome', '')} ({user.get('email', '')})" if user.get("email") else f"{user.get('nome', '')}",
                            size=12,
                            color=_color("texto_sec", dark),
                        ),
                    ],
                    spacing=4,
                ),
            ),
            ft.Divider(height=1, color=_soft_border(dark, 0.12)),
            *destinations,
            ft.Divider(height=1, color=_soft_border(dark, 0.12)),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.DARK_MODE, size=16, color=_color("texto_sec", dark)),
                                ft.Text("Modo escuro", color=_color("texto", dark)),
                            ],
                            spacing=8,
                        ),
                        ft.Switch(value=dark, on_change=toggle_dark, scale=0.9),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ),
            ft.Container(
                padding=ft.padding.only(left=12, right=12, bottom=12),
                content=ft.ElevatedButton(
                    "Sair",
                    icon=ft.Icons.LOGOUT,
                    on_click=_logout_and_close,
                    bgcolor=CORES["erro"],
                    color="white",
                ),
            ),
        ],
    )

    _sanitize_control_texts(drawer)
    page.drawer = drawer
    if hasattr(page, "show_drawer"):
        page.show_drawer()
        try:
            page.update()
        except Exception:
            pass
        return
    try:
        drawer.open = True
        page.update()
    except Exception:
        pass


def _build_shell_view(page: ft.Page, state: dict, route: str, body: ft.Control, on_logout, dark: bool, toggle_dark):
    def navigate(target: str):
        target_route = _normalize_route_path(target)
        current_route = _normalize_route_path(page.route or route or "/home")
        if current_route not in {"/", "/login"} and current_route != target_route:
            history = state.setdefault("route_history", [])
            if not history or history[-1] != current_route:
                history.append(current_route)
            # Mantem historico enxuto para evitar crescimento indefinido.
            if len(history) > 80:
                del history[:-80]
        page.go(target_route)

    def go_back(_=None):
        try:
            current_route = _normalize_route_path(page.route or route or "/home")
            history = state.setdefault("route_history", [])
            while history:
                prev = _normalize_route_path(history.pop())
                if prev and prev not in {"/", "/login"} and prev != current_route:
                    page.go(prev)
                    return
            page.go("/home" if state.get("usuario") else "/login")
        except Exception:
            page.go("/home" if state.get("usuario") else "/login")

    menu_ref = {"panel": None, "scrim": None, "row": None}

    def _set_inline_menu_visible(visible: bool):
        panel = menu_ref.get("panel")
        scrim = menu_ref.get("scrim")
        row = menu_ref.get("row")
        is_open = bool(visible)
        if panel is not None:
            panel.visible = is_open
        if scrim is not None:
            scrim.visible = is_open
        if row is not None:
            row.visible = is_open
        state["menu_inline_open"] = is_open
        try:
            if panel is not None:
                panel.update()
            if scrim is not None:
                scrim.update()
            if row is not None:
                row.update()
        except Exception:
            page.update()

    def _close_inline_menu(_=None):
        panel = menu_ref["panel"]
        if panel is None:
            return
        if bool(panel.visible):
            _set_inline_menu_visible(False)

    def _toggle_inline_menu(_=None):
        panel = menu_ref["panel"]
        if panel is None:
            return
        is_open = not bool(panel.visible)
        _set_inline_menu_visible(is_open)
        log_event("menu_click", f"route={route} inline_open={panel.visible}")

    def _navigate_from_menu(target: str):
        target_route = _normalize_route_path(target)
        current_route = _normalize_route_path(page.route or route or "/home")
        _set_inline_menu_visible(False)
        state["menu_inline_open"] = False
        if target_route == current_route:
            return
        try:
            page.update()
        except Exception:
            pass
        navigate(target_route)

    def _toggle_dark_icon(_=None):
        current_dark = bool(state.get("tema_escuro", False))
        class _Ctl:
            value = not current_dark
        class _Evt:
            control = _Ctl()
        page.run_task(toggle_dark, _Evt())

    normalized_route = _normalize_route_path(route)
    screen_w = _screen_width(page)
    compact = screen_w < 980
    very_compact = screen_w < 760
    show_back = normalized_route not in {"/home", "/welcome"}
    route_labels = {r: label for r, label, _ in APP_ROUTES}
    route_labels.update({r: label for r, label, _ in APP_ROUTES_SECONDARY})
    route_labels.update(
        {
            "/welcome": "Boas-vindas",
            "/simulado": "Simulado",
            "/revisao/sessao": "Revisao do Dia",
            "/revisao/erros": "Caderno de Erros",
            "/revisao/marcadas": "Marcadas",
        }
    )
    route_label = route_labels.get(normalized_route)
    if not route_label:
        clean_route = normalized_route.strip("/") or "home"
        route_label = clean_route.replace("-", " ").replace("/", " / ").title()
    focus_routes = {"/quiz", "/flashcards", "/open-quiz", "/simulado"}
    focus_mode = normalized_route in focus_routes
    low_noise_user_routes = {"/home", "/mais", "/profile", "/settings"}

    if normalized_route == "/home":
        title = "Quiz Vance"
    elif focus_mode and not very_compact:
        title = f"Modo foco: {route_label}"
    else:
        title = route_label

    user = state.get("usuario") or {}

    right_controls = []
    if very_compact:
        right_controls.append(
            ft.IconButton(
                icon=ft.Icons.DARK_MODE if dark else ft.Icons.LIGHT_MODE,
                tooltip="Tema",
                on_click=_toggle_dark_icon,
                icon_color=_color("texto_sec", dark),
            )
        )
    else:
        right_controls.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.DARK_MODE, size=16, color=_color("texto_sec", dark)),
                    ft.Switch(value=dark, on_change=toggle_dark, scale=0.88 if compact else 0.92),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

    if (not very_compact) and (normalized_route in low_noise_user_routes):
        user_text = f"{user.get('nome', '')}" if compact else f"{user.get('nome', '')} ({user.get('email', '')})"
        right_controls.append(
            AppText(
                user_text,
                variant="caption",
                dark=dark,
                short_label=True,
                size=11 if compact else 12,
                color=_color("texto_sec", dark),
            )
        )

    if compact or focus_mode:
        right_controls.append(
            ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", on_click=on_logout, icon_color=CORES["erro"])
        )
    else:
        right_controls.append(
            ft.ElevatedButton("Sair", on_click=on_logout, bgcolor=CORES["erro"], color="white")
        )

    inline_menu_controls = [
        ft.Text("Menu", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
        ft.Divider(height=1, color=_soft_border(dark, 0.12)),
    ]
    for target_route, label, icon in APP_ROUTES:
        selected = target_route == normalized_route
        inline_menu_controls.append(
            ft.TextButton(
                on_click=lambda _, r=target_route: _navigate_from_menu(r),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]) if selected else "transparent",
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding(10, 8, 10, 8),
                ),
                content=ft.Row(
                    [
                        ft.Icon(icon, size=18, color=CORES["primaria"] if selected else _color("texto_sec", dark)),
                        ft.Text(
                            label,
                            size=13,
                            weight=ft.FontWeight.BOLD if selected else ft.FontWeight.W_500,
                            color=CORES["primaria"] if selected else _color("texto", dark),
                        ),
                    ],
                    spacing=10,
                ),
            )
        )

    inline_menu = ft.Container(
        visible=bool(state.get("menu_inline_open", False)),
        width=220 if not compact else max(150, min(200, int(screen_w * 0.46))),
        bgcolor=_color("card", dark),
        border=ft.border.only(right=ft.BorderSide(1, _soft_border(dark, 0.10))),
        padding=10,
        content=ft.Column(
            inline_menu_controls,
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
    )
    menu_ref["panel"] = inline_menu

    topbar = ft.Container(
        padding=ft.padding.symmetric(horizontal=8 if very_compact else (10 if compact else 16), vertical=10),
        bgcolor=ft.Colors.with_opacity(0.05, _color("texto", dark)),
        border=ft.border.only(bottom=ft.BorderSide(1, _soft_border(dark, 0.10))),
        content=ft.Row(
            [
                ft.Container(
                    expand=True,
                    content=ft.Row(
                        [
                            ft.IconButton(icon=ft.Icons.MENU_ROUNDED, tooltip="Menu", on_click=_toggle_inline_menu),
                            ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="Voltar", on_click=go_back, visible=show_back),
                            AppText(
                                title,
                                variant="h3",
                                dark=dark,
                                short_label=True,
                                size=14 if very_compact else (16 if compact else 18),
                                color=_color("texto", dark),
                            ),
                        ],
                        spacing=2,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.Row(
                    right_controls,
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    ai_busy_text = ft.Text(
        str(state.get("ai_busy_message") or "Processando com IA..."),
        size=12,
        color=_color("texto_sec", dark),
    )
    ai_busy_bar = ft.ProgressBar(
        value=None,
        color=CORES["primaria"],
        bgcolor=ft.Colors.with_opacity(0.16, _color("texto", dark)),
        visible=False,
    )
    ai_busy_box = ft.Container(
        visible=False,
        padding=ft.padding.symmetric(horizontal=12 if compact else 16, vertical=8),
        bgcolor=ft.Colors.with_opacity(0.035, _color("texto", dark)),
        border=ft.border.only(bottom=ft.BorderSide(1, _soft_border(dark, 0.08))),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.ProgressRing(width=12, height=12, stroke_width=2),
                        ft.Container(expand=True, content=ai_busy_text),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ai_busy_bar,
            ],
            spacing=6,
            tight=True,
        ),
    )
    state["_ai_busy_box_ctl"] = ai_busy_box
    state["_ai_busy_text_ctl"] = ai_busy_text
    state["_ai_busy_bar_ctl"] = ai_busy_bar
    _sync_ai_indicator_controls(state)

    menu_scrim = ft.Container(
        visible=bool(state.get("menu_inline_open", False)),
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.20, "#000000"),
        on_click=_close_inline_menu,
    )
    menu_row = ft.Row(
        [
            inline_menu,
            ft.Container(expand=True, on_click=_close_inline_menu),
        ],
        spacing=0,
        expand=True,
        visible=bool(state.get("menu_inline_open", False)),
    )
    menu_ref["scrim"] = menu_scrim
    menu_ref["row"] = menu_row

    content_layout = (
        ft.Stack(
            [
                ft.Container(expand=True, content=body),
                menu_scrim,
                menu_row,
            ],
            expand=True,
        )
        if compact
        else ft.Row(
            [
                inline_menu,
                ft.Container(expand=True, content=body),
            ],
            spacing=0,
            expand=True,
        )
    )
    content = ds_page_scaffold(
        page=page,
        content=content_layout,
        dark=dark,
        safe_area=False,
        max_width=1360,
        pad_h_mobile=DS.SP_8,
        pad_h_tablet=DS.SP_12,
        pad_h_desktop=DS.SP_16,
        pad_v=DS.SP_8,
    )

    shell_column = ft.Column(
        controls=[topbar, ai_busy_box, ft.Container(expand=True, content=content)],
        spacing=0,
        expand=True,
    )
    return ft.View(route=route, controls=[ft.SafeArea(expand=True, content=shell_column)], bgcolor=_color("fundo", dark))

def _build_revisao_body(state: dict, navigate, dark: bool):
    db = state.get("db")
    user = state.get("usuario") or {}
    user_id = int(user.get("id") or 0)
    counters = {"flashcards_pendentes": 0, "questoes_pendentes": 0}
    if db and user_id:
        try:
            counters = db.contadores_revisao(user_id)
        except Exception as ex:
            log_exception(ex, "main._build_revisao_body.contadores")

    flashcards_pendentes = int(counters.get("flashcards_pendentes") or 0)
    questoes_pendentes = int(counters.get("questoes_pendentes") or 0)
    total_hoje = flashcards_pendentes + questoes_pendentes

    def _card(title: str, desc: str, value: int, route: str, color: str):
        return ds_card(
            dark=dark,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(title, size=DS.FS_BODY, weight=DS.FW_SEMI, color=DS.text_color(dark)),
                            ft.Container(expand=True),
                            ds_badge(str(value), color=color),
                        ],
                        spacing=DS.SP_8,
                    ),
                    ft.Text(desc, size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                    ft.Row(
                        [ds_btn_primary("Abrir", on_click=lambda _: navigate(route), dark=dark)],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=DS.SP_8,
            ),
        )

    return ft.Container(
        expand=True,
        padding=DS.SP_16,
        content=ft.Column(
            [
                ds_section_title("Revisao", dark=dark),
                ft.Text(
                    f"{total_hoje} itens pendentes para hoje" if total_hoje else "Nada pendente para hoje",
                    size=DS.FS_BODY_S,
                    color=DS.text_sec_color(dark),
                ),
                _card("Revisao do Dia", "Fila combinada 3 flashcards -> 2 questoes", total_hoje, "/revisao/sessao", DS.P_500),
                _card("Caderno de Erros", "Questoes em que voce errou e precisam reforco", questoes_pendentes, "/revisao/erros", DS.ERRO),
                _card("Marcadas", "Questoes marcadas manualmente para revisar", questoes_pendentes, "/revisao/marcadas", DS.WARNING),
                _card("Flashcards", "Revisao ativa com lembrei/rever/pular", flashcards_pendentes, "/flashcards", DS.SUCESSO),
            ],
            spacing=DS.SP_12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )


def _build_simulado_body(state: dict, navigate, dark: bool):
    page = state.get("page")
    user = state.get("usuario") or {}
    db = state.get("db")
    premium = _is_premium_active(user)
    user_id = int(user.get("id") or 0)
    policy = MockExamService(db) if db else None
    usados_hoje = policy.daily_used(user_id) if (policy and user_id and not premium) else 0
    plan_hint_text = (
        "Premium ativo: sem limite diario e com mais opcoes de quantidade."
        if premium
        else MockExamService.plan_hint(False)
    )
    usage_hint_text = (
        "Sem limite diario no Premium."
        if premium
        else f"Simulados usados hoje: {usados_hoje}"
    )

    tempo_field = ft.TextField(label="Tempo total (min)", value="60", keyboard_type=ft.KeyboardType.NUMBER, border_radius=DS.R_MD)
    dificuldade_dd = ft.Dropdown(
        label="Dificuldade",
        value="intermediario",
        options=[
            ft.dropdown.Option("facil", "Facil"),
            ft.dropdown.Option("intermediario", "Intermediario"),
            ft.dropdown.Option("dificil", "Dificil"),
        ],
    )
    preset_counts = MockExamService.preset_counts(premium)
    qtd_dd = ft.Dropdown(
        label="Quantidade",
        value=str(preset_counts[1] if len(preset_counts) > 1 else preset_counts[0]),
        options=[ft.dropdown.Option(str(v), f"{v} questoes") for v in preset_counts] + [ft.dropdown.Option("custom", "Custom")],
    )
    qtd_custom = ft.TextField(label="Qtd custom (opcional)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=DS.R_MD)
    disciplina_field = ft.TextField(label="Disciplina (opcional)", border_radius=DS.R_MD)
    assunto_field = ft.TextField(label="Assunto (opcional)", border_radius=DS.R_MD)

    def _iniciar(_):
        if policy and user_id:
            allowed, _used, _limit = policy.can_start_today(user_id, premium=premium)
            if not allowed:
                _show_upgrade_dialog(page, navigate, "Plano Free: limite diario de simulado atingido.")
                return

        try:
            tempo = max(5, int(str(tempo_field.value or "60").strip()))
        except Exception:
            tempo = 60

        count = 20
        custom_raw = str(qtd_custom.value or "").strip()
        if custom_raw.isdigit():
            count = int(custom_raw)
        else:
            try:
                count = int(str(qtd_dd.value or "20"))
            except Exception:
                count = 20
        count, _capped = MockExamService.normalize_question_count(count, premium)

        disciplina = str(disciplina_field.value or "").strip()
        assunto = str(assunto_field.value or "").strip()
        disciplinas = [disciplina] if disciplina else []
        assuntos = [assunto] if assunto else []
        topic = disciplina or assunto or "Geral"
        state["quiz_preset"] = {
            "topic": topic,
            "count": str(count),
            "difficulty": dificuldade_dd.value or "intermediario",
            "simulado_mode": True,
            "feedback_imediato": False,
            "simulado_tempo": tempo,
            "auto_start": True,
            "advanced_filters": {
                "disciplinas": disciplinas,
                "assuntos": assuntos,
            },
            "reason": f"Modo Simulado - {tempo}min - {count} questoes",
        }
        navigate("/simulado")

    return ft.Container(
        expand=True,
        padding=DS.SP_16,
        content=ft.Column(
            [
                ds_section_title("Modo Simulado", dark=dark),
                ft.Text(plan_hint_text, size=DS.FS_CAPTION, color=DS.SUCESSO if premium else DS.WARNING),
                ft.Text(
                    usage_hint_text,
                    size=DS.FS_CAPTION,
                    color=DS.text_sec_color(dark),
                ),
                ds_card(
                    dark=dark,
                    content=ft.Column(
                        [
                            ft.ResponsiveRow(
                                [
                                    ft.Container(col={"xs": 6, "md": 3}, content=qtd_dd),
                                    ft.Container(col={"xs": 6, "md": 3}, content=qtd_custom),
                                    ft.Container(col={"xs": 6, "md": 3}, content=tempo_field),
                                    ft.Container(col={"xs": 6, "md": 3}, content=dificuldade_dd),
                                    ft.Container(col={"xs": 12, "md": 6}, content=disciplina_field),
                                    ft.Container(col={"xs": 12, "md": 6}, content=assunto_field),
                                ],
                                run_spacing=DS.SP_8,
                                spacing=DS.SP_8,
                            ),
                            ft.ResponsiveRow(
                                [
                                    ft.Container(
                                        col={"xs": 12, "md": 6},
                                        content=ds_btn_primary("Iniciar Simulado", on_click=_iniciar, dark=dark, icon=ft.Icons.PLAY_ARROW_ROUNDED),
                                    ),
                                    ft.Container(
                                        col={"xs": 12, "md": 6},
                                        content=ds_btn_ghost("Voltar", on_click=lambda _: navigate("/mais"), dark=dark),
                                    ),
                                ],
                                run_spacing=DS.SP_8,
                                spacing=DS.SP_8,
                            ),
                        ],
                        spacing=DS.SP_10,
                    ),
                ),
            ],
            spacing=DS.SP_12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )



def _build_error_view(page: ft.Page, route: str):

    return ft.View(
        route=route,
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, color=CORES["erro"], size=48),
                        ft.Text("Erro ao renderizar tela", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Detalhes nos logs do aplicativo.", size=14),
                        ft.ElevatedButton("Voltar ao login", on_click=lambda _: page.go("/login")),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            )
        ],
        bgcolor=CORES["fundo"],
    )


def main(page: ft.Page):
    try:
        log_event("main_enter", "flet page created")
        page.title = "Quiz Vance"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0
        page.bgcolor = CORES["fundo"]
        _apply_global_theme(page)
        is_android_runtime = bool(os.getenv("ANDROID_DATA"))
        if not is_android_runtime:
            page.window_width = 1280
            page.window_height = 820
            page.window_min_width = 560
            page.window_min_height = 520
        # Guarda global: saneia controles antes de cada update.
        raw_page_update = page.update
        if not bool(getattr(page, "_qv_safe_update_installed", False)):
            def _safe_page_update(*args, **kwargs):
                _sanitize_page_controls(page)
                return raw_page_update(*args, **kwargs)
            try:
                page.update = _safe_page_update
                setattr(page, "_qv_safe_update_installed", True)
            except Exception:
                pass

        # Recuperacao automatica para erro de layout wrap+expand.
        _recovering_wrap_error = {"active": False}

        def _on_page_error(e):
            msg = str(getattr(e, "data", "") or "")
            dbg = ""
            try:
                top_view = page.views[-1] if getattr(page, "views", None) else None
                dbg = _debug_scan_wrap_conflicts(top_view)
            except Exception:
                pass
            log_exception(Exception(f"{msg} | route={getattr(page, 'route', '')} | {dbg}"), "flet.page.on_error")
            if (
                ("WrapParentData" not in msg)
                and ("FlexParentData" not in msg)
                and ("ParentDataWidget" not in msg)
                and ("ParentData" not in msg)
            ):
                return
            if _recovering_wrap_error["active"]:
                return
            _recovering_wrap_error["active"] = True
            try:
                _sanitize_page_controls(page)
                page.update()
            except Exception as ex_inner:
                log_exception(ex_inner, "flet.page.on_error.recover")
            finally:
                _recovering_wrap_error["active"] = False

        page.on_error = _on_page_error

        # Estado minimo; carregamos recursos pesados de forma assincrona para evitar AL_Kill.
        state = {
            "usuario": None,
            "db": None,
            "backend": None,
            "sounds": None,
            "tema_escuro": False,
            "view_cache": {},
            "last_theme": False,
            "page": page,
            "splash_done": False,
            "init_ready": False,
            "init_error": None,
            "init_task_running": False,
            "last_resize_ts": 0.0,
            "last_resize_size": None,
            "size_class": None,
            "menu_inline_open": False,
            "route_history": [],
            "async_guard": AsyncActionGuard(),
            "stats_sync_running": False,
            "stats_sync_inflight": False,
            "summary_sync_inflight": False,
            "settings_sync_inflight": False,
            "sync_loop_interval_s": _QUIZ_STATS_SYNC_INTERVAL_S,
            "last_summary_sync_ts": 0.0,
            "last_settings_sync_ts": 0.0,
            "stats_summary_signature": "",
            "settings_sync_signature": "",
            "ai_busy_count": 0,
            "ai_busy_message": "",
            "_ai_busy_box_ctl": None,
            "_ai_busy_text_ctl": None,
            "_ai_busy_bar_ctl": None,
            "pending_theme_refresh": False,
            "_theme_refresh_cb": None,
        }

        async def _init_runtime():
            try:
                log_event("init_start", "runtime")
                state["init_error"] = None
                ensure_runtime_dirs()
                db = Database()
                db.iniciar_banco()
                state["db"] = db
                log_event("db_ready", str(get_db_path()))
                state["backend"] = BackendClient()
                state["sounds"] = create_sound_manager(page)
                state["init_ready"] = True
                log_event("init_done", "runtime_ok")
                _ensure_stats_sync_task()
            except Exception as ex_inner:
                state["init_error"] = str(ex_inner)
                log_exception(ex_inner, "main.async_init")
            finally:
                state["init_task_running"] = False
                if not state.get("usuario"):
                    try:
                        route_change(None)
                    except Exception as ex_refresh:
                        log_exception(ex_refresh, "main.refresh_after_init")

        def _start_runtime_init():
            if state.get("db") is not None or state.get("init_task_running"):
                return
            state["init_task_running"] = True
            try:
                page.run_task(_init_runtime)
            except Exception as ex_sched:
                state["init_task_running"] = False
                state["init_error"] = str(ex_sched)
                log_exception(ex_sched, "main.schedule_init")

    except Exception as ex:
        # Qualquer falha no setup inicial deve aparecer em tela e ser logada.
        log_exception(ex, 'main.setup')
        page.views[:] = [_build_error_view(page, '/error')]
        page.update()
        return

    def log_state(event: str):
        user = state.get("usuario") or {}
        log_event(
            event,
            f"route={page.route} user_id={user.get('id')} email={user.get('email')} dark={state.get('tema_escuro')}",
        )

    def apply_theme(dark: bool):
        state["tema_escuro"] = dark
        page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        page.bgcolor = _color("fundo", dark)
        page.update()

    def navigate(route: str):
        target_route = _normalize_route_path(route)
        current_route = _normalize_route_path(page.route or "/home")
        if current_route not in {"/", "/login"} and current_route != target_route:
            history = state.setdefault("route_history", [])
            if not history or history[-1] != current_route:
                history.append(current_route)
            if len(history) > 80:
                del history[:-80]
        page.go(target_route)

    async def _sync_cloud_quiz_summary_once(force: bool = False) -> bool:
        if state.get("summary_sync_inflight"):
            return False
        now = time.monotonic()
        min_gap = _ROUTE_SYNC_MIN_GAP_S * (0.5 if force else 1.0)
        if (now - float(state.get("last_summary_sync_ts") or 0.0)) < min_gap:
            return False
        db_ref = state.get("db")
        backend_ref = state.get("backend")
        usuario = state.get("usuario") or {}
        if not db_ref or not backend_ref or not backend_ref.enabled():
            return False
        if not usuario or not usuario.get("id"):
            return False
        local_uid = int(usuario.get("id") or 0)
        backend_uid = _backend_user_id(usuario)
        if local_uid <= 0 or backend_uid <= 0:
            return False
        state["summary_sync_inflight"] = True
        state["last_summary_sync_ts"] = now
        try:
            summary_raw = await asyncio.to_thread(backend_ref.get_quiz_stats_summary, int(backend_uid))
            summary = {
                "total_questoes": int((summary_raw or {}).get("total_questoes") or 0),
                "total_acertos": int((summary_raw or {}).get("total_acertos") or 0),
                "total_xp": int((summary_raw or {}).get("total_xp") or 0),
                "today_questoes": int((summary_raw or {}).get("today_questoes") or 0),
                "today_acertos": int((summary_raw or {}).get("today_acertos") or 0),
                "today_xp": int((summary_raw or {}).get("today_xp") or 0),
            }
            await asyncio.to_thread(
                db_ref.sync_cloud_quiz_totals,
                int(local_uid),
                int(summary.get("total_questoes") or 0),
                int(summary.get("total_acertos") or 0),
                int(summary.get("total_xp") or 0),
                int(summary.get("today_questoes") or 0),
                int(summary.get("today_acertos") or 0),
            )
            prev_sig = str(state.get("stats_summary_signature") or "")
            next_sig = json.dumps(summary, ensure_ascii=True, sort_keys=True)
            state["stats_summary_signature"] = next_sig
            changed = next_sig != prev_sig
            if state.get("usuario") and int((state["usuario"] or {}).get("id") or 0) == int(local_uid):
                prev_local = (
                    int(state["usuario"].get("total_questoes", 0) or 0),
                    int(state["usuario"].get("acertos", 0) or 0),
                    int(state["usuario"].get("xp", 0) or 0),
                )
                state["usuario"]["total_questoes"] = max(prev_local[0], int(summary.get("total_questoes") or 0))
                state["usuario"]["acertos"] = max(prev_local[1], int(summary.get("total_acertos") or 0))
                state["usuario"]["xp"] = max(prev_local[2], int(summary.get("total_xp") or 0))
                changed = changed or prev_local != (
                    int(state["usuario"].get("total_questoes", 0) or 0),
                    int(state["usuario"].get("acertos", 0) or 0),
                    int(state["usuario"].get("xp", 0) or 0),
                )
            return bool(changed)
        except Exception as ex_summary:
            log_exception(ex_summary, "main._sync_cloud_quiz_summary_once")
            return False
        finally:
            state["summary_sync_inflight"] = False

    async def _sync_quiz_stats_once(force_summary: bool = False) -> bool:
        if state.get("stats_sync_inflight"):
            return False
        db_ref = state.get("db")
        backend_ref = state.get("backend")
        usuario = state.get("usuario") or {}
        if not db_ref or not backend_ref or not backend_ref.enabled():
            return False
        if not usuario or not usuario.get("id"):
            return False
        local_uid = int(usuario.get("id") or 0)
        backend_uid = _backend_user_id(usuario)
        if local_uid <= 0 or backend_uid <= 0:
            return False
        state["stats_sync_inflight"] = True
        try:
            pending = await asyncio.to_thread(db_ref.list_pending_quiz_stats_events, local_uid, 200)
            if not pending:
                return await _sync_cloud_quiz_summary_once(force=bool(force_summary))
            events = []
            event_to_row = {}
            for item in pending:
                ev = item.get("event") if isinstance(item, dict) else None
                if not isinstance(ev, dict):
                    continue
                eid = str(ev.get("event_id") or item.get("event_id") or "").strip()
                if not eid:
                    continue
                ev["event_id"] = eid
                events.append(ev)
                event_to_row[eid] = int(item.get("id") or 0)
            if not events:
                return await _sync_cloud_quiz_summary_once(force=bool(force_summary))
            try:
                resp = await asyncio.to_thread(backend_ref.sync_quiz_stats_batch, int(backend_uid), events)
            except Exception as ex:
                log_exception(ex, "main._sync_quiz_stats_once.backend")
                return False
            consumed = list((resp or {}).get("consumed_event_ids") or [])
            if not consumed:
                consumed = [str(ev.get("event_id") or "") for ev in events]
            delete_ids = [event_to_row.get(str(eid or "").strip(), 0) for eid in consumed]
            delete_ids = [int(i) for i in delete_ids if int(i or 0) > 0]
            if delete_ids:
                try:
                    await asyncio.to_thread(db_ref.delete_pending_quiz_stats_events, delete_ids)
                except Exception as ex:
                    log_exception(ex, "main._sync_quiz_stats_once.delete_queue")
            return await _sync_cloud_quiz_summary_once(force=True)
        finally:
            state["stats_sync_inflight"] = False

    async def _sync_remote_user_settings_once(force: bool = False) -> bool:
        if state.get("settings_sync_inflight"):
            return False
        now = time.monotonic()
        min_gap = _ROUTE_SYNC_MIN_GAP_S if force else _SETTINGS_SYNC_INTERVAL_S
        if (now - float(state.get("last_settings_sync_ts") or 0.0)) < min_gap:
            return False
        db_ref = state.get("db")
        backend_ref = state.get("backend")
        usuario = state.get("usuario") or {}
        if not db_ref or not backend_ref or not backend_ref.enabled():
            return False
        if not usuario or not usuario.get("id"):
            return False
        local_uid = int(usuario.get("id") or 0)
        backend_uid = _backend_user_id(usuario)
        if local_uid <= 0 or backend_uid <= 0:
            return False
        state["settings_sync_inflight"] = True
        state["last_settings_sync_ts"] = now
        try:
            remote_cfg = await asyncio.to_thread(backend_ref.get_user_settings, int(backend_uid))
            provider = _normalize_ai_provider((remote_cfg or {}).get("provider") or usuario.get("provider") or "gemini")
            modelos = list(AI_PROVIDERS.get(provider, AI_PROVIDERS["gemini"]).get("models") or [])
            default_model = str(AI_PROVIDERS.get(provider, AI_PROVIDERS["gemini"]).get("default_model") or (modelos[0] if modelos else "gemini-2.5-flash")).strip()
            model_raw = str((remote_cfg or {}).get("model") or "").strip()
            local_model = str((usuario or {}).get("model") or "").strip()
            model = model_raw or local_model or default_model
            if modelos and model not in modelos:
                model = default_model
            api_keys_remote: dict[str, Optional[str]] = {}
            for p in _AI_KEY_PROVIDERS:
                raw = (remote_cfg or {}).get(_provider_api_field(p))
                txt = str(raw).strip() if raw is not None else ""
                api_keys_remote[p] = txt or None
            active_raw = (remote_cfg or {}).get("api_key")
            active_key = str(active_raw).strip() if active_raw is not None else ""
            if active_key and not api_keys_remote.get(provider):
                api_keys_remote[provider] = active_key
            economia_mode = bool((remote_cfg or {}).get("economia_mode"))
            telemetry_opt_in = bool((remote_cfg or {}).get("telemetry_opt_in"))
            remote_sig = _settings_signature(
                provider,
                model,
                economia_mode,
                telemetry_opt_in,
                api_keys_remote,
            )
            prev_sig = str(state.get("settings_sync_signature") or "")
            if (not force) and remote_sig == prev_sig:
                return False
            await asyncio.to_thread(
                db_ref.sync_ai_preferences,
                int(local_uid),
                provider,
                model,
                api_keys_remote.get(provider),
                bool(economia_mode),
                bool(telemetry_opt_in),
            )
            await asyncio.to_thread(
                db_ref.atualizar_api_keys,
                int(local_uid),
                api_keys_remote,
                provider,
            )
            current = state.get("usuario") or {}
            if int(current.get("id") or 0) == int(local_uid):
                current["provider"] = provider
                current["model"] = model
                current["api_key"] = api_keys_remote.get(provider)
                for p in _AI_KEY_PROVIDERS:
                    current[_provider_api_field(p)] = api_keys_remote.get(p)
                current["economia_mode"] = 1 if bool(economia_mode) else 0
                current["telemetry_opt_in"] = 1 if bool(telemetry_opt_in) else 0
            state["settings_sync_signature"] = remote_sig
            return remote_sig != prev_sig
        except Exception as ex_settings:
            log_exception(ex_settings, "main._sync_remote_user_settings_once")
            return False
        finally:
            state["settings_sync_inflight"] = False

    async def _sync_cross_device_snapshot_once(force: bool = False, refresh_ui: bool = True) -> None:
        stats_changed = await _sync_quiz_stats_once(force_summary=bool(force))
        settings_changed = await _sync_remote_user_settings_once(force=bool(force))
        if not (refresh_ui and (stats_changed or settings_changed)):
            return
        try:
            current_route = _normalize_route_path(page.route or "/home")
            if current_route in {"/home", "/stats", "/profile", "/mais"}:
                route_change(None)
            elif current_route == "/settings":
                page.update()
        except Exception:
            pass

    async def _sync_quiz_stats_loop():
        if state.get("stats_sync_running"):
            return
        state["stats_sync_running"] = True
        try:
            while True:
                await _sync_cross_device_snapshot_once(force=False, refresh_ui=True)
                await asyncio.sleep(float(state.get("sync_loop_interval_s") or _QUIZ_STATS_SYNC_INTERVAL_S))
        except asyncio.CancelledError:
            return
        except Exception as ex:
            log_exception(ex, "main._sync_quiz_stats_loop")
        finally:
            state["stats_sync_running"] = False

    def _ensure_stats_sync_task():
        if state.get("stats_sync_running"):
            return
        try:
            page.run_task(_sync_quiz_stats_loop)
        except Exception as ex:
            log_exception(ex, "main._ensure_stats_sync_task")

    async def _sync_subscription_after_login_async(local_user_id: int, backend_uid: int):
        backend_ref = state.get("backend")
        db_ref = state.get("db")
        if not backend_ref or not backend_ref.enabled() or not db_ref:
            return
        try:
            current = state.get("usuario") or {}
            if int(current.get("backend_user_id") or 0) <= 0:
                await asyncio.to_thread(
                    backend_ref.upsert_user,
                    int(backend_uid),
                    current.get("nome", ""),
                    current.get("email", ""),
                )
            b = await asyncio.to_thread(backend_ref.get_plan, int(backend_uid))
            sub = {
                "plan_code": b.get("plan_code", "free"),
                "premium_active": 1 if b.get("premium_active") else 0,
                "premium_until": b.get("premium_until"),
                "trial_used": 1 if b.get("plan_code") == "trial" else int(current.get("trial_used", 0) or 0),
            }
            await asyncio.to_thread(
                db_ref.sync_subscription_status,
                int(local_user_id),
                str(sub.get("plan_code") or "free"),
                sub.get("premium_until"),
                int(sub.get("trial_used") or 0),
            )
            try:
                summary = await asyncio.to_thread(backend_ref.get_quiz_stats_summary, int(backend_uid))
                await asyncio.to_thread(
                    db_ref.sync_cloud_quiz_totals,
                    int(local_user_id),
                    int((summary or {}).get("total_questoes") or 0),
                    int((summary or {}).get("total_acertos") or 0),
                    int((summary or {}).get("total_xp") or 0),
                    int((summary or {}).get("today_questoes") or 0),
                    int((summary or {}).get("today_acertos") or 0),
                )
                if state.get("usuario") and int((state["usuario"] or {}).get("id") or 0) == int(local_user_id):
                    state["usuario"]["total_questoes"] = max(
                        int(state["usuario"].get("total_questoes", 0) or 0),
                        int((summary or {}).get("total_questoes") or 0),
                    )
                    state["usuario"]["acertos"] = max(
                        int(state["usuario"].get("acertos", 0) or 0),
                        int((summary or {}).get("total_acertos") or 0),
                    )
                    state["usuario"]["xp"] = max(
                        int(state["usuario"].get("xp", 0) or 0),
                        int((summary or {}).get("total_xp") or 0),
                    )
            except Exception as ex_summary:
                log_exception(ex_summary, "main._sync_subscription_after_login_async.summary")
        except Exception as ex:
            log_exception(ex, "main._sync_subscription_after_login_async.backend")
            try:
                sub = await asyncio.to_thread(db_ref.get_subscription_status, int(local_user_id))
            except Exception:
                return

        current = state.get("usuario") or {}
        if int(current.get("id") or 0) != int(local_user_id):
            return
        current["backend_user_id"] = int(backend_uid)
        current.update(sub)
        for route_key in ("/plans", "/home", "/stats", "/profile", "/mais"):
            state["view_cache"].pop(route_key, None)
        try:
            current_route = _normalize_route_path(page.route or "/home")
            if current_route in {"/home", "/stats", "/profile", "/mais", "/plans"}:
                route_change(None)
            else:
                page.update()
        except Exception:
            pass

    def on_login_success(usuario: dict):
        try:
            db = state.get("db")
            if db is None:
                page.snack_bar = ft.SnackBar(content=ft.Text("Carregando recursos... tente novamente em instantes."), bgcolor=CORES["warning"], show_close_icon=True)
                page.snack_bar.open = True
                page.update()
                return
            if usuario and usuario.get("id"):
                sub = db.get_subscription_status(int(usuario["id"]))
                has_remote_sub = any(k in usuario for k in ("plan_code", "premium_active", "premium_until"))
                if has_remote_sub:
                    trial_used = int(usuario.get("trial_used", sub.get("trial_used", 0)) or 0)
                    db.sync_subscription_status(
                        int(usuario["id"]),
                        str(usuario.get("plan_code") or "free"),
                        usuario.get("premium_until"),
                        trial_used,
                    )
                    usuario["trial_used"] = trial_used
                else:
                    usuario.update(sub)
            state["usuario"] = usuario
            state["tema_escuro"] = bool(usuario.get("tema_escuro", 0))
            state["view_cache"].clear()
            state["route_history"] = []
            state["last_theme"] = state["tema_escuro"]
            state["settings_sync_signature"] = _settings_signature(
                _normalize_ai_provider(usuario.get("provider") or "gemini"),
                str(usuario.get("model") or "").strip(),
                bool(usuario.get("economia_mode")),
                bool(usuario.get("telemetry_opt_in")),
                _extract_user_api_keys(usuario),
            )
            state["stats_summary_signature"] = ""
            sounds_ref = state.get("sounds")
            if sounds_ref:
                sounds_ref.play_level_up()
            apply_theme(state["tema_escuro"])
            precisa_setup_inicial = (not usuario.get("oauth_google")) and (not _resolve_user_api_key(usuario))
            show_welcome_offer = _should_show_welcome_offer(usuario)
            if show_welcome_offer:
                navigate("/welcome")
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Conta Free: veja os beneficios Premium antes de continuar."),
                    bgcolor=CORES["warning"],
                    show_close_icon=True,
                )
                page.snack_bar.open = True
                page.update()
            else:
                navigate("/settings" if precisa_setup_inicial else "/home")
                if precisa_setup_inicial:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Primeiro acesso: configure provider/modelo e API key para usar IA."),
                        bgcolor=CORES["warning"],
                        show_close_icon=True,
                    )
                    page.snack_bar.open = True
                    page.update()
            backend_ref = state.get("backend")
            if backend_ref and backend_ref.enabled() and usuario and usuario.get("id"):
                backend_uid = _backend_user_id(usuario)
                usuario["backend_user_id"] = int(backend_uid or 0)
                if int(backend_uid or 0) > 0:
                    try:
                        page.run_task(
                            _sync_subscription_after_login_async,
                            int(usuario.get("id") or 0),
                            int(backend_uid),
                        )
                    except Exception as ex:
                        log_exception(ex, "main.on_login_success.schedule_plan_sync")
                try:
                    _ensure_stats_sync_task()
                    page.run_task(_sync_cross_device_snapshot_once, True, True)
                except Exception as ex:
                    log_exception(ex, "main.on_login_success.schedule_stats_sync")
            log_event("login_success", f"user_id={usuario.get('id')} email={usuario.get('email')}")
            _emit_opt_in_event(usuario, "session_started", "app_session")
            log_state("state_after_login")
        except Exception as ex:
            log_exception(ex, "main.on_login_success")
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Erro ao finalizar login. Veja os logs do aplicativo."),
                bgcolor=CORES["erro"],
                show_close_icon=True,
            )
            page.snack_bar.open = True
            page.update()

    def on_logout(_):
        try:
            backend_ref = state.get("backend")
            if backend_ref:
                backend_ref.clear_access_token()
        except Exception:
            pass
        state["usuario"] = None
        state["view_cache"].clear()
        state["route_history"] = []
        state["settings_sync_signature"] = ""
        state["stats_summary_signature"] = ""
        state["last_summary_sync_ts"] = 0.0
        state["last_settings_sync_ts"] = 0.0
        log_event("logout", "user logout")
        log_state("state_after_logout")
        navigate("/login")

    async def toggle_dark(e):
        try:
            dark = bool(e.control.value)
            state["menu_inline_open"] = False
            state["last_theme"] = dark
            state["tema_escuro"] = dark
            if state.get("usuario"):
                db = state.get("db")
                if db:
                    db.atualizar_tema_escuro(state["usuario"]["id"], dark)
                    state["usuario"]["tema_escuro"] = 1 if dark else 0

            apply_theme(dark)

            # Android: widgets tem cores hardcoded, precisam de rebuild completo.
            # Limpa somente a rota atual do cache para preservar quiz_sessions etc.
            current_route = _normalize_route_path(page.route or "/home")
            if current_route == "/simulado/sessao":
                current_route = "/simulado"
            state.get("view_cache", {}).pop(current_route, None)
            state["pending_theme_refresh"] = False
            page.route = current_route
            route_change(None)

            log_event("theme_toggle", f"dark={dark}")
            log_state("state_after_theme_toggle")
        except Exception as ex:
            log_exception(ex, "main.toggle_dark")




    def route_change(e):
        try:
            state["menu_inline_open"] = False
            raw_route = page.route or "/login"
            if raw_route in ("/", "/login"):
                route = raw_route
            else:
                route = _normalize_route_path(raw_route)
                if route == "/simulado/sessao":
                    page.go("/simulado")
                    return
                if route != raw_route:
                    page.go(route)
                    return

            # Login/landing: sem cache
            if route in ("/", "/login"):
                db_ref = state.get("db")
                if db_ref is None:
                    _start_runtime_init()
                    init_error = state.get("init_error")
                    init_running = bool(state.get("init_task_running"))
                    if init_error and not init_running:
                        error_view = ft.View(
                            route=route,
                            controls=[
                                ft.Container(
                                    expand=True,
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.Column(
                                        [
                                            ft.Icon(ft.Icons.ERROR_OUTLINE, color=CORES["erro"], size=42),
                                            ft.Text("Falha na inicializacao", size=20, weight=ft.FontWeight.BOLD),
                                            ft.Text(str(init_error), size=13),
                                            ft.ElevatedButton(
                                                "Tentar novamente",
                                                on_click=lambda _: (_start_runtime_init(), route_change(None)),
                                            ),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        spacing=10,
                                    ),
                                )
                            ],
                            bgcolor=_color("fundo", bool(state.get("tema_escuro"))),
                        )
                        _sanitize_control_texts(error_view)
                        page.views[:] = [error_view]
                        page.update()
                        return
                    loading = ft.View(
                        route=route,
                        controls=[
                            ft.Container(
                                expand=True,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Column(
                                    [
                                        ft.ProgressRing(),
                                        ft.Text("Carregando recursos..." if init_running else "Iniciando recursos..."),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=12,
                                ),
                            )
                        ],
                        bgcolor=_color("fundo", bool(state.get("tema_escuro"))),
                    )
                    _sanitize_control_texts(loading)
                    page.views[:] = [loading]
                    page.update()
                    return
                login_view = LoginView(page, db_ref, on_login_success, backend=state.get("backend"))
                _style_form_controls(login_view, bool(state.get("tema_escuro")))
                _sanitize_control_texts(login_view)
                page.views[:] = [login_view]
                page.update()
                log_event("route", route)
                log_state("state_after_route")
                return

            # Protegido
            if not state["usuario"]:
                page.go("/login")
                return
            if route == "/welcome" and _is_premium_active(state.get("usuario") or {}):
                page.go("/home")
                return

            if route in {"/home", "/stats", "/profile", "/mais", "/settings"}:
                try:
                    page.run_task(_sync_cross_device_snapshot_once, True, True)
                except Exception as ex_sync:
                    log_exception(ex_sync, "main.route_change.schedule_cross_device_sync")

            dark = state.get("tema_escuro", False)
            # invalida cache se tema mudou
            if dark != state.get("last_theme"):
                state["view_cache"].clear()
                state["last_theme"] = dark

            cache = state["view_cache"]
            view = cache.get(route)

            if view is None:
                if route == "/home":
                    body = _ext_build_home_body(state, navigate, dark)
                elif route == "/quiz":
                    body = _ext_build_quiz_body(state, navigate, dark)
                elif route == "/revisao":
                    body = _build_revisao_body(state, navigate, dark)
                elif route == "/mais":
                    body = _ext_build_mais_body(state, navigate, dark, on_logout, toggle_dark)
                elif route == "/library":
                    body = _ext_build_library_body(state, navigate, dark)
                elif route == "/study-plan":
                    body = _ext_build_study_plan_body(state, navigate, dark)
                elif route == "/flashcards":
                    body = _ext_build_flashcards_body(state, navigate, dark)
                elif route == "/open-quiz":
                    body = _ext_build_open_quiz_body(state, navigate, dark)
                elif route == "/stats":
                    body = _ext_build_stats_body(state, navigate, dark)
                elif route == "/profile":
                    body = _ext_build_profile_body(state, navigate, dark)
                elif route == "/ranking":
                    body = _ext_build_ranking_body(state, navigate, dark)
                elif route == "/conquistas":
                    body = _ext_build_conquistas_body(state, navigate, dark)
                elif route == "/plans":
                    body = _ext_build_plans_body(state, navigate, dark)
                elif route == "/welcome":
                    body = _ext_build_onboarding_body(state, navigate, dark)
                elif route == "/settings":
                    body = _ext_build_settings_body(state, navigate, dark)
                elif route in ("/revisao/sessao", "/revisao/erros", "/revisao/marcadas"):
                    body = build_review_session_body(state, navigate, dark, modo=route.split("/")[-1])
                elif route == "/simulado":
                    body = _ext_build_quiz_body(state, navigate, dark)
                else:
                    page.go("/home")
                    return

                view = _build_shell_view(page, state, route, body, on_logout, dark, toggle_dark)
                form_heavy_routes = {
                    "/quiz",
                    "/flashcards",
                    "/open-quiz",
                    "/study-plan",
                    "/settings",
                    "/plans",
                    "/simulado",
                    "/library",
                }
                if route in form_heavy_routes:
                    _style_form_controls(view, dark)
                _sanitize_control_texts(view)
                # Rotas dinamicas nao devem ser cacheadas (estado interno muda)
                _no_cache_routes = {"/home", "/stats", "/profile",
                                    "/quiz", "/flashcards", "/open-quiz", "/settings", "/library",
                                    "/revisao", "/revisao/sessao", "/revisao/erros", "/revisao/marcadas",
                                    "/mais", "/simulado"}
                if route not in _no_cache_routes:
                    cache[route] = view

            # Evita piscadas: sÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³ troca se for outra instÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ncia
            if page.views and page.views[-1] is view:
                log_event("route_cached", route)
                return
            page.views[:] = [view]
            page.update()
            log_event("route", route)
            log_state("state_after_route")
        except Exception as ex:
            import traceback
            print(f"\n{'='*60}")
            print(f"[ERRO FATAL] Rota: {page.route}")
            traceback.print_exc()
            print(f"{'='*60}\n")
            log_exception(ex, "main.route_change")
            page.views.clear()
            page.views.append(_build_error_view(page, page.route))
            page.update()

    def view_pop(e):
        try:
            history = state.setdefault("route_history", [])
            current = _normalize_route_path(page.route or "/home")
            while history:
                prev = _normalize_route_path(history.pop())
                if prev and prev not in {"/", "/login"} and prev != current:
                    page.go(prev)
                    return
            page.go("/home" if state["usuario"] else "/login")
        except Exception as ex:
            log_exception(ex, "main.view_pop")
            page.go("/login")

    def on_resized(e):
        try:
            now = time.time()
            width = int(_screen_width(page))
            height = int(_screen_height(page))
            size = (width, height)
            size_class = (width < 980, width < 760)
            last_ts = float(state.get("last_resize_ts") or 0.0)
            last_size = state.get("last_resize_size")
            last_size_class = state.get("size_class")
            # Ignora eventos que nao mudam o layout responsivo.
            if last_size_class == size_class and (now - last_ts) < 1.0:
                return
            # Debounce agressivo para reduzir reconstrucoes da UI.
            if last_size == size and (now - last_ts) < 0.35:
                return
            if (now - last_ts) < 0.20:
                return
            state["last_resize_ts"] = now
            state["last_resize_size"] = size
            state["size_class"] = size_class
            route = page.route or "/login"
            state["view_cache"].pop(route, None)
            route_change(None)
        except Exception as ex:
            log_exception(ex, "main.on_resized")

    page.on_route_change = route_change
    state["_theme_refresh_cb"] = route_change
    page.on_view_pop = view_pop
    page.on_resized = on_resized
    page.update()
    # Splash e runtime em paralelo para reduzir percepcao de lentidao:
    # 1) mostra splash
    # 2) inicia runtime em background durante o splash
    # 3) navega para /login com runtime ja adiantado
    is_android = bool(os.getenv("ANDROID_DATA"))
    _start_runtime_init()
    splash_view, logo_box, tagline = _build_splash(page, navigate, state["tema_escuro"])
    page.views[:] = [splash_view]
    page.update()

    async def run_splash():
        # Android: splash curta e estatica para reduzir risco de black screen.
        if is_android:
            # Keep Android splash static and visible (no fade), then navigate.
            logo_box.opacity = 1
            logo_box.width = 200
            logo_box.height = 200
            tagline.opacity = 1
            if splash_view.controls and hasattr(splash_view.controls[0], "content"):
                splash_root = splash_view.controls[0].content
                splash_root.opacity = 1
            page.update()
            await asyncio.sleep(1.2)
            page.go("/login")
            page.update()
            return

        # Desktop: fade curto
        logo_box.opacity = 1
        logo_box.width = 200
        logo_box.height = 200
        tagline.opacity = 1
        page.update()
        await asyncio.sleep(0.95)
        # fade out curto
        if splash_view.controls and hasattr(splash_view.controls[0], "content"):
            splash_root = splash_view.controls[0].content
            splash_root.opacity = 0
            page.update()
        await asyncio.sleep(0.12)
        page.go("/login")
        page.update()
    try:
        page.run_task(run_splash)
    except Exception as ex:
        # Fallback para versoes de Flet com comportamento diferente em run_task.
        log_exception(ex, "main.run_splash")
        page.go("/login")
