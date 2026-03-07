# -*- coding: utf-8 -*-
"""
Monitoramento centralizado de erros da aplicacao.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
import threading
import traceback
import uuid
from core.app_paths import get_log_file_path, get_logs_dir


LOG_DIR = str(get_logs_dir())
LOG_FILE = str(get_log_file_path())
SESSION_ID = str(uuid.uuid4())
_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def _rotate_if_needed() -> None:
    """Rotaciona o log quando ultrapassa _MAX_LOG_BYTES (mantém 1 backup)."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > _MAX_LOG_BYTES:
            backup = LOG_FILE + ".1"
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(LOG_FILE, backup)
    except Exception:
        pass


def _append_log(level: str, title: str, details: str) -> None:
    _ensure_log_dir()
    _rotate_if_needed()
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = (
        f"\n[{timestamp}] [{level}] [session={SESSION_ID}] {title}\n"
        f"{details.rstrip()}\n"
        f"{'-' * 80}\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(block)


def log_message(title: str, details: str = "") -> None:
    _append_log("INFO", title, details or "-")


def log_exception(exc: BaseException, where: str = "") -> None:
    location = where or "unhandled"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _append_log("ERROR", f"{location}: {exc}", tb)

def log_event(name: str, data: str = "") -> None:
    _append_log("EVENT", name, data or "-")


def setup_global_error_hooks() -> None:
    def _sys_hook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _append_log("FATAL", f"sys.excepthook: {exc_value}", tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_hook(args: threading.ExceptHookArgs):
        tb = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
        _append_log("ERROR", f"threading.excepthook: {args.exc_value}", tb)

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Sem event loop ativo neste momento.
        loop = None

    if loop is not None:
        def _async_hook(loop_obj, context):
            exc = context.get("exception")
            if exc:
                log_exception(exc, "asyncio")
            else:
                _append_log("ERROR", "asyncio", str(context))

        loop.set_exception_handler(_async_hook)

