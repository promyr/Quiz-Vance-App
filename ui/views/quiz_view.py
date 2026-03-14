import time
import asyncio
import os
import re
import random
import unicodedata
import hashlib
import textwrap
from typing import Optional, Any
import flet as ft

from core.helpers.ui_helpers import screen_width, screen_height, build_focus_header, wrap_study_content, status_banner, is_premium_active
from core.ui_route_theme import _normalize_route_path
from core.helpers.ai_helpers import (
    create_user_ai_service,
    resolve_available_provider_keys,
    resolve_provider_switch_options,
    provider_api_field,
    is_ai_quota_exceeded,
    ai_issue_kind,
    schedule_ai_task,
    generation_profile,
)
from core.helpers.file_helpers import normalize_uploaded_file_path, extract_uploaded_material, format_upload_info_label, pick_study_files
from ui.design_system import DS, AppText, ds_card, ds_btn_primary, ds_btn_ghost, ds_empty_state, ds_toast, ds_bottom_sheet, ds_section_title, ds_stat_card, ds_badge, ds_divider, ds_skeleton, ds_skeleton_card, ds_chip, ds_btn_secondary, ds_progress_bar, ds_icon_btn, ds_action_bar, ds_content_text
from core.error_monitor import log_exception
from core.ui_route_theme import _color
from core.ui_async_guard import state_async_guard
from core.helpers.ui_helpers import close_dialog_compat, show_dialog_compat, show_confirm_dialog, set_feedback_text, show_upgrade_dialog, show_quota_dialog, show_api_issue_dialog, backend_user_id
from core.ui_text_sanitizer import _sanitize_payload_texts, _fix_mojibake_text, _sanitize_control_texts
from core.helpers.ai_helpers import emit_opt_in_event, build_quiz_stats_event_payload
from config import AI_PROVIDERS, CORES, DIFICULDADES
from core.mock_exam_runtime import (
    new_quiz_session,
    reset_runtime_state,
    track_question_time,
)
from core.library_service import LibraryService
from core.services.mock_exam_service import MockExamService
from core.services.mock_exam_report_service import MockExamReportService
from core.services.quiz_filter_service import QuizFilterService
from core.repositories.question_progress_repository import QuestionProgressRepository


def has_quiz_generation_context(topic: str = "", referencia: Optional[list[Any]] = None) -> bool:
    if str(topic or "").strip():
        return True
    if isinstance(referencia, list):
        return any(str(item or "").strip() for item in referencia)
    return bool(referencia)


