# -*- coding: utf-8 -*-
"""
ui/design_system.py
Design System do QuizVance — Tokens + Componentes Premium

Uso:
    from ui.design_system import DS, ds_card, ds_btn_primary, ds_chip, ...

Tokens disponíveis via DS.*:
    DS.P_500       → cor primária principal
    DS.FS_H1       → tamanho H1
    DS.SP_16       → espaçamento 16dp
    DS.R_MD        → raio médio
    DS.shadow_md() → sombra BoxShadow

Componentes:
    ds_card, ds_chip, ds_btn_primary, ds_btn_secondary, ds_btn_ghost,
    ds_skeleton, ds_skeleton_card, ds_empty_state, ds_toast, ds_bottom_sheet,
    ds_stat_card, ds_section_title, ds_badge, ds_divider
"""

import re
from typing import Optional, Callable, List, Sequence
import flet as ft


# ──────────────────────────────────────────────────────────────────────────────
# TOKENS
# ──────────────────────────────────────────────────────────────────────────────

class DS:
    """Namespace de todos os tokens do design system."""

    # Paleta — Primária (Indigo)
    P_900 = "#312E81"
    P_800 = "#3730A3"
    P_700 = "#4338CA"
    P_600 = "#4F46E5"
    P_500 = "#6366F1"  # ← principal
    P_400 = "#818CF8"
    P_300 = "#A5B4FC"
    P_100 = "#E0E7FF"

    # Paleta — Acento (Emerald)
    A_700 = "#059669"
    A_500 = "#10B981"  # ← principal
    A_300 = "#34D399"
    A_100 = "#D1FAE5"

    # Nuances (Gray)
    G_900 = "#111827"
    G_700 = "#374151"
    G_500 = "#6B7280"
    G_300 = "#D1D5DB"
    G_200 = "#E5E7EB"
    G_100 = "#F3F4F6"
    G_50  = "#F9FAFB"
    WHITE = "#FFFFFF"

    # Status
    ERRO    = "#EF4444"
    SUCESSO = "#10B981"
    WARNING = "#F59E0B"
    INFO    = "#3B82F6"

    # Fundos
    BG_LIGHT = "#F9FAFB"
    BG_DARK  = "#161616"

    # Superfícies
    CARD_LIGHT = "#FFFFFF"
    CARD_DARK  = "#232323"
    SURF_DARK  = "#2C2C2C"

    # Texto
    TEXT_LIGHT     = "#111827"
    TEXT_DARK      = "#F3F4F6"
    TEXT_SEC_LIGHT = "#6B7280"
    TEXT_SEC_DARK  = "#B3B3B3"

    # ── Tipografia ────────────────────────────────────────────────────────────
    FS_H1     = 28
    FS_H2     = 22
    FS_H3     = 18
    FS_BODY   = 15
    FS_BODY_S = 14
    FS_LABEL  = 13
    FS_CAPTION= 12

    FW_BOLD   = ft.FontWeight.W_700
    FW_SEMI   = ft.FontWeight.W_600
    FW_MED    = ft.FontWeight.W_500
    FW_REG    = ft.FontWeight.W_400

    TYPO_H1 = {"size": FS_H1, "weight": FW_BOLD}
    TYPO_H2 = {"size": FS_H2, "weight": FW_SEMI}
    TYPO_BODY = {"size": FS_BODY, "weight": FW_REG}
    TYPO_CAPTION = {"size": FS_CAPTION, "weight": FW_REG}

    # ── Espaçamento (8-point grid) ────────────────────────────────────────────
    SP_4  = 4
    SP_8  = 8
    SP_10 = 10
    SP_12 = 12
    SP_14 = 14
    SP_16 = 16
    SP_24 = 24
    SP_32 = 32
    SP_48 = 48
    SPACING_SCALE = (SP_8, SP_12, SP_16, SP_24)

    # ── Raios ─────────────────────────────────────────────────────────────────
    R_SM   = 8
    R_MD   = 12
    R_LG   = 16
    R_XL   = 20
    R_XXL  = 24
    R_PILL = 100

    # ── Alturas mínimas (tap area) ────────────────────────────────────────────
    TAP_MIN  = 48
    TAP_ITEM = 56

    # ── Animações ─────────────────────────────────────────────────────────────
    ANIM_FAST   = 120
    ANIM_NORMAL = 200
    ANIM_SLOW   = 350

    @staticmethod
    def shadow_sm(dark: bool = False) -> List[ft.BoxShadow]:
        c = "0x14000000" if not dark else "0x28000000"
        return [ft.BoxShadow(blur_radius=4, spread_radius=0, offset=ft.Offset(0, 1), color=c)]

    @staticmethod
    def shadow_md(dark: bool = False) -> List[ft.BoxShadow]:
        c = "0x1A000000" if not dark else "0x33000000"
        return [ft.BoxShadow(blur_radius=12, spread_radius=0, offset=ft.Offset(0, 4), color=c)]

    @staticmethod
    def shadow_lg(dark: bool = False) -> List[ft.BoxShadow]:
        c = "0x22000000" if not dark else "0x40000000"
        return [ft.BoxShadow(blur_radius=24, spread_radius=0, offset=ft.Offset(0, 8), color=c)]

    @staticmethod
    def text_color(dark: bool) -> str:
        return DS.TEXT_DARK if dark else DS.TEXT_LIGHT

    @staticmethod
    def text_sec_color(dark: bool) -> str:
        return DS.TEXT_SEC_DARK if dark else DS.TEXT_SEC_LIGHT

    @staticmethod
    def bg_color(dark: bool) -> str:
        return DS.BG_DARK if dark else DS.BG_LIGHT

    @staticmethod
    def card_color(dark: bool) -> str:
        return DS.CARD_DARK if dark else DS.CARD_LIGHT

    @staticmethod
    def border_color(dark: bool, opacity: float = 0.10) -> str:
        base = DS.G_900 if not dark else DS.WHITE
        alpha = int(opacity * 255)
        r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
        return f"#{alpha:02X}{r:02X}{g:02X}{b:02X}"

    @staticmethod
    def with_opacity(color: str, opacity: float) -> str:
        """Aplica opacidade (0.0 a 1.0) a uma cor hex (#RRGGBB)."""
        try:
            c = str(color).strip().upper()
            if not c.startswith("#"):
                return c
            # Remove o alpha antigo se houver (formato #AARRGGBB)
            if len(c) == 9:
                c = "#" + c[3:]
            alpha = int(opacity * 255)
            return f"#{alpha:02X}{c[1:]}"
        except Exception:
            return color


