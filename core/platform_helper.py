"""
core/platform_helper.py
Detecta a plataforma em que o app está rodando.
Uso:
    from core.platform_helper import is_android, is_windows, get_platform
"""
import os
import sys
import platform as _platform


def is_android() -> bool:
    """Retorna True se rodando no Android (empacotado via Flet/Buildozer)."""
    return bool(os.getenv("ANDROID_DATA")) or os.path.exists("/data/data")


def is_windows() -> bool:
    """Retorna True se rodando no Windows."""
    return _platform.system() == "Windows"


def is_macos() -> bool:
    """Retorna True se rodando no macOS."""
    return _platform.system() == "Darwin"


def is_linux() -> bool:
    """Retorna True se rodando no Linux."""
    return _platform.system() == "Linux"


def is_mobile() -> bool:
    """Retorna True para Android (plataforma mobile)."""
    return is_android()


def is_desktop() -> bool:
    """Retorna True para Windows, macOS ou Linux."""
    return not is_mobile()


def get_platform() -> str:
    """Retorna string descritiva da plataforma: 'android'|'windows'|'macos'|'linux'."""
    if is_android():
        return "android"
    if is_windows():
        return "windows"
    if is_macos():
        return "macos"
    return "linux"