def build_quiz_body(state, navigate, dark: bool):
    page = state.get("page")
    current_route = _normalize_route_path(getattr(page, "route", "/quiz")) if page else "/quiz"
    simulado_route_active = current_route in {"/simulado", "/simulado/sessao"}
    screen_w = screen_width(page) if page else 1280
    compact = screen_w < 1000
    very_compact = screen_w < 760
    field_w_small = max(140, min(220, int(screen_w - 120)))
    user = state.get("usuario") or {}
    db = state.get("db")
    library_service = LibraryService(db) if db else None

    # Persistencia por rota para evitar vazamento de estado entre /quiz e /simulado.
    # Compatibilidade: reaproveita sessao legada unica somente quando bate com o modo da rota atual.
    quiz_sessions = state.get("quiz_sessions")
    if not isinstance(quiz_sessions, dict):
        quiz_sessions = {}
        state["quiz_sessions"] = quiz_sessions
    session_key = "simulado" if simulado_route_active else "questoes"
    session = quiz_sessions.get(session_key)
    if not session:
        legacy = state.get("quiz_session")
        if isinstance(legacy, dict):
            legacy_estado = legacy.get("estado") or {}
            legacy_is_simulado = bool(legacy_estado.get("simulado_mode"))
            if legacy_is_simulado == bool(simulado_route_active):
                session = legacy
    if not session:
        session = new_quiz_session(simulado_mode_default=simulado_route_active)
        # alinhar filtros default esperados
        session["estado"]["advanced_filters_draft"] = QuizFilterService.empty_filters()
        session["estado"]["advanced_filters_applied"] = QuizFilterService.empty_filters()
    quiz_sessions[session_key] = session
    # Mantem ponteiro da sessao ativa para compatibilidade interna.
    state["quiz_session"] = session

    questoes = session["questoes"]
    estado = session["estado"]
    estado.setdefault("respostas", {})
    estado.setdefault("corrigido", False)
    estado.setdefault("favoritas", set())
    estado.setdefault("marcadas_erro", set())
    estado.setdefault("current_idx", 0)
    estado.setdefault("feedback_imediato", True)
    estado.setdefault("simulado_mode", False)
    estado.setdefault("modo_continuo", False)
    estado.setdefault("start_time", None)
    estado.setdefault("confirmados", set())
    estado.setdefault("puladas", set())
    estado.setdefault("show_secondary_tools", False)
    if "ui_stage" not in estado:
        estado["ui_stage"] = "study" if bool(questoes) else "config"
    estado.setdefault("advanced_filters_draft", QuizFilterService.empty_filters())
    estado.setdefault("advanced_filters_applied", QuizFilterService.empty_filters())
    estado.setdefault("mock_exam_session_id", None)
    estado.setdefault("mock_exam_started_at", None)
    estado.setdefault("prova_deadline", None)
    estado.setdefault("tempo_limite_s", None)
    estado.setdefault("simulado_report", None)
    estado.setdefault("simulado_items", [])
    estado.setdefault("question_time_ms", {})
    estado.setdefault("question_last_ts", None)
    estado.setdefault("stats_synced_idxs", set())
    estado.setdefault("source_lock_material", False)
    estado.setdefault("simulado_infinite", False)
    estado.setdefault("infinite_batch_size", 5)
    estado.setdefault("prefetch_inflight", False)
    estado.setdefault("upload_texts", [])
    estado.setdefault("upload_names", [])
    estado.setdefault("upload_selected_names", [])
    cards_column = ft.Column(
        spacing=12,
        expand=False,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    mapa_prova_wrap = ft.Row(wrap=True, spacing=6, run_spacing=6)
    mapa_prova_container = ft.Container(
        visible=False,
        padding=10,
        border_radius=10,
        bgcolor=_color("card", dark),
        content=ft.Column(
            [
                ft.Text("Mapa da prova", size=12, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                mapa_prova_wrap,
            ],
            spacing=8,
        ),
    )
    simulado_report_column = ft.Column(controls=[], spacing=DS.SP_8, visible=False)
    resultado = ft.Text("", weight=ft.FontWeight.BOLD)
    resultado_box = ft.Container(
        padding=10,
        border_radius=8,
        bgcolor=_color("card", dark),
        content=resultado,
        visible=False,
    )
    carregando = ft.ProgressRing(width=30, height=30, visible=False)
    status_text = ft.Text("", size=12, weight=ft.FontWeight.W_400, color=_color("texto_sec", dark))
    status_estudo = ft.Text("", size=12, weight=ft.FontWeight.W_400, color=_color("texto_sec", dark))
    status_box = status_text
    status_box.visible = False
    status_estudo_box = status_estudo
    status_estudo_box.visible = False
    recomendacao_text = ft.Text("", size=12, weight=ft.FontWeight.W_400, color=_color("texto_sec", dark), visible=False)
    recomendacao_button = ft.ElevatedButton("Proxima acao", icon=ft.Icons.NAVIGATE_NEXT, visible=False)
    contador_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    progresso_text = ft.Text("0/0 respondidas", size=12, color=_color("texto_sec", dark))
    tempo_text = ft.Text("Tempo: 00:00", size=12, color=_color("texto_sec", dark))
    preview_count_text = ft.Text("10", size=13, weight=ft.FontWeight.BOLD, color=_color("texto", dark))
    etapa_text = ft.Text("Etapa 1 de 2: configure e gere", size=13, weight=ft.FontWeight.W_500, color=_color("texto_sec", dark))
    filtro_resumo_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    upload_info = ft.Text(
        "Nenhum material anexado.",
        size=12,
        weight=ft.FontWeight.W_600,
        color=_color("texto", dark),
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    material_source_hint = ft.Text(
        "Voce pode continuar so com o topico ou anexar um material para orientar a IA.",
        size=11,
        color=_color("texto_sec", dark),
        visible=True,
    )
    material_helper_text = ft.Text(
        "Anexe um PDF/TXT ou use um arquivo da biblioteca. Quando houver material, a IA prioriza esse conteudo na geracao.",
        size=12,
        color=_color("texto_sec", dark),
    )
    material_status_label = ft.Text("Opcional", size=11, weight=ft.FontWeight.W_500, color=DS.WHITE)
    material_status_chip = ft.Container(
        content=material_status_label,
        bgcolor=DS.G_500,
        border_radius=DS.R_PILL,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
    )
    clear_material_button = ft.TextButton("Limpar material", icon=ft.Icons.DELETE_OUTLINE)
    material_clear_container = ft.Container(content=clear_material_button, visible=False)
    material_state_panel = ft.Container(
        padding=ft.padding.symmetric(horizontal=DS.SP_12, vertical=DS.SP_10),
        border=ft.border.all(1, DS.with_opacity(DS.P_500, 0.20)),
        border_radius=DS.R_MD,
        bgcolor=DS.with_opacity(DS.P_500, 0.08),
    )
    ai_enabled = bool(create_user_ai_service(user))
    study_footer_actions = ft.ResponsiveRow([], run_spacing=6, spacing=10, visible=True)

    def _sync_resultado_box_visibility():
        resultado_box.visible = bool(str(resultado.value or "").strip()) and bool(estado.get("corrigido"))

    dificuldade_padrao = "intermediario" if "intermediario" in DIFICULDADES else next(iter(DIFICULDADES))
    difficulty_dropdown = ft.Dropdown(
        label="Dificuldade",
        width=field_w_small if compact else 220,
        options=[ft.dropdown.Option(key=key, text=cfg["nome"]) for key, cfg in DIFICULDADES.items()],
        value=dificuldade_padrao,
    )
    quiz_count_options = [
        ft.dropdown.Option(key="10", text="10 questoes"),
        ft.dropdown.Option(key="20", text="20 questoes"),
        ft.dropdown.Option(key="30", text="30 questoes"),
    ]
    if simulado_route_active:
        quiz_count_options.append(ft.dropdown.Option(key="inf", text="Continuo"))
    else:
        quiz_count_options.append(ft.dropdown.Option(key="cont", text="Continuo"))
    quiz_count_dropdown = ft.Dropdown(
        label="Quantidade",
        width=field_w_small if compact else 240,
        options=quiz_count_options,
        value="30" if simulado_route_active else "10",
    )
    def _on_count_change(e):
        val = e.control.value or "10"
        preview_count_text.value = "\u221e" if val in {"cont", "inf"} else str(val)
        if page:
            page.update()
    quiz_count_dropdown.on_change = _on_count_change
    preview_count_text.value = "\u221e" if quiz_count_dropdown.value in {"cont", "inf"} else str(quiz_count_dropdown.value or "10")
    session_mode_dropdown = ft.Dropdown(
        label="Sessao",
        width=field_w_small if compact else 220,
        options=[
            ft.dropdown.Option(key="nova", text="Nova sessao"),
            ft.dropdown.Option(key="erradas", text="Erradas recentes"),
            ft.dropdown.Option(key="favoritas", text="Favoritas"),
            ft.dropdown.Option(key="nao_resolvidas", text="Nao resolvidas"),
        ],
        value="nova",
    )
    simulado_mode_switch = ft.Switch(value=bool(estado.get("simulado_mode", False)))
    simulado_time_field = ft.TextField(
        label="Tempo (min)",
        width=field_w_small if compact else 180,
        keyboard_type=ft.KeyboardType.NUMBER,
        value=str(max(5, int((estado.get("tempo_limite_s") or (60 * 60)) / 60))),
    )
    feedback_policy_text = ft.Text("", size=11, color=_color("texto_sec", dark), no_wrap=False, max_lines=2)

    def _sync_feedback_policy_ui():
        is_prova = bool(simulado_mode_switch.value)
        estado["simulado_mode"] = is_prova
        estado["feedback_imediato"] = not is_prova
        feedback_policy_text.value = (
            "Feedback: correcao apenas ao encerrar a prova."
            if is_prova
            else "Feedback: imediato (sempre ativo fora do modo prova)."
        )

    def _on_simulado_mode_change(_=None):
        _sync_feedback_policy_ui()
        if page:
            page.update()

    simulado_mode_switch.on_change = _on_simulado_mode_change
    _sync_feedback_policy_ui()
    save_filter_name = ft.TextField(label="Salvar filtro como", width=field_w_small if compact else 240, hint_text="Ex.: Revisao Direito")
    saved_filters_dropdown = ft.Dropdown(label="Filtros salvos", width=field_w_small if compact else 280, options=[])

    preset = state.pop("quiz_preset", None)
    preset_auto_start = bool(isinstance(preset, dict) and preset.get("auto_start"))
    package_questions = state.pop("quiz_package_questions", None)

    topic_field = ft.TextField(
        label="Topico (opcional)",
        hint_text="Ex.: Direito Administrativo ou Sistemas Distribuidos",
        expand=True,
    )
    referencia_field = ft.TextField(
        label="Conteudo de referencia (opcional)",
        hint_text="Cole texto, resumo ou instrucoes especificas para a IA.",
        expand=True,
        min_lines=3,
        max_lines=6,
        multiline=True,
    )
    advanced_section_labels = {
        "disciplinas": "Disciplinas",
        "assuntos": "Assuntos",
        "bancas": "Bancas",
        "cargos": "Cargos",
        "anos": "Anos",
        "status": "Status",
    }
    advanced_filters_button = ft.OutlinedButton("Filtros avancados (0)", icon=ft.Icons.TUNE)
    advanced_filters_hint = ft.Text("Sem filtros avancados", size=11, color=_color("texto_sec", dark))

    def _get_applied_advanced_filters() -> dict:
        return QuizFilterService.normalize_filters(estado.get("advanced_filters_applied") or {})

    def _set_applied_advanced_filters(value: dict):
        estado["advanced_filters_applied"] = QuizFilterService.normalize_filters(value)
        total = QuizFilterService.selection_count(estado["advanced_filters_applied"])
        advanced_filters_button.text = f"Filtros avancados ({total})"
        if total > 0:
            advanced_filters_hint.value = QuizFilterService.summary(estado["advanced_filters_applied"], max_items=8)
            advanced_filters_hint.visible = True
            filtro_resumo_text.value = f"Filtro ativo: {advanced_filters_hint.value}"
            filtro_resumo_text.visible = True
        else:
            advanced_filters_hint.value = ""
            advanced_filters_hint.visible = False
            filtro_resumo_text.value = ""
            filtro_resumo_text.visible = False

    def _open_advanced_filters_dialog(_=None):
        if not page:
            return
        estado["advanced_filters_draft"] = QuizFilterService.normalize_filters(_get_applied_advanced_filters())
        search_map = {sec: "" for sec in QuizFilterService.SECTIONS}
        dialog_ref = {"dlg": None}

        def _toggle_chip(section: str, option_id: str):
            draft = QuizFilterService.normalize_filters(estado.get("advanced_filters_draft") or {})
            estado["advanced_filters_draft"] = QuizFilterService.toggle_value(draft, section, option_id)
            _render_dialog_content()
            page.update()

        def _set_search(section: str, value: str):
            search_map[section] = str(value or "")
            _render_dialog_content()
            page.update()

        def _render_section(section: str) -> ft.Control:
            draft = QuizFilterService.normalize_filters(estado.get("advanced_filters_draft") or {})
            selected = set(draft.get(section) or [])
            options = QuizFilterService.filtered_options(section, search_map.get(section) or "")
            chips = [
                ds_chip(
                    str(item.get("label") or item.get("id") or ""),
                    selected=str(item.get("id") or "") in selected,
                    on_click=lambda _, s=section, oid=str(item.get("id") or ""): _toggle_chip(s, oid),
                    dark=dark,
                    small=True,
                )
                for item in options
            ]
            if not chips:
                chips = [ft.Text("Nenhuma opcao para este filtro.", size=11, color=_color("texto_sec", dark))]
            return ds_card(
                dark=dark,
                padding=DS.SP_12,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(advanced_section_labels.get(section, section.title()), size=13, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                                ft.Container(expand=True),
                                ds_badge(str(len(selected)), color=DS.P_500 if len(selected) else DS.G_500),
                            ]
                        ),
                        ft.TextField(
                            label="Buscar",
                            hint_text=f"Filtrar {advanced_section_labels.get(section, section)}",
                            value=search_map.get(section) or "",
                            on_change=lambda e, s=section: _set_search(s, getattr(e.control, "value", "")),
                            dense=True,
                        ),
                        ft.Row(chips, wrap=True, spacing=6),
                    ],
                    spacing=8,
                ),
            )

        def _render_dialog_content():
            draft = QuizFilterService.normalize_filters(estado.get("advanced_filters_draft") or {})
            total = QuizFilterService.selection_count(draft)
            dialog_ref["dlg"].title = ft.Text(f"Filtros avancados ({total})")
            dialog_ref["dlg"].content = ft.Container(
                width=min(980, max(420, int(screen_width(page) * 0.92))),
                height=min(760, max(460, int(screen_height(page) * 0.86))),
                content=ft.Column(
                    [
                        ft.Text(
                            "Aplique filtros por secoes com busca e contadores.",
                            size=12,
                            color=_color("texto_sec", dark),
                        ),
                        _render_section("disciplinas"),
                        _render_section("assuntos"),
                        _render_section("bancas"),
                        _render_section("cargos"),
                        _render_section("anos"),
                        _render_section("status"),
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.ALWAYS,
                ),
            )

        def _apply_filters(_):
            _set_applied_advanced_filters(estado.get("advanced_filters_draft") or {})
            close_dialog_compat(page, dialog_ref["dlg"])
            set_feedback_text(status_text, "Filtros avancados aplicados.", "success")
            if page:
                ds_toast(page, "Filtros avancados aplicados.", tipo="sucesso")
            _refresh_status_boxes()
            page.update()

        def _clear_filters(_):
            estado["advanced_filters_draft"] = QuizFilterService.empty_filters()
            _render_dialog_content()
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Filtros avancados"),
            content=ft.Container(),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: close_dialog_compat(page, dlg)),
                ft.TextButton("Limpar", on_click=_clear_filters),
                ft.ElevatedButton("Aplicar", on_click=_apply_filters),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dialog_ref["dlg"] = dlg
        _render_dialog_content()
        show_dialog_compat(page, dlg)

    advanced_filters_button.on_click = _open_advanced_filters_dialog

    if isinstance(preset, dict):
        topic_field.value = str(preset.get("topic") or "")
        difficulty_dropdown.value = str(preset.get("difficulty") or dificuldade_padrao)
        quiz_count_dropdown.value = str(preset.get("count") or "10")
        preview_count_text.value = "\u221e" if quiz_count_dropdown.value in {"cont", "inf"} else str(quiz_count_dropdown.value or "10")
        session_mode_dropdown.value = str(preset.get("session_mode") or "nova")
        simulado_mode_switch.value = bool(preset.get("simulado_mode", False))
        _sync_feedback_policy_ui()
        if preset.get("simulado_tempo") is not None:
            try:
                estado["tempo_limite_s"] = max(300, int(preset.get("simulado_tempo")) * 60)
            except Exception:
                estado["tempo_limite_s"] = 60 * 60
        _set_applied_advanced_filters(preset.get("advanced_filters") or {})
        status_text.value = str(preset.get("reason") or "Preset aplicado.")
    else:
        _set_applied_advanced_filters(estado.get("advanced_filters_applied") or {})
    if simulado_route_active:
        session_mode_dropdown.value = "nova"
        simulado_mode_switch.value = True
        _sync_feedback_policy_ui()

    # dropdown da biblioteca
    library_opts = []
    if library_service and user.get("id"):
        library_files = library_service.listar_arquivos(user["id"])
        library_opts = [ft.dropdown.Option(str(f["id"]), text=f["nome_arquivo"]) for f in library_files]

    def _guess_topic_from_name(raw_name: str) -> str:
        nome = str(raw_name or "").strip()
        if nome.startswith("[LIB]"):
            nome = nome[5:].strip()
        nome = os.path.basename(nome)
        guess = os.path.splitext(nome)[0].replace("_", " ").replace("-", " ").strip()
        return " ".join(guess.split())[:64]

    def _infer_topic_from_uploaded_texts(texts: list[str]) -> str:
        if not texts:
            return ""
        candidates: list[str] = []
        preferred: list[str] = []
        for raw in texts[:3]:
            for ln in str(raw or "").splitlines()[:140]:
                line = " ".join(str(ln or "").strip().split())
                if len(line) < 12 or len(line) > 110:
                    continue
                low = line.lower()
                if re.fullmatch(r"[\d\W_]+", line):
                    continue
                if any(
                    token in low
                    for token in (
                        "isbn",
                        "issn",
                        "autor",
                        "elaborador",
                        "ediÃ§Ã£o",
                        "edicao",
                        "versÃ£o",
                        "versao",
                        "sumÃ¡rio",
                        "sumario",
                        "copyright",
                        "todos os direitos",
                    )
                ):
                    continue
                if line.isupper() and len(line) <= 48:
                    continue
                if any(token in low for token in ("capÃ­tulo", "capitulo", "seÃ§Ã£o", "secao", "tema", "tÃ³pico", "topico")):
                    preferred.append(line)
                candidates.append(line)
        for raw in (preferred + candidates):
            words = [w for w in re.split(r"\s+", raw) if w]
            if 3 <= len(words) <= 14:
                return raw[:72]
        return (preferred[0] if preferred else (candidates[0] if candidates else ""))[:72]

    def _resolve_theme_value() -> str:
        manual = str(topic_field.value or "").strip()
        if manual:
            return manual
        inferred = _infer_topic_from_uploaded_texts(list(estado.get("upload_texts") or []))
        if inferred:
            return inferred
        names = list(estado.get("upload_names") or estado.get("upload_selected_names") or [])
        for raw_name in names:
            guessed = _guess_topic_from_name(raw_name)
            if guessed:
                return guessed
        return ""

    def _on_library_select(e):
        fid = e.control.value
        if not fid: return

        nome = next((f["nome_arquivo"] for f in library_files if str(f["id"]) == fid), "Arquivo Biblioteca")
        nome_tag = f"[LIB] {nome}"
        texto = library_service.get_conteudo_arquivo(int(fid))
        estado["upload_selected_names"] = [nome_tag]
        if texto:
            # Biblioteca selecionada vira a fonte principal (sem misturar com anexos antigos).
            estado["upload_texts"] = [texto]
            estado["upload_names"] = [nome_tag]
            if not str(topic_field.value or "").strip():
                guessed = _guess_topic_from_name(nome_tag)
                if guessed:
                    topic_field.value = guessed
            session_mode_dropdown.value = "nova"
            _set_upload_info()
            status_text.value = f"Adicionado da biblioteca: {nome}"
        else:
            estado["upload_texts"] = []
            estado["upload_names"] = []
            _set_upload_info()
            set_feedback_text(status_text, "Arquivo da biblioteca sem texto extraivel.", "warning")
        # Resetar dropdown para permitir selecionar outro
        e.control.value = None
        e.control.update()
        if page:
            page.update()

    library_dropdown = ft.Dropdown(
        label="Ou escolher da biblioteca",
        options=library_opts,
        disabled=not library_opts,
        expand=True,
    )
    library_dropdown.on_change = _on_library_select

    def _normalize_question_for_ui(q: dict) -> Optional[dict]:
        if not isinstance(q, dict):
            return None
        q = _sanitize_payload_texts(q)
        enunciado = _fix_mojibake_text(str(q.get("enunciado") or q.get("pergunta") or "")).strip()
        alternativas = q.get("alternativas") or q.get("opcoes") or []
        if not enunciado or not isinstance(alternativas, list) or len(alternativas) < 2:
            return None
        alternativas = [
            _fix_mojibake_text(str(a)).strip()
            for a in alternativas
            if _fix_mojibake_text(str(a)).strip()
        ]
        if len(alternativas) < 2:
            return None
        alternativas_ui = alternativas[:4]
        correta_idx = q.get("correta_index", q.get("correta", 0))
        try:
            correta_idx = int(correta_idx)
        except Exception:
            correta_idx = 0
        if len(alternativas) > 4 and correta_idx >= 4:
            # Evita recortar alternativas e manter gabarito errado.
            return None
        correta_idx = max(0, min(correta_idx, len(alternativas_ui) - 1))
        out = {
            "enunciado": enunciado,
            "alternativas": alternativas_ui,
            "correta_index": correta_idx,
        }
        if q.get("explicacao"):
            out["explicacao"] = _fix_mojibake_text(str(q.get("explicacao")))
        if q.get("tema"):
            out["tema"] = _fix_mojibake_text(str(q.get("tema")))
        if q.get("assunto"):
            out["assunto"] = _fix_mojibake_text(str(q.get("assunto")))
        elif q.get("subtema"):
            out["assunto"] = _fix_mojibake_text(str(q.get("subtema")))
        if q.get("_meta"):
            out["_meta"] = _sanitize_payload_texts(q.get("_meta"))
        return out

    def _current_filter_payload() -> dict:
        count_raw = str(quiz_count_dropdown.value or "5")
        count_val = int(count_raw) if count_raw.isdigit() else count_raw
        return {
            "topic": (topic_field.value or "").strip(),
            "difficulty": difficulty_dropdown.value or dificuldade_padrao,
            "count": count_val,
            "session_mode": session_mode_dropdown.value or "nova",
            "feedback_imediato": not bool(simulado_mode_switch.value),
            "simulado_mode": bool(simulado_mode_switch.value),
            "advanced_filters": _get_applied_advanced_filters(),
        }

    def _load_saved_filters():
        if not db or not user.get("id"):
            saved_filters_dropdown.options = []
            return
        try:
            filtros = db.listar_filtros_quiz(user["id"])
            saved_filters_dropdown.options = [
                ft.dropdown.Option(key=str(f["id"]), text=f["nome"])
                for f in filtros
            ]
            saved_filters_dropdown.data = {str(f["id"]): f for f in filtros}
        except Exception as ex:
            log_exception(ex, "main._build_quiz_body._load_saved_filters")
            saved_filters_dropdown.options = []
            saved_filters_dropdown.data = {}

    def _apply_saved_filter(e):
        key = e.control.value
        if not key:
            return
        data_map = getattr(saved_filters_dropdown, "data", {}) or {}
        item = data_map.get(key)
        if not isinstance(item, dict):
            return
        filtro = item.get("filtro", {})
        if not isinstance(filtro, dict):
            filtro = {}
        topic_field.value = filtro.get("topic", "")
        difficulty_dropdown.value = filtro.get("difficulty", dificuldade_padrao)
        quiz_count_dropdown.value = str(filtro.get("count", 5))
        preview_count_text.value = "\u221e" if (quiz_count_dropdown.value or "") in {"cont", "inf"} else str(quiz_count_dropdown.value or "10")
        session_mode_dropdown.value = filtro.get("session_mode", "nova")
        simulado_mode_switch.value = bool(filtro.get("simulado_mode", False))
        _sync_feedback_policy_ui()
        _set_applied_advanced_filters(filtro.get("advanced_filters") or {})
        status_text.value = f"Filtro aplicado: {item.get('nome', '')}"
        if page:
            ds_toast(page, f"Filtro aplicado: {item.get('nome', '')}", tipo="sucesso")
            page.update()

    def _save_current_filter(_):
        if not db or not user.get("id"):
            set_feedback_text(status_text, "Entre na conta para salvar filtros (backup e sync).", "warning")
            _refresh_status_boxes()
            if page:
                page.update()
            navigate("/login")
            return
        nome = (save_filter_name.value or "").strip()
        if not nome:
            status_text.value = "Informe um nome para salvar o filtro."
            if page:
                page.update()
            return
        try:
            db.salvar_filtro_quiz(user["id"], nome, _current_filter_payload())
            emit_opt_in_event(user, "save_filter_clicked", "quiz_filter")
            save_filter_name.value = ""
            _load_saved_filters()
            status_text.value = f"Filtro salvo: {nome}"
            if page:
                ds_toast(page, f"Filtro salvo: {nome}", tipo="sucesso")
                page.update()
        except Exception as ex:
            log_exception(ex, "main._build_quiz_body._save_current_filter")
            status_text.value = "Falha ao salvar filtro."
            if page:
                page.update()

    def _delete_selected_filter(_):
        if not db or not user.get("id"):
            return
        key = saved_filters_dropdown.value
        if not key:
            status_text.value = "Selecione um filtro salvo para excluir."
            if page:
                page.update()
            return
        def _confirmed_delete():
            try:
                db.excluir_filtro_quiz(int(key), user["id"])
                saved_filters_dropdown.value = None
                _load_saved_filters()
                status_text.value = "Filtro excluido."
                if page:
                    ds_toast(page, "Filtro excluido.", tipo="sucesso")
                    page.update()
            except Exception as ex:
                log_exception(ex, "main._build_quiz_body._delete_selected_filter")
                if page:
                    ds_toast(page, "Falha ao excluir filtro.", tipo="erro")

        show_confirm_dialog(
            page,
            "Excluir filtro",
            "Deseja excluir o filtro salvo selecionado?",
            _confirmed_delete,
            confirm_label="Excluir",
        )

    saved_filters_dropdown.on_change = _apply_saved_filter

    def _update_session_meta():
        total = len(questoes)
        respondidas = len([k for k, v in estado["respostas"].items() if v is not None])
        if bool(estado.get("simulado_mode")) and bool(estado.get("corrigido")):
            report = estado.get("simulado_report") or {}
            total_report = int(report.get("total") or 0)
            if total_report <= 0:
                total_report = total
            progresso_text.value = f"{max(0, total_report)}/{max(0, total)} respondidas"
            tempo_text.value = "Tempo restante: 00:00"
            return
        progresso_text.value = f"{respondidas}/{total} respondidas"
        if estado.get("simulado_mode") and estado.get("prova_deadline"):
            restante = int(max(0, float(estado.get("prova_deadline") or 0) - time.monotonic()))
            tempo_text.value = f"Tempo restante: {restante // 60:02d}:{restante % 60:02d}"
        elif estado.get("start_time"):
            elapsed = int(max(0, time.monotonic() - estado["start_time"]))
            tempo_text.value = f"Tempo: {elapsed // 60:02d}:{elapsed % 60:02d}"
        else:
            tempo_text.value = "Tempo: 00:00"

    def _refresh_status_boxes():
        in_study = str(estado.get("ui_stage") or "config") == "study"
        status_box.visible = bool(status_text.value.strip()) and (not in_study)
        status_estudo_box.visible = bool(status_estudo.value.strip()) and in_study

    def _refresh_simulado_report_mode():
        has_report_payload = bool(estado.get("simulado_report")) or bool(simulado_report_column.controls)
        report_mode = bool(estado.get("simulado_mode")) and bool(estado.get("corrigido")) and has_report_payload
        # Se houve rebuild/navegacao, reconstrui um card minimo a partir do estado persistido.
        if report_mode and not bool(simulado_report_column.controls):
            _ensure_simulado_report_controls_from_state()
            has_report_payload = bool(estado.get("simulado_report")) or bool(simulado_report_column.controls)
        cards_column.visible = not report_mode
        study_footer_actions.visible = not report_mode
        simulado_report_column.visible = bool(report_mode and has_report_payload)
        if report_mode:
            mapa_prova_container.visible = False
            mapa_prova_wrap.controls = []

    def _refresh_filter_summary():
        total = QuizFilterService.selection_count(_get_applied_advanced_filters())
        text = QuizFilterService.summary(_get_applied_advanced_filters(), max_items=8)
        if total > 0:
            filtro_resumo_text.value = f"Filtro ativo: {text}"
            filtro_resumo_text.visible = True
        else:
            filtro_resumo_text.value = ""
            filtro_resumo_text.visible = False

    def _set_upload_info():
        names = estado["upload_names"] or estado.get("upload_selected_names") or []
        names_label = format_upload_info_label(names)
        has_material_text = bool(estado.get("upload_texts"))
        material_clear_container.visible = bool(names or has_material_text)
        if has_material_text:
            upload_info.value = names_label
            material_source_hint.value = "Pronto para gerar questoes com base nesse material. O app usa essa fonte como prioridade."
            material_status_label.value = "Pronto"
            material_status_chip.bgcolor = DS.SUCESSO
            panel_icon = ft.Icons.CHECK_CIRCLE_OUTLINE
            panel_icon_color = DS.SUCESSO
            panel_bg = DS.with_opacity(DS.SUCESSO, 0.08)
            panel_border = ft.border.all(1, DS.with_opacity(DS.SUCESSO, 0.28))
        elif names:
            upload_info.value = names_label
            material_source_hint.value = "Arquivo selecionado, mas sem texto extraido. Use um PDF pesquisavel, TXT ou outro material."
            material_status_label.value = "Atencao"
            material_status_chip.bgcolor = DS.WARNING
            panel_icon = ft.Icons.WARNING_AMBER_ROUNDED
            panel_icon_color = DS.WARNING
            panel_bg = DS.with_opacity(DS.WARNING, 0.10)
            panel_border = ft.border.all(1, DS.with_opacity(DS.WARNING, 0.30))
        else:
            upload_info.value = "Nenhum material anexado"
            material_source_hint.value = "Voce pode gerar so com o topico ou anexar um material para deixar a geracao mais precisa."
            material_status_label.value = "Opcional"
            material_status_chip.bgcolor = DS.G_500
            panel_icon = ft.Icons.AUTO_AWESOME_OUTLINED
            panel_icon_color = DS.P_500 if not dark else DS.P_300
            panel_bg = DS.with_opacity(DS.P_500, 0.08)
            panel_border = ft.border.all(1, DS.with_opacity(DS.P_500, 0.20))
        material_state_panel.bgcolor = panel_bg
        material_state_panel.border = panel_border
        material_state_panel.content = ft.Row(
            [
                ft.Icon(panel_icon, size=18, color=panel_icon_color),
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        [
                            upload_info,
                            material_source_hint,
                        ],
                        spacing=3,
                    ),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

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
            log_exception(ex, "main._build_quiz_body._pick_files_async")
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
                    (
                        "Nao foi possivel extrair texto dos arquivos. "
                        "Para PDF, confirme que nao e imagem escaneada ou protegido por senha."
                    ),
                    "warning",
                )
            else:
                if failed_names:
                    set_feedback_text(
                        status_text,
                        f"Material carregado: {len(upload_texts)} arquivo(s). Ignorados: {len(failed_names)}.",
                        "warning",
                    )
                else:
                    set_feedback_text(status_text, f"Material carregado: {len(upload_texts)} arquivo(s).", "success")
                session_mode_dropdown.value = "nova"
            _set_upload_info()

        await guard.run(
            "quiz.upload.files",
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
            estado["source_lock_material"] = False
            _set_upload_info()
            set_feedback_text(status_text, "Material removido.", "info")
            if page:
                ds_toast(page, "Material removido.", tipo="info")
                page.update()

        show_confirm_dialog(
            page,
            "Limpar material",
            "Deseja remover todo material anexado desta sessao?",
            _confirmed_clear,
            confirm_label="Limpar",
        )

    clear_material_button.on_click = _limpar_material

    material_entry_section = ds_card(
        dark=dark,
        padding=DS.SP_12,
        shadow=False,
        border_radius=DS.R_MD,
        border_color=DS.border_color(dark, 0.12),
        bgcolor=DS.with_opacity(DS.P_500, 0.04),
        content=ft.Column(
            [
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "md": 8},
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.UPLOAD_FILE, size=18, color=DS.P_500 if not dark else DS.P_300),
                                            ft.Text(
                                                "Usar material como base",
                                                size=14,
                                                weight=ft.FontWeight.W_600,
                                                color=_color("texto", dark),
                                            ),
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    material_helper_text,
                                ],
                                spacing=4,
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "md": 4},
                            content=ft.Row(
                                [
                                    material_status_chip,
                                    ft.Container(expand=True),
                                    material_clear_container,
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ],
                    spacing=10,
                    run_spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "md": 4},
                            content=ds_btn_primary("Anexar PDF/TXT", icon=ft.Icons.UPLOAD_FILE, on_click=_upload_material, expand=True, dark=dark),
                        ),
                        ft.Container(col={"xs": 12, "md": 8}, content=library_dropdown),
                    ],
                    run_spacing=6,
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                material_state_panel,
            ],
            spacing=DS.SP_10,
        ),
    )

    async def _on_explain_click(q_idx):
        if not page: return
        
        # Mostrar loading
        dlg = ft.AlertDialog(
            title=ft.Text("Consultando IA..."),
            content=ft.Column([ft.ProgressRing(), ft.Text("Gerando explicacao simplificada...")], tight=True, alignment=ft.MainAxisAlignment.CENTER),
            modal=True
        )
        show_dialog_compat(page, dlg)
        
        # Obter dados
        questao = questoes[q_idx]
        pergunta_txt = _fix_mojibake_text(str(questao.get("enunciado") or ""))
        correta_idx = questao.get("correta_index", 0)
        alternativas = list(questao.get("alternativas") or [])
        correta_idx = max(0, min(int(correta_idx or 0), max(0, len(alternativas) - 1)))
        resposta_txt = _fix_mojibake_text(str(alternativas[correta_idx] if alternativas else ""))
        
        # Chamar AI
        service = create_user_ai_service(user)
        explicacao = "Erro ao conectar com IA."
        if service:
            explicacao = await asyncio.to_thread(service.explain_simple, pergunta_txt, resposta_txt)
        explicacao = _fix_mojibake_text(str(explicacao or ""))
            
        # Fechar loading e mostrar resultado
        close_dialog_compat(page, dlg)
        
        await asyncio.sleep(0.1)
        
        res_dlg = ft.AlertDialog(
            title=ft.Text("Explicacao Simplificada"),
            content=ft.Text(explicacao, size=15),
            actions=[ft.TextButton("Entendi", on_click=lambda e: close_dialog_compat(page, res_dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        show_dialog_compat(page, res_dlg)

    def _persist_question_flags(qidx: int, tentativa_correta: Optional[bool] = None):
        if not db or not user.get("id"):
            return
        if qidx < 0 or qidx >= len(questoes):
            return
        q = questoes[qidx]
        tema = (topic_field.value or "").strip() or q.get("tema", "Geral")
        dificuldade = difficulty_dropdown.value or dificuldade_padrao
        try:
            db.registrar_questao_usuario(
                user["id"],
                q,
                tema=tema,
                dificuldade=dificuldade,
                tentativa_correta=tentativa_correta,
                favorita=(qidx in estado["favoritas"]),
                marcado_erro=(qidx in estado["marcadas_erro"]),
            )
        except Exception as ex:
            log_exception(ex, "main._build_quiz_body._persist_question_flags")

    async def _push_quiz_stats_event_immediate_async(payload: dict) -> None:
        backend_ref = state.get("backend")
        backend_uid = backend_user_id(user)
        if not (backend_ref and backend_ref.enabled()):
            return
        if int(backend_uid or 0) <= 0:
            return
        try:
            await asyncio.to_thread(
                backend_ref.sync_quiz_stats_batch,
                int(backend_uid),
                [payload or {}],
            )
        except Exception as ex_push:
            log_exception(ex_push, "main._build_quiz_body.push_quiz_stats_event_immediate")

    def _persist_realtime_quiz_stats(qidx: int, tentativa_correta: bool) -> None:
        if not db or not user.get("id"):
            return
        if bool(estado.get("simulado_mode")):
            return
        synced = estado.setdefault("stats_synced_idxs", set())
        if qidx in synced:
            return
        try:
            delta = db.registrar_resposta_quiz_tempo_real(int(user["id"]), bool(tentativa_correta), xp_por_acerto=10)
            synced.add(qidx)
            payload = None
            try:
                payload = build_quiz_stats_event_payload(bool(tentativa_correta), delta or {})
                db.enqueue_quiz_stats_event(int(user["id"]), str(payload.get("event_id") or ""), payload)
            except Exception as ex_enqueue:
                log_exception(ex_enqueue, "main._build_quiz_body.enqueue_quiz_stats_event")
            if payload and page:
                try:
                    page.run_task(_push_quiz_stats_event_immediate_async, dict(payload))
                except Exception as ex_immediate:
                    log_exception(ex_immediate, "main._build_quiz_body.schedule_immediate_stats_push")
            if state.get("usuario"):
                state["usuario"]["xp"] = int(state["usuario"].get("xp", 0) or 0) + int(delta.get("xp_ganho", 0) or 0)
                state["usuario"]["acertos"] = int(state["usuario"].get("acertos", 0) or 0) + int(delta.get("acertos_delta", 0) or 0)
                state["usuario"]["total_questoes"] = int(state["usuario"].get("total_questoes", 0) or 0) + int(
                    delta.get("questoes_delta", 0) or 0
                )
                state["usuario"]["streak_dias"] = int(delta.get("streak_dias", state["usuario"].get("streak_dias", 0)) or 0)
        except Exception as ex:
            log_exception(ex, "main._build_quiz_body._persist_realtime_quiz_stats")

    def _is_skipped_question(qidx: int) -> bool:
        return int(qidx) in set(estado.get("puladas") or set())

    def _is_finalized_question(qidx: int) -> bool:
        return int(qidx) in set(estado.get("confirmados") or set())

    def _find_navigable_index(current_idx: int, step: int) -> Optional[int]:
        idx = int(current_idx) + int(step)
        while 0 <= idx < len(questoes):
            if not _is_skipped_question(idx):
                return idx
            idx += int(step)
        return None

    def _maybe_schedule_prefetch(current_idx: int) -> None:
        if not page:
            return
        if not bool(estado.get("modo_continuo")):
            return
        if bool(estado.get("prefetch_inflight")):
            return
        prefetch_batch_size = max(1, int(estado.get("infinite_batch_size") or 5))
        if len(questoes) - int(current_idx) > prefetch_batch_size:
            return
        estado["prefetch_inflight"] = True
        try:
            page.run_task(_prefetch_one_async)
        except Exception:
            estado["prefetch_inflight"] = False

    def _next_question(_=None):
        if not questoes:
            return
        idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
        _maybe_schedule_prefetch(idx)
        simulado_mode_active = bool(estado.get("simulado_mode"))
        if (not simulado_mode_active) and (not _is_finalized_question(idx)):
            set_feedback_text(status_estudo, "Para avancar, confirme a resposta ou use Pular.", "warning")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        target_idx = (idx + 1) if simulado_mode_active else _find_navigable_index(idx, +1)

        # Trata o bloqueio de final de lista se NÃƒO for modo continuo/infinito
        is_continuous = bool(estado.get("modo_continuo")) or bool(estado.get("simulado_infinite"))
        if target_idx is not None and target_idx >= len(questoes):
            if not is_continuous:
                target_idx = None  # bloqueia no fim da prova
            else:
                # No modo continuo, pode ser apenas atraso do prefetch
                pass # target_idx continua apontando pro futuro (pode causar IndexError se nÃ£o tratado no _go_to_question/_rebuild_cards)

        if target_idx is None or target_idx >= len(questoes):
            if is_continuous:
                 set_feedback_text(status_estudo, "Gerando mais questoes... aguarde.", "info")
            else:
                 set_feedback_text(status_estudo, "Nao ha proxima questao disponivel.", "info")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        track_question_time(estado, questoes)
        estado["current_idx"] = int(target_idx)
        _persist_mock_progress()
        _maybe_schedule_prefetch(int(target_idx))
        _rebuild_cards()
        if page:
            page.update()

    def _prev_question(_=None):
        if not questoes:
            return
        idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
        simulado_mode_active = bool(estado.get("simulado_mode"))
        target_idx = (idx - 1) if simulado_mode_active else _find_navigable_index(idx, -1)
        if simulado_mode_active and target_idx < 0:
            target_idx = None
        if target_idx is None:
            set_feedback_text(status_estudo, "Nao ha questao anterior disponivel.", "info")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        track_question_time(estado, questoes)
        estado["current_idx"] = int(target_idx)
        _persist_mock_progress()
        _rebuild_cards()
        if page:
            page.update()

    def _skip_question(_=None):
        if bool(estado.get("simulado_mode")):
            set_feedback_text(status_estudo, "Modo simulado: pular desativado.", "info")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        if not questoes:
            return
        idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
        if _is_finalized_question(idx):
            set_feedback_text(status_estudo, "Questao ja finalizada.", "info")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        estado["respostas"][idx] = None
        estado["puladas"].add(idx)
        estado["confirmados"].add(idx)
        _persist_mock_progress()
        _next_question()

    def _toggle_favorita(_=None):
        qidx = estado.get("current_idx", 0)
        if qidx in estado["favoritas"]:
            estado["favoritas"].remove(qidx)
        else:
            estado["favoritas"].add(qidx)
        _persist_question_flags(qidx, None)
        _rebuild_cards()
        if page:
            page.update()

    def _toggle_marcada_erro(_=None):
        qidx = estado.get("current_idx", 0)
        if qidx in estado["marcadas_erro"]:
            estado["marcadas_erro"].remove(qidx)
        else:
            estado["marcadas_erro"].add(qidx)
        _persist_question_flags(qidx, None)
        _rebuild_cards()
        if page:
            page.update()

    def _report_question_issue(_=None):
        if not questoes:
            return
        qidx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
        estado["marcadas_erro"].add(qidx)
        _persist_question_flags(qidx, None)
        set_feedback_text(status_estudo, "Questao reportada e marcada para revisao.", "info")
        _refresh_status_boxes()
        _rebuild_cards()
        if page:
            page.update()

    timer_ref = {"token": 0, "task": None}

    def _cancel_timer_task():
        task = timer_ref.get("task")
        if task and hasattr(task, "cancel"):
            try:
                task.cancel()
            except Exception:
                pass
        timer_ref["task"] = None

    def _reset_mock_exam_runtime(clear_mode: bool = False):
        _cancel_timer_task()
        reset_runtime_state(estado, clear_mode=clear_mode)
        simulado_report_column.visible = False
        simulado_report_column.controls = []

    def _question_simulado_meta(question: dict) -> dict:
        meta = question.get("_meta") or {}
        disciplina = str(meta.get("disciplina") or question.get("tema") or topic_field.value or "Geral").strip() or "Geral"
        assunto = str(meta.get("assunto") or question.get("assunto") or "Geral").strip() or "Geral"
        return {"disciplina": disciplina, "assunto": assunto, "tema": disciplina}

    def _looks_like_material_metadata_question(q: dict) -> bool:
        raw = str((q or {}).get("enunciado") or (q or {}).get("pergunta") or "").strip()
        if not raw:
            return False
        t = " ".join(raw.lower().split())
        if not ("?" in raw or raw.endswith(":")):
            return False
        if re.search(r"\b(?:ema|ciaa)\s*[-/]?\s*\d+(?:\s*[./-]\s*\d+)?\b", t):
            return True
        has_editorial = any(tok in t for tok in ("manual", "publicacao", "guia", "sumario", "prefacio", "introducao", "codigo"))
        if has_editorial and re.search(r"\b(objetivo|finalidade|introducao|prefacio|sumario|classifica)\b", t):
            return True
        if re.search(r"\bde acordo com o?\s*(ema|ciaa)\b", t):
            return True
        if re.search(r"\bconforme\s+apresentado\s+no\s+contexto\s+do\b", t):
            return True
        if re.search(r"\bcurso\s+especial\s+de\s+habilitacao\b", t):
            return True
        if re.search(r"\bpromocao\s+a\s+sargentos\b", t):
            return True
        return False

    def _list_wrong_questions_from_state() -> list[dict]:
        wrong_questions: list[dict] = []
        seen_stems: set[str] = set()
        for item in (estado.get("simulado_items") or []):
            if str(item.get("resultado") or "").strip().lower() != "wrong":
                continue
            raw_q = item.get("question") or {}
            if not isinstance(raw_q, dict):
                continue
            qnorm = _normalize_question_for_ui(raw_q)
            if not qnorm:
                continue
            stem = str(qnorm.get("enunciado") or qnorm.get("pergunta") or "").strip().lower()
            if stem and stem in seen_stems:
                continue
            if stem:
                seen_stems.add(stem)
            wrong_questions.append(dict(qnorm))
        return wrong_questions

    def _review_wrong_from_state(_=None):
        wrong_questions = _list_wrong_questions_from_state()
        if not wrong_questions:
            set_feedback_text(status_estudo, "Sem questoes erradas para revisar.", "info")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        questoes[:] = [dict(q) for q in wrong_questions]
        _reset_mock_exam_runtime(clear_mode=True)
        estado["current_idx"] = 0
        estado["respostas"] = {}
        estado["confirmados"] = set()
        estado["puladas"] = set()
        estado["show_secondary_tools"] = False
        estado["stats_synced_idxs"] = set()
        estado["corrigido"] = False
        estado["ui_stage"] = "study"
        estado["question_last_ts"] = time.monotonic()
        resultado.value = ""
        _sync_resultado_box_visibility()
        set_feedback_text(status_estudo, "Revisao de erradas iniciada.", "success")
        _rebuild_cards()
        if page:
            page.update()

    def _add_wrong_to_notebook_from_state(_=None):
        wrong_questions = _list_wrong_questions_from_state()
        if not (db and user.get("id") and wrong_questions):
            set_feedback_text(status_estudo, "Sem questoes erradas para adicionar.", "info")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        try:
            qrepo = QuestionProgressRepository(db)
            for q in wrong_questions:
                qrepo.register_result(int(user["id"]), q, "mark")
            set_feedback_text(status_estudo, "Erradas adicionadas ao caderno de revisao.", "success")
        except Exception as ex:
            log_exception(ex, "main._build_quiz_body._add_wrong_to_notebook_from_state")
            set_feedback_text(status_estudo, "Falha ao adicionar erradas ao caderno.", "error")
        _refresh_status_boxes()
        if page:
            page.update()

    def _flashcards_from_wrong_from_state(_=None):
        wrong_questions = _list_wrong_questions_from_state()
        if not wrong_questions:
            set_feedback_text(status_estudo, "Sem questoes erradas para gerar flashcards.", "info")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        seeds = []
        for q in wrong_questions[:15]:
            en = str(q.get("enunciado") or q.get("pergunta") or "").strip()
            alts = q.get("alternativas") or q.get("opcoes") or []
            try:
                cidx = int(q.get("correta_index", q.get("correta", 0)) or 0)
            except Exception:
                cidx = 0
            cidx = max(0, min(cidx, max(0, len(alts) - 1)))
            correta_txt = str(alts[cidx] if alts else "").strip()
            if en and correta_txt:
                seeds.append({"frente": en, "verso": correta_txt, "tema": str(q.get("tema") or topic_field.value or "Geral")})
        state["flashcards_seed_cards"] = seeds
        navigate("/flashcards")

    def _ensure_simulado_report_controls_from_state():
        if bool(simulado_report_column.controls):
            return
        report = estado.get("simulado_report") or {}
        if not isinstance(report, dict) or not report:
            return
        total = int(report.get("total") or len(questoes) or 0)
        acertos = int(report.get("acertos") or 0)
        erros = int(report.get("erros") or 0)
        puladas = int(report.get("puladas") or 0)
        score_pct = float(report.get("score_pct") or 0.0)
        tempo_total_s = int(report.get("tempo_total_s") or 0)
        tempo_medio_s = int(report.get("tempo_medio_s") or 0)
        simulado_report_column.controls = [
            ds_card(
                dark=dark,
                padding=DS.SP_12,
                shadow=False,
                border_color=DS.border_color(dark, 0.16),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                AppText("Relatorio do simulado", variant="h3", dark=dark, weight=ft.FontWeight.W_700),
                                ft.Container(expand=True),
                                ds_badge(f"{total} itens", color=DS.P_500),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        AppText(
                            f"Score: {score_pct:.1f}% | Acertos: {acertos} | Erros: {erros} | Puladas: {puladas}",
                            variant="body",
                            dark=dark,
                        ),
                        AppText(
                            f"Tempo total: {tempo_total_s}s | Tempo medio: {tempo_medio_s}s",
                            variant="caption",
                            dark=dark,
                            color=_color("texto_sec", dark),
                        ),
                        ds_action_bar(
                            [
                                {"label": "Novo simulado", "icon": ft.Icons.RESTART_ALT, "on_click": _novo_simulado_config, "kind": "ghost"},
                                {"label": "Revisar erradas", "icon": ft.Icons.AUTO_FIX_HIGH, "on_click": _review_wrong_from_state, "kind": "primary"},
                                {"label": "Adicionar ao caderno", "icon": ft.Icons.BOOKMARK_ADD_OUTLINED, "on_click": _add_wrong_to_notebook_from_state, "kind": "warning"},
                                {"label": "Gerar flashcards", "icon": ft.Icons.STYLE_OUTLINED, "on_click": _flashcards_from_wrong_from_state, "kind": "ghost"},
                            ],
                            dark=dark,
                        ),
                    ],
                    spacing=10,
                ),
            )
        ]
        simulado_report_column.visible = True

    def _persist_mock_progress():
        if not (db and user.get("id") and estado.get("simulado_mode") and estado.get("mock_exam_session_id")):
            return
        try:
            db.salvar_mock_exam_progresso(
                int(estado.get("mock_exam_session_id")),
                int(estado.get("current_idx") or 0),
                dict(estado.get("respostas") or {}),
            )
        except Exception as ex:
            log_exception(ex, "main._build_quiz_body._persist_mock_progress")

    def _render_mapa_prova():
        if not questoes or not bool(estado.get("simulado_mode")):
            mapa_prova_container.visible = False
            mapa_prova_wrap.controls = []
            return
        mapa_prova_wrap.controls = []
        for idx in range(len(questoes)):
            skipped = _is_skipped_question(idx)
            answered = (estado.get("respostas") or {}).get(idx) is not None
            confirmed = _is_finalized_question(idx)
            is_current = idx == int(estado.get("current_idx") or 0)
            if is_current:
                color = DS.P_500
            elif skipped:
                color = DS.ERRO
            elif confirmed and answered:
                color = DS.SUCESSO
            elif answered:
                color = DS.WARNING
            else:
                color = DS.G_500
            mapa_prova_wrap.controls.append(
                ft.Container(
                    width=32,
                    height=32,
                    alignment=ft.Alignment(0, 0),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.16, color),
                    border=ft.border.all(1, color),
                    content=ft.Text(str(idx + 1), size=11, weight=ft.FontWeight.W_600, color=color),
                    on_click=(None if skipped else (lambda _, i=idx: _go_to_question(i))),
                )
            )
        mapa_prova_container.visible = True

    def _go_to_question(idx: int):
        if not questoes:
            return
        idx = int(max(0, min(len(questoes) - 1, int(idx))))
        current_idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
        if (not bool(estado.get("simulado_mode"))) and idx != current_idx and _is_skipped_question(idx):
            set_feedback_text(status_estudo, "Questao pulada e bloqueada para retorno.", "warning")
            _refresh_status_boxes()
            if page:
                page.update()
            return
        track_question_time(estado, questoes)
        estado["current_idx"] = idx
        _persist_mock_progress()
        _maybe_schedule_prefetch(idx)
        _rebuild_cards()
        if page:
            page.update()

    def _ensure_mock_exam_session(total_questoes: int):
        if not (db and user.get("id") and bool(estado.get("simulado_mode"))):
            return
        if estado.get("mock_exam_session_id"):
            return
        try:
            tempo_total_s = int(max(0, estado.get("tempo_limite_s") or 0))
            filtro_snapshot = _current_filter_payload()
            sid = db.criar_mock_exam_session(
                int(user["id"]),
                filtro_snapshot=filtro_snapshot,
                total_questoes=int(max(1, total_questoes)),
                tempo_total_s=tempo_total_s,
                modo="timed" if tempo_total_s > 0 else "treino",
            )
            estado["mock_exam_session_id"] = int(sid)
            estado["mock_exam_started_at"] = time.monotonic()
            _persist_mock_progress()
        except Exception as ex:
            log_exception(ex, "main._build_quiz_body._ensure_mock_exam_session")

    async def _cronometro_task(token: int):
        while True:
            if token != timer_ref.get("token"):
                return
            if not bool(estado.get("simulado_mode")):
                return
            deadline = float(estado.get("prova_deadline") or 0)
            if deadline <= 0:
                return
            restante = int(max(0, deadline - time.monotonic()))
            _update_session_meta()
            if page:
                page.update()
            if restante <= 0:
                try:
                    corrigir(None, forcar_timeout=True)
                except Exception as ex:
                    log_exception(ex, "main._build_quiz_body._cronometro_task.timeout")
                return
            await asyncio.sleep(1.0)

    def _rebuild_cards():
        cards_column.controls.clear()
        _sync_resultado_box_visibility()
        sw = screen_width(page) if page else 1280
        mobile = sw < 760
        q_font = 16 if sw < 520 else (18 if sw < 760 else (21 if sw < 1000 else 26))
        if not questoes:
            cards_column.controls.append(
                ft.Container(
                    padding=14,
                    border_radius=10,
                    bgcolor=_color("card", dark),
                    content=ft.Text("Nenhuma questao carregada.", color=_color("texto_sec", dark)),
                )
            )
            contador_text.value = "0 questoes prontas"
            progresso_text.value = "0/0 respondidas"
            tempo_text.value = "Tempo: 00:00"
            mapa_prova_container.visible = False
            mapa_prova_wrap.controls = []
            _refresh_simulado_report_mode()
            _refresh_status_boxes()
            return

        idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
        estado["current_idx"] = idx
        pergunta = _normalize_question_for_ui(questoes[idx]) or _sanitize_payload_texts(dict(questoes[idx]))
        if isinstance(pergunta, dict):
            questoes[idx] = dict(pergunta)
        options = []
        correta_idx = int(pergunta.get("correta_index", pergunta.get("correta", 0)) or 0)
        selected = estado["respostas"].get(idx)
        is_corrigido = estado["corrigido"]
        if not estado.get("simulado_mode") and idx in estado["confirmados"]:
            is_corrigido = True

        def _on_change(e):
            if estado["corrigido"] or idx in estado["confirmados"] or _is_skipped_question(idx):
                return
            valor = getattr(e.control, "value", None)
            if valor in (None, ""):
                valor = getattr(e.control, "data", None)
            if valor in (None, ""):
                valor = getattr(e, "data", None)
            try:
                estado["respostas"][idx] = int(valor) if valor not in (None, "", "null") else None
            except Exception:
                estado["respostas"][idx] = None
            if idx in estado["puladas"]:
                estado["puladas"].discard(idx)
            if idx in estado["confirmados"]:
                estado["confirmados"].discard(idx)
            _persist_mock_progress()
            _update_session_meta()
            _rebuild_cards()
            if page:
                page.update()

        alternativas = list(pergunta.get("alternativas") or [])
        for i, alt in enumerate(alternativas):
            fill_color = CORES["primaria"]
            opacity = 1.0
            if is_corrigido and selected is not None:
                if i == correta_idx:
                    fill_color = CORES["sucesso"]
                elif i == selected and i != correta_idx:
                    fill_color = CORES["erro"]
                else:
                    opacity = 0.55
            option_text = " ".join(str(alt or "").replace("\r", "\n").split())
            bg_color = ft.Colors.TRANSPARENT
            border_color = _color("borda", dark)
            is_selected = (selected == i)
            if is_selected:
                border_color = CORES["primaria"]
                bg_color = CORES["primaria"] + "11"
            
            if is_corrigido and selected is not None:
                if i == correta_idx:
                    border_color = CORES["sucesso"]
                    bg_color = CORES["sucesso"] + "11"
                elif i == selected and i != correta_idx:
                    border_color = CORES["erro"]
                    bg_color = CORES["erro"] + "11"

            opt_container = ft.Container(
                content=ft.Row(
                    [
                        ft.Radio(value=str(i), fill_color=fill_color),
                        ft.Text(option_text, expand=True, size=15, color=_color("texto", dark), weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.NORMAL)
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=8,
                border=ft.border.all(1.5 if is_selected else 1, border_color),
                bgcolor=bg_color,
                opacity=opacity,
                data=str(i),
                on_click=_on_change,
                ink=True,
                disabled=estado.get("corrigido") or idx in estado.get("confirmados", set())
            )
            options.append(opt_container)

        header_badges = []
        if idx in estado["favoritas"]:
            header_badges.append(ft.Icon(ft.Icons.STAR, color=CORES["warning"], size=18))
        if idx in estado["marcadas_erro"]:
            header_badges.append(ft.Icon(ft.Icons.FLAG, color=CORES["erro"], size=18))

        question_content_controls = [
            ft.Row(
                [
                    ft.Text(f"Questao {idx + 1}/{len(questoes)}", size=13, color=_color("texto_sec", dark)),
                    ft.Container(expand=True),
                    *header_badges,
                ]
            ),
            ft.Container(
                alignment=ft.Alignment(-1, 0),
                padding=ft.padding.only(top=2, bottom=4),
                content=ds_content_text(
                    _fix_mojibake_text(str(pergunta.get("enunciado") or "")),
                    dark=dark,
                    variant="h3",
                    selectable=True,
                    size=q_font,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.LEFT,
                ),
            ),
            ft.RadioGroup(
                key=f"quiz-rg-{idx}",
                value=str(selected) if selected is not None else None,
                on_change=_on_change,
                content=ft.Column(options, spacing=6, tight=True),
                disabled=estado["corrigido"] or idx in estado["confirmados"],
            ),
        ]

        if selected is not None and (estado["corrigido"] or idx in estado["confirmados"]):
            feedback_color = CORES["sucesso"] if selected == correta_idx else CORES["erro"]
            feedback_msg = "Correto!" if selected == correta_idx else "Incorreto."
            question_content_controls.append(
                ft.Row(
                    [
                        ft.Text(feedback_msg, color=feedback_color, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "Ver explicacao",
                            icon=ft.Icons.PSYCHOLOGY,
                            on_click=lambda _, i=idx: schedule_ai_task(
                                page,
                                state,
                                _on_explain_click,
                                i,
                                message="IA gerando explicacao simplificada...",
                                status_control=status_text,
                            ),
                            visible=ai_enabled,
                        ),
                    ]
                )
            )
            if selected != correta_idx:

                def _flashcards_do_erro(_=None):
                    card_seed = []
                    en = str(pergunta.get("enunciado") or "")
                    correta_txt = str((pergunta.get("alternativas") or [""])[correta_idx] if (pergunta.get("alternativas") or []) else "")
                    tema_seed = str(topic_field.value or pergunta.get("tema") or "Geral")
                    if en and correta_txt:
                        for n in range(1, 4):
                            card_seed.append(
                                {
                                    "frente": f"[Erro {n}] {en}",
                                    "verso": f"Resposta correta: {correta_txt}",
                                    "tema": tema_seed,
                                }
                            )
                    if card_seed:
                        state["flashcards_seed_cards"] = card_seed
                        navigate("/flashcards")

                def _praticar_assunto(_=None):
                    tema = str(pergunta.get("tema") or topic_field.value or "Geral").strip() or "Geral"
                    topic_field.value = tema
                    quiz_count_dropdown.value = "10"
                    simulado_mode_switch.value = False
                    _sync_feedback_policy_ui()
                    session_mode_dropdown.value = "nova"
                    set_feedback_text(status_text, f"Praticando mais de: {tema}", "info")
                    if page:
                        page.update()
                    _on_gerar_clique(None)

                question_content_controls.append(
                    ft.ResponsiveRow(
                        [
                            ft.Container(
                                col={"xs": 12, "md": 7},
                                content=ft.OutlinedButton(
                                    "Gerar 3 flashcards do erro",
                                    icon=ft.Icons.STYLE_OUTLINED,
                                    on_click=_flashcards_do_erro,
                                    expand=True,
                                ),
                            ),
                            ft.Container(
                                col={"xs": 12, "md": 5},
                                content=ft.TextButton(
                                    "Praticar o tema",
                                    icon=ft.Icons.SCHOOL_OUTLINED,
                                    on_click=_praticar_assunto,
                                ),
                            ),
                        ],
                        run_spacing=6,
                        spacing=8,
                    )
                )

        def _confirm_and_next(_=None):
            if bool(estado.get("simulado_mode")):
                _next_question()
                return
            current_idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0)))) if questoes else 0
            if not _is_finalized_question(current_idx):
                set_feedback_text(status_estudo, "Para avancar, confirme a resposta ou use Pular.", "warning")
                _refresh_status_boxes()
                if page:
                    page.update()
                return
            _next_question()

        compact_label = sw < 520
        prev_label = "Ant." if compact_label else "Anterior"
        next_label = "Prox." if compact_label else "Proxima"
        confirm_label = "Confirmar" if compact_label else "Confirmar resposta"
        fav_label = "Favorito" if compact_label else "Favoritar"
        err_label = "Erro" if compact_label else "Marcar erro"
        rep_label = "Reportar"
        secondary_tools_open = bool(estado.get("show_secondary_tools", False))
        simulado_mode_active = bool(estado.get("simulado_mode"))

        def _toggle_secondary_tools(_=None):
            estado["show_secondary_tools"] = not bool(estado.get("show_secondary_tools", False))
            _rebuild_cards()
            if page:
                page.update()

        note_default = ""
        if db and user.get("id"):
            try:
                note_default = db.obter_nota_questao(user["id"], pergunta)
            except Exception as ex:
                log_exception(ex, "main._build_quiz_body.obter_nota_questao")
        note_default = _fix_mojibake_text(str(note_default or ""))
        # Evita box gigante quando nota salva vem com quebras/markup inesperados.
        note_default = " ".join(note_default.replace("\r", "\n").split())
        if len(note_default) > 260:
            note_default = note_default[:260]
        note_field = ft.TextField(
            label="Anotacao (opcional)",
            value=note_default,
            multiline=False,
            min_lines=1,
            max_lines=1,
            height=46,
            dense=True,
            expand=True,
        )

        def _save_note(_):
            if not db or not user.get("id"):
                return
            try:
                db.salvar_nota_questao(user["id"], pergunta, note_field.value or "")
                status_estudo.value = "Anotacao salva."
                if page:
                    page.update()
            except Exception as ex:
                log_exception(ex, "main._build_quiz_body.salvar_nota_questao")
                status_estudo.value = "Falha ao salvar anotacao."
                if page:
                    page.update()

        nav_controls = [
            ft.Container(
                col={"xs": 4, "md": 3},
                content=ds_btn_secondary(prev_label, icon=ft.Icons.CHEVRON_LEFT, on_click=_prev_question, dark=dark, expand=True),
            ),
            ft.Container(
                col={"xs": 4, "md": 3},
                content=ds_btn_secondary(
                    next_label,
                    icon=ft.Icons.CHEVRON_RIGHT,
                    on_click=(_next_question if simulado_mode_active else _confirm_and_next),
                    disabled=(False if simulado_mode_active else (idx not in estado["confirmados"])),
                    expand=True,
                ),
            ),
        ]
        if not simulado_mode_active:
            nav_controls.insert(
                1,
                ft.Container(
                    col={"xs": 4, "md": 3},
                    content=ds_btn_secondary(
                        "Pular",
                        icon=ft.Icons.SKIP_NEXT,
                        on_click=_skip_question,
                        dark=dark,
                        disabled=idx in estado["confirmados"],
                        expand=True,
                    ),
                ),
            )
            nav_controls.append(
                ft.Container(
                    col={"xs": 12, "md": 3},
                    content=ds_btn_primary(
                        confirm_label,
                        icon=ft.Icons.CHECK_CIRCLE,
                        on_click=_confirmar,
                        disabled=selected is None or idx in estado["confirmados"],
                        expand=True,
                    ),
                ),
            )

        action_section = ft.Column(
            [
                ft.ResponsiveRow(nav_controls, run_spacing=6, spacing=6),
                ft.Container(
                    alignment=ft.Alignment(-1, 0),
                    content=ds_btn_ghost(
                        "Mais acoes" if not secondary_tools_open else "Ocultar acoes",
                        icon=ft.Icons.MORE_HORIZ if not secondary_tools_open else ft.Icons.EXPAND_LESS,
                        on_click=_toggle_secondary_tools,
                        dark=dark,
                    ),
                ),
                ft.Container(
                    visible=secondary_tools_open,
                    content=ft.Column(
                        [
                            ds_action_bar(
                                [
                                    {
                                        "label": fav_label,
                                        "icon": ft.Icons.STAR if idx in estado["favoritas"] else ft.Icons.STAR_BORDER,
                                        "on_click": _toggle_favorita,
                                        "kind": "ghost",
                                    },
                                    {
                                        "label": err_label,
                                        "icon": ft.Icons.FLAG if idx in estado["marcadas_erro"] else ft.Icons.FLAG_OUTLINED,
                                        "on_click": _toggle_marcada_erro,
                                        "kind": "warning",
                                    },
                                    {
                                        "label": rep_label,
                                        "icon": ft.Icons.REPORT_GMAILERRORRED_OUTLINED,
                                        "on_click": _report_question_issue,
                                        "kind": "danger",
                                    },
                                ],
                                dark=dark,
                            ),
                            ft.ResponsiveRow(
                                [
                                    ft.Container(col={"xs": 12, "md": 8}, content=note_field),
                                    ft.Container(
                                        col={"xs": 12, "md": 4},
                                        content=ft.ElevatedButton(
                                            "Salvar anotacao",
                                            icon=ft.Icons.NOTE_ALT,
                                            on_click=_save_note,
                                            expand=True,
                                        ),
                                    ),
                                ],
                                run_spacing=6,
                                spacing=8,
                            ),
                        ],
                        spacing=8,
                    ),
                ),
            ],
            spacing=8,
        )

        cards_column.controls.append(
            ft.Container(
                width=min(980, max(300, int(sw * (0.96 if mobile else 0.82)))),
                content=ds_card(
                    dark=dark,
                    padding=10 if mobile else 12,
                    border_radius=DS.R_XL,
                    shadow=True,
                    content=ft.Column(
                        [
                            ft.Column(question_content_controls, spacing=8),
                            ds_divider(dark),
                            action_section,
                        ],
                        spacing=8,
                    ),
                ),
            )
        )
        if not cards_column.controls and not simulado_report_column.controls:
            cards_column.controls.append(
                ds_card(
                    dark=dark,
                    padding=12,
                    content=ft.Column(
                        [
                            AppText("Nao foi possivel renderizar a questao atual.", variant="body", dark=dark),
                            ds_btn_primary("Recarregar", icon=ft.Icons.REFRESH, on_click=lambda _: _rebuild_cards(), dark=dark),
                        ],
                        spacing=8,
                    ),
                )
            )
        contador_text.value = f"{len(questoes)} questoes prontas"
        _update_session_meta()
        _render_mapa_prova()
        _refresh_simulado_report_mode()
        _sanitize_control_texts(cards_column)

    def _confirmar(_=None):
        if not questoes:
            return
        idx = int(max(0, min(len(questoes) - 1, estado.get("current_idx", 0))))
        pergunta = questoes[idx]
        selected = (estado.get("respostas") or {}).get(idx)
        correta_idx = int(pergunta.get("correta_index", pergunta.get("correta", 0)) or 0)
        if selected is None or idx in estado["confirmados"]:
            return
        track_question_time(estado, questoes)
        if idx in estado["puladas"]:
            estado["puladas"].discard(idx)
        estado["confirmados"].add(idx)
        if not estado.get("simulado_mode"):
            tentativa_correta = selected == correta_idx
            _persist_question_flags(idx, tentativa_correta)
            _persist_realtime_quiz_stats(idx, tentativa_correta)
            status_estudo.value = "Resposta correta." if tentativa_correta else "Resposta incorreta."
        else:
            status_estudo.value = "Resposta registrada para correcao no final."
        _persist_mock_progress()
        _maybe_schedule_prefetch(idx)
        _rebuild_cards()
        if page:
            page.update()

    def _mostrar_etapa_config():
        estado["ui_stage"] = "config"
        etapa_text.value = "Etapa 1 de 2: configure e gere"
        config_section.visible = True
        study_section.visible = False
        _sync_resultado_box_visibility()

    def _mostrar_etapa_estudo():
        if not questoes:
            _mostrar_etapa_config()
            set_feedback_text(status_text, "Gere questoes para iniciar a resolucao.", "info")
            _refresh_status_boxes()
            return
        estado["ui_stage"] = "study"
        etapa_text.value = "Etapa 2 de 2: resolva e corrija"
        config_section.visible = False
        study_section.visible = True
        _sync_resultado_box_visibility()

    def _provider_switch_options() -> list[tuple[str, str]]:
        current_user = state.get("usuario") if isinstance(state.get("usuario"), dict) else user
        return resolve_provider_switch_options(current_user, db=db)

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
            current_user = state.get("usuario") if isinstance(state.get("usuario"), dict) else user
            keys = resolve_available_provider_keys(current_user, db=db)
            active_key = str(keys.get(selected) or "").strip() or None
            user["provider"] = selected
            if next_model:
                user["model"] = next_model
            user["api_key"] = active_key
            for provider_name in ("gemini", "openai", "groq"):
                provider_value = str(keys.get(provider_name) or "").strip() or None
                user[provider_api_field(provider_name)] = provider_value
            if isinstance(state.get("usuario"), dict):
                state["usuario"]["provider"] = selected
                if next_model:
                    state["usuario"]["model"] = next_model
                state["usuario"]["api_key"] = active_key
                for provider_name in ("gemini", "openai", "groq"):
                    provider_value = str(keys.get(provider_name) or "").strip() or None
                    state["usuario"][provider_api_field(provider_name)] = provider_value
            if db and user.get("id") and hasattr(db, "atualizar_provider_ia"):
                db.atualizar_provider_ia(int(user["id"]), selected, next_model or fallback_model)
            state["last_settings_sync_ts"] = time.monotonic()

            backend_ref = state.get("backend")
            backend_uid = backend_user_id(state.get("usuario") or {})

            async def _push_provider_switch_async():
                if not (backend_ref and backend_ref.enabled()):
                    return
                if int(backend_uid or 0) <= 0:
                    return
                try:
                    current_keys = resolve_available_provider_keys(
                        state.get("usuario") if isinstance(state.get("usuario"), dict) else user,
                        db=db,
                    )
                    await asyncio.to_thread(
                        backend_ref.upsert_user_settings,
                        int(backend_uid),
                        selected,
                        next_model or fallback_model,
                        str(current_keys.get(selected) or "").strip() or None,
                        bool(user.get("economia_mode")),
                        bool(user.get("telemetry_opt_in")),
                        api_key_gemini=str(current_keys.get("gemini") or "").strip() or None,
                        api_key_openai=str(current_keys.get("openai") or "").strip() or None,
                        api_key_groq=str(current_keys.get("groq") or "").strip() or None,
                    )
                except Exception as ex_remote:
                    log_exception(ex_remote, "quiz_view.switch_provider_and_retry.sync_remote")

            if page:
                try:
                    page.run_task(_push_provider_switch_async)
                except Exception as ex_task:
                    log_exception(ex_task, "quiz_view.switch_provider_and_retry.schedule_remote")
            provider_name = str(cfg.get("name") or selected)
            set_feedback_text(status_text, f"Provider alterado para {provider_name}. Reexecutando geracao...", "info")
            if page:
                page.update()
            _on_gerar_clique(None)
        except Exception as ex_switch:
            log_exception(ex_switch, "quiz_view.switch_provider_and_retry")

    async def _prefetch_one_async():
        try:
            if not page:
                return
            batch_size = max(1, int(estado.get("infinite_batch_size") or 5))
            filtro = estado.get("ultimo_filtro") or {}
            topic = (filtro.get("topic") or "").strip()
            referencia = filtro.get("referencia") or []
            strict_material_source = bool(filtro.get("source_lock_material"))
            difficulty_key = filtro.get("difficulty") or dificuldade_padrao
            if not has_quiz_generation_context(topic, referencia):
                return
            gen_profile = generation_profile(user, "quiz")
            service = create_user_ai_service(user, force_economic=bool(gen_profile.get("force_economic")))
            novas = []
            if gen_profile.get("delay_s", 0) > 0:
                await asyncio.sleep(float(gen_profile["delay_s"]))
            if is_ai_quota_exceeded(service):
                return
            # Gerar batch inteiro em 1 chamada (evita loop lento)
            if service and (topic or referencia):
                avoid_snippets = [
                    " ".join(str((q.get("enunciado") or q.get("pergunta") or "")).split())[:220]
                    for q in (questoes[-24:] if isinstance(questoes, list) else [])
                    if str(q.get("enunciado") or q.get("pergunta") or "").strip()
                ]
                for _attempt in range(2):
                    try:
                        batch = await asyncio.to_thread(
                            service.generate_quiz_batch,
                            referencia or None,
                            topic or None,
                            DIFICULDADES.get(difficulty_key, {}).get("nome", "Intermediario"),
                            batch_size,
                            2,
                            avoid_snippets,
                        )
                        if batch:
                            for questao in batch:
                                qnorm = _normalize_question_for_ui(questao) if questao else None
                                if qnorm and (not _looks_like_material_metadata_question(qnorm)):
                                    novas.append(dict(qnorm))
                                    questoes.append(dict(qnorm))
                                    if db:
                                        try:
                                            db.salvar_questao_cache(topic or "Geral", difficulty_key, qnorm, user_id=int(user["id"]) if user.get("id") else None)
                                        except Exception as ex:
                                            log_exception(ex, "main._build_quiz_body.prefetch.salvar_questao_cache")
                            if novas:
                                break
                    except Exception as ex:
                        log_exception(ex, "main._build_quiz_body.prefetch")
                        if is_ai_quota_exceeded(service):
                            break
            # Fallback: cache ou defaults
            if not novas and (not strict_material_source) and topic and db:
                try:
                    cached = db.listar_questoes_cache(topic, difficulty_key, batch_size, user_id=int(user["id"]) if user.get("id") else None)
                    for x in cached:
                        qnorm = _normalize_question_for_ui(x)
                        if qnorm and (not _looks_like_material_metadata_question(qnorm)):
                            novas.append(dict(qnorm))
                            questoes.append(dict(qnorm))
                            if len(novas) >= batch_size:
                                break
                except Exception as ex:
                    log_exception(ex, "main._build_quiz_body.prefetch.cache")
            if novas:
                msg_prefix = "Modo continuo"
                set_feedback_text(status_text, f"{msg_prefix}: +{len(novas)} questoes prontas ({len(questoes)} total).", "info")
                _rebuild_cards()
                _refresh_status_boxes()
                if page:
                    page.update()
            elif strict_material_source:
                set_feedback_text(status_text, "Sem novas questoes validas do material no momento.", "warning")
                _refresh_status_boxes()
                if page:
                    page.update()
        finally:
            estado["prefetch_inflight"] = False

    def corrigir(_=None, forcar_timeout: bool = False):
        if not questoes:
            status_estudo.value = "Gere questoes antes de corrigir."
            if page:
                page.update()
            return
        if estado["corrigido"] and not bool(estado.get("simulado_mode")):
            return

        total = len(questoes)
        simulado_mode = bool(estado.get("simulado_mode"))
        puladas_set = set(estado.get("puladas") or set())
        nao_respondidas = [i for i in range(total) if estado["respostas"].get(i) is None and i not in puladas_set]
        if nao_respondidas and (not simulado_mode):
            status_estudo.value = f"Existem {len(nao_respondidas)} questoes sem resposta."
            if page:
                page.update()
            return

        track_question_time(estado, questoes)
        time_map = dict(estado.get("question_time_ms") or {})
        acertos = 0
        erros = 0
        puladas = 0
        items_report = []
        wrong_questions = []

        for idx, q in enumerate(questoes):
            escolhida = estado["respostas"].get(idx)
            correta = int(q.get("correta_index", q.get("correta", 0)) or 0)
            if escolhida is None:
                puladas += 1
                resultado_item = "skip"
                _persist_question_flags(idx, False)
            elif int(escolhida) == correta:
                acertos += 1
                resultado_item = "correct"
                _persist_question_flags(idx, True)
            else:
                erros += 1
                resultado_item = "wrong"
                wrong_questions.append(q)
                _persist_question_flags(idx, False)

            items_report.append(
                {
                    "ordem": idx + 1,
                    "question": q,
                    "resultado": resultado_item,
                    "resposta_index": (None if escolhida is None else int(escolhida)),
                    "correta_index": int(correta),
                    "tempo_ms": int(time_map.get(idx, 0) or 0),
                    "meta": _question_simulado_meta(q),
                }
            )

        xp = acertos * 10
        db_local = state["db"]
        if state.get("usuario") and db_local:
            if simulado_mode:
                db_local.registrar_resultado_quiz(state["usuario"]["id"], acertos, total, xp)
                state["usuario"]["xp"] += xp
                state["usuario"]["acertos"] += acertos
                state["usuario"]["total_questoes"] += total
                try:
                    progresso = db_local.obter_progresso_diario(state["usuario"]["id"])
                    state["usuario"]["streak_dias"] = int(progresso.get("streak_dias", state["usuario"].get("streak_dias", 0)))
                except Exception:
                    pass
            else:
                synced = estado.setdefault("stats_synced_idxs", set())
                for idx, q in enumerate(questoes):
                    escolhida = estado["respostas"].get(idx)
                    if escolhida is None or idx in synced:
                        continue
                    correta = int(q.get("correta_index", q.get("correta", 0)) or 0)
                    _persist_realtime_quiz_stats(idx, int(escolhida) == correta)

        # Simulado: persistencia de itens + finalizacao + relatorio
        if simulado_mode and db_local and user.get("id"):
            _cancel_timer_task()
            _ensure_mock_exam_session(total)
            sid = int(estado.get("mock_exam_session_id") or 0)
            if sid > 0:
                try:
                    for item in items_report:
                        db_local.registrar_mock_exam_item(
                            session_id=sid,
                            ordem=int(item["ordem"]),
                            question=dict(item["question"]),
                            meta=dict(item["meta"] or {}),
                            resposta_index=item["resposta_index"],
                            correta_index=item["correta_index"],
                            tempo_ms=int(item.get("tempo_ms") or 0),
                        )
                    tempo_total_s = 0
                    if estado.get("mock_exam_started_at"):
                        tempo_total_s = int(max(0, time.monotonic() - float(estado.get("mock_exam_started_at"))))
                    elif estado.get("start_time"):
                        tempo_total_s = int(max(0, time.monotonic() - float(estado.get("start_time"))))
                    score_pct = (acertos / max(1, total)) * 100.0
                    db_local.finalizar_mock_exam_session(
                        sid,
                        acertos=acertos,
                        erros=erros,
                        puladas=puladas,
                        score_pct=score_pct,
                        tempo_gasto_s=tempo_total_s,
                    )
                except Exception as ex:
                    log_exception(ex, "main._build_quiz_body.corrigir.finalizar_mock_exam")

            report = MockExamReportService.summarize_items(items_report)
            estado["simulado_items"] = list(items_report)
            estado["simulado_report"] = dict(report)

            def _review_wrong(_=None):
                if not wrong_questions:
                    set_feedback_text(status_estudo, "Sem questoes erradas para revisar.", "info")
                    _refresh_status_boxes()
                    if page:
                        page.update()
                    return
                questoes[:] = [
                    dict(qn)
                    for qn in (_normalize_question_for_ui(q) for q in wrong_questions)
                    if qn
                ]
                _reset_mock_exam_runtime(clear_mode=True)
                estado["current_idx"] = 0
                estado["respostas"] = {}
                estado["confirmados"] = set()
                estado["puladas"] = set()
                estado["show_secondary_tools"] = False
                estado["stats_synced_idxs"] = set()
                estado["corrigido"] = False
                estado["ui_stage"] = "study"
                estado["question_last_ts"] = time.monotonic()
                resultado.value = ""
                _sync_resultado_box_visibility()
                set_feedback_text(status_estudo, "Revisao de erradas iniciada.", "success")
                _rebuild_cards()
                if page:
                    page.update()

            def _add_wrong_to_notebook(_=None):
                if not (db_local and user.get("id") and wrong_questions):
                    set_feedback_text(status_estudo, "Sem questoes erradas para adicionar.", "info")
                    _refresh_status_boxes()
                    if page:
                        page.update()
                    return
                try:
                    qrepo = QuestionProgressRepository(db_local)
                    for q in wrong_questions:
                        qrepo.register_result(int(user["id"]), q, "mark")
                    set_feedback_text(status_estudo, "Erradas adicionadas ao caderno de revisao.", "success")
                except Exception as ex:
                    log_exception(ex, "main._build_quiz_body._add_wrong_to_notebook")
                    set_feedback_text(status_estudo, "Falha ao adicionar erradas ao caderno.", "error")
                _refresh_status_boxes()
                if page:
                    page.update()

            def _flashcards_from_wrong(_=None):
                if not wrong_questions:
                    set_feedback_text(status_estudo, "Sem questoes erradas para gerar flashcards.", "info")
                    _refresh_status_boxes()
                    if page:
                        page.update()
                    return
                seeds = []
                for q in wrong_questions[:15]:
                    en = str(q.get("enunciado") or q.get("pergunta") or "").strip()
                    alts = q.get("alternativas") or q.get("opcoes") or []
                    try:
                        cidx = int(q.get("correta_index", q.get("correta", 0)) or 0)
                    except Exception:
                        cidx = 0
                    cidx = max(0, min(cidx, max(0, len(alts) - 1)))
                    correta_txt = str(alts[cidx] if alts else "").strip()
                    if en and correta_txt:
                        seeds.append({"frente": en, "verso": correta_txt, "tema": str(q.get("tema") or topic_field.value or "Geral")})
                state["flashcards_seed_cards"] = seeds
                navigate("/flashcards")

            def _metric_block(title: str, value: str, color: str) -> ft.Control:
                return ds_card(
                    dark=dark,
                    padding=DS.SP_8,
                    shadow=False,
                    border_color=DS.border_color(dark, 0.14),
                    content=ft.Column(
                        [
                            AppText(title, variant="caption", dark=dark, color=DS.text_sec_color(dark)),
                            AppText(value, variant="h3", dark=dark, color=color, weight=ft.FontWeight.W_700),
                        ],
                        spacing=3,
                    ),
                )

            by_disc = report.get("by_disciplina") or {}
            by_ass = report.get("by_assunto") or {}
            score_pct = float(report.get("score_pct") or 0.0)
            tempo_total_s = int(report.get("tempo_total_s", 0) or 0)
            tempo_medio_s = int(report.get("tempo_medio_s", 0) or 0)

            disc_controls = [AppText("Por disciplina", variant="label", dark=dark, weight=ft.FontWeight.W_600)]
            for name, stats in list(by_disc.items())[:6]:
                ratio = float(stats.get("acertos", 0)) / max(1, int(stats.get("total", 0)))
                disc_controls.append(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    AppText(str(name), variant="caption", dark=dark),
                                    ft.Container(expand=True),
                                    AppText(
                                        f"{int(stats.get('acertos', 0))}/{int(stats.get('total', 0))}",
                                        variant="caption",
                                        dark=dark,
                                        color=_color("texto_sec", dark),
                                    ),
                                ]
                            ),
                            ds_progress_bar(ratio, dark=dark, color=DS.P_500, height=7),
                        ],
                        spacing=3,
                    )
                )
            if len(disc_controls) == 1:
                disc_controls.append(AppText("Sem dados de disciplina.", variant="caption", dark=dark, color=_color("texto_sec", dark)))

            ass_controls = [AppText("Por assunto", variant="label", dark=dark, weight=ft.FontWeight.W_600)]
            for name, stats in list(by_ass.items())[:6]:
                ratio = float(stats.get("acertos", 0)) / max(1, int(stats.get("total", 0)))
                ass_controls.append(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    AppText(str(name), variant="caption", dark=dark),
                                    ft.Container(expand=True),
                                    AppText(
                                        f"{int(stats.get('acertos', 0))}/{int(stats.get('total', 0))}",
                                        variant="caption",
                                        dark=dark,
                                        color=_color("texto_sec", dark),
                                    ),
                                ]
                            ),
                            ds_progress_bar(ratio, dark=dark, color=DS.A_500, height=7),
                        ],
                        spacing=3,
                    )
                )
            if len(ass_controls) == 1:
                ass_controls.append(AppText("Sem dados de assunto.", variant="caption", dark=dark, color=_color("texto_sec", dark)))

            try:
                simulado_report_column.controls = [
                    ds_card(
                        dark=dark,
                        padding=DS.SP_12,
                        shadow=False,
                        border_color=DS.border_color(dark, 0.16),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        AppText("Relatorio do simulado", variant="h3", dark=dark, weight=ft.FontWeight.W_700),
                                        ft.Container(expand=True),
                                        ds_badge(f"{total} itens", color=DS.P_500),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(col={"xs": 6, "md": 3}, content=_metric_block("Score", f"{score_pct:.1f}%", DS.P_500)),
                                        ft.Container(col={"xs": 6, "md": 3}, content=_metric_block("Acertos", str(acertos), DS.SUCESSO)),
                                        ft.Container(col={"xs": 6, "md": 3}, content=_metric_block("Erros", str(erros), DS.ERRO)),
                                        ft.Container(col={"xs": 6, "md": 3}, content=_metric_block("Puladas", str(puladas), DS.WARNING)),
                                    ],
                                    spacing=8,
                                    run_spacing=8,
                                ),
                                ft.Container(
                                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                                    border_radius=DS.R_MD,
                                    bgcolor=DS.with_opacity(DS.INFO, 0.08),
                                    border=ft.border.all(1, DS.with_opacity(DS.INFO, 0.28)),
                                    content=ft.Row(
                                        [
                                            ft.Icon(ft.Icons.TIMER_OUTLINED, size=16, color=DS.INFO),
                                            AppText(f"Tempo total: {tempo_total_s}s", variant="caption", dark=dark),
                                            ft.Container(width=8),
                                            AppText("|", variant="caption", dark=dark, color=DS.text_sec_color(dark)),
                                            ft.Container(width=8),
                                            ft.Icon(ft.Icons.SPEED, size=16, color=DS.INFO),
                                            AppText(f"Tempo medio: {tempo_medio_s}s", variant="caption", dark=dark),
                                        ],
                                        wrap=True,
                                        spacing=4,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ),
                                ds_divider(dark),
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(
                                            col={"xs": 12, "md": 6},
                                            content=ds_card(
                                                dark=dark,
                                                shadow=False,
                                                padding=DS.SP_10,
                                                border_color=DS.border_color(dark, 0.14),
                                                content=ft.Column(disc_controls, spacing=5),
                                            ),
                                        ),
                                        ft.Container(
                                            col={"xs": 12, "md": 6},
                                            content=ds_card(
                                                dark=dark,
                                                shadow=False,
                                                padding=DS.SP_10,
                                                border_color=DS.border_color(dark, 0.14),
                                                content=ft.Column(ass_controls, spacing=5),
                                            ),
                                        ),
                                    ],
                                    spacing=8,
                                    run_spacing=8,
                                ),
                                ds_action_bar(
                                    [
                                        {
                                            "label": "Novo simulado",
                                            "icon": ft.Icons.RESTART_ALT,
                                            "on_click": _novo_simulado_config,
                                            "kind": "ghost",
                                        },
                                        {
                                            "label": "Revisar erradas",
                                            "icon": ft.Icons.AUTO_FIX_HIGH,
                                            "on_click": _review_wrong,
                                            "kind": "primary",
                                        },
                                        {
                                            "label": "Adicionar ao caderno",
                                            "icon": ft.Icons.BOOKMARK_ADD_OUTLINED,
                                            "on_click": _add_wrong_to_notebook,
                                            "kind": "warning",
                                        },
                                        {
                                            "label": "Gerar flashcards",
                                            "icon": ft.Icons.STYLE_OUTLINED,
                                            "on_click": _flashcards_from_wrong,
                                            "kind": "ghost",
                                        },
                                    ],
                                    dark=dark,
                                ),
                            ],
                            spacing=10,
                        ),
                    )
                ]
            except Exception as ex_report_ui:
                log_exception(ex_report_ui, "main._build_quiz_body.corrigir.simulado_report_ui")
                simulado_report_column.controls = [
                    ds_card(
                        dark=dark,
                        padding=DS.SP_12,
                        shadow=False,
                        border_color=DS.border_color(dark, 0.16),
                        content=ft.Column(
                            [
                                AppText("Relatorio do simulado", variant="h3", dark=dark, weight=ft.FontWeight.W_700),
                                AppText(
                                    f"Score: {score_pct:.1f}% | Acertos: {acertos} | Erros: {erros} | Puladas: {puladas}",
                                    variant="body",
                                    dark=dark,
                                ),
                                ds_action_bar(
                                    [
                                        {"label": "Novo simulado", "icon": ft.Icons.RESTART_ALT, "on_click": _novo_simulado_config, "kind": "ghost"},
                                        {"label": "Revisar erradas", "icon": ft.Icons.AUTO_FIX_HIGH, "on_click": _review_wrong, "kind": "primary"},
                                        {"label": "Adicionar ao caderno", "icon": ft.Icons.BOOKMARK_ADD_OUTLINED, "on_click": _add_wrong_to_notebook, "kind": "warning"},
                                        {"label": "Gerar flashcards", "icon": ft.Icons.STYLE_OUTLINED, "on_click": _flashcards_from_wrong, "kind": "ghost"},
                                    ],
                                    dark=dark,
                                ),
                            ],
                            spacing=10,
                        ),
                    )
                ]
            simulado_report_column.visible = True

        taxa = (acertos / max(1, total))
        if not simulado_mode:
            if taxa < 0.6:
                recomendacao_text.value = "Recomendado: revisar erros agora para consolidar base."
                recomendacao_button.text = "Iniciar revisao de erros"
                recomendacao_button.icon = ft.Icons.AUTO_FIX_HIGH
                recomendacao_button.on_click = _quick_due_reviews
            else:
                recomendacao_text.value = "Bom ritmo: avance para nova sessao em nivel igual ou acima."
                recomendacao_button.text = "Nova sessao (progresso)"
                recomendacao_button.icon = ft.Icons.TRENDING_UP
                recomendacao_button.on_click = _quick_new_session
            recomendacao_text.visible = True
            recomendacao_button.visible = True
        else:
            recomendacao_text.visible = False
            recomendacao_button.visible = False

        resultado.value = f"Acertos: {acertos}/{total} | XP ganho: {xp}"
        resultado.color = CORES["sucesso"] if acertos else CORES["erro"]
        _sync_resultado_box_visibility()
        status_estudo.value = "Correcao concluida." if not forcar_timeout else "Tempo esgotado. Simulado corrigido."
        resultado.update()
        estado["corrigido"] = True
        estado["question_last_ts"] = None
        _rebuild_cards()
        if page:
            page.update()

    async def _gerar_quiz_async():
        if not page:
            return
        try:
            dropdown_val = quiz_count_dropdown.value or "10"
            infinite_mode = dropdown_val == "inf"
            modo_continuo = dropdown_val == "cont" or infinite_mode
            estado["modo_continuo"] = modo_continuo
            estado["simulado_infinite"] = infinite_mode
            estado["infinite_batch_size"] = 5 if infinite_mode else estado.get("infinite_batch_size", 5)
            quantidade = 5 if infinite_mode else (5 if modo_continuo else int(dropdown_val))
            quantidade = max(1, quantidade if infinite_mode else min(30, quantidade))
        except ValueError:
            quantidade = 10
            estado["modo_continuo"] = False
            estado["simulado_infinite"] = False
            estado["infinite_batch_size"] = 5
        generate_button.disabled = True
        carregando.visible = True
        gen_profile = generation_profile(user, "quiz")
        if gen_profile.get("label") == "free_slow":
            set_feedback_text(status_text, f"Modo Free: gerando {quantidade} questoes (economico e mais lento)...", "info")
        else:
            set_feedback_text(status_text, f"Gerando {quantidade} questoes...", "info")
        _refresh_status_boxes()
        page.update()

        difficulty_key = difficulty_dropdown.value or dificuldade_padrao
        topic = (topic_field.value or "").strip()
        advanced_applied = _get_applied_advanced_filters()
        if not topic:
            topic = QuizFilterService.primary_topic(advanced_applied) or topic
        selected_library_id = str(getattr(library_dropdown, "value", "") or "").strip()
        if selected_library_id and library_service:
            nome = next(
                (f["nome_arquivo"] for f in (library_files or []) if str(f.get("id")) == selected_library_id),
                "Arquivo Biblioteca",
            )
            nome_tag = f"[LIB] {nome}"
            estado["upload_selected_names"] = [nome_tag]
            try:
                texto_lib = library_service.get_conteudo_arquivo(int(selected_library_id))
            except Exception:
                texto_lib = ""
            if texto_lib:
                estado["upload_texts"] = [texto_lib]
                estado["upload_names"] = [nome_tag]
                if not topic:
                    topic = _guess_topic_from_name(nome_tag)
                    topic_field.value = topic
            else:
                estado["upload_texts"] = []
                estado["upload_names"] = []
            _set_upload_info()
        material_selected = bool(estado.get("upload_selected_names")) or bool(estado.get("upload_names"))
        material_text_ready = bool(estado.get("upload_texts"))
        if material_selected and (not material_text_ready):
            set_feedback_text(
                status_text,
                "PDF selecionado, mas sem texto extraido. Use um PDF com texto selecionavel (nao escaneado) ou adicione referencia.",
                "warning",
            )
            carregando.visible = False
            generate_button.disabled = False
            _refresh_status_boxes()
            page.update()
            return
        material_source_locked = bool(material_selected and material_text_ready)
        if material_source_locked and not topic:
            first_pool = (estado.get("upload_names") or estado.get("upload_selected_names") or [""])
            first_name = str(first_pool[0] or "").strip()
            if first_name.startswith("[LIB]"):
                first_name = first_name[5:].strip()
            first_name = os.path.basename(first_name)
            guess_topic = os.path.splitext(first_name)[0].replace("_", " ").replace("-", " ").strip()
            guess_topic = " ".join(guess_topic.split())
            if guess_topic:
                topic = guess_topic[:64]
                topic_field.value = topic
        referencia_manual = [line.strip() for line in (referencia_field.value or "").splitlines() if line.strip()]
        referencia = list(estado["upload_texts"]) + referencia_manual
        if material_source_locked:
            referencia.append(
                "INSTRUCAO: use apenas conteudo conceitual do material; nao cite metadados "
                "(nome de curso, codigo EMA/CIAA, capitulo/secao/anexo, sumario/prefacio/edicao)."
            )
        advanced_hint = QuizFilterService.to_generation_hint(advanced_applied)
        if advanced_hint:
            referencia.append(advanced_hint)
        if bool(simulado_mode_switch.value) or bool(simulado_route_active):
            referencia.append(
                "INSTRUCAO: gere questoes variadas em subtemas diferentes, sem repetir pergunta nem resposta correta."
            )
        service = create_user_ai_service(user, force_economic=bool(gen_profile.get("force_economic")))
        geradas = []
        session_mode = session_mode_dropdown.value or "nova"
        if material_source_locked and session_mode != "nova":
            session_mode = "nova"
            session_mode_dropdown.value = "nova"
            set_feedback_text(status_text, "Material anexado detectado: modo 'Nova sessao' ativado automaticamente.", "info")
        if material_source_locked and not service:
            set_feedback_text(
                status_text,
                "Para gerar questoes a partir do PDF, configure a IA em Configuracoes.",
                "warning",
            )
            carregando.visible = False
            generate_button.disabled = False
            _refresh_status_boxes()
            page.update()
            return
        estado["simulado_mode"] = bool(simulado_mode_switch.value)
        if simulado_route_active:
            session_mode = "nova"
            session_mode_dropdown.value = "nova"
            simulado_mode_switch.value = True
            estado["simulado_mode"] = True
            _sync_feedback_policy_ui()
        estado["feedback_imediato"] = not bool(estado["simulado_mode"])
        _reset_mock_exam_runtime(clear_mode=False)
        mock_exam_policy = MockExamService(db) if db else None
        if estado["simulado_mode"]:
            if simulado_route_active:
                try:
                    tempo_min = max(5, int(str(simulado_time_field.value or "60").strip()))
                    estado["tempo_limite_s"] = tempo_min * 60
                except Exception:
                    pass
            premium_active = is_premium_active(user)
            quantidade, capped = MockExamService.normalize_question_count(quantidade, premium_active)
            if capped:
                quiz_count_dropdown.value = str(quantidade)
                preview_count_text.value = str(quantidade)
                set_feedback_text(
                    status_text,
                    f"Plano Free: simulado limitado a {MockExamService.FREE_MAX_QUESTIONS} questoes.",
                    "warning",
                )
            if (not premium_active) and mock_exam_policy and user.get("id"):
                allowed, _used, _limit = mock_exam_policy.consume_start_today(int(user["id"]), premium=False)
                if not allowed:
                    set_feedback_text(status_text, "Plano Free: limite diario de simulado atingido.", "warning")
                    show_upgrade_dialog(page, navigate, "No Premium voce pode fazer simulados ilimitados por dia.")
                    carregando.visible = False
                    generate_button.disabled = False
                    _refresh_status_boxes()
                    page.update()
                    return
            tempo_limite_s = int(max(300, int(estado.get("tempo_limite_s") or (60 * 60))))
            estado["tempo_limite_s"] = tempo_limite_s
            estado["prova_deadline"] = time.monotonic() + tempo_limite_s
        else:
            estado["tempo_limite_s"] = None
        estado["ultimo_filtro"] = {
            "topic": topic,
            "referencia": referencia,
            "difficulty": difficulty_key,
            "advanced_filters": advanced_applied,
            "advanced_hint": advanced_hint,
            "source_lock_material": material_source_locked,
        }
        estado["source_lock_material"] = material_source_locked

        # Prepara sessao vazia para permitir renderizacao progressiva.
        questoes.clear()
        estado["current_idx"] = 0
        estado["respostas"].clear()
        estado["corrigido"] = False
        estado["confirmados"] = set()
        estado["puladas"] = set()
        estado["show_secondary_tools"] = False
        estado["ui_stage"] = "config"
        estado["stats_synced_idxs"] = set()
        estado["prefetch_inflight"] = False
        estado["start_time"] = time.monotonic()
        estado["question_time_ms"] = {}
        estado["question_last_ts"] = time.monotonic()
        resultado.value = ""
        _sync_resultado_box_visibility()
        recomendacao_text.visible = False
        recomendacao_button.visible = False
        status_estudo.value = ""
        estado["favoritas"] = set()
        estado["marcadas_erro"] = set()

        seen_question_signatures: set[str] = set()
        seen_stem_signatures: set[str] = set()
        seen_stem_token_sets: list[set[str]] = []
        seen_semantic_token_sets: list[set[str]] = []
        is_mock_exam = bool(estado.get("simulado_mode"))
        near_dup_threshold = (0.68 if quantidade <= 12 else 0.72) if is_mock_exam else 0.78
        semantic_dup_threshold = (0.56 if quantidade <= 12 else 0.60) if is_mock_exam else 0.64
        near_dup_min_tokens = 4 if is_mock_exam else 5
        if is_mock_exam:
            answer_repeat_limit = 1 if quantidade <= 12 else 2
            if quantidade >= 25:
                answer_repeat_limit = 3
        else:
            answer_repeat_limit = max(2, int(max(2, quantidade // 3)))
        concept_repeat_limit = 1 if quantidade <= 10 else (2 if quantidade <= 20 else max(2, int((quantidade + 3) // 4)))
        numeric_repeat_limit = 1 if quantidade <= 20 else 2
        fact_repeat_limit = 1 if quantidade <= 20 else 2
        template_repeat_limit = 1 if quantidade <= 12 else (2 if quantidade <= 20 else 3)
        topic_bucket_repeat_limit = 2 if quantidade <= 12 else (3 if quantidade <= 20 else max(3, int((quantidade + 2) // 4)))
        answer_signature_counts: dict[str, int] = {}
        answer_signature_stems: dict[str, list[set[str]]] = {}
        concept_signature_counts: dict[str, int] = {}
        numeric_signature_counts: dict[str, int] = {}
        fact_signature_counts: dict[str, int] = {}
        template_signature_counts: dict[str, int] = {}
        topic_bucket_counts: dict[str, int] = {}

        def _normalize_sig_text(raw: Any) -> str:
            txt = _fix_mojibake_text(str(raw or ""))
            txt = unicodedata.normalize("NFKD", txt)
            txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
            txt = txt.strip().lower()
            if not txt:
                return ""
            txt = "".join(ch if ch.isalnum() else " " for ch in txt)
            return " ".join(txt.split())

        def _is_metadata_question_local(q: dict) -> bool:
            raw = str(q.get("enunciado") or q.get("pergunta") or "").strip()
            if not raw:
                return False
            t = _normalize_sig_text(raw)
            if not t:
                return False
            question_like = (
                "?" in raw
                or raw.rstrip().endswith(":")
                or t.startswith("qual ")
                or t.startswith("quem ")
                or t.startswith("quando ")
                or t.startswith("como ")
                or t.startswith("o que ")
                or t.startswith("por que ")
                or t.startswith("o objetivo ")
                or t.startswith("a finalidade ")
            )
            if not question_like:
                return False
            has_doc_code = bool(
                re.search(r"\b(?:ema|ciaa)\s*[-/]?\s*\d+(?:\s*[./-]\s*\d+)?\b", t)
                or re.search(r"\b(capitulo|secao|anexo)\s*\d+\b", t)
            )
            has_editorial = any(
                tok in t
                for tok in (
                    "manual",
                    "publicacao",
                    "guia",
                    "sumario",
                    "prefacio",
                    "introducao",
                    "edicao",
                    "classificacao",
                    "codigo",
                )
            )
            has_compound = bool(
                re.search(r"\b(objetivo|finalidade)\s+(central\s+)?da?\s+(publicacao|guia|manual)\b", t)
                or re.search(r"\b(introducao|prefacio|sumario)\s+da?\s+(publicacao|guia|manual)\b", t)
                or re.search(r"\bde\s+acordo\s+com\s+o?\s*(ema|ciaa)\b", t)
                or re.search(r"\bse\s+classifica\b.*\b(publicacao|manual)\b", t)
                or re.search(r"\bconforme\s+apresentado\s+no\s+contexto\s+do\b", t)
                or re.search(r"\bcurso\s+especial\s+de\s+habilitacao\b", t)
                or re.search(r"\bpromocao\s+a\s+sargentos\b", t)
            )
            return bool(has_doc_code or (has_editorial and has_compound))

        def _canonical_token(token: str) -> str:
            tok = str(token or "").strip().lower()
            if not tok:
                return ""
            for old, new in (
                ("acoes", "acao"),
                ("icoes", "icao"),
                ("coes", "cao"),
                ("oes", "ao"),
                ("ais", "al"),
            ):
                if tok.endswith(old) and len(tok) > len(old) + 2:
                    tok = tok[: -len(old)] + new
                    break
            if tok.endswith("mente") and len(tok) > 8:
                tok = tok[:-5]
            if tok.endswith("s") and len(tok) > 5:
                tok = tok[:-1]
            return tok

        raw_topic_buckets: dict[str, set[str]] = {
            "economia_comercio": {
                "economia", "economico", "comercio", "exportacao", "importacao", "balanca",
                "mercado", "logistica", "porto", "portuario", "fluxo", "movimentacao",
                "cabotagem", "receita",
            },
            "soberania_defesa": {
                "soberania", "defesa", "estrategia", "estrategico", "territorio", "fronteira",
                "militar", "seguranca", "patrulha", "marinha", "presenca", "nacional",
            },
            "ambiental_clima": {
                "ambiental", "ambiente", "biodiversidade", "ecossistema", "recife", "manguezal",
                "clima", "sustentavel", "sustentabilidade", "preservacao", "conservacao", "biologico",
            },
            "energia_recursos": {
                "energia", "energetico", "petroleo", "gas", "pre", "sal", "mineral", "minerio",
                "reserva", "exploracao", "extracao", "recurso",
            },
            "juridico_geopolitico": {
                "onu", "cnudm", "zee", "plataforma", "continental", "territorial", "juridico",
                "direito", "norma", "convencao", "reconhecimento", "equatorial",
            },
            "ciencia_sociedade": {
                "pesquisa", "oceanografia", "cientifico", "educacao", "sociedade", "mentalidade",
                "conscientizacao", "cultura", "futuro", "visao", "planejamento",
            },
        }
        topic_bucket_keywords = {
            bucket: {_canonical_token(tok) for tok in terms if _canonical_token(tok)}
            for bucket, terms in raw_topic_buckets.items()
        }

        def _stem_tokens(stem: str) -> set[str]:
            tokens = [t for t in stem.split() if len(t) >= 3]
            if not tokens:
                return set()
            # Remove termos muito genericos para comparar melhor perguntas parecidas.
            stopwords = {
                "qual", "quais", "como", "sobre", "acerca", "segundo", "desta", "deste",
                "esta", "este", "essa", "esse", "para", "com", "das", "dos", "uma", "um",
                "que", "quais", "onde", "quando", "porque", "por", "pela", "pelo", "nos",
                "nas", "entre", "apos", "antes", "manual", "guia", "publicacao", "capitulo",
                "texto", "material", "documento", "amazonia", "azul", "brasil", "brasileiro",
                "importancia", "impacto", "economica", "economico", "estrategica", "estrategico",
                "segundo", "acordo", "afirma", "destaca", "regiao",
            }
            stopword_roots = {_canonical_token(x) for x in stopwords}
            filtered = {_canonical_token(t) for t in tokens if _canonical_token(t) not in stopword_roots}
            if len(filtered) >= 3:
                return filtered
            return {_canonical_token(t) for t in tokens if _canonical_token(t)}

        def _is_near_duplicate_stem(tokens: set[str]) -> bool:
            if not tokens:
                return False
            if len(tokens) < near_dup_min_tokens:
                return False
            for existing in seen_stem_token_sets:
                union = len(tokens | existing)
                if union == 0:
                    continue
                overlap = len(tokens & existing) / float(union)
                if overlap >= near_dup_threshold:
                    return True
            return False

        def _stem_signature(q: dict) -> tuple[str, set[str]]:
            stem = _normalize_sig_text(q.get("enunciado") or q.get("pergunta"))
            if not stem:
                return "", set()
            sig = hashlib.sha1(stem.encode("utf-8", errors="ignore")).hexdigest()
            return sig, _stem_tokens(stem)

        def _question_signature(q: dict) -> str:
            try:
                enunciado = _normalize_sig_text(q.get("enunciado") or q.get("pergunta"))
                alternativas = q.get("alternativas") or q.get("opcoes") or []
                alt_norm: list[str] = []
                if isinstance(alternativas, list):
                    for alt in alternativas[:4]:
                        norm = _normalize_sig_text(alt)
                        if norm:
                            alt_norm.append(norm)
                base = enunciado
                if alt_norm:
                    base = f"{base}|{'|'.join(alt_norm)}"
                if not base.strip("|"):
                    return ""
                return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()
            except Exception:
                return ""

        def _answer_signature(q: dict) -> str:
            try:
                alternativas = q.get("alternativas") or q.get("opcoes") or []
                if not isinstance(alternativas, list) or not alternativas:
                    return ""
                correta_idx = q.get("correta_index", q.get("correta", 0))
                try:
                    correta_idx = int(correta_idx)
                except Exception:
                    correta_idx = 0
                correta_idx = max(0, min(correta_idx, len(alternativas) - 1))
                answer = _normalize_sig_text(alternativas[correta_idx])
                if not answer:
                    return ""
                parts = answer.split()
                if len(parts) >= 2 and parts[0] in {"a", "b", "c", "d"}:
                    answer = " ".join(parts[1:]).strip()
                return answer
            except Exception:
                return ""

        def _answer_tokens(q: dict) -> set[str]:
            ans = _answer_signature(q)
            if not ans:
                return set()
            return {_canonical_token(tok) for tok in ans.split() if len(_canonical_token(tok)) >= 4}

        def _concept_signature(tokens: set[str]) -> str:
            if not tokens:
                return ""
            noise = {
                "amazonia", "azul", "brasil", "brasileiro", "texto", "material",
                "documento", "questao", "pergunta", "importancia", "impacto",
                "economica", "economico", "estrategica", "estrategico", "regiao",
            }
            core = [t for t in tokens if t not in noise and len(t) >= 5]
            if len(core) < 2:
                core = [t for t in tokens if len(t) >= 4]
            if not core:
                return ""
            top = sorted(core, key=lambda t: (-len(t), t))[:3]
            return "|".join(sorted(top))

        def _numeric_signature(q: dict) -> str:
            try:
                stem = str(q.get("enunciado") or q.get("pergunta") or "")
                alternativas = q.get("alternativas") or q.get("opcoes") or []
                joined_alts = " ".join(str(x or "") for x in (alternativas[:4] if isinstance(alternativas, list) else []))
                base = _normalize_sig_text(f"{stem} {joined_alts}")
                nums = re.findall(r"\b\d+(?:[\.,]\d+)?\b", base)
                if not nums:
                    return ""
                uniq = sorted(set(nums))
                return "|".join(uniq[:3])
            except Exception:
                return ""

        def _semantic_tokens(q: dict) -> set[str]:
            raw = set(_stem_tokens(_normalize_sig_text(q.get("enunciado") or q.get("pergunta")))) | _answer_tokens(q)
            noise = {
                "texto", "material", "documento", "questao", "pergunta", "alternativa",
                "correta", "amazonia", "azul", "brasil", "brasileiro", "regiao",
                "importancia", "impacto", "relevancia", "estrategico", "economico",
                "segundo", "acordo", "afirma", "destaca",
            }
            refined = {tok for tok in raw if len(tok) >= 4 and tok not in noise}
            return refined or raw

        def _is_semantic_duplicate(tokens: set[str]) -> bool:
            if len(tokens) < 4:
                return False
            for existing in seen_semantic_token_sets:
                union = len(tokens | existing)
                if union == 0:
                    continue
                overlap = len(tokens & existing) / float(union)
                if overlap >= semantic_dup_threshold:
                    return True
            return False

        def _fact_signature(q: dict, semantic_tokens: set[str]) -> str:
            try:
                stem = str(q.get("enunciado") or q.get("pergunta") or "")
                alternativas = q.get("alternativas") or q.get("opcoes") or []
                answer = _answer_signature(q)
                joined_alts = " ".join(str(x or "") for x in (alternativas[:4] if isinstance(alternativas, list) else []))
                base = _normalize_sig_text(f"{stem} {answer} {joined_alts}")
                nums = sorted(set(re.findall(r"\b\d+(?:[\.,]\d+)?\b", base)))
                anchors = [tok for tok in semantic_tokens if len(tok) >= 5]
                if not nums and not anchors:
                    return ""
                top = sorted(anchors, key=lambda t: (-len(t), t))[:3]
                num_part = "|".join(nums[:2]) if nums else ""
                anchor_part = "|".join(sorted(top)) if top else ""
                if num_part and anchor_part:
                    return f"{num_part}::{anchor_part}"
                return num_part or anchor_part
            except Exception:
                return ""

        template_alias = {
            "relevancia": "importancia",
            "efeito": "impacto",
            "funcao": "papel",
            "objetivo": "finalidade",
        }
        template_frame_terms = {
            "qual", "como", "porque", "por", "que", "sobre", "segundo", "acordo", "texto",
            "papel", "relacao", "importancia", "impacto", "finalidade", "definicao",
            "composicao", "visao", "cenario", "aplicacao", "consequencia", "causa",
        }

        def _template_signature(q: dict) -> str:
            stem = _normalize_sig_text(q.get("enunciado") or q.get("pergunta"))
            if not stem:
                return ""
            roots = [_canonical_token(tok) for tok in stem.split()[:16] if _canonical_token(tok)]
            if not roots:
                return ""
            frame: list[str] = []
            for tok in roots:
                canon = template_alias.get(tok, tok)
                if canon in template_frame_terms:
                    if not frame or frame[-1] != canon:
                        frame.append(canon)
                if len(frame) >= 5:
                    break
            if len(frame) >= 3:
                return "|".join(frame[:4])
            core = [template_alias.get(tok, tok) for tok in roots if tok not in {"", "a", "o", "de", "do", "da"}]
            return "|".join(core[:3])

        def _topic_bucket_signature(q: dict, semantic_tokens: set[str]) -> str:
            tokens = set(semantic_tokens or set())
            assunto = _normalize_sig_text(q.get("assunto") or q.get("subtema") or q.get("tema"))
            if assunto:
                tokens |= {_canonical_token(tok) for tok in assunto.split() if _canonical_token(tok)}
            if not tokens:
                return ""
            buckets: list[str] = []
            for bucket, words in topic_bucket_keywords.items():
                if tokens & words:
                    buckets.append(bucket)
            if not buckets:
                return ""
            return "|".join(sorted(buckets)[:2])

        def _append_generated_question(item: dict, update_live: bool = False) -> bool:
            qnorm = _normalize_question_for_ui(item)
            if not qnorm:
                return False
            if _is_metadata_question_local(qnorm):
                return False
            qsig = _question_signature(qnorm)
            stem_sig, stem_tokens = _stem_signature(qnorm)
            answer_sig = _answer_signature(qnorm)
            concept_sig = _concept_signature(set(stem_tokens) | _answer_tokens(qnorm))
            numeric_sig = _numeric_signature(qnorm)
            semantic_tokens = _semantic_tokens(qnorm)
            fact_sig = _fact_signature(qnorm, semantic_tokens)
            template_sig = _template_signature(qnorm)
            topic_bucket_sig = _topic_bucket_signature(qnorm, semantic_tokens)
            if qsig and qsig in seen_question_signatures:
                return False
            if stem_sig and stem_sig in seen_stem_signatures:
                return False
            if stem_tokens and _is_near_duplicate_stem(stem_tokens):
                return False
            if semantic_tokens and _is_semantic_duplicate(semantic_tokens):
                return False
            if answer_sig:
                if answer_signature_counts.get(answer_sig, 0) >= answer_repeat_limit:
                    return False
                if stem_tokens:
                    for prev_tokens in answer_signature_stems.get(answer_sig, []):
                        union = len(stem_tokens | prev_tokens)
                        if union == 0:
                            continue
                        overlap = len(stem_tokens & prev_tokens) / float(union)
                        if overlap >= (0.30 if is_mock_exam else 0.38):
                            return False
            if concept_sig and concept_signature_counts.get(concept_sig, 0) >= concept_repeat_limit:
                return False
            if numeric_sig and numeric_signature_counts.get(numeric_sig, 0) >= numeric_repeat_limit:
                return False
            if fact_sig and fact_signature_counts.get(fact_sig, 0) >= fact_repeat_limit:
                return False
            if template_sig and template_signature_counts.get(template_sig, 0) >= template_repeat_limit:
                return False
            if topic_bucket_sig and topic_bucket_counts.get(topic_bucket_sig, 0) >= topic_bucket_repeat_limit:
                return False
            if qsig:
                seen_question_signatures.add(qsig)
            if stem_sig:
                seen_stem_signatures.add(stem_sig)
            if stem_tokens:
                seen_stem_token_sets.append(stem_tokens)
            if semantic_tokens:
                seen_semantic_token_sets.append(semantic_tokens)
            if answer_sig:
                answer_signature_counts[answer_sig] = answer_signature_counts.get(answer_sig, 0) + 1
                if stem_tokens:
                    answer_signature_stems.setdefault(answer_sig, []).append(set(stem_tokens))
            if concept_sig:
                concept_signature_counts[concept_sig] = concept_signature_counts.get(concept_sig, 0) + 1
            if numeric_sig:
                numeric_signature_counts[numeric_sig] = numeric_signature_counts.get(numeric_sig, 0) + 1
            if fact_sig:
                fact_signature_counts[fact_sig] = fact_signature_counts.get(fact_sig, 0) + 1
            if template_sig:
                template_signature_counts[template_sig] = template_signature_counts.get(template_sig, 0) + 1
            if topic_bucket_sig:
                topic_bucket_counts[topic_bucket_sig] = topic_bucket_counts.get(topic_bucket_sig, 0) + 1
            qfinal = dict(qnorm)
            geradas.append(qfinal)
            questoes.append(dict(qfinal))
            if update_live:
                set_feedback_text(status_text, f"Gerando questoes... {len(geradas)}/{quantidade}", "info")
                if len(questoes) == 1:
                    _mostrar_etapa_estudo()
                _rebuild_cards()
                _refresh_status_boxes()
                if page:
                    page.update()
            return True

        async def _fill_missing_with_ai_unique(target_total: int) -> None:
            if len(geradas) >= int(target_total):
                return
            if not service or not (topic or referencia):
                return
            def _avoid_questions_snapshot(max_items: int = 12) -> list[str]:
                out: list[str] = []
                for q in geradas[-max_items:]:
                    txt = str(q.get("enunciado") or q.get("pergunta") or "").strip()
                    if txt:
                        out.append(" ".join(txt.split())[:220])
                return out
            max_attempts = max(int(target_total) * 6, 24)
            attempts = 0
            while len(geradas) < int(target_total) and attempts < max_attempts:
                attempts += 1
                try:
                    remaining = int(target_total) - len(geradas)
                    difficulty_name = DIFICULDADES.get(difficulty_key, {}).get("nome", "Intermediario")
                    batch_size = min(5 if is_mock_exam else 4, max(1, remaining))
                    avoid_questions = _avoid_questions_snapshot()
                    appended_any = False
                    if batch_size > 1:
                        lote = await asyncio.to_thread(
                            service.generate_quiz_batch,
                            referencia or None,
                            topic or None,
                            difficulty_name,
                            batch_size,
                            1,
                            avoid_questions,
                        )
                        if isinstance(lote, list):
                            for questao in lote:
                                if _append_generated_question(questao, update_live=True):
                                    appended_any = True
                                    if db:
                                        try:
                                            tema_cache = topic or "Geral"
                                            db.salvar_questao_cache(tema_cache, difficulty_key, geradas[-1], user_id=int(user["id"]) if user.get("id") else None)
                                        except Exception as ex_cache:
                                            log_exception(ex_cache, "main._build_quiz_body.salvar_questao_cache")
                    if appended_any:
                        continue
                    questao = await asyncio.to_thread(
                        service.generate_quiz,
                        referencia or None,
                        topic or None,
                        difficulty_name,
                        1,
                        avoid_questions,
                    )
                    if questao and _append_generated_question(questao, update_live=True):
                        if db:
                            try:
                                tema_cache = topic or "Geral"
                                db.salvar_questao_cache(tema_cache, difficulty_key, geradas[-1], user_id=int(user["id"]) if user.get("id") else None)
                            except Exception as ex_cache:
                                log_exception(ex_cache, "main._build_quiz_body.salvar_questao_cache")
                        continue
                    issue_kind = ai_issue_kind(service)
                    if issue_kind in {"quota", "auth", "dependency"}:
                        if issue_kind == "quota":
                            set_feedback_text(
                                status_text,
                                f"Cota de IA atingida durante a geracao ({len(geradas)}/{quantidade}). Completando com modo offline.",
                                "warning",
                            )
                        else:
                            set_feedback_text(
                                status_text,
                                "IA indisponivel no provider atual. Revise chave/provider em Configuracoes.",
                                "warning",
                            )
                        break
                except Exception as ex_ai:
                    log_exception(ex_ai, "main._build_quiz_body")
                    issue_kind = ai_issue_kind(service)
                    if issue_kind in {"quota", "auth", "dependency"}:
                        if issue_kind == "quota":
                            set_feedback_text(
                                status_text,
                                f"Cota de IA atingida durante a geracao ({len(geradas)}/{quantidade}). Completando com modo offline.",
                                "warning",
                            )
                        else:
                            set_feedback_text(
                                status_text,
                                "IA indisponivel no provider atual. Revise chave/provider em Configuracoes.",
                                "warning",
                            )
                        break

        def _fill_from_cache_unique(target_total: int) -> None:
            if len(geradas) >= int(target_total):
                return
            if not (topic and db):
                return
            try:
                fetch_limit = max(int(target_total) * 4, 40)
                cache_items = db.listar_questoes_cache(topic, difficulty_key, fetch_limit, user_id=int(user["id"]) if user.get("id") else None) or []
                for item in cache_items:
                    if len(geradas) >= int(target_total):
                        break
                    _append_generated_question(item, update_live=True)
            except Exception as ex_cache:
                log_exception(ex_cache, "main._build_quiz_body.listar_questoes_cache")
        if db and user.get("id") and session_mode != "nova":
            try:
                geradas_db = db.listar_questoes_usuario(user["id"], modo=session_mode, limite=quantidade) or []
                for item in geradas_db:
                    _append_generated_question(item, update_live=False)
            except Exception as ex:
                log_exception(ex, "main._build_quiz_body.listar_questoes_usuario")

        if not geradas and not has_quiz_generation_context(topic, referencia):
            msg = "Informe um topico ou anexe um material para gerar questoes." if session_mode == "nova" else "Sem questoes salvas para essa sessao. Informe um topico ou anexe um material."
            set_feedback_text(status_text, msg, "warning")
            set_feedback_text(status_estudo, msg, "warning")
            carregando.visible = False
            generate_button.disabled = False
            _refresh_status_boxes()
            if page:
                page.update()
            return

        if gen_profile.get("delay_s", 0) > 0:
            await asyncio.sleep(float(gen_profile["delay_s"]))
        if service and (topic or referencia) and len(geradas) < quantidade:
            await _fill_missing_with_ai_unique(quantidade)

        issue_kind = ai_issue_kind(service)
        if not geradas:
            if material_source_locked:
                if issue_kind in {"auth", "dependency"}:
                    msg = "Nao consegui gerar questoes com o provider atual. Revise chave/provider em Configuracoes e tente novamente."
                else:
                    msg = "Nao consegui gerar questoes do material anexado. Revise o PDF/referencia e tente novamente."
                set_feedback_text(status_text, msg, "warning")
                set_feedback_text(status_estudo, msg, "warning")
                ds_toast(page, msg, tipo="warning")
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
                generate_button.disabled = False
                _refresh_status_boxes()
                page.update()
                return
            _fill_from_cache_unique(quantidade)
            if not geradas and topic:
                msg = "Sem material offline dessa materia ainda. Tente gerar essa materia com IA quando houver cota."
                if issue_kind in {"auth", "dependency"}:
                    msg = "IA indisponivel no provider atual e sem cache local dessa materia. Revise configuracoes da IA."
                set_feedback_text(status_text, msg, "warning")
                set_feedback_text(status_estudo, msg, "warning")
                ds_toast(page, msg, tipo="warning")
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
                generate_button.disabled = False
                page.update()
                return
            if issue_kind == "quota":
                set_feedback_text(status_text, f"Cotas da IA esgotadas. Modo offline: {len(geradas)} questoes prontas.", "warning")
                show_api_issue_dialog(
                    page,
                    navigate,
                    "quota",
                    provider_options=_provider_switch_options(),
                    on_select_provider=_switch_provider_and_retry,
                )
            elif issue_kind in {"auth", "dependency"}:
                set_feedback_text(status_text, f"Modo offline: {len(geradas)} questoes prontas. Ajuste a IA em Configuracoes.", "warning")
                show_api_issue_dialog(
                    page,
                    navigate,
                    "auth" if issue_kind == "auth" else ("dependency" if issue_kind == "dependency" else "generic"),
                    provider_options=_provider_switch_options(),
                    on_select_provider=_switch_provider_and_retry,
                )
            else:
                set_feedback_text(status_text, f"Modo offline: {len(geradas)} questoes prontas.", "info")
        else:
            if (not material_source_locked) and len(geradas) < quantidade:
                _fill_from_cache_unique(quantidade)
            if service and (topic or referencia) and len(geradas) < quantidade:
                await _fill_missing_with_ai_unique(quantidade)
            if session_mode == "nova":
                set_feedback_text(status_text, f"IA: {len(geradas)} questoes geradas.", "success")
            else:
                set_feedback_text(status_text, f"Sessao rapida ({session_mode}): {len(geradas)} questoes.", "success")

        if len(geradas) < quantidade:
            msg = (
                f"Foram geradas {len(geradas)}/{quantidade} questoes unicas "
                f"(repetidas ou invalidas foram descartadas automaticamente)."
            )
            set_feedback_text(status_text, msg, "warning")
            set_feedback_text(status_estudo, msg, "warning")
            ds_toast(page, msg, tipo="warning")
        _refresh_status_boxes()

        if db and user.get("id"):
            for idx, q in enumerate(questoes):
                meta = q.get("_meta") or {}
                if meta.get("favorita"):
                    estado["favoritas"].add(idx)
                if meta.get("marcado_erro"):
                    estado["marcadas_erro"].add(idx)
                _persist_question_flags(idx, None)

        if bool(estado.get("simulado_mode")):
            _ensure_mock_exam_session(len(questoes))
            _cancel_timer_task()
            timer_ref["token"] = int(timer_ref.get("token") or 0) + 1
            if page:
                try:
                    timer_ref["task"] = page.run_task(_cronometro_task, int(timer_ref["token"]))
                except Exception as ex:
                    log_exception(ex, "main._build_quiz_body.start_timer")

        _rebuild_cards()
        _mostrar_etapa_estudo()
        carregando.visible = False
        generate_button.disabled = False
        page.update()

    def _on_gerar_clique(e):
        if not page:
            return
        schedule_ai_task(
            page,
            state,
            _gerar_quiz_async,
            message="IA gerando questoes...",
            status_control=status_text,
        )

    def limpar_respostas(_):
        if not questoes:
            set_feedback_text(status_text, "Ainda nao ha questoes para limpar.", "info")
            _mostrar_etapa_config()
            _refresh_status_boxes()
            if page:
                page.update()
            return
        estado["respostas"].clear()
        estado["corrigido"] = False
        resultado.value = ""
        _sync_resultado_box_visibility()
        recomendacao_text.visible = False
        recomendacao_button.visible = False
        estado["confirmados"] = set()
        estado["puladas"] = set()
        estado["show_secondary_tools"] = False
        estado["stats_synced_idxs"] = set()
        _reset_mock_exam_runtime(clear_mode=False)
        estado["question_time_ms"] = {}
        estado["question_last_ts"] = time.monotonic()
        status_estudo.value = "Respostas limpas."
        _refresh_status_boxes()
        _rebuild_cards()
        if page:
            page.update()

    def _novo_simulado_config(_=None):
        questoes.clear()
        estado["respostas"] = {}
        estado["corrigido"] = False
        resultado.value = ""
        _sync_resultado_box_visibility()
        recomendacao_text.visible = False
        recomendacao_button.visible = False
        estado["confirmados"] = set()
        estado["puladas"] = set()
        estado["show_secondary_tools"] = False
        estado["stats_synced_idxs"] = set()
        _reset_mock_exam_runtime(clear_mode=False)
        estado["question_time_ms"] = {}
        estado["question_last_ts"] = None
        if simulado_route_active:
            simulado_mode_switch.value = True
            estado["simulado_mode"] = True
            _sync_feedback_policy_ui()
        _mostrar_etapa_config()
        set_feedback_text(status_text, "Configure um novo simulado.", "info")
        _refresh_status_boxes()
        _rebuild_cards()
        if page:
            page.update()

    def _encerrar_sessao(_=None, go_home: bool = False):
        """
        Encerra completamente a sessao atual de simulado/quiz.
        Usado ao sair da tela para evitar que o usuario retorne a um estado pendurado.
        """
        questoes.clear()
        estado["respostas"] = {}
        estado["corrigido"] = False
        estado["confirmados"] = set()
        estado["puladas"] = set()
        estado["show_secondary_tools"] = False
        estado["stats_synced_idxs"] = set()
        estado["ui_stage"] = "config"
        estado["prefetch_inflight"] = False
        estado["modo_continuo"] = False
        _reset_mock_exam_runtime(clear_mode=True)
        status_text.value = ""
        status_estudo.value = ""
        carregando.visible = False
        resultado.value = ""
        _sync_resultado_box_visibility()
        _rebuild_cards()
        _refresh_status_boxes()
        if page:
            page.update()
            if go_home:
                navigate("/home")

    def _voltar_config(_):
        _mostrar_etapa_config()
        if page:
            page.update()

    study_footer_actions.controls = [
        ft.Container(
            col={"xs": 12, "md": 4},
            content=ft.ElevatedButton("Corrigir", icon=ft.Icons.CHECK, on_click=corrigir, expand=True),
        ),
        ft.Container(
            col={"xs": 12, "md": 8},
            content=ft.Row(
                [
                    ft.TextButton("Limpar respostas", icon=ft.Icons.RESTART_ALT, on_click=limpar_respostas),
                    ft.TextButton(
                        "Voltar para setup do simulado" if simulado_route_active else "Voltar para configuracao",
                        icon=ft.Icons.ARROW_BACK,
                        on_click=_voltar_config,
                    ),
                    ft.TextButton("Voltar ao Inicio", icon=ft.Icons.HOME_OUTLINED, on_click=lambda e: _encerrar_sessao(e, go_home=True)),
                ],
                wrap=True,
                spacing=10,
            ),
        ),
    ]

    generate_button_label = "Iniciar simulado" if simulado_route_active else "Gerar e iniciar estudo"
    generate_button_icon = ft.Icons.PLAY_ARROW_ROUNDED if simulado_route_active else ft.Icons.BOLT
    generate_button = ft.ElevatedButton(
        generate_button_label,
        icon=generate_button_icon,
        on_click=_on_gerar_clique,
        style=ft.ButtonStyle(bgcolor=CORES["primaria"], color="white"),
    )

    advanced_visible = {"value": False}
    advanced_show_label = "Mostrar configuracoes de prova" if simulado_route_active else "Mostrar ajustes avancados"
    advanced_hide_label = "Ocultar configuracoes de prova" if simulado_route_active else "Ocultar ajustes avancados"
    advanced_button = ft.TextButton(advanced_show_label, icon=ft.Icons.TUNE)

    def _toggle_advanced(_):
        advanced_visible["value"] = not advanced_visible["value"]
        advanced_section.visible = advanced_visible["value"]
        advanced_button.text = advanced_hide_label if advanced_visible["value"] else advanced_show_label
        if page:
            page.update()

    advanced_button.on_click = _toggle_advanced

    def _quick_new_session(_):
        session_mode_dropdown.value = "nova"
        simulado_mode_switch.value = False
        _sync_feedback_policy_ui()
        quiz_count_dropdown.value = "10"
        preview_count_text.value = "10"
        _reset_mock_exam_runtime(clear_mode=True)
        set_feedback_text(status_text, "Modo treino rapido selecionado.", "info")
        if page:
            page.update()
        _on_gerar_clique(None)

    def _quick_due_reviews(_):
        session_mode_dropdown.value = "erradas"
        simulado_mode_switch.value = False
        _sync_feedback_policy_ui()
        quiz_count_dropdown.value = "10"
        preview_count_text.value = "10"
        _reset_mock_exam_runtime(clear_mode=True)
        set_feedback_text(status_text, "Modo revisao de erros selecionado.", "info")
        if page:
            page.update()
        _on_gerar_clique(None)

    def _quick_simulado(_):
        session_mode_dropdown.value = "nova"
        simulado_mode_switch.value = True
        _sync_feedback_policy_ui()
        quiz_count_dropdown.value = "30"
        preview_count_text.value = "30"
        _reset_mock_exam_runtime(clear_mode=False)
        estado["tempo_limite_s"] = 60 * 60
        set_feedback_text(status_text, "Modo prova selecionado.", "info")
        if page:
            page.update()
        _on_gerar_clique(None)

    advanced_section = ft.Column(
        [
            ft.ResponsiveRow(
                [
                    ft.Container(col={"xs": 12, "md": 3}, content=difficulty_dropdown),
                    ft.Container(col={"xs": 12, "md": 3}, content=session_mode_dropdown, visible=not simulado_route_active),
                    ft.Container(col={"xs": 12, "md": 3}, content=simulado_time_field, visible=simulado_route_active),
                    ft.Container(
                        col={"xs": 12, "md": 2},
                        content=ft.Row([simulado_mode_switch, ft.Text("Modo prova")], wrap=True, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        visible=not simulado_route_active,
                    ),
                    ft.Container(col={"xs": 12, "md": 2}, content=ft.Container(padding=ft.padding.only(top=4), content=feedback_policy_text)),
                    ft.Container(
                        col={"xs": 12, "md": 2},
                        content=ft.Row(
                            [ft.Text("Questoes encontradas:"), preview_count_text],
                            wrap=True,
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                spacing=12,
                run_spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            referencia_field,
            ft.Row(
                [
                    save_filter_name,
                    ft.ElevatedButton("Salvar filtro", icon=ft.Icons.SAVE, on_click=_save_current_filter),
                    saved_filters_dropdown,
                    ft.TextButton("Excluir", icon=ft.Icons.DELETE_OUTLINE, on_click=_delete_selected_filter),
                ],
                wrap=True,
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        spacing=10,
        visible=False,
    )

    config_section = ft.Column(
        [
            ds_card(
                dark=dark,
                padding=14,
                content=ft.Column(
                    [
                        ft.Text(
                            "Configure seu simulado" if simulado_route_active else "Inicie sua sessao de estudo",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=_color("texto", dark),
                        ),
                        ft.ResponsiveRow(
                            [
                                ft.Container(content=topic_field, col={"sm": 12, "md": 8}),
                                ft.Container(content=quiz_count_dropdown, col={"sm": 12, "md": 4}),
                            ],
                            spacing=12,
                            run_spacing=8,
                        ),
                        material_entry_section,
                        ft.ResponsiveRow(
                            [
                                ft.Container(content=advanced_filters_button, col={"xs": 12, "md": 5}),
                                ft.Container(content=advanced_filters_hint, col={"xs": 12, "md": 7}),
                            ],
                            spacing=10,
                            run_spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.ResponsiveRow(
                            [
                                ft.Container(
                                    col={"xs": 12, "md": 6},
                                    content=ds_btn_primary(
                                        "Treino rapido",
                                        icon=ft.Icons.PLAY_CIRCLE_FILL,
                                        on_click=_quick_new_session,
                                        expand=True,
                                        dark=dark,
                                    ),
                                ),
                                ft.Container(
                                    col={"xs": 12, "md": 6},
                                    content=ds_btn_secondary(
                                        "Revisar erros",
                                        icon=ft.Icons.AUTO_FIX_HIGH,
                                        on_click=_quick_due_reviews,
                                        expand=True,
                                        dark=dark,
                                    ),
                                ),
                            ],
                            run_spacing=6,
                            spacing=10,
                            visible=not simulado_route_active,
                        ),
                        advanced_button,
                        advanced_section,
                        ft.ResponsiveRow(
                            [
                                ft.Container(col={"xs": 12, "md": 4}, content=generate_button),
                                ft.Container(
                                    col={"xs": 12, "md": 8},
                                    content=ft.Column([carregando, status_banner(status_text, dark)], spacing=6),
                                ),
                            ],
                            run_spacing=6,
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=10,
                ),
            )
        ],
        spacing=12,
        visible=True,
    )

    study_section = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        "Resolva o simulado" if simulado_route_active else "Resolva as questoes",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=_color("texto", dark),
                    ),
                    ft.Row([contador_text, progresso_text, tempo_text], spacing=10, wrap=True),
                ],
                wrap=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            filtro_resumo_text,
            status_estudo_box,
            mapa_prova_container,
            cards_column,
            resultado_box,
            ft.Row([recomendacao_text, recomendacao_button], wrap=True, spacing=10),
            study_footer_actions,
            simulado_report_column,
        ],
        spacing=12,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        visible=False,
    )

    _load_saved_filters()
    _refresh_filter_summary()
    _set_upload_info()
    _rebuild_cards()
    if isinstance(package_questions, list) and package_questions:
        questoes[:] = [
            dict(qn)
            for qn in (_normalize_question_for_ui(q) for q in package_questions)
            if qn
        ]
        estado["current_idx"] = 0
        estado["respostas"].clear()
        estado["confirmados"] = set()
        estado["puladas"] = set()
        estado["show_secondary_tools"] = False
        estado["stats_synced_idxs"] = set()
        estado["corrigido"] = False
        estado["start_time"] = time.monotonic()
        estado["ui_stage"] = "study"
        estado["question_time_ms"] = {}
        estado["question_last_ts"] = time.monotonic()
        status_estudo.value = "Sessao carregada de pacote da Biblioteca."
        _rebuild_cards()
        _mostrar_etapa_estudo()

    if preset_auto_start and (not questoes) and page:
        schedule_ai_task(
            page,
            state,
            _gerar_quiz_async,
            message="IA gerando questoes...",
            status_control=status_text,
        )

    if questoes:
        if str(estado.get("ui_stage") or "study") == "config":
            _mostrar_etapa_config()
        else:
            _mostrar_etapa_estudo()
    else:
        _mostrar_etapa_config()

    retorno = wrap_study_content(
        ft.Column(
            [
                build_focus_header(
                    "Simulado" if simulado_route_active else "Questoes",
                    "Fluxo: 1) Configure  2) Gere  3) Responda e corrija",
                    etapa_text,
                    dark,
                ),
                config_section,
                study_section,
            ],
            spacing=12,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        dark,
    )

    if not ai_enabled:
        status_text.value = "Configure uma API key em Configuracoes para desbloquear a IA."
    return retorno