# ──────────────────────────────────────────────────────────────────────────────
# COMPONENTES
# ──────────────────────────────────────────────────────────────────────────────

def ds_card(
    content: ft.Control,
    dark: bool = False,
    padding: int = DS.SP_16,
    border_radius: int = DS.R_XL,
    shadow: bool = True,
    on_click: Optional[Callable] = None,
    border_color: Optional[str] = None,
    expand: bool = False,
    width: Optional[int] = None,
    height: Optional[int] = None,
    bgcolor: Optional[str] = None,
) -> ft.Container:
    """Card padrão do design system."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=bgcolor or DS.card_color(dark),
        shadow=DS.shadow_md(dark) if shadow else None,
        border=ft.border.all(1, border_color or DS.border_color(dark, 0.08)),
        on_click=on_click,
        animate=ft.Animation(DS.ANIM_NORMAL, ft.AnimationCurve.EASE_OUT) if on_click else None,
        expand=expand,
        width=width,
        height=height,
        ink=bool(on_click),
    )


def ds_chip(
    text: str,
    selected: bool = False,
    on_click: Optional[Callable] = None,
    dark: bool = False,
    icon: Optional[str] = None,
    count: Optional[int] = None,
    small: bool = False,
) -> ft.Container:
    """Chip selecionável (single ou multi)."""
    pad_h = DS.SP_12 if not small else DS.SP_8
    pad_v = DS.SP_8 if not small else DS.SP_4
    fs = DS.FS_LABEL if not small else DS.FS_CAPTION

    if selected:
        bg   = DS.P_500
        text_c = DS.WHITE
        border_c = DS.P_500
    else:
        bg   = DS.SURF_DARK if dark else DS.G_100
        text_c = DS.text_color(dark)
        border_c = DS.border_color(dark, 0.15)

    label_content: List[ft.Control] = []
    if icon:
        label_content.append(ft.Icon(icon, size=fs + 2, color=text_c))
    label_content.append(ft.Text(text, size=fs, color=text_c, weight=DS.FW_MED))
    if count is not None:
        label_content.append(
            ft.Container(
                content=ft.Text(str(count), size=DS.FS_CAPTION - 1, color=text_c, weight=DS.FW_BOLD),
                bgcolor=f"#{50:02X}{255:02X}{255:02X}{255:02X}" if selected else DS.border_color(dark, 0.15),
                border_radius=DS.R_PILL,
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
            )
        )

    return ft.Container(
        content=ft.Row(label_content, spacing=DS.SP_4, tight=True),
        bgcolor=bg,
        border_radius=DS.R_PILL,
        border=ft.border.all(1, border_c),
        padding=ft.padding.symmetric(horizontal=pad_h, vertical=pad_v),
        on_click=on_click,
        animate=ft.Animation(DS.ANIM_FAST, ft.AnimationCurve.EASE_OUT),
        ink=True,
    )


def ds_btn_primary(
    text: str,
    on_click: Optional[Callable] = None,
    icon: Optional[str] = None,
    width: Optional[int] = None,
    height: int = DS.TAP_ITEM,
    disabled: bool = False,
    loading: bool = False,
    expand: bool = False,
    dark: bool = False,
) -> ft.Control:
    """Botão primário com gradiente e sombra."""
    return ft.ElevatedButton(
        content=ft.Text(text) if not loading else ft.Text("Carregando..."),
        icon=icon if not loading else None,
        disabled=disabled or loading,
        on_click=on_click,
        width=width,
        height=height,
        expand=expand,
        style=ft.ButtonStyle(
            bgcolor=DS.P_500,
            color=DS.WHITE,
            shape=ft.RoundedRectangleBorder(radius=DS.R_MD),
            padding=ft.padding.symmetric(horizontal=DS.SP_16, vertical=0),
            elevation=2 if not disabled else 0,
        )
    )


def ds_btn_secondary(
    text: str,
    on_click: Optional[Callable] = None,
    icon: Optional[str] = None,
    width: Optional[int] = None,
    height: int = DS.TAP_ITEM,
    dark: bool = False,
    expand: bool = False,
    disabled: bool = False,
) -> ft.Control:
    """Botão secundário com borda e fundo sutil."""
    return ft.OutlinedButton(
        content=ft.Text(text),
        icon=icon,
        on_click=on_click,
        width=width,
        height=height,
        expand=expand,
        disabled=disabled,
        style=ft.ButtonStyle(
            color=DS.P_500 if not dark else DS.P_300,
            side=ft.BorderSide(1.5, DS.P_500 if not dark else DS.P_300),
            shape=ft.RoundedRectangleBorder(radius=DS.R_MD),
            padding=ft.padding.symmetric(horizontal=DS.SP_16, vertical=0),
        )
    )


def ds_btn_ghost(
    text: str,
    on_click: Optional[Callable] = None,
    icon: Optional[str] = None,
    color: Optional[str] = None,
    dark: bool = False,
    height: int = DS.TAP_MIN,
    expand: bool = False,
) -> ft.Control:
    """Botão terciário/ghost — sem fundo, só texto clicável."""
    c = color or (DS.P_500 if not dark else DS.P_300)
    return ft.TextButton(
        content=ft.Text(text),
        icon=icon,
        on_click=on_click,
        height=height,
        expand=expand,
        style=ft.ButtonStyle(
            color=c,
            shape=ft.RoundedRectangleBorder(radius=DS.R_MD),
            padding=ft.padding.symmetric(horizontal=DS.SP_12, vertical=0),
        )
    )


def ds_skeleton(width: int, height: int, dark: bool = False, radius: int = DS.R_MD) -> ft.Container:
    """Retângulo de skeleton loading (shimmer estático)."""
    color = DS.SURF_DARK if dark else DS.G_200
    return ft.Container(
        width=width,
        height=height,
        border_radius=radius,
        bgcolor=color,
        animate=ft.Animation(800, ft.AnimationCurve.EASE_IN_OUT),
    )


def ds_skeleton_card(dark: bool = False) -> ft.Container:
    """Card completo de skeleton para listas de questões/cards."""
    return ds_card(
        dark=dark,
        content=ft.Column(
            [
                ft.Row([
                    ds_skeleton(120, 14, dark, DS.R_PILL),
                    ds_skeleton(60, 14, dark, DS.R_PILL),
                ], spacing=DS.SP_8),
                ds_skeleton(999, 16, dark),
                ds_skeleton(999, 14, dark),
                ds_skeleton(240, 14, dark),
                ft.Row([
                    ds_skeleton(80, 32, dark, DS.R_MD),
                    ds_skeleton(80, 32, dark, DS.R_MD),
                ], spacing=DS.SP_8),
            ],
            spacing=DS.SP_12,
        ),
    )


def ds_empty_state(
    icon: str,
    title: str,
    subtitle: str = "",
    cta_text: Optional[str] = None,
    cta_action: Optional[Callable] = None,
    dark: bool = False,
) -> ft.Container:
    """Empty state com ícone, título, subtítulo e CTA opcional."""
    controls: List[ft.Control] = [
        ft.Container(
            content=ft.Icon(icon, size=64, color=DS.border_color(dark, 0.30)),
            padding=ft.padding.only(bottom=DS.SP_8),
        ),
        ft.Text(title, size=DS.FS_H3, weight=DS.FW_SEMI, color=DS.text_color(dark),
                text_align=ft.TextAlign.CENTER),
    ]
    if subtitle:
        controls.append(
            ft.Text(subtitle, size=DS.FS_BODY_S, color=DS.text_sec_color(dark),
                    text_align=ft.TextAlign.CENTER, max_lines=3)
        )
    if cta_text and cta_action:
        controls.append(ft.Container(height=DS.SP_8))
        controls.append(ds_btn_primary(cta_text, on_click=cta_action, dark=dark))

    return ft.Container(
        content=ft.Column(
            controls,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=DS.SP_8,
        ),
        alignment=ft.Alignment(0, 0),
        padding=ft.padding.symmetric(horizontal=DS.SP_32, vertical=DS.SP_48),
    )


def ds_toast(
    page: ft.Page,
    message: str,
    tipo: str = "info",  # "info" | "sucesso" | "erro" | "warning"
    duration_ms: int = 3000,
) -> None:
    """Exibe um toast/snackbar padronizado."""
    icons_map   = {"info": ft.Icons.INFO_OUTLINE, "sucesso": ft.Icons.CHECK_CIRCLE_OUTLINE,
                   "erro": ft.Icons.ERROR_OUTLINE, "warning": ft.Icons.WARNING_AMBER_OUTLINED}
    colors_map  = {"info": DS.INFO, "sucesso": DS.SUCESSO, "erro": DS.ERRO, "warning": DS.WARNING}

    color = colors_map.get(tipo, DS.INFO)
    icon  = icons_map.get(tipo, ft.Icons.INFO_OUTLINE)

    snack = ft.SnackBar(
        content=ft.Row(
            [ft.Icon(icon, color=DS.WHITE, size=18),
             ft.Text(message, color=DS.WHITE, size=DS.FS_BODY_S, expand=True)],
            spacing=DS.SP_8,
        ),
        bgcolor=color,
        duration=duration_ms,
        show_close_icon=True,
        close_icon_color=DS.WHITE,
    )
    page.snack_bar = snack
    page.snack_bar.open = True
    try:
        page.update()
    except Exception:
        pass


def ds_bottom_sheet(
    page: ft.Page,
    content: ft.Control,
    title: str = "",
    dark: bool = False,
    on_dismiss: Optional[Callable] = None,
    show_drag_handle: bool = True,
) -> ft.BottomSheet:
    """Bottom sheet padronizado com handle e título."""
    sheet_controls: List[ft.Control] = []

    if show_drag_handle:
        sheet_controls.append(
            ft.Container(
                content=ft.Container(
                    width=40, height=4,
                    bgcolor=DS.border_color(dark, 0.25),
                    border_radius=DS.R_PILL,
                ),
                alignment=ft.Alignment(0, 0),
                padding=ft.padding.only(top=DS.SP_12),
            )
        )

    if title:
        sheet_controls.append(
            ft.Container(
                content=ft.Text(title, size=DS.FS_H3, weight=DS.FW_SEMI, color=DS.text_color(dark)),
                padding=ft.padding.symmetric(horizontal=DS.SP_24, vertical=DS.SP_16),
            )
        )
        sheet_controls.append(ft.Divider(height=1, color=DS.border_color(dark, 0.10)))

    sheet_controls.append(
        ft.Container(content=content, padding=ft.padding.only(
            left=DS.SP_16, right=DS.SP_16, bottom=DS.SP_32
        ))
    )

    sheet = ft.BottomSheet(
        content=ft.Container(
            content=ft.Column(sheet_controls, spacing=0, scroll=ft.ScrollMode.AUTO),
            bgcolor=DS.card_color(dark),
            border_radius=ft.border_radius.only(top_left=DS.R_XXL, top_right=DS.R_XXL),
        ),
        on_dismiss=on_dismiss,
    )
    page.overlay.append(sheet)
    sheet.open = True
    try:
        page.update()
    except Exception:
        pass
    return sheet


def ds_stat_card(
    icon: str,
    label: str,
    value: str,
    subtitle: str = "",
    dark: bool = False,
    icon_color: Optional[str] = None,
    on_click: Optional[Callable] = None,
    trend_up: Optional[bool] = None,
    col: Optional[dict] = None,
    height: Optional[int] = None,
) -> ft.Container:
    """Card de estatística/métrica para o dashboard."""
    ic_color = icon_color or DS.P_500

    trend_widget = ft.Container()
    if trend_up is not None:
        trend_icon = ft.Icons.TRENDING_UP if trend_up else ft.Icons.TRENDING_DOWN
        trend_color = DS.SUCESSO if trend_up else DS.ERRO
        trend_widget = ft.Row([
            ft.Icon(trend_icon, size=14, color=trend_color),
        ], tight=True)

    card = ds_card(
        dark=dark,
        on_click=on_click,
        height=height,
        content=ft.Column(
            [
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=20, color=ic_color),
                        bgcolor=DS.with_opacity(ic_color, 0.15),
                        border_radius=DS.R_MD,
                        padding=DS.SP_8,
                    ),
                    ft.Container(expand=True),
                    trend_widget,
                ]),
                ft.Text(value, size=DS.FS_H2, weight=DS.FW_BOLD, color=DS.text_color(dark)),
                ft.Text(label, size=DS.FS_LABEL, color=DS.text_sec_color(dark)),
                ft.Container(
                    height=18,
                    alignment=ft.Alignment(-1, 0),
                    content=ft.Text(subtitle, size=DS.FS_CAPTION, color=DS.text_sec_color(dark), max_lines=1)
                    if subtitle
                    else None,
                ),
            ],
            spacing=DS.SP_4,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN if height else ft.MainAxisAlignment.START,
        ),
    )
    if col:
        card.col = col
    return card


def ds_section_title(text: str, dark: bool = False, action_text: str = "", action_fn: Optional[Callable] = None) -> ft.Row:
    """Título de seção com ação opcional à direita."""
    controls = [ft.Text(text, size=DS.FS_H3, weight=DS.FW_SEMI, color=DS.text_color(dark))]
    if action_text and action_fn:
        controls += [ft.Container(expand=True), ds_btn_ghost(action_text, on_click=action_fn, dark=dark)]
    return ft.Row(controls, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def ds_badge(text: str, color: str = DS.P_500, size: int = DS.FS_CAPTION) -> ft.Container:
    """Badge colorido para status, nível, etc."""
    return ft.Container(
        content=ft.Text(text, size=size, color=DS.WHITE, weight=DS.FW_MED),
        bgcolor=color,
        border_radius=DS.R_PILL,
        padding=ft.padding.symmetric(horizontal=DS.SP_8, vertical=2),
    )


def ds_divider(dark: bool = False) -> ft.Container:
    """Divisor visual horizontal."""
    return ft.Container(
        height=1,
        bgcolor=DS.border_color(dark, 0.10),
        margin=ft.margin.symmetric(vertical=DS.SP_4),
    )


def ds_progress_bar(
    value: float,
    dark: bool = False,
    height: int = 8,
    color: str = DS.P_500,
    bgcolor: Optional[str] = None,
    border_radius: int = DS.R_PILL,
) -> ft.Container:
    """Barra de progresso estilizada."""
    bg = bgcolor or (DS.SURF_DARK if dark else DS.G_200)
    clamped = max(0.0, min(1.0, value))
    return ft.Container(
        height=height,
        border_radius=border_radius,
        bgcolor=bg,
        content=ft.Container(
            width=None,
            height=height,
            border_radius=border_radius,
            bgcolor=color,
            animate=ft.Animation(DS.ANIM_NORMAL, ft.AnimationCurve.EASE_OUT),
        ) if clamped == 0 else None,
    ) if clamped == 0 else ft.ProgressBar(
        value=clamped,
        color=color,
        bgcolor=bg,
        border_radius=border_radius,
        height=height,
    )


def ds_icon_btn(
    icon: str,
    on_click: Optional[Callable] = None,
    tooltip: str = "",
    color: Optional[str] = None,
    dark: bool = False,
    size: int = 20,
) -> ft.IconButton:
    """Botão de ícone padronizado."""
    return ft.IconButton(
        icon=icon,
        icon_color=color or DS.text_sec_color(dark),
        icon_size=size,
        tooltip=tooltip,
        on_click=on_click,
    )


class AppText(ft.Text):
    """Wrapper padrao de texto para evitar overflow e quebra ruim em labels."""

    _VARIANT_SIZE = {
        "h1": DS.FS_H1,
        "h2": DS.FS_H2,
        "h3": DS.FS_H3,
        "body": DS.FS_BODY,
        "body_s": DS.FS_BODY_S,
        "label": DS.FS_LABEL,
        "caption": DS.FS_CAPTION,
    }

    _VARIANT_WEIGHT = {
        "h1": DS.FW_BOLD,
        "h2": DS.FW_SEMI,
        "h3": DS.FW_SEMI,
        "body": DS.FW_REG,
        "body_s": DS.FW_REG,
        "label": DS.FW_MED,
        "caption": DS.FW_REG,
    }

    def __init__(
        self,
        value: str = "",
        *,
        variant: str = "body",
        dark: bool = False,
        short_label: bool = False,
        force_wrap: bool = False,
        **kwargs,
    ):
        text_value = str(value or "")
        resolved_variant = str(variant or "body").lower()
        if resolved_variant not in self._VARIANT_SIZE:
            resolved_variant = "body"

        kwargs.setdefault("size", self._VARIANT_SIZE[resolved_variant])
        kwargs.setdefault("weight", self._VARIANT_WEIGHT[resolved_variant])
        kwargs.setdefault("color", DS.text_color(dark))

        is_short = short_label or ("\n" not in text_value and len(text_value) <= 28)
        if force_wrap:
            kwargs.setdefault("no_wrap", False)
        elif is_short:
            kwargs.setdefault("max_lines", 1)
            kwargs.setdefault("overflow", ft.TextOverflow.ELLIPSIS)
            kwargs.setdefault("no_wrap", False)
        else:
            kwargs.setdefault("no_wrap", False)

        super().__init__(value=text_value, **kwargs)


def ds_page_scaffold(
    *,
    page: Optional[ft.Page],
    content: ft.Control,
    dark: bool = False,
    safe_area: bool = True,
    max_width: int = 1180,
    pad_h_mobile: int = DS.SP_12,
    pad_h_tablet: int = DS.SP_16,
    pad_h_desktop: int = DS.SP_24,
    pad_v: int = DS.SP_12,
) -> ft.Control:
    """Scaffold universal com safe area, padding e largura limitada."""
    width = 1280.0
    if page is not None:
        for attr in ("width", "window_width"):
            raw = getattr(page, attr, None)
            if raw:
                try:
                    width = max(320.0, float(raw))
                    break
                except Exception:
                    pass

    if width < 760:
        pad_h = pad_h_mobile
    elif width < 1100:
        pad_h = pad_h_tablet
    else:
        pad_h = pad_h_desktop

    host = ft.Container(
        expand=True,
        bgcolor=DS.bg_color(dark),
        alignment=ft.Alignment(0, -1),
        padding=ft.padding.symmetric(horizontal=pad_h, vertical=pad_v),
        content=ft.Container(
            width=min(max_width, int(width) - (pad_h * 2)),
            alignment=ft.Alignment(0, -1),
            content=content,
        ),
    )
    if not safe_area:
        return host
    return ft.SafeArea(content=host, expand=True)


def _is_probably_code_snippet(raw_text: str) -> bool:
    text = str(raw_text or "").strip("\n")
    if not text:
        return False
    if "```" in text:
        return True
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False

    code_markers = (
        "public class ",
        "private ",
        "protected ",
        "import ",
        "return ",
        "if (",
        "for (",
        "while (",
        "=>",
        "::",
        "{",
        "}",
        ";",
    )
    hits = 0
    for ln in lines[:12]:
        if any(marker in ln for marker in code_markers):
            hits += 1
        if re.match(r"^\s{2,}\S", ln):
            hits += 1
    return hits >= 2


def ds_code_block(text: str, dark: bool = False, language: str = "") -> ft.Control:
    """Bloco de codigo padrao com fonte monoespacada e scroll horizontal."""
    code = str(text or "").strip("\n")
    label = str(language or "").strip()
    border = DS.border_color(dark, 0.16)
    bg = DS.with_opacity(DS.G_900 if not dark else DS.G_100, 0.06)

    header = ft.Container()
    if label:
        header = ft.Container(
            padding=ft.padding.only(bottom=DS.SP_8),
            content=AppText(label.upper(), variant="caption", dark=dark, short_label=True, color=DS.text_sec_color(dark)),
        )

    return ft.Container(
        border_radius=DS.R_MD,
        bgcolor=bg,
        border=ft.border.all(1, border),
        padding=DS.SP_12,
        content=ft.Column(
            [
                header,
                ft.Row(
                    [
                        ft.Text(
                            code,
                            selectable=True,
                            no_wrap=True,
                            size=DS.FS_BODY_S,
                            color=DS.text_color(dark),
                            font_family="Consolas,Monaco,monospace",
                        )
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
            ],
            spacing=0,
        ),
    )


def ds_content_text(
    text: str,
    dark: bool = False,
    *,
    variant: str = "body",
    selectable: bool = True,
    **text_kwargs,
) -> ft.Control:
    """Renderiza texto comum ou bloco de codigo com heuristica unica."""
    raw = str(text or "")
    if _is_probably_code_snippet(raw):
        cleaned = raw.replace("```", "").strip()
        return ds_code_block(cleaned, dark=dark)
    return AppText(raw, variant=variant, dark=dark, force_wrap=True, selectable=selectable, **text_kwargs)


def ds_action_bar(actions: Sequence[dict], dark: bool = False) -> ft.Control:
    """Barra de acoes adaptativa com hitbox minima consistente."""
    controls: List[ft.Control] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        label = str(action.get("label") or "").strip() or "Acao"
        icon = action.get("icon")
        on_click = action.get("on_click")
        kind = str(action.get("kind") or "ghost").lower()
        disabled = bool(action.get("disabled"))
        icon_color = action.get("icon_color")
        min_height = int(action.get("min_height") or DS.TAP_MIN)

        text_kwargs = {}
        if kind == "ghost":
            text_kwargs["color"] = DS.text_color(dark)
        text_control = AppText(
            label,
            variant="label",
            dark=dark,
            short_label=True,
            **text_kwargs,
        )
        row_controls: List[ft.Control] = []
        if icon:
            row_controls.append(ft.Icon(icon, size=18, color=icon_color or DS.text_sec_color(dark)))
        row_controls.append(ft.Container(expand=True, content=text_control))

        bg = "transparent"
        border = ft.border.all(1, DS.border_color(dark, 0.16))
        if kind == "danger":
            bg = DS.with_opacity(DS.ERRO, 0.08)
            border = ft.border.all(1, DS.with_opacity(DS.ERRO, 0.35))
        elif kind == "primary":
            bg = DS.with_opacity(DS.P_500, 0.12)
            border = ft.border.all(1, DS.with_opacity(DS.P_500, 0.45))
        elif kind == "warning":
            bg = DS.with_opacity(DS.WARNING, 0.12)
            border = ft.border.all(1, DS.with_opacity(DS.WARNING, 0.40))

        controls.append(
            ft.Container(
                col={"xs": 12, "sm": 4, "md": 4},
                height=max(44, min_height),
                border_radius=DS.R_MD,
                bgcolor=bg,
                border=border,
                padding=ft.padding.symmetric(horizontal=DS.SP_12, vertical=DS.SP_8),
                on_click=on_click if not disabled else None,
                ink=not disabled,
                opacity=0.55 if disabled else 1.0,
                content=ft.Row(
                    row_controls,
                    spacing=DS.SP_8,
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    return ft.ResponsiveRow(controls=controls, spacing=DS.SP_8, run_spacing=DS.SP_8)
