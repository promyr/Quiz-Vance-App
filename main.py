# -*- coding: utf-8 -*-
"""
Entrypoint padrao para builds do Flet.
"""

import flet as ft

from main_v2 import main


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
