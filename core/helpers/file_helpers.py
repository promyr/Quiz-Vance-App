# -*- coding: utf-8 -*-
"""Helpers para manipulação de arquivos/upload — extraídos do main_v2.py.

Funções compartilhadas pelas views library, quiz, flashcards e open_quiz.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from collections.abc import Mapping
from typing import Optional
from urllib.parse import unquote, urlparse

import flet as ft

from core.error_monitor import log_event, log_exception
from core.platform_helper import is_android
from core.ui_async_guard import AsyncActionGuard


# ---------------------------------------------------------------------------
# Normalização de caminhos
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Leitura de conteúdo de arquivos
# ---------------------------------------------------------------------------

def read_uploaded_study_text(file_path: str) -> str:
    normalized_path = normalize_uploaded_file_path(file_path)
    if not normalized_path or normalized_path.lower().startswith("content://"):
        return ""
    ext = os.path.splitext(normalized_path)[1].lower()
    if ext == ".pdf":
        try:
            from core.helpers.pdf_ocr import read_pdf_with_ocr_fallback
            return read_pdf_with_ocr_fallback(normalized_path)
        except Exception as ex:
            log_exception(ex, "file_helpers.read_uploaded_study_text.pdf")
            return ""

    if ext in {".txt", ".md", ".csv", ".json", ".log"}:
        for encoding in ("utf-8", "latin-1"):
            try:
                with open(normalized_path, "r", encoding=encoding, errors="ignore") as f:
                    return (f.read() or "").strip()[:24000]
            except Exception:
                continue
    return ""


# ---------------------------------------------------------------------------
# Seleção nativa de arquivos (tkinter fallback)
# ---------------------------------------------------------------------------

def pick_study_files_native() -> list[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as ex:
        log_exception(ex, "file_helpers.pick_study_files_native.import")
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
        log_exception(ex, "file_helpers.pick_study_files_native.dialog")
        return []
    finally:
        try:
            root.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# FilePicker do Flet
# ---------------------------------------------------------------------------

def get_or_create_file_picker(page: ft.Page) -> Optional[ft.FilePicker]:
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
        log_exception(ex, "file_helpers.get_or_create_file_picker")
        return None


# ---------------------------------------------------------------------------
# Seleção de arquivos (Flet FilePicker com fallback nativo)
# ---------------------------------------------------------------------------

async def pick_study_files(page: Optional[ft.Page]) -> list[str]:
    if not page:
        return []

    picker = get_or_create_file_picker(page)
    if picker is None:
        if is_android():
            return []
        return await asyncio.to_thread(pick_study_files_native)

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
                selected_paths = _extract_paths([
                    getattr(e, "path", None),
                    getattr(e, "file", None),
                    getattr(e, "paths", None),
                    getattr(e, "data", None),
                ])
            if not result_future.done():
                result_future.set_result(selected_paths)
        except Exception as ex_inner:
            if not result_future.done():
                result_future.set_exception(ex_inner)

    async def _call_pick_files_with_compat(**kwargs):
        pick_fn = getattr(picker, "pick_files", None)
        if inspect.iscoroutinefunction(pick_fn):
            return await pick_fn(**kwargs)
        result = pick_fn(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    try:
        if has_on_result:
            picker.on_result = _on_result
        try:
            pick_result = await _call_pick_files_with_compat(
                allow_multiple=True,
                file_type=ft.FilePickerFileType.ANY,
                allowed_extensions=["pdf", "txt", "md", "csv", "json", "log"],
            )
        except Exception:
            try:
                pick_result = await _call_pick_files_with_compat(allow_multiple=True)
            except Exception as ex:
                log_exception(ex, "file_helpers.pick_study_files.pick_files")
                if is_android():
                    return []
                return await asyncio.to_thread(pick_study_files_native)

        direct_payload = pick_result if isinstance(pick_result, (list, tuple)) else [pick_result]
        direct_paths = _extract_paths(direct_payload)
        if not direct_paths and pick_result is not None:
            direct_paths = _extract_paths([
                getattr(pick_result, "files", None),
                getattr(pick_result, "path", None),
                getattr(pick_result, "paths", None),
                getattr(pick_result, "data", None),
            ])
        if direct_paths or (pick_result is not None and not is_android()):
            return direct_paths

        if not has_on_result:
            if is_android():
                return []
            try:
                return await asyncio.to_thread(pick_study_files_native)
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
                return await asyncio.to_thread(pick_study_files_native)
            except Exception:
                return []
        return selected
    except Exception as ex:
        log_exception(ex, "file_helpers.pick_study_files")
        if is_android():
            return []
        return await asyncio.to_thread(pick_study_files_native)
    finally:
        if has_on_result:
            picker.on_result = previous_handler


# ---------------------------------------------------------------------------
# Guard de estado async
# ---------------------------------------------------------------------------

def state_async_guard(state: Optional[dict]) -> AsyncActionGuard:
    if not isinstance(state, dict):
        return AsyncActionGuard()
    guard = state.get("async_guard")
    if isinstance(guard, AsyncActionGuard):
        return guard
    guard = AsyncActionGuard()
    state["async_guard"] = guard
    return guard


# ---------------------------------------------------------------------------
# Extração de material de upload
# ---------------------------------------------------------------------------

def extract_uploaded_material(file_paths: list[str]) -> tuple[list[str], list[str], list[str]]:
    upload_texts = []
    upload_names = []
    failed_names = []
    for file_path in file_paths:
        safe_path = normalize_uploaded_file_path(file_path)
        basename = os.path.basename(safe_path or str(file_path or "")) or "arquivo"
        ext = os.path.splitext(safe_path)[1].lower()
        extracted = read_uploaded_study_text(file_path)
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


# ---------------------------------------------------------------------------
# Formatação de label de upload
# ---------------------------------------------------------------------------

def format_upload_info_label(names: list[str], max_names: int = 3, max_preview_chars: int = 80) -> str:
    if not names:
        return "Nenhum material enviado."
    preview = ", ".join(str(n or "") for n in names[:max_names]).strip()
    if len(preview) > max_preview_chars:
        preview = f"{preview[: max_preview_chars - 1]}..."
    if len(names) > max_names:
        preview += f" +{len(names) - max_names}"
    return f"{len(names)} arquivo(s): {preview}"
