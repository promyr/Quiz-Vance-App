# -*- coding: utf-8 -*-
"""
Sistema de Componentes UI - Design Moderno e Ousado
Inspirado em: Vercel, Linear, Arc Browser
"""

import flet as ft
from config import CORES


# ========== HELPERS ==========
def get_cor(nome: str, tema_escuro: bool = False) -> str:
    """Retorna cor baseada no tema"""
    if tema_escuro:
        mapa = {
            "fundo": CORES["fundo_escuro"],
            "card": CORES["card_escuro"],
            "texto": CORES["texto_escuro"],
            "texto_sec": CORES["texto_sec_escuro"],
        }
        return mapa.get(nome, CORES.get(nome, "#FFFFFF"))
    return CORES.get(nome, "#000000")


# ========== SOMBRAS MODERNAS ==========
SOMBRAS = {
    "none": None,
    "sm": ft.BoxShadow(
        blur_radius=2,
        spread_radius=0,
        offset=ft.Offset(0, 1),
        color=ft.Colors.with_opacity(0.05, "#000000")
    ),
    "md": ft.BoxShadow(
        blur_radius=6,
        spread_radius=-1,
        offset=ft.Offset(0, 4),
        color=ft.Colors.with_opacity(0.1, "#000000")
    ),
    "lg": ft.BoxShadow(
        blur_radius=15,
        spread_radius=-3,
        offset=ft.Offset(0, 10),
        color=ft.Colors.with_opacity(0.15, "#000000")
    ),
    "xl": ft.BoxShadow(
        blur_radius=25,
        spread_radius=-5,
        offset=ft.Offset(0, 20),
        color=ft.Colors.with_opacity(0.2, "#000000")
    ),
    "glow": ft.BoxShadow(
        blur_radius=20,
        spread_radius=0,
        offset=ft.Offset(0, 0),
        color=ft.Colors.with_opacity(0.3, CORES["primaria"])
    )
}


# ========== BOTÕES MODERNOS ==========
def criar_botao_primario(
    texto: str,
    on_click,
    icone: str = None,
    width: int = None,
    height: int = 56,
    tema_escuro: bool = False,
    gradient: bool = True
) -> ft.Container:
    """Botão primário com gradiente e animações"""
    
    # Gradiente moderno
    if gradient:
        gradient_bg = ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[CORES["primaria"], CORES["primaria_escura"]]
        )
    else:
        gradient_bg = None
    
    conteudo = []
    if icone:
        conteudo.append(ft.Icon(icone, color="white", size=20))
    conteudo.append(ft.Text(texto, color="white", size=15, weight="w600"))
    
    return ft.Container(
        content=ft.Row(
            conteudo,
            alignment="center",
            spacing=10
        ),
        width=width,
        height=height,
        bgcolor=CORES["primaria"] if not gradient else None,
        gradient=gradient_bg,
        border_radius=14,
        padding=ft.Padding.symmetric(horizontal=24, vertical=16),
        shadow=SOMBRAS["md"],
        on_click=on_click,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(100, ft.AnimationCurve.EASE_OUT),
        ink=True
    )


def criar_botao_secundario(
    texto: str,
    on_click,
    icone: str = None,
    width: int = None,
    height: int = 56,
    tema_escuro: bool = False
) -> ft.Container:
    """Botão secundário com borda"""
    
    conteudo = []
    if icone:
        conteudo.append(ft.Icon(icone, color=CORES["primaria"], size=20))
    conteudo.append(ft.Text(texto, color=CORES["primaria"], size=15, weight="w600"))
    
    return ft.Container(
        content=ft.Row(
            conteudo,
            alignment="center",
            spacing=10
        ),
        width=width,
        height=height,
        bgcolor=ft.Colors.with_opacity(0.05, CORES["primaria"]),
        border_radius=14,
        border=ft.Border.all(2, CORES["primaria"]),
        padding=ft.Padding.symmetric(horizontal=24, vertical=16),
        on_click=on_click,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        ink=True
    )


