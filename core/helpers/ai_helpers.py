# -*- coding: utf-8 -*-
"""Helpers de IA extraÃ­dos do main_v2.py â€” criaÃ§Ã£o de serviÃ§o, telemetria, processamento."""

from __future__ import annotations

import hashlib
import json
import datetime
from typing import Any, Callable, Optional

import flet as ft

from config import AI_PROVIDERS
from core.ai_service_v2 import AIService, create_ai_provider
from core.error_monitor import log_exception, log_event


_AI_KEY_PROVIDERS = ("gemini", "openai", "groq")


def normalize_ai_provider(value: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in _AI_KEY_PROVIDERS else "gemini"


def provider_api_field(provider: str) -> str:
    return f"api_key_{normalize_ai_provider(provider)}"


def extract_user_api_keys(usuario: Optional[dict]) -> dict[str, str]:
    user = usuario or {}
    keys: dict[str, str] = {}
    for p in _AI_KEY_PROVIDERS:
        keys[p] = str(user.get(provider_api_field(p)) or "").strip()
    legacy = str(user.get("api_key") or "").strip()
    if legacy and not any(bool(v) for v in keys.values()):
        provider = normalize_ai_provider(user.get("provider") or "gemini")
        keys[provider] = legacy
    return keys


def resolve_available_provider_keys(usuario: Optional[dict], db: Optional[Any] = None) -> dict[str, str]:
    user = usuario or {}
    keys = extract_user_api_keys(user)
    user_id = 0
    try:
        user_id = int(user.get("id") or 0)
    except Exception:
        user_id = 0

    if db is not None and user_id > 0:
        getter = getattr(db, "obter_api_keys_ia", None)
        if callable(getter):
            try:
                db_keys = getter(int(user_id)) or {}
                for p in _AI_KEY_PROVIDERS:
                    txt = str(db_keys.get(p) or "").strip()
                    if txt:
                        keys[p] = txt
            except Exception as ex:
                log_exception(ex, "ai_helpers.resolve_available_provider_keys")
    return keys


def resolve_provider_switch_options(
    usuario: Optional[dict],
    db: Optional[Any] = None,
    current_provider: Optional[str] = None,
) -> list[tuple[str, str]]:
    user = usuario or {}
    current = normalize_ai_provider(current_provider or user.get("provider") or "gemini")
    keys = resolve_available_provider_keys(user, db=db)
    options: list[tuple[str, str]] = []
    for provider in _AI_KEY_PROVIDERS:
        if provider == current:
            continue
        if not str(keys.get(provider) or "").strip():
            continue
        provider_name = str(AI_PROVIDERS.get(provider, {}).get("name") or provider.capitalize())
        options.append((provider, provider_name))
    return options


def resolve_user_api_key(usuario: Optional[dict], provider: Optional[str] = None) -> str:
    user = usuario or {}
    provider_key = normalize_ai_provider(provider or user.get("provider") or "gemini")
    keys = extract_user_api_keys(user)
    active = str(keys.get(provider_key) or "").strip()
    if active:
        return active
    if not any(bool(v) for v in keys.values()):
        return str(user.get("api_key") or "").strip()
    return ""


def create_user_ai_service(usuario: dict, force_economic: bool = False) -> Optional[AIService]:
    if not usuario:
        return None
    provider_type = normalize_ai_provider(usuario.get("provider") or "gemini")
    api_key = resolve_user_api_key(usuario, provider_type)
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
        log_exception(ex, "ai_helpers.create_user_ai_service")
        return None


def emit_opt_in_event(
    usuario: Optional[dict],
    event_name: str,
    feature_name: str,
    latency_ms: int = 0,
    error_code: str = "",
) -> None:
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


def is_ai_quota_exceeded(service: Optional[AIService]) -> bool:
    if not service:
        return False
    provider = getattr(service, "provider", None)
    kind = str(getattr(provider, "last_error_kind", "") or "").lower()
    if kind in {"quota_hard", "quota_soft"}:
        return True
    msg = str(getattr(provider, "last_error_message", "") or "").lower()
    return ("quota exceeded" in msg) or ("429" in msg) or ("rate limit" in msg)


def ai_issue_kind(service: Optional[AIService]) -> str:
    """
    Classifica o ultimo erro do provider para orientar UX:
    - quota
    - auth
    - dependency
    - generic
    - none
    """
    if not service:
        return "none"
    provider = getattr(service, "provider", None)
    kind = str(getattr(provider, "last_error_kind", "") or "").strip().lower()
    if kind in {"quota_hard", "quota_soft"}:
        return "quota"
    if kind == "auth":
        return "auth"
    if kind == "dependency":
        return "dependency"
    msg = str(getattr(provider, "last_error_message", "") or "").lower()
    if ("quota exceeded" in msg) or ("429" in msg) or ("rate limit" in msg):
        return "quota"
    if ("invalid api key" in msg) or ("unauthorized" in msg) or ("401" in msg):
        return "auth"
    if ("no module named" in msg) or ("modulenotfounderror" in msg):
        return "dependency"
    return "generic"



def is_ai_processing(state: Optional[dict]) -> bool:
    try:
        return int((state or {}).get("ai_busy_count") or 0) > 0
    except Exception:
        return False


def sync_ai_indicator_controls(state: Optional[dict]) -> None:
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


def begin_ai_processing(state: Optional[dict], page: Optional[ft.Page], message: str = "") -> None:
    if not isinstance(state, dict):
        return
    count = max(0, int(state.get("ai_busy_count") or 0)) + 1
    state["ai_busy_count"] = count
    if str(message or "").strip():
        state["ai_busy_message"] = str(message).strip()
    elif not str(state.get("ai_busy_message") or "").strip():
        state["ai_busy_message"] = "Processando com IA..."
    sync_ai_indicator_controls(state)
    if page:
        try:
            page.update()
        except Exception:
            pass


def end_ai_processing(state: Optional[dict], page: Optional[ft.Page]) -> None:
    if not isinstance(state, dict):
        return
    count = max(0, int(state.get("ai_busy_count") or 0) - 1)
    state["ai_busy_count"] = count
    if count == 0:
        state["ai_busy_message"] = ""
    sync_ai_indicator_controls(state)
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


def schedule_ai_task(
    page: Optional[ft.Page],
    state: Optional[dict],
    coro_fn: Callable[..., Any],
    *args,
    message: str = "Processando com IA...",
    status_control: Optional[ft.Text] = None,
) -> bool:
    from core.helpers.ui_helpers import set_feedback_text, ds_toast_safe

    if not page:
        return False
    if is_ai_processing(state):
        if status_control is not None:
            set_feedback_text(status_control, "Aguarde: a IA ainda esta processando a solicitacao anterior.", "info")
        else:
            ds_toast_safe(page, "IA em processamento. Aguarde concluir.", tipo="info")
        try:
            page.update()
        except Exception:
            pass
        return False

    begin_ai_processing(state, page, message=message)
    if status_control is not None and str(message or "").strip():
        set_feedback_text(status_control, str(message).strip(), "info")
        try:
            page.update()
        except Exception:
            pass

    async def _runner():
        try:
            await coro_fn(*args)
        finally:
            end_ai_processing(state, page)

    try:
        page.run_task(_runner)
        return True
    except Exception:
        end_ai_processing(state, page)
        return False


def generation_profile(usuario: dict, feature_key: str) -> dict:
    from core.helpers.ui_helpers import is_premium_active

    if is_premium_active(usuario):
        return {"force_economic": False, "delay_s": 0.0, "label": "premium"}
    if feature_key in {"quiz", "flashcards"}:
        return {"force_economic": True, "delay_s": 0.0, "label": "free_fast"}
    return {"force_economic": False, "delay_s": 0.0, "label": "free"}


def build_quiz_stats_event_payload(correta: bool, delta: dict) -> dict:
    import datetime, hashlib, random
    now_local = datetime.datetime.now().astimezone()  # timezone local do dispositivo
    now_iso = now_local.replace(microsecond=0).isoformat()  # inclui offset ex: 2025-03-02T23:00:00-03:00
    raw = f"{now_iso}|{int(delta.get('questoes_delta', 0) or 0)}|{int(delta.get('acertos_delta', 0) or 0)}|{int(delta.get('xp_ganho', 0) or 0)}|{1 if correta else 0}|{random.random()}"
    event_id = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:40]
    return {
        "event_id": event_id,
        "questoes_delta": int(delta.get("questoes_delta", 0) or 0),
        "acertos_delta": int(delta.get("acertos_delta", 0) or 0),
        "xp_delta": int(delta.get("xp_ganho", 0) or 0),
        "correta": bool(correta),
        "occurred_at": now_iso,
    }
