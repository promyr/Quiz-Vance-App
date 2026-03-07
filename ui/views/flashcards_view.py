# -*- coding: utf-8 -*-
"""View de Flashcards â€” extraÃ­da do main_v2.py."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import flet as ft

from config import AI_PROVIDERS, CORES
from core.error_monitor import log_exception
from core.library_service import LibraryService
from core.ui_route_theme import _color
from core.ui_text_sanitizer import (
    _fix_mojibake_text,
    _sanitize_control_texts,
    _sanitize_payload_texts,
)

from core.helpers.ai_helpers import (
    create_user_ai_service,
    extract_user_api_keys,
    generation_profile,
    is_ai_quota_exceeded,
    ai_issue_kind,
    schedule_ai_task,
)
from core.helpers.file_helpers import (
    extract_uploaded_material,
    format_upload_info_label,
    normalize_uploaded_file_path,
    pick_study_files,
    state_async_guard,
)
from core.helpers.ui_helpers import (
    build_focus_header,
    screen_height,
    screen_width,
    set_feedback_text,
    show_confirm_dialog,
    show_quota_dialog,
    show_api_issue_dialog,
    status_banner,
    wrap_study_content,
)
from ui.design_system import (
    DS,
    ds_action_bar,
    ds_badge,
    ds_btn_ghost,
    ds_btn_primary,
    ds_btn_secondary,
    ds_card,
    ds_content_text,
    ds_divider,
    ds_toast,
)


def build_flashcards_body(state: dict, navigate, dark: bool) -> ft.Control:
    page = state.get("page")
    screen_w = screen_width(page) if page else 1280
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
    ai_enabled = bool(create_user_ai_service(user))

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
            log_exception(ex, "flashcards_view._build_flashcards_body.listar_arquivos")
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
        upload_info.value = format_upload_info_label(names)
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
            log_exception(ex, "flashcards_view._build_flashcards_body.library_select")
            texto = ""
            
        if texto:
            estado["upload_texts"] = [texto]
            estado["upload_names"] = [nome_tag]
            if not str(tema_field.value or "").strip():
                guessed = _guess_topic_from_name(nome_tag)
                if guessed:
                    tema_field.value = guessed
            _persist_form_inputs()
            _set_upload_info()
            set_feedback_text(status_text, f"Adicionado da biblioteca: {nome}", "success")
        else:
            estado["upload_texts"] = []
            estado["upload_names"] = []
            _set_upload_info()
            set_feedback_text(status_text, "Arquivo da biblioteca sem texto extraivel.", "warning")
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
        guard = state_async_guard(state)

        def _on_start():
            set_feedback_text(status_text, "Abrindo seletor de arquivos...", "info")
            page.update()

        def _on_timeout():
            set_feedback_text(status_text, "Tempo esgotado ao buscar arquivos.", "warning")

        def _on_error(ex: Exception):
            log_exception(ex, "flashcards_view._build_flashcards_body._pick_files_async")
            set_feedback_text(status_text, "Falha ao abrir arquivos.", "error")

        async def _run_pick():
            file_paths = await pick_study_files(page)
            if not file_paths:
                set_feedback_text(status_text, "", "info")
                return
            estado["upload_selected_names"] = [
                (os.path.basename(normalize_uploaded_file_path(fp) or str(fp or "")) or "arquivo")
                for fp in file_paths
            ]
            upload_texts, upload_names, failed_names = extract_uploaded_material(file_paths)
            estado["upload_texts"] = upload_texts
            estado["upload_names"] = upload_names
            if not upload_texts:
                set_feedback_text(
                    status_text,
                    ("Nao foi possivel extrair texto dos arquivos. "
                     "Para PDF, confirme que nao e imagem escaneada ou protegido por senha."),
                    "warning",
                )
            else:
                if failed_names:
                    set_feedback_text(status_text, f"Material carregado: {len(upload_texts)} arquivo(s). Ignorados: {len(failed_names)}.", "warning")
                else:
                    set_feedback_text(status_text, f"Material carregado: {len(upload_texts)} arquivo(s).", "success")
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
            set_feedback_text(status_text, "Nao ha material para remover.", "info")
            if page:
                page.update()
            return

        def _confirmed_clear():
            estado["upload_texts"] = []
            estado["upload_names"] = []
            estado["upload_selected_names"] = []
            estado["cont_source_lock_material"] = False
            _set_upload_info()
            set_feedback_text(status_text, "Material removido.", "info")
            if page:
                ds_toast(page, "Material removido.", tipo="info")
                page.update()

        show_confirm_dialog(page, "Limpar material", "Deseja remover todo material anexado desta sessao?", _confirmed_clear, confirm_label="Limpar")

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
        screen = (screen_width(page) if page else 1280)
        screen_h = (screen_height(page) if page else 820)
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
                dark=dark, width=card_w, height=card_h, padding=14, border_radius=DS.R_XXL, bgcolor=card_bg,
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
                            expand=True, padding=14, border_radius=DS.R_LG, bgcolor=inner_bg,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        expand=True, alignment=ft.Alignment(-1, -1),
                                        content=ft.ListView(
                                            controls=[ds_content_text(frente, dark=dark, variant="h3", size=front_font, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.LEFT)],
                                            spacing=0, expand=True, auto_scroll=False,
                                        ),
                                    ),
                                    ft.Container(
                                        visible=bool(estado["mostrar_verso"]), padding=12, border_radius=DS.R_MD, bgcolor=ft.Colors.with_opacity(0.10, CORES["primaria"]),
                                        content=ft.Column(
                                            [
                                                ft.Text("Resposta", size=11, weight=ft.FontWeight.W_600, color=CORES["primaria"]),
                                                ds_content_text(verso, dark=dark, variant="body", text_align=ft.TextAlign.LEFT),
                                            ],
                                            spacing=6, horizontal_alignment=ft.CrossAxisAlignment.START,
                                        ),
                                    ),
                                ],
                                spacing=10, expand=True,
                            ),
                        ),
                    ],
                    spacing=12, expand=True,
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
                log_exception(ex, "flashcards_view._build_flashcards_body._registrar_avaliacao")
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
        profile = generation_profile(user, "flashcards")
        service = create_user_ai_service(user, force_economic=bool(profile.get("force_economic")))
        novos = []
        try:
            if service and base_content:
                try:
                    novos = await asyncio.to_thread(service.generate_flashcards, base_content, prefetch_qtd)
                except Exception as ex:
                    log_exception(ex, "flashcards_view._build_flashcards_body.prefetch")
            if not novos and strict_material_source:
                set_feedback_text(status_estudo, "Modo continuo: sem novos cards do material anexado no momento.", "warning")
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

    def _provider_switch_options() -> list[tuple[str, str]]:
        keys = extract_user_api_keys(user)
        current_provider = str(user.get("provider") or "gemini").strip().lower()
        options: list[tuple[str, str]] = []
        for p in ("gemini", "openai", "groq"):
            if p == current_provider:
                continue
            if not str(keys.get(p) or "").strip():
                continue
            provider_name = str(AI_PROVIDERS.get(p, {}).get("name") or p.capitalize())
            options.append((p, provider_name))
        return options

    def _switch_provider_and_retry(provider_key: str):
        try:
            selected = str(provider_key or "").strip().lower()
            if selected not in {"gemini", "openai", "groq"}:
                return
            cfg = AI_PROVIDERS.get(selected, AI_PROVIDERS.get("gemini", {}))
            model_candidates = list(cfg.get("models") or [])
            current_model = str(user.get("model") or "").strip()
            fallback_model = str(cfg.get("default_model") or (model_candidates[0] if model_candidates else current_model)).strip()
            next_model = current_model if current_model in model_candidates else fallback_model
            user["provider"] = selected
            if next_model:
                user["model"] = next_model
            if isinstance(state.get("usuario"), dict):
                state["usuario"]["provider"] = selected
                if next_model:
                    state["usuario"]["model"] = next_model
            if db and user.get("id") and hasattr(db, "atualizar_provider_ia"):
                db.atualizar_provider_ia(int(user["id"]), selected, next_model or fallback_model)
            provider_name = str(cfg.get("name") or selected)
            set_feedback_text(status_text, f"Provider alterado para {provider_name}. Reexecutando geracao...", "info")
            if page:
                page.update()
            _on_gerar(None)
        except Exception as ex_switch:
            log_exception(ex_switch, "flashcards_view.switch_provider_and_retry")

    async def _gerar_flashcards_async():
        if not page:
            return
        _persist_form_inputs()
        gerar_button.disabled = True
        carregando.visible = True
        pre_profile = generation_profile(user, "flashcards")
        if pre_profile.get("label") == "free_slow":
            set_feedback_text(status_text, "Modo Free: gerando flashcards (economico e mais lento)...", "info")
        else:
            set_feedback_text(status_text, "Gerando flashcards...", "info")
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
            nome = next((str(f.get("nome_arquivo") or "Arquivo Biblioteca") for f in (library_files or []) if str(f.get("id")) == selected_library_id), "Arquivo Biblioteca")
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
            set_feedback_text(status_text, "PDF selecionado, mas sem texto extraido. Use um PDF com texto selecionavel (nao escaneado) ou adicione referencia.", "warning")
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
            base_content.append("INSTRUCAO DE FOCO: Gere os flashcards com base principal no material anexado, sem sair do assunto.")
        if not base_content and tema:
            base_content = [tema]
            
        estado["cont_theme"] = tema or "Conceito"
        estado["cont_base_content"] = list(base_content)
        estado["cont_prefetching"] = False
        estado["cont_source_lock_material"] = material_source_locked
        gen_profile = pre_profile
        service = create_user_ai_service(user, force_economic=bool(gen_profile.get("force_economic")))
        gerados = []
        
        if material_source_locked and not service:
            set_feedback_text(status_text, "Para gerar flashcards do PDF, configure a IA em Configuracoes.", "warning")
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
                log_exception(ex, "flashcards_view._build_flashcards_body")
                
        issue_kind = ai_issue_kind(service)
        if not gerados:
            if material_source_locked:
                if issue_kind in {"auth", "dependency"}:
                    set_feedback_text(status_text, "Nao consegui gerar flashcards com o provider atual. Revise chave/provider em Configuracoes.", "warning")
                else:
                    set_feedback_text(status_text, "Nao consegui gerar flashcards do material anexado. Revise o PDF/referencia e tente novamente.", "warning")
                if issue_kind == "quota":
                    show_api_issue_dialog(
                        page,
                        navigate,
                        "quota",
                        provider_options=_provider_switch_options(),
                        on_select_provider=_switch_provider_and_retry,
                    )
                elif issue_kind in {"auth", "dependency"}:
                    show_api_issue_dialog(
                        page,
                        navigate,
                        "auth" if issue_kind == "auth" else ("dependency" if issue_kind == "dependency" else "generic"),
                        provider_options=_provider_switch_options(),
                        on_select_provider=_switch_provider_and_retry,
                    )
                carregando.visible = False
                gerar_button.disabled = False
                page.update()
                return
            base = tema or "Conceito"
            gerados = [{"frente": f"{base} {i+1}", "verso": f"Resumo ou dica do {base} {i+1}."} for i in range(quantidade)]
            if issue_kind == "quota":
                set_feedback_text(status_text, "Cotas da IA esgotadas. Flashcards offline prontos.", "warning")
                show_api_issue_dialog(
                    page,
                    navigate,
                    "quota",
                    provider_options=_provider_switch_options(),
                    on_select_provider=_switch_provider_and_retry,
                )
            elif issue_kind in {"auth", "dependency"}:
                set_feedback_text(status_text, "Flashcards offline prontos. Ajuste a IA em Configuracoes.", "warning")
                show_api_issue_dialog(
                    page,
                    navigate,
                    "auth" if issue_kind == "auth" else ("dependency" if issue_kind == "dependency" else "generic"),
                    provider_options=_provider_switch_options(),
                    on_select_provider=_switch_provider_and_retry,
                )
            else:
                set_feedback_text(status_text, "Flashcards offline prontos.", "info")
        else:
            set_feedback_text(status_text, f"{len(gerados)} flashcards gerados com IA.", "success")
            
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
        schedule_ai_task(page, state, _gerar_flashcards_async, message="IA gerando flashcards...", status_control=status_text)

    gerar_button = ds_btn_primary("Gerar e iniciar revisao", icon=ft.Icons.BOLT, on_click=_on_gerar, dark=dark, expand=True)

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
                        ft.ResponsiveRow([ft.Container(content=tema_field, col={"sm": 12, "md": 8}), ft.Container(content=quantidade_dropdown, col={"sm": 12, "md": 4})], spacing=12, run_spacing=8),
                        referencia_field,
                        ft.ResponsiveRow(
                            [
                                ft.Container(col={"xs": 12, "md": 4}, content=ds_btn_secondary("Anexar material", icon=ft.Icons.UPLOAD_FILE, on_click=_upload_material, dark=dark, expand=True)),
                                ft.Container(col={"xs": 12, "md": 5}, content=library_dropdown),
                                ft.Container(col={"xs": 12, "md": 3}, content=ds_btn_ghost("Limpar material", on_click=_limpar_material, dark=dark)),
                                ft.Container(col={"xs": 12, "md": 12}, content=upload_info),
                                ft.Container(col={"xs": 12, "md": 12}, content=material_source_hint),
                            ],
                            run_spacing=6, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.ResponsiveRow(
                            [
                                ft.Container(col={"xs": 12, "md": 4}, content=gerar_button),
                                ft.Container(col={"xs": 12, "md": 8}, content=ft.Column([carregando, status_banner(status_text, dark)], spacing=6)),
                            ],
                            run_spacing=6, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=8,
                ),
            ),
        ],
        spacing=10, visible=True,
    )

    study_section = ft.Column(
        [
            ft.Row([ft.Text("Revisao de flashcards", size=17, weight=ft.FontWeight.W_600, color=_color("texto", dark)), ft.Row([contador_flashcards, desempenho_text], spacing=10, wrap=True)], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            status_banner(status_estudo, dark),
            ft.Container(alignment=ft.Alignment(0, 0), content=cards_host),
            ds_action_bar(
                [
                    {"label": "Mostrar resposta", "icon": ft.Icons.VISIBILITY, "on_click": _mostrar_resposta_click, "kind": "primary"},
                    {"label": "Lembrei", "icon": ft.Icons.CHECK_CIRCLE, "on_click": _mark_lembrei, "kind": "primary"},
                    {"label": "Rever", "icon": ft.Icons.REFRESH, "on_click": _mark_rever, "kind": "warning"},
                ],
                dark=dark,
            ),
            ft.ResponsiveRow([ft.Container(col={"xs": 12, "md": 6}, content=ds_btn_secondary("Anterior", icon=ft.Icons.CHEVRON_LEFT, on_click=_prev_card_click, dark=dark, expand=True)), ft.Container(col={"xs": 12, "md": 6}, content=ds_btn_secondary("Proximo", icon=ft.Icons.CHEVRON_RIGHT, on_click=_next_card_click, dark=dark, expand=True))], run_spacing=6, spacing=10),
            ft.ResponsiveRow([ft.Container(col={"xs": 12, "md": 6}, content=ds_btn_ghost("Voltar para configuracao", icon=ft.Icons.ARROW_BACK, on_click=_voltar_config, dark=dark)), ft.Container(col={"xs": 12, "md": 6}, content=ds_btn_ghost("Voltar ao Inicio", icon=ft.Icons.HOME_OUTLINED, on_click=lambda _: navigate("/home"), dark=dark))], run_spacing=6, spacing=10),
        ],
        spacing=10, expand=True, scroll=ft.ScrollMode.AUTO, visible=False,
    )

    _set_upload_info()
    _render_flashcards()
    if estado.get("ui_stage") == "study" and flashcards:
        _mostrar_etapa_estudo()
    else:
        _mostrar_etapa_config()

    retorno = wrap_study_content(
        ft.Column(
            [
                build_focus_header("Flashcards", "Fluxo: 1) Configure  2) Gere  3) Revise ativamente", etapa_text, dark),
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