def criar_botao_ghost(
    texto: str,
    on_click,
    icone: str = None,
    cor: str = None,
    tema_escuro: bool = False
) -> ft.Container:
    """Botão fantasma (sem fundo)"""
    
    cor_final = cor or CORES["primaria"]
    
    conteudo = []
    if icone:
        conteudo.append(ft.Icon(icone, color=cor_final, size=18))
    conteudo.append(ft.Text(texto, color=cor_final, size=14, weight="w500"))
    
    return ft.Container(
        content=ft.Row(
            conteudo,
            alignment="center",
            spacing=8
        ),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        border_radius=10,
        on_click=on_click,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        ink=True,
        ink_color=ft.Colors.with_opacity(0.1, cor_final)
    )


def criar_botao_icone(
    icone: str,
    on_click,
    cor: str = None,
    tamanho: int = 40,
    tooltip: str = None
) -> ft.Container:
    """Botão de ícone moderno"""
    
    cor_final = cor or CORES["primaria"]
    
    return ft.Container(
        content=ft.Icon(icone, color=cor_final, size=20),
        width=tamanho,
        height=tamanho,
        border_radius=tamanho // 2,
        bgcolor=ft.Colors.with_opacity(0.1, cor_final),
        alignment=ft.Alignment.CENTER,
        on_click=on_click,
        tooltip=tooltip,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(100, ft.AnimationCurve.EASE_OUT),
        ink=True
    )


# ========== CARDS MODERNOS ===========
def criar_card(
    conteudo,
    padding: int = 24,
    border_radius: int = 20,
    tema_escuro: bool = False,
    hover: bool = False,
    border_color: str = None
) -> ft.Container:
    """Card moderno com sombra suave"""
    
    card = ft.Container(
        content=conteudo,
        padding=padding,
        border_radius=border_radius,
        bgcolor=get_cor("card", tema_escuro),
        shadow=SOMBRAS["md"],
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT) if hover else None,
        border=ft.Border.all(1, border_color) if border_color else None
    )
    
    return card


def criar_card_glassmorphism(
    conteudo,
    padding: int = 24,
    border_radius: int = 20,
    tema_escuro: bool = False
) -> ft.Container:
    """Card com efeito glassmorphism"""
    
    return ft.Container(
        content=conteudo,
        padding=padding,
        border_radius=border_radius,
        bgcolor=ft.Colors.with_opacity(0.7 if not tema_escuro else 0.3, get_cor("card", tema_escuro)),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, "white" if tema_escuro else "black")),
        shadow=SOMBRAS["lg"],
        blur=(10, 10)
    )


# ========== BADGES E CHIPS ==========
def criar_badge(
    texto: str,
    cor_bg: str = None,
    cor_texto: str = "white",
    icone: str = None,
    size: str = "md"
) -> ft.Container:
    """Badge moderno"""
    
    sizes = {
        "sm": {"padding": 6, "text_size": 11, "icon_size": 12},
        "md": {"padding": 8, "text_size": 13, "icon_size": 14},
        "lg": {"padding": 10, "text_size": 15, "icon_size": 16}
    }
    
    config = sizes.get(size, sizes["md"])
    cor_final = cor_bg or CORES["primaria"]
    
    conteudo = []
    if icone:
        conteudo.append(ft.Icon(icone, color=cor_texto, size=config["icon_size"]))
    conteudo.append(ft.Text(texto, color=cor_texto, size=config["text_size"], weight="w600"))
    
    return ft.Container(
        content=ft.Row(conteudo, spacing=6, alignment="center"),
        bgcolor=cor_final,
        padding=ft.Padding.symmetric(horizontal=config["padding"] * 2, vertical=config["padding"]),
        border_radius=100,  # Totalmente arredondado
        shadow=SOMBRAS["sm"]
    )


def criar_chip(
    texto: str,
    on_click=None,
    selecionado: bool = False,
    icone: str = None,
    tema_escuro: bool = False
) -> ft.Container:
    """Chip selecionável"""
    
    if selecionado:
        bg = CORES["primaria"]
        texto_cor = "white"
        borda = None
    else:
        bg = ft.Colors.with_opacity(0.05, CORES["texto"])
        texto_cor = get_cor("texto", tema_escuro)
        borda = ft.Border.all(1, ft.Colors.with_opacity(0.1, CORES["texto"]))
    
    conteudo = []
    if icone:
        conteudo.append(ft.Icon(icone, color=texto_cor, size=16))
    conteudo.append(ft.Text(texto, color=texto_cor, size=13, weight="w500"))
    
    return ft.Container(
        content=ft.Row(conteudo, spacing=6, alignment="center"),
        bgcolor=bg,
        border=borda,
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        border_radius=100,
        on_click=on_click,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        ink=True if on_click else False
    )


