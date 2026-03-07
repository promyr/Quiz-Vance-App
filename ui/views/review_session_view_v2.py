# -*- coding: utf-8 -*-
"""Tela de sessao de revisao com fila diaria combinada."""

from __future__ import annotations

import time
import re
from typing import Dict, List, Optional

import flet as ft

from core.error_monitor import log_exception
from core.repositories.flashcard_repository import FlashcardRepository
from core.repositories.question_progress_repository import QuestionProgressRepository
from core.repositories.review_session_repository import ReviewSessionRepository
from core.services.daily_review_service import DailyReviewService
from core.services.review_session_service import ReviewSessionService
from core.services.spaced_repetition_service import SpacedRepetitionService
from ui.design_system import DS, AppText, ds_badge, ds_btn_ghost, ds_btn_primary, ds_btn_secondary, ds_card, ds_divider, ds_empty_state, ds_progress_bar, ds_section_title, ds_content_text


_REVIEW_CONTENT_MAX_WIDTH = 1040


def _review_content_width(page) -> int:
    try:
        sw = int(float(getattr(page, "width", 0) or 1280))
    except Exception:
        sw = 1280
    return min(_REVIEW_CONTENT_MAX_WIDTH, max(320, int(sw * 0.92)))


def _is_compact_layout(page) -> bool:
    return _review_content_width(page) < 700


def _adaptive_actions_row(
    controls: List[Optional[ft.Control]],
    page,
    center: bool = False,
    spacing: int = DS.SP_8,
) -> ft.Control:
    safe_controls = [ctrl for ctrl in controls if ctrl is not None]
    compact = _is_compact_layout(page)
    if compact:
        return ft.Column(
            safe_controls,
            spacing=spacing,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER if center else ft.CrossAxisAlignment.START,
        )
    return ft.Row(
        safe_controls,
        spacing=spacing,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER if center else ft.MainAxisAlignment.START,
        scroll=ft.ScrollMode.AUTO,
    )


def _review_centered_content(ctrl: ft.Control, page) -> ft.Control:
    return ft.Container(
        width=_review_content_width(page),
        alignment=ft.Alignment(0, 0),
        content=ctrl,
    )


