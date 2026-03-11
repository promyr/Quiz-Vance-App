# -*- coding: utf-8 -*-
"""View de dissertativa (open_quiz) — extraída do main_v2.py."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Optional

import flet as ft

from config import CORES
from core.error_monitor import log_exception
from core.library_service import LibraryService
from core.ui_route_theme import _color
from core.ui_text_sanitizer import _fix_mojibake_text

from core.helpers.ai_helpers import (
    create_user_ai_service,
    is_ai_quota_exceeded,
    schedule_ai_task,
)
from core.helpers.file_helpers import (
    extract_uploaded_material,
    format_upload_info_label,
    pick_study_files,
    state_async_guard,
)
from core.helpers.ui_helpers import (
    backend_user_id,
    build_focus_header,
    close_dialog_compat,
    is_premium_active,
    screen_height,
    screen_width,
    set_feedback_text,
    show_confirm_dialog,
    show_dialog_compat,
    show_quota_dialog,
    show_upgrade_dialog,
    status_banner,
    wrap_study_content,
)
from ui.design_system import (
    ds_action_bar,
    ds_btn_ghost,
    ds_btn_primary,
    ds_btn_secondary,
    ds_card,
    ds_divider,
    ds_toast,
)


def build_open_quiz_body(state: dict, navigate, dark: bool) -> ft.Control:
    page = state.get("page")
    screen_h = screen_height(page) if page else 820
    screen_w = screen_width(page) if page else 1280
    user = state.get("usuario") or {}
    db = state.get("db")
    library_service = LibraryService(db) if db else None
    backend = state.get("backend")
    service = create_user_ai_service(user)
    runtime = state.setdefault("open_quiz_runtime", {}) if isinstance(state, dict) else {}
    if not isinstance(runtime, dict):
        runtime = {}
        if isinstance(state, dict):
            state["open_quiz_runtime"] = runtime
    
    status = ft.Text("", size=12, color=_color("texto_sec", dark))
    pergunta_text = ft.Text("", size=18, weight=ft.FontWeight.W_600, color=_color("texto", dark), text_align=ft.TextAlign.LEFT)
    gabarito_text = ft.Text("", size=13, color=_color("texto_sec", dark), visible=False)
    resposta_field = ft.TextField(
        label="Sua resposta",
        multiline=True,
        min_lines=12,
        max_lines=20,
        expand=True,
        hint_text="Escreva sua resposta dissertativa aqui...",
    )
    study_card_width = max(280, min(1320, int(min(screen_w, 1360) - 24)))
    tema_field = ft.TextField(label="Tema", hint_text="Ex.: Direito Constitucional", expand=True, value=str(runtime.get("tema") or ""))
    loading = ft.ProgressRing(width=24, height=24, visible=False)
    estado = {
        "pergunta": str(runtime.get("pergunta") or ""),
        "gabarito": str(runtime.get("gabarito") or ""),
        "contexto_gerado": str(runtime.get("contexto_gerado") or ""),
        "upload_texts": list(runtime.get("upload_texts") or []),
        "upload_names": list(runtime.get("upload_names") or []),
        "upload_selected_names": list(runtime.get("upload_selected_names") or []),
        "etapa": int(runtime.get("etapa") or 1),
    }
    secao_texto = ft.Text(str(runtime.get("secao_texto") or "Aguardando pergunta..."), size=12, color=_color("texto_sec", dark))
    contexto_gerado_text = ft.Text(
        str(runtime.get("contexto_text") or (f"Contexto: {estado['contexto_gerado']}" if estado.get("contexto_gerado") else "")),
        size=13,
        color=_color("texto_sec", dark),
        text_align=ft.TextAlign.LEFT,
    )
    escala_text = ft.Text(
        "Escala: nota 0-100 | Aprovado >= 70. Criterios: aderencia ao tema, estrutura, clareza e fundamentacao.",
        size=12,
        color=_color("texto_sec", dark),
    )
    pergunta_text.value = str(runtime.get("pergunta_text") or estado.get("pergunta") or "")
    resposta_field.value = str(runtime.get("resposta") or "")
    gabarito_text.value = str(runtime.get("gabarito_text") or "")
    gabarito_text.visible = bool(runtime.get("gabarito_visible"))
    if str(runtime.get("status") or "").strip():
        status.value = str(runtime.get("status") or "")
        saved_color = str(runtime.get("status_color") or "").strip()
        if saved_color:
            status.color = saved_color

    def _persist_open_quiz_runtime():
        if not isinstance(state, dict):
            return
        state["open_quiz_runtime"] = {
            "tema": str(tema_field.value or ""),
            "resposta": str(resposta_field.value or ""),
            "status": str(status.value or ""),
            "status_color": str(status.color or ""),
            "etapa": int(estado.get("etapa") or 1),
            "pergunta": str(estado.get("pergunta") or ""),
            "gabarito": str(estado.get("gabarito") or ""),
            "contexto_gerado": str(estado.get("contexto_gerado") or ""),
            "gabarito_text": str(gabarito_text.value or ""),
            "gabarito_visible": bool(gabarito_text.visible),
            "upload_texts": list(estado.get("upload_texts") or []),
            "upload_names": list(estado.get("upload_names") or []),
            "upload_selected_names": list(estado.get("upload_selected_names") or []),
            "secao_texto": str(secao_texto.value or ""),
            "contexto_text": str(contexto_gerado_text.value or ""),
            "pergunta_text": str(pergunta_text.value or ""),
        }

    upload_info = ft.Text(
        "Nenhum material enviado.",
        size=12,
        color=_color("texto_sec", dark),
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    etapa_text = ft.Text("Etapa 1 de 2: defina o tema", size=13, color=_color("texto_sec", dark))
    library_files = []
    if library_service and user.get("id"):
        try:
            library_files = library_service.listar_arquivos(user["id"])
        except Exception as ex:
            log_exception(ex, "open_quiz_view._build_open_quiz_body.listar_arquivos")
            
    library_dropdown = ft.Dropdown(
        label="Adicionar da Biblioteca",
        options=[ft.dropdown.Option(str(f["id"]), text=str(f["nome_arquivo"])) for f in library_files],
        disabled=not library_files,
        expand=True,
    )

    def _set_upload_info():
        names = estado["upload_names"] or estado.get("upload_selected_names") or []
        upload_info.value = format_upload_info_label(names)
        _persist_open_quiz_runtime()

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
        return ""

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
            log_exception(ex, "open_quiz_view._build_open_quiz_body.library_select")
            texto = ""
        if texto:
            estado["upload_texts"] = [texto]
            estado["upload_names"] = [nome_tag]
            if not str(tema_field.value or "").strip():
                guessed = _guess_topic_from_name(nome_tag)
                if guessed:
                    tema_field.value = guessed
            _set_upload_info()
            set_feedback_text(status, f"Adicionado da biblioteca: {nome}", "success")
        else:
            estado["upload_texts"] = []
            estado["upload_names"] = []
            _set_upload_info()
            set_feedback_text(status, "Arquivo da biblioteca sem texto extraivel.", "warning")
        e.control.value = None
        try:
            e.control.update()
        except Exception:
            pass
        if page:
            page.update()
        _persist_open_quiz_runtime()

    library_dropdown.on_change = _on_library_select

    async def _pick_files_async():
        if not page:
            return
        guard = state_async_guard(state)

        def _on_start():
            set_feedback_text(status, "Abrindo seletor de arquivos...", "info")
            page.update()

        def _on_timeout():
            set_feedback_text(status, "Tempo esgotado ao buscar arquivos.", "warning")

        def _on_error(ex: Exception):
            log_exception(ex, "open_quiz_view._build_open_quiz_body._pick_files_async")
            set_feedback_text(status, "Falha ao abrir arquivos.", "error")

        async def _run_pick():
            file_paths = await pick_study_files(page)
            if not file_paths:
                set_feedback_text(status, "", "info")
                return
            upload_texts, upload_names, failed_names = extract_uploaded_material(file_paths)
            estado["upload_texts"] = upload_texts
            estado["upload_names"] = upload_names
            estado["upload_selected_names"] = list(upload_names)
            if not upload_texts:
                set_feedback_text(
                    status,
                    ("Nao foi possivel extrair texto dos arquivos. "
                     "Para PDF, confirme que nao e imagem escaneada ou protegido por senha."),
                    "warning",
                )
            else:
                if failed_names:
                    set_feedback_text(status, f"Material carregado: {len(upload_texts)} arquivo(s). Ignorados: {len(failed_names)}.", "warning")
                else:
                    set_feedback_text(status, f"Material carregado: {len(upload_texts)} arquivo(s).", "success")
            _set_upload_info()
            _persist_open_quiz_runtime()

        await guard.run(
            "open_quiz.upload.files",
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
            set_feedback_text(status, "Nao ha material para remover.", "info")
            if page:
                page.update()
            return

        def _confirmed_clear():
            estado["upload_texts"] = []
            estado["upload_names"] = []
            estado["upload_selected_names"] = []
            _set_upload_info()
            set_feedback_text(status, "Material removido.", "info")
            _persist_open_quiz_runtime()
            if page:
                ds_toast(page, "Material removido.", tipo="info")
                page.update()

        show_confirm_dialog(page, "Limpar material", "Deseja remover todo material anexado desta sessao?", _confirmed_clear, confirm_label="Limpar")

    def _mostrar_etapa_geracao():
        estado["etapa"] = 1
        etapa_text.value = "Etapa 1 de 2: defina o tema"
        config_section.visible = True
        study_section.visible = False
        _persist_open_quiz_runtime()

    def _mostrar_etapa_resposta():
        estado["etapa"] = 2
        etapa_text.value = "Etapa 2 de 2: responda com base no contexto"
        config_section.visible = False
        study_section.visible = True
        _persist_open_quiz_runtime()

    def _voltar_geracao(_=None):
        _mostrar_etapa_geracao()
        if page:
            page.update()

    def _show_open_quiz_grade_dialog(feedback: dict):
        if not page:
            return
        nota = int(feedback.get("nota", 0) or 0)
        aprovado = bool(feedback.get("correto"))
        criterios = feedback.get("criterios") if isinstance(feedback.get("criterios"), dict) else {}
        aderencia = int(criterios.get("aderencia", 0) or 0)
        estrutura = int(criterios.get("estrutura", 0) or 0)
        clareza = int(criterios.get("clareza", 0) or 0)
        fundamentacao = int(criterios.get("fundamentacao", 0) or 0)

        def _as_lines(value, limit: int = 3):
            if isinstance(value, list):
                items = [str(x).strip() for x in value if str(x).strip()]
            else:
                raw = str(value or "").strip()
                items = [p.strip(" -•\t") for p in re.split(r"[\n;]+", raw) if p.strip(" -•\t")]
            return items[: max(1, int(limit or 1))]

        fortes = _as_lines(feedback.get("pontos_fortes"), limit=3)
        melhorar = _as_lines(feedback.get("pontos_melhorar"), limit=3)
        feedback_txt = _fix_mojibake_text(str(feedback.get("feedback", "") or "").strip())

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Correcao da dissertativa"),
            content=ft.Container(
                width=max(320, min(760, int((screen_width(page) if page else 1280) - 80))),
                content=ft.Column(
                    [
                        ft.Text(f"Nota: {nota} | {'Aprovado' if aprovado else 'Revisar'}", size=18, weight=ft.FontWeight.BOLD, color=CORES["sucesso"] if aprovado else CORES["warning"]),
                        ft.Text(f"Criterios - Aderencia: {aderencia} | Estrutura: {estrutura} | Clareza: {clareza} | Fundamentacao: {fundamentacao}", size=13, color=_color("texto_sec", dark)),
                        ft.Divider(height=14),
                        ft.Text("Pontos fortes", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text("• " + ("\n• ".join(fortes) if fortes else "Sem destaques registrados."), size=13),
                        ft.Text("Pontos para melhorar", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text("• " + ("\n• ".join(melhorar) if melhorar else "Sem observacoes adicionais."), size=13),
                        ft.Text("Feedback geral", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text(feedback_txt or "Sem feedback detalhado.", size=13),
                        ft.Text("Obs.: a avaliacao nao exige copia literal da resposta esperada.", size=12, color=_color("texto_sec", dark)),
                    ],
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
            ),
        )
        dlg.actions = [ft.ElevatedButton("Fechar", on_click=lambda _: close_dialog_compat(page, dlg))]
        dlg.actions_alignment = ft.MainAxisAlignment.END
        show_dialog_compat(page, dlg)

    async def gerar(_):
        if not page:
            return
        loading.visible = True
        set_feedback_text(status, "Gerando contexto e pergunta-estopim...", "info")
        page.update()
        selected_library_id = str(getattr(library_dropdown, "value", "") or "").strip()
        if selected_library_id and library_service and not estado.get("upload_texts"):
            nome = next((str(f.get("nome_arquivo") or "Arquivo Biblioteca") for f in library_files if str(f.get("id")) == selected_library_id), "Arquivo Biblioteca")
            nome_tag = f"[LIB] {nome}"
            estado["upload_selected_names"] = [nome_tag]
            try:
                texto_lib = library_service.get_conteudo_arquivo(int(selected_library_id))
            except Exception as ex:
                log_exception(ex, "open_quiz_view.generate.library_select")
                texto_lib = ""
            if texto_lib:
                estado["upload_texts"] = [texto_lib]
                estado["upload_names"] = [nome_tag]
                _set_upload_info()
            else:
                estado["upload_texts"] = []
                estado["upload_names"] = []
                _set_upload_info()

        selected_names = list(estado.get("upload_names") or estado.get("upload_selected_names") or [])
        if selected_names and not estado.get("upload_texts"):
            loading.visible = False
            set_feedback_text(status, "O PDF selecionado nao teve texto extraido. Use um PDF com texto pesquisavel ou anexe outro arquivo.", "warning")
            page.update()
            return

        tema = _resolve_theme_value()
        if not tema:
            if estado.get("upload_texts"):
                tema = "Conteudo principal do material anexado"
            else:
                loading.visible = False
                set_feedback_text(status, "Defina o tema antes de gerar ou selecione um PDF com texto extraivel.", "warning")
                page.update()
                return
        if not str(tema_field.value or "").strip():
            tema_field.value = tema

        contexto = [f"Tema central: {tema}"]
        source_lock = bool(estado["upload_texts"])
        if estado["upload_texts"]:
            source_label = ", ".join(selected_names[:2]) if selected_names else "material anexado"
            contexto.append(f"INSTRUCAO DE FOCO: Gere contexto e pergunta usando apenas o material selecionado ({source_label}).")
            contexto.extend(list(estado["upload_texts"]))
        content_for_open_question = list(estado["upload_texts"]) if estado["upload_texts"] else list(contexto)
        pergunta = None
        if service:
            try:
                pergunta = await asyncio.to_thread(service.generate_open_question, content_for_open_question, tema, source_lock, "Medio")
            except Exception as ex:
                log_exception(ex, "open_quiz_view.generate")
        if not pergunta:
            contexto_gerado = f"Você está analisando o tema '{tema}' em um cenário prático, exigindo argumento claro, exemplos e conclusão."
            pergunta = {
                "pergunta": f"Explique os pontos principais sobre {tema}.",
                "resposta_esperada": f"Resposta esperada com fundamentos, estrutura clara e exemplos sobre {tema}.",
                "contexto": contexto_gerado,
            }
            if is_ai_quota_exceeded(service):
                set_feedback_text(status, "Cotas da IA esgotadas. Contexto/pergunta gerados no modo offline.", "warning")
                show_quota_dialog(page, navigate)
            else:
                set_feedback_text(status, "Contexto e pergunta gerados no modo offline.", "info")
        else:
            set_feedback_text(status, "Contexto e pergunta gerados com IA.", "success")
            
        estado["contexto_gerado"] = pergunta.get("contexto") or pergunta.get("cenario") or f"Cenário gerado para o tema '{tema}'."
        estado["contexto_gerado"] = _fix_mojibake_text(str(estado["contexto_gerado"] or ""))
        sw = screen_width(page) if page else 1280
        pergunta_text.size = 16 if sw < 900 else (18 if sw < 1280 else 20)
        estado["pergunta"] = _fix_mojibake_text(str(pergunta.get("pergunta", "") or ""))
        estado["gabarito"] = _fix_mojibake_text(str(pergunta.get("resposta_esperada", "") or ""))
        contexto_gerado_text.value = f"Contexto: {estado['contexto_gerado']}"
        pergunta_text.value = estado["pergunta"]
        gabarito_text.value = "Gabarito oculto ate a correcao."
        gabarito_text.visible = False
        secao_texto.value = "Contexto e pergunta prontos."
        resposta_field.value = ""
        _mostrar_etapa_resposta()
        _persist_open_quiz_runtime()
        loading.visible = False
        page.update()

    async def corrigir(_):
        if not page:
            return
        if not estado["pergunta"] or not resposta_field.value:
            status.value = "Gere uma pergunta e responda antes de corrigir."
            page.update()
            return
        if (not is_premium_active(user)) and user.get("id"):
            allowed = True
            _used = 0
            consumed_online = False
            if backend and backend.enabled():
                try:
                    backend_uid_val = backend_user_id(user)
                    if int(backend_uid_val or 0) > 0:
                        usage = await asyncio.to_thread(backend.consume_usage, int(backend_uid_val), "open_quiz_grade", 1)
                        allowed = bool(usage.get("allowed"))
                        _used = int(usage.get("used") or 0)
                        consumed_online = True
                except Exception as ex:
                    log_exception(ex, "open_quiz_view.consume_usage_backend")
            if (not consumed_online) and db:
                allowed, _used = db.consumir_limite_diario(user["id"], "open_quiz_grade", 1)
            if not allowed:
                set_feedback_text(status, "Free: limite diario da dissertativa atingido (1/dia).", "warning")
                show_upgrade_dialog(page, navigate, "No plano Free voce pode corrigir 1 dissertativa por dia.")
                page.update()
                return
        loading.visible = True
        set_feedback_text(status, "Corrigindo resposta...", "info")
        page.update()
        feedback = None
        if service:
            try:
                feedback = await asyncio.to_thread(service.grade_open_answer, estado["pergunta"], resposta_field.value, estado["gabarito"])
            except Exception as ex:
                log_exception(ex, "open_quiz_view.grade")
        if not feedback:
            nota = 80 if len(resposta_field.value.split()) > 40 else 55
            feedback = {
                "nota": nota,
                "correto": nota >= 70,
                "criterios": {"aderencia": nota, "estrutura": max(45, nota - 8), "clareza": max(45, nota - 5), "fundamentacao": max(40, nota - 10)},
                "pontos_fortes": ["Resposta objetiva e conectada ao tema proposto."],
                "pontos_melhorar": ["Aprofunde argumentos com exemplos e conclusao mais forte."],
                "feedback": "Estruture melhor em introducao, desenvolvimento e conclusao para melhorar a nota.",
            }
            if is_ai_quota_exceeded(service):
                show_quota_dialog(page, navigate)
        if db and user.get("id"):
            try:
                db.registrar_progresso_diario(user["id"], discursivas=1)
            except Exception as ex:
                log_exception(ex, "open_quiz_view.registrar_progresso_diario")
        set_feedback_text(status, f"Nota: {feedback.get('nota', 0)} | {'Aprovado' if feedback.get('correto') else 'Revisar'}", "success" if feedback.get("correto") else "warning")
        gabarito_text.value = ""
        gabarito_text.visible = False
        _show_open_quiz_grade_dialog(feedback)
        _persist_open_quiz_runtime()
        loading.visible = False
        page.update()

    def _on_gerar_click(e):
        if not page:
            return
        schedule_ai_task(page, state, gerar, e, message="IA gerando contexto e pergunta...", status_control=status)

    def _on_corrigir_click(_):
        if not page:
            return
        schedule_ai_task(page, state, corrigir, _, message="IA corrigindo resposta dissertativa...", status_control=status)

    def limpar(_):
        estado["pergunta"] = ""
        estado["gabarito"] = ""
        estado["contexto_gerado"] = ""
        contexto_gerado_text.value = ""
        pergunta_text.value = ""
        gabarito_text.value = ""
        gabarito_text.visible = False
        resposta_field.value = ""
        status.value = "Campos limpos."
        secao_texto.value = "Aguardando pergunta..."
        _mostrar_etapa_geracao()
        _persist_open_quiz_runtime()
        if page:
            page.update()

    config_section = ds_card(
        dark=dark,
        padding=14,
        content=ft.Column(
            [
                ft.Text("1) Defina o tema", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                ft.ResponsiveRow([ft.Container(content=tema_field, col={"sm": 12, "md": 6})]),
                ft.Text("A IA vai gerar automaticamente o contexto e a pergunta-estopim para sua dissertacao.", size=12, color=_color("texto_sec", dark)),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 4}, content=ds_btn_secondary("Anexar material", icon=ft.Icons.UPLOAD_FILE, on_click=_upload_material, dark=dark, expand=True)),
                        ft.Container(col={"xs": 12, "md": 5}, content=library_dropdown),
                        ft.Container(col={"xs": 12, "md": 3}, content=ds_btn_ghost("Limpar material", on_click=_limpar_material, dark=dark)),
                        ft.Container(col={"xs": 12, "md": 12}, content=upload_info),
                    ],
                    run_spacing=6, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 4}, content=ds_btn_primary("Gerar contexto e pergunta", icon=ft.Icons.BOLT, on_click=_on_gerar_click, expand=True, dark=dark)),
                        ft.Container(col={"xs": 12, "md": 8}, content=ft.Row([loading, ft.Container(expand=True, content=status_banner(status, dark))], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)),
                    ],
                    run_spacing=6, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=10,
        ),
    )

    study_section = ft.Column(
        [
            ft.Row([ft.Text("2) Sua resposta", size=18, weight=ft.FontWeight.BOLD, color=_color("texto", dark)), secao_texto], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ResponsiveRow(
                [
                    ft.Container(
                        col={"xs": 12, "md": 12},
                        content=ds_card(
                            dark=dark, padding=8, expand=True,
                            content=ft.Container(
                                height=max(200, min(340, int(screen_h * 0.38))),
                                content=ft.Column(
                                    [
                                        ft.Text("Contexto", size=12, weight=ft.FontWeight.W_600, color=_color("texto_sec", dark)),
                                        ft.Container(alignment=ft.Alignment(-1, 0), content=contexto_gerado_text),
                                        ds_divider(dark),
                                        ft.Text("Pergunta", size=12, weight=ft.FontWeight.W_600, color=_color("texto_sec", dark)),
                                        ft.Container(alignment=ft.Alignment(-1, 0), content=pergunta_text),
                                    ],
                                    spacing=8, scroll=ft.ScrollMode.AUTO,
                                ),
                            ),
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 12},
                        content=ds_card(
                            dark=dark, padding=8, expand=True,
                            content=ft.Column(
                                [
                                    ft.Text("Sua resposta", size=12, weight=ft.FontWeight.W_600, color=_color("texto_sec", dark)),
                                    ft.Container(expand=True, content=resposta_field),
                                ],
                                spacing=8,
                            ),
                        ),
                    ),
                ],
                spacing=10, run_spacing=10,
            ),
            escala_text,
            ft.Row([ft.Container(content=ds_btn_primary("3) Corrigir Avaliação", icon=ft.Icons.CHECK, on_click=_on_corrigir_click, dark=dark), expand=True)]),
            ft.Row(
                [
                    ft.TextButton("Limpar", icon=ft.Icons.RESTART_ALT, on_click=limpar),
                    ft.TextButton("Refazer Geração", icon=ft.Icons.ARROW_BACK, on_click=_voltar_geracao),
                    ft.TextButton("Início", icon=ft.Icons.HOME_OUTLINED, on_click=lambda _: navigate("/home"))
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=15,
                wrap=True
            ),
            gabarito_text,
        ],
        spacing=10, expand=True, scroll=ft.ScrollMode.AUTO, visible=False,
    )

    if estado.get("etapa") == 2 and str(estado.get("pergunta") or "").strip():
        _mostrar_etapa_resposta()
    else:
        _mostrar_etapa_geracao()

    _set_upload_info()
    tema_field.on_change = lambda _: _persist_open_quiz_runtime()
    resposta_field.on_change = lambda _: _persist_open_quiz_runtime()

    return wrap_study_content(
        ft.Column(
            [
                build_focus_header("Dissertativo", "Fluxo: 1) Tema  2) Contexto e pergunta  3) Resposta e correcao", etapa_text, dark),
                config_section,
                study_section,
            ],
            spacing=10,
            expand=True,
        ),
        dark,
    )