# ========== NÍVEIS E PROGRESSO ==========
def criar_badge_nivel(
    nivel: str,
    xp: int,
    tema_escuro: bool = False
) -> ft.Container:
    """Badge de nível com estilo moderno"""
    
    # Mapear cores
    cores_nivel = {
        "Bronze": (CORES["bronze"], "workspace_premium"),
        "Prata": (CORES["prata"], "military_tech"),
        "Ouro": (CORES["ouro"], "emoji_events"),
        "Diamante": (CORES["diamante"], "diamond"),
        "Mestre": (CORES["mestre"], "stars")
    }
    
    nivel_nome = nivel.split()[-1] if nivel else "Bronze"
    cor, icone = cores_nivel.get(nivel_nome, (CORES["primaria"], "shield"))
    
    return ft.Container(
        content=ft.Row([
            ft.Icon(icone, color="white", size=20),
            ft.Text(f"{nivel_nome}", color="white", size=15, weight="bold"),
            ft.Container(width=4),
            ft.Text(f"{xp} XP", color="white", size=13, weight="w500", opacity=0.9)
        ], spacing=8, alignment="center"),
        bgcolor=cor,
        padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        border_radius=100,
        shadow=ft.BoxShadow(
            blur_radius=10,
            offset=ft.Offset(0, 4),
            color=ft.Colors.with_opacity(0.3, cor)
        ),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
    )


def criar_progress_bar(
    xp: int,
    tema_escuro: bool = False
) -> ft.Column:
    """Barra de progresso moderna"""
    
    # Calcular progresso
    marcos = [2500, 7000, 15000, 30000]
    inicio_faixa = 0
    alvo = marcos[-1]
    
    for m in marcos:
        if xp < m:
            alvo = m
            break
        inicio_faixa = m
    
    faixa = max(1, alvo - inicio_faixa)
    atual_na_faixa = max(0, xp - inicio_faixa)
    progresso = min(1.0, atual_na_faixa / faixa)
    
    return ft.Column([
        ft.Row([
            ft.Text(
                "Próximo nível:",
                size=13,
                color=get_cor("texto_sec", tema_escuro),
                weight="w500"
            ),
            ft.Text(
                f"{atual_na_faixa} / {faixa} XP",
                size=13,
                weight="bold",
                color=CORES["primaria"]
            )
        ], alignment="spaceBetween"),
        ft.Container(height=8),
        ft.Container(
            content=ft.Stack([
                # Fundo
                ft.Container(
                    height=8,
                    border_radius=100,
                    bgcolor=ft.Colors.with_opacity(0.1, CORES["primaria"])
                ),
                # Progresso
                ft.Container(
                    height=8,
                    width=f"{progresso * 100}%",
                    border_radius=100,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.CENTER_LEFT,
                        end=ft.Alignment.CENTER_RIGHT,
                        colors=[CORES["acento"], CORES["primaria"]]
                    ),
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        offset=ft.Offset(0, 2),
                        color=ft.Colors.with_opacity(0.3, CORES["primaria"])
                    )
                )
            ]),
            animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT)
        ),
        ft.Container(height=4),
        ft.Text(
            f"{int(progresso * 100)}% completo",
            size=11,
            color=get_cor("texto_sec", tema_escuro),
            weight="w500"
        )
    ], spacing=0)


# ========== ESTATÍSTICAS ==========
def criar_stat_card(
    icone: str,
    valor: str,
    label: str,
    cor: str = None,
    tema_escuro: bool = False
) -> ft.Container:
    """Card de estatística moderna"""
    
    cor_final = cor or CORES["primaria"]
    
    return ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Icon(icone, color=cor_final, size=28),
                padding=12,
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.1, cor_final)
            ),
            ft.Container(height=12),
            ft.Text(
                str(valor),
                size=24,
                weight="bold",
                color=get_cor("texto", tema_escuro)
            ),
            ft.Text(
                label,
                size=12,
                color=get_cor("texto_sec", tema_escuro),
                weight="w500"
            )
        ], horizontal_alignment="center", spacing=4),
        padding=20,
        bgcolor=get_cor("card", tema_escuro),
        border_radius=16,
        shadow=SOMBRAS["md"],
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        expand=True
    )