def build_review_session_body(state: dict, navigate, dark: bool, modo: str = "sessao"):
    db = state.get("db")
    user = state.get("usuario") or {}
    page = state.get("page")
    user_id = int(user.get("id") or 0)
    premium = bool(int(user.get("premium_active") or 0) == 1)

    titulo_modo = "Revisao do Dia"
    itens_revisao: List[Dict] = []
    spaced_service = None
    session_service = None

    if db and user_id:
        try:
            flash_repo = FlashcardRepository(db)
            question_repo = QuestionProgressRepository(db)
            spaced_service = SpacedRepetitionService(flash_repo, question_repo)
            session_service = ReviewSessionService(ReviewSessionRepository(db))
            daily_service = DailyReviewService(flash_repo, question_repo)

            if modo == "erros":
                titulo_modo = "Caderno de Erros"
                itens_revisao = [{"item_type": "question", "payload": q} for q in question_repo.list_errors(user_id, limit=40)]
            elif modo == "marcadas":
                titulo_modo = "Marcadas para Revisar"
                itens_revisao = [{"item_type": "question", "payload": q} for q in question_repo.list_marked(user_id, limit=40)]
            else:
                titulo_modo = "Revisao do Dia"
                itens_revisao = daily_service.build_daily_queue(user_id=user_id, premium=premium, free_limit=30)
        except Exception as ex:
            log_exception(ex, "review_session_view.init")

    if not itens_revisao:
        return ft.Container(
            expand=True,
            padding=DS.SP_16,
            content=_review_centered_content(
                ft.Column(
                [
                    ds_section_title(titulo_modo, dark=dark),
                    ft.Container(height=DS.SP_32),
                    ds_empty_state(
                        ft.Icons.CHECK_CIRCLE_OUTLINE,
                        "Nada para revisar!",
                        "Voce esta em dia neste modo. Continue praticando para acumular questoes.",
                        cta_text="Estudar novas questoes",
                        cta_action=lambda _: navigate("/quiz"),
                        dark=dark,
                    ),
                ],
                spacing=DS.SP_16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                page,
            ),
        )

    total = len(itens_revisao)
    sess = state.setdefault(
        "revisao_sessao_v2",
        {
            "idx": 0,
            "answers": {},
            "question_confirmed": set(),
            "outcomes": {},
            "show_back": False,
            "started_at": time.monotonic(),
            "review_session_id": None,
            "finalized": False,
        },
    )
    if state.get("revisao_sessao_v2_modo") != modo:
        sess.clear()
        sess.update(
            {
                "idx": 0,
                "answers": {},
                "question_confirmed": set(),
                "outcomes": {},
                "show_back": False,
                "started_at": time.monotonic(),
                "review_session_id": None,
                "finalized": False,
            }
        )
        state["revisao_sessao_v2_modo"] = modo

    if session_service and not sess.get("review_session_id"):
        try:
            sess["review_session_id"] = session_service.start(user_id, str(modo or "daily"), total)
        except Exception:
            sess["review_session_id"] = None

    cards_col = ft.Column(
        spacing=DS.SP_12,
        expand=False,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    status_txt = ft.Text("", size=DS.FS_CAPTION, color=DS.text_sec_color(dark))

    def _get_counts():
        outcomes = dict(sess.get("outcomes") or {})
        acertos = sum(1 for v in outcomes.values() if v in {"correct", "remembered"})
        erros = sum(1 for v in outcomes.values() if v in {"wrong", "review"})
        puladas = sum(1 for v in outcomes.values() if v == "skip")
        return acertos, erros, puladas

    def _record(item_type: str, payload: dict, resultado: str, is_correct):
        if not session_service or not sess.get("review_session_id"):
            return
        try:
            if item_type == "question":
                item_ref = db._question_hash(payload) if db else str(hash(str(payload)))
            else:
                item_ref = db._flashcard_hash(payload) if db else str(hash(str(payload)))
            session_service.record(
                int(sess["review_session_id"]),
                item_type=item_type,
                item_ref=item_ref,
                resultado=resultado,
                is_correct=is_correct,
                response_time_ms=0,
            )
        except Exception as ex:
            log_exception(ex, "review_session_view.record")

    def _finalize_if_needed():
        if sess.get("finalized"):
            return
        if not session_service or not sess.get("review_session_id"):
            sess["finalized"] = True
            return
        acertos, erros, puladas = _get_counts()
        tempo_ms = int(max(0, (time.monotonic() - float(sess.get("started_at") or time.monotonic())) * 1000))
        try:
            session_service.finish(int(sess["review_session_id"]), acertos, erros, puladas, tempo_ms)
        except Exception as ex:
            log_exception(ex, "review_session_view.finish")
        sess["finalized"] = True

    def _advance():
        sess["idx"] = int(sess.get("idx", 0)) + 1
        sess["show_back"] = False

    def _prev(_=None):
        sess["idx"] = max(0, int(sess.get("idx", 0)) - 1)
        sess["show_back"] = False
        _render_card()
        if page:
            page.update()

    def _restart(_=None):
        sess.clear()
        sess.update(
            {
                "idx": 0,
                "answers": {},
                "question_confirmed": set(),
                "outcomes": {},
                "show_back": False,
                "started_at": time.monotonic(),
                "review_session_id": session_service.start(user_id, str(modo or "daily"), total) if session_service else None,
                "finalized": False,
            }
        )
        _render_card()
        if page:
            page.update()

    def _render_card():
        cards_col.controls.clear()
        idx = int(sess.get("idx", 0))
        prog = min(1.0, idx / max(1, total))

        if idx >= total:
            _finalize_if_needed()
            acertos, erros, puladas = _get_counts()
            taxa = (acertos / max(1, total)) * 100.0
            cor = DS.SUCESSO if taxa >= 70 else (DS.WARNING if taxa >= 50 else DS.ERRO)
            cards_col.controls.append(
                _review_centered_content(ds_card(
                    dark=dark,
                    padding=DS.SP_24,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.EMOJI_EVENTS, size=48, color=cor),
                            ft.Text("Sessao concluida", size=DS.FS_H2, weight=DS.FW_BOLD, color=DS.text_color(dark)),
                            ft.Text(f"Acertos: {acertos} â€¢ Erros: {erros} â€¢ Puladas: {puladas}", size=DS.FS_BODY, color=DS.text_sec_color(dark)),
                            ft.Text(f"Taxa: {taxa:.0f}%", size=DS.FS_BODY, color=cor, weight=DS.FW_SEMI),
                            ds_divider(dark),
                            _adaptive_actions_row(
                                [
                                    ds_btn_primary("Nova sessÃ£o", on_click=_restart, dark=dark, icon=ft.Icons.REFRESH),
                                    ds_btn_ghost("Voltar", on_click=lambda _: navigate("/revisao"), dark=dark),
                                ],
                                page=page,
                                center=True,
                                spacing=DS.SP_8,
                            ),
                        ],
                        spacing=DS.SP_12,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ), page)
            )
            return

        item = itens_revisao[idx]
        item_type = str(item.get("item_type") or "question")
        payload = item.get("payload") or {}
        cards_col.controls.append(
            _review_centered_content(ds_card(
                dark=dark,
                padding=DS.SP_14,
                content=ft.Column(
                    [
                        ft.Row([ds_progress_bar(prog, dark=dark, color=DS.P_500)], spacing=0),
                        ft.Row(
                            [
                                ft.Text(f"Item {idx + 1}/{total}", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                                ft.Container(expand=True),
                                ds_badge("Flashcard" if item_type == "flashcard" else "Questao", color=DS.P_500 if item_type == "question" else DS.SUCESSO),
                            ],
                            spacing=DS.SP_8,
                        ),
                    ],
                    spacing=DS.SP_8,
                ),
            ), page)
        )

        if item_type == "flashcard":
            frente = str(payload.get("frente") or "").strip()
            verso = str(payload.get("verso") or "").strip()
            mostrando_verso = bool(sess.get("show_back"))

            def _toggle_verso(_=None):
                sess["show_back"] = not bool(sess.get("show_back"))
                _render_card()
                if page:
                    page.update()

            def _avaliar_flash(acao: str):
                if spaced_service and user_id:
                    spaced_service.review_flashcard(user_id, payload, acao)
                    db.registrar_progresso_diario(user_id, flashcards=1)
                resultado = "remembered" if acao == "lembrei" else ("review" if acao == "rever" else "skip")
                sess["outcomes"][idx] = resultado
                _record("flashcard", payload, resultado, True if resultado == "remembered" else (False if resultado == "review" else None))
                _advance()
                _render_card()
                if page:
                    page.update()

            cards_col.controls.append(
                _review_centered_content(ds_card(
                    dark=dark,
                    padding=DS.SP_16,
                    content=ft.Column(
                        [
                            ft.Text("Frente", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                            ds_content_text(
                                frente or "Flashcard sem frente.",
                                dark=dark,
                                variant="body",
                                text_align=ft.TextAlign.CENTER,
                                weight=DS.FW_SEMI,
                            ),
                            ft.Container(height=DS.SP_8),
                            ft.Text("Verso", size=DS.FS_CAPTION, color=DS.text_sec_color(dark)),
                            ds_content_text(
                                verso if mostrando_verso else "Toque em Mostrar verso para revelar.",
                                dark=dark,
                                variant="body_s",
                                text_align=ft.TextAlign.CENTER,
                            ),
                            _adaptive_actions_row(
                                [
                                    ds_btn_ghost("Mostrar verso", on_click=_toggle_verso, dark=dark, icon=ft.Icons.VISIBILITY_OUTLINED),
                                    ds_btn_primary("Lembrei", on_click=lambda _: _avaliar_flash("lembrei"), dark=dark, icon=ft.Icons.CHECK_CIRCLE_OUTLINED),
                                    ds_btn_secondary("Rever", on_click=lambda _: _avaliar_flash("rever"), dark=dark, icon=ft.Icons.REFRESH),
                                    ds_btn_ghost("Pular", on_click=lambda _: _avaliar_flash("pular"), dark=dark, icon=ft.Icons.SKIP_NEXT_OUTLINED),
                                ],
                                page=page,
                                spacing=DS.SP_8,
                            ),
                        ],
                        spacing=DS.SP_8,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ), page)
            )
        else:
            enunciado = str(payload.get("enunciado") or payload.get("pergunta") or "").strip()
            alternativas_raw = payload.get("alternativas") or payload.get("opcoes") or []

            def _norm_alt(value) -> str:
                if isinstance(value, dict):
                    value = (
                        value.get("texto")
                        or value.get("text")
                        or value.get("alternativa")
                        or value.get("opcao")
                        or ""
                    )
                txt = str(value or "").replace("\r", "\n")
                txt = " ".join(part for part in txt.split())
                txt = txt.strip()
                # Evita duplicidade visual: "A) A. texto", "B) B) texto", etc.
                txt = re.sub(r"^[A-Ea-e][\)\.\:\-]\s*", "", txt)
                txt = re.sub(r"^\(?\d{1,2}[\)\.\:\-]\s*", "", txt)
                return txt.strip()

            alternativas = []
            for alt in (alternativas_raw if isinstance(alternativas_raw, list) else []):
                norm = _norm_alt(alt)
                if norm:
                    alternativas.append(norm)
            if len(alternativas) > 5:
                alternativas = alternativas[:5]
            try:
                correta_idx = int(payload.get("correta_index", payload.get("correta", 0)))
            except Exception:
                correta_idx = 0
            correta_idx = max(0, min(correta_idx, max(0, len(alternativas) - 1)))
            confirmado = idx in set(sess.get("question_confirmed") or set())
            selecao = (sess.get("answers") or {}).get(idx)

            def _selecionar(alt_idx: int, _=None):
                if confirmado:
                    return
                sess.setdefault("answers", {})[idx] = alt_idx
                _render_card()
                if page:
                    page.update()

            def _skip_question(_=None):
                if spaced_service and user_id:
                    spaced_service.skip_question(user_id, payload)
                sess["outcomes"][idx] = "skip"
                _record("question", payload, "skip", None)
                _advance()
                _render_card()
                if page:
                    page.update()

            def _confirmar(_=None):
                if selecao is None or confirmado:
                    return
                acertou = int(selecao) == int(correta_idx)
                if spaced_service and user_id:
                    spaced_service.review_question(user_id, payload, acertou)
                    db.registrar_progresso_diario(user_id, questoes=1, acertos=1 if acertou else 0)
                sess.setdefault("question_confirmed", set()).add(idx)
                resultado = "correct" if acertou else "wrong"
                sess["outcomes"][idx] = resultado
                _record("question", payload, resultado, bool(acertou))
                _render_card()
                if page:
                    page.update()

            def _next_after_confirm(_=None):
                _advance()
                _render_card()
                if page:
                    page.update()

            alt_controls = []
            alt_width = max(280, _review_content_width(page) - 96)
            for a_idx, alt in enumerate(alternativas):
                if confirmado:
                    if a_idx == correta_idx:
                        bg = ft.Colors.with_opacity(0.15, DS.SUCESSO)
                        border = ft.border.all(2, DS.SUCESSO)
                    elif a_idx == selecao:
                        bg = ft.Colors.with_opacity(0.15, DS.ERRO)
                        border = ft.border.all(2, DS.ERRO)
                    else:
                        bg = ft.Colors.with_opacity(0.04, DS.text_sec_color(dark))
                        border = ft.border.all(1, ft.Colors.with_opacity(0.12, DS.text_sec_color(dark)))
                else:
                    selected = selecao == a_idx
                    bg = ft.Colors.with_opacity(0.12, DS.P_500) if selected else ft.Colors.with_opacity(0.04, DS.text_sec_color(dark))
                    border = ft.border.all(2 if selected else 1, DS.P_500 if selected else ft.Colors.with_opacity(0.18, DS.text_sec_color(dark)))
                alt_controls.append(
                    ft.Container(
                        width=alt_width,
                        content=AppText(
                            f"{chr(65 + a_idx)}) {str(alt)}",
                            variant="body_s",
                            dark=dark,
                            max_lines=4,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=bg,
                        border=border,
                        border_radius=DS.R_MD,
                        padding=DS.SP_12,
                        on_click=lambda e, ai=a_idx: _selecionar(ai, e),
                    )
                )

            cards_col.controls.append(
                _review_centered_content(ds_card(
                    dark=dark,
                    padding=DS.SP_16,
                    content=ft.Column(
                        [
                            ds_content_text(
                                enunciado or "Questao sem enunciado.",
                                dark=dark,
                                variant="body",
                                weight=DS.FW_SEMI,
                            ),
                            *alt_controls,
                            _adaptive_actions_row(
                                [
                                    ds_btn_ghost("Anterior", on_click=_prev, dark=dark) if idx > 0 else None,
                                    ds_btn_ghost("Pular", on_click=_skip_question, dark=dark, icon=ft.Icons.SKIP_NEXT_OUTLINED) if not confirmado else None,
                                    ds_btn_primary("Confirmar", on_click=_confirmar, dark=dark, icon=ft.Icons.CHECK_ROUNDED, disabled=selecao is None or confirmado)
                                    if not confirmado
                                    else ds_btn_secondary("Proxima", on_click=_next_after_confirm, dark=dark, icon=ft.Icons.CHEVRON_RIGHT),
                                ],
                                page=page,
                                spacing=DS.SP_8,
                            ),
                        ],
                        spacing=DS.SP_8,
                    ),
                ), page)
            )

    _render_card()
    header_row = _adaptive_actions_row(
        [
            ds_btn_ghost("Revisao", on_click=lambda _: navigate("/revisao"), dark=dark, icon=ft.Icons.ARROW_BACK),
            ds_section_title(titulo_modo, dark=dark),
        ],
        page=page,
        spacing=DS.SP_10,
    )
    return ft.Container(
        expand=True,
        padding=DS.SP_16,
        content=ft.Column(
            [
                _review_centered_content(header_row, page),
                _review_centered_content(status_txt, page),
                _review_centered_content(cards_col, page),
            ],
            spacing=DS.SP_8,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
