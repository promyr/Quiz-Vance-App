# -*- coding: utf-8 -*-
"""
Configuracao centralizada de encoding UTF-8.

Importe este modulo cedo (ex: em run.py) para garantir que
stdout/stderr usam UTF-8 no Windows e Android.
"""

from __future__ import annotations

import io
import os
import sys
from typing import cast


def configure_utf8() -> None:
    """Forca encoding UTF-8 para stdout/stderr no Windows."""
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if sys.platform == "win32":
        try:
            stdout = cast(io.TextIOWrapper, sys.stdout)
            stderr = cast(io.TextIOWrapper, sys.stderr)
            stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