# ========== LOADING ==========
def criar_loading(
    mensagem: str = "Carregando...",
    tema_escuro: bool = False
) -> ft.Column:
    """Indicador de loading moderno"""
    
    return ft.Column([
        ft.Container(
            content=ft.ProgressRing(
                width=60,
                height=60,
                stroke_width=4,
                color=CORES["primaria"]
            ),
            padding=20,
            border_radius=100,
            bgcolor=ft.Colors.with_opacity(0.05, CORES["primaria"])
        ),
        ft.Container(height=16),
        ft.Text(
            mensagem,
            size=14,
            color=get_cor("texto_sec", tema_escuro),
            weight="w500",
            text_align="center"
        )
    ], horizontal_alignment="center", spacing=0)


# ========== INPUTS MODERNOS ==========
def criar_input(
    label: str,
    hint: str = None,
    icone: str = None,
    password: bool = False,
    width: int = None,
    on_change=None,
    tema_escuro: bool = False
) -> ft.TextField:
    """Input moderno"""
    
    return ft.TextField(
        label=label,
        hint_text=hint,
        prefix_icon=icone,
        password=password,
        can_reveal_password=password,
        width=width,
        height=56,
        text_size=15,
        bgcolor=get_cor("card", tema_escuro),
        border_radius=14,
        border_color=ft.Colors.with_opacity(0.1, CORES["texto"]),
        focused_border_color=CORES["primaria"],
        on_change=on_change,
        content_padding=ft.Padding.symmetric(horizontal=16, vertical=16)
    )


# ========== TOAST/SNACKBAR ==========
def criar_toast(
    mensagem: str,
    tipo: str = "info",
    tema_escuro: bool = False
) -> ft.SnackBar:
    """Toast notification moderna"""
    
    config = {
        "sucesso": ("check_circle", CORES["sucesso"]),
        "erro": ("error", CORES["erro"]),
        "warning": ("warning", CORES["warning"]),
        "info": ("info", CORES["info"])
    }
    
    icone, cor = config.get(tipo, config["info"])
    
    return ft.SnackBar(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(icone, color="white", size=20),
                padding=8,
                border_radius=100,
                bgcolor=ft.Colors.with_opacity(0.2, "white")
            ),
            ft.Text(mensagem, color="white", size=14, weight="w500")
        ], spacing=12),
        bgcolor=cor,
        behavior=ft.SnackBarBehavior.FLOATING,
        margin=16,
        padding=16,
        shape=ft.RoundedRectangleBorder(radius=12),
        duration=3000,
        show_close_icon=True
    )


# ========== DIVIDER ==========
def criar_divider(tema_escuro: bool = False) -> ft.Divider:
    """Divider sutil"""
    
    return ft.Divider(
        height=1,
        thickness=1,
        color=ft.Colors.with_opacity(0.08, CORES["texto"])
    )


# ========== HEADER DE SEÇÃO ==========
def criar_header_secao(
    titulo: str,
    subtitulo: str = None,
    acao_btn: str = None,
    acao_on_click=None,
    tema_escuro: bool = False
) -> ft.Row:
    """Header de seção moderno"""
    
    esquerda = ft.Column([
        ft.Text(
            titulo,
            size=24,
            weight="bold",
            color=get_cor("texto", tema_escuro)
        ),
        ft.Text(
            subtitulo,
            size=14,
            color=get_cor("texto_sec", tema_escuro),
            weight="w500"
        ) if subtitulo else ft.Container()
    ], spacing=4)
    
    direita = (
        criar_botao_ghost(acao_btn, acao_on_click, tema_escuro=tema_escuro)
        if acao_btn and acao_on_click
        else ft.Container()
    )
    
    return ft.Row([esquerda, direita], alignment="spaceBetween")
