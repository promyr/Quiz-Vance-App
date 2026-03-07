# -*- coding: utf-8 -*-
"""View de biblioteca — extraída do main_v2.py."""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import os
import random

import flet as ft

from config import CORES
from core.error_monitor import log_event, log_exception
from core.quiz_defaults import DEFAULT_QUIZ_QUESTIONS
from core.library_service import LibraryService
from core.services.study_summary_service import StudySummaryService
from core.ui_route_theme import _color
from core.ui_text_sanitizer import _sanitize_payload_texts
from core.helpers.ai_helpers import create_user_ai_service, schedule_ai_task
from core.helpers.file_helpers import (
    normalize_uploaded_file_path,
    pick_study_files,
    state_async_guard,
)
from core.helpers.ui_helpers import (
    is_premium_active,
    show_api_issue_dialog,
    show_confirm_dialog,
    show_upgrade_dialog,
)
from core.app_paths import get_data_dir
from ui.design_system import (
    ds_btn_primary,
    ds_card,
    ds_section_title,
    ds_toast,
)


def build_library_body(state: dict, navigate, dark: bool) -> ft.Control:
    page = state.get("page")
    user = state.get("usuario") or {}
    db = state.get("db")
    if not db or not user:
        return ft.Text("Erro: Usuario nao autenticado")

    library_service = LibraryService(db)
    summary_service = StudySummaryService()

    file_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=False)
    package_list = ft.Column(spacing=6)
    status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    upload_ring = ft.ProgressRing(width=20, height=20, visible=False)
    files_count_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=_color("texto", dark))
    packs_count_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=CORES["primaria"])

    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    def _start_quiz_from_package(dados: dict):
        dados = _as_dict(dados)
        questions = dados.get("questoes") or []
        if not questions:
            status_text.value = "Pacote sem questoes."
            status_text.color = CORES["warning"]
            if page:
                page.update()
            return
        state["quiz_package_questions"] = questions
        navigate("/quiz")

    def _start_flashcards_from_package(dados: dict):
        dados = _as_dict(dados)
        cards = dados.get("flashcards") or []
        if not cards:
            summary = _as_dict(dados.get("summary_v2"))
            cards = summary.get("sugestoes_flashcards") or []
        seed_cards = []
        for item in cards:
            if not isinstance(item, dict):
                continue
            frente = str(item.get("frente") or item.get("front") or "").strip()
            verso = str(item.get("verso") or item.get("back") or "").strip()
            if frente and verso:
                seed_cards.append({"frente": frente, "verso": verso})
        if not seed_cards:
            status_text.value = "Pacote sem flashcards."
            status_text.color = CORES["warning"]
            if page:
                page.update()
            return
        state["flashcards_seed_cards"] = seed_cards
        navigate("/flashcards")

    def _start_plan_from_package(pkg: dict):
        pkg = _as_dict(pkg)
        dados = _as_dict(pkg.get("dados"))
        summary = _as_dict(dados.get("summary_v2"))
        topicos = summary.get("topicos_principais") or summary.get("topicos") or dados.get("topicos") or []
        topicos = [str(t).strip() for t in topicos if str(t).strip()][:10]
        state["study_plan_seed"] = {"objetivo": str(pkg.get("titulo") or "Plano de estudo"), "data_prova": "", "tempo_diario": 90, "topicos": topicos}
        navigate("/study-plan")

    def _safe_file_stub(value: str) -> str:
        return summary_service.safe_file_stub(value)

    def _build_package_markdown(pkg: dict) -> str:
        return summary_service.build_package_markdown(pkg)

    def _build_package_plain_text(pkg: dict) -> str:
        return summary_service.build_package_plain_text(pkg)

    def _write_simple_pdf(path, title: str, text: str):
        _ = title
        summary_service.write_simple_pdf(path, text)

    def _export_package_markdown(pkg: dict):
        try:
            export_dir = get_data_dir() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_base = _safe_file_stub(pkg.get("titulo") or "pacote_estudo")
            out_path = export_dir / f"{nome_base}_{stamp}.md"
            markdown = _build_package_markdown(pkg)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(markdown)
            status_text.value = f"Resumo exportado: {out_path}"
            status_text.color = CORES["sucesso"]
            if page:
                ds_toast(page, "Exportado em Markdown.", tipo="sucesso")
                page.update()
        except Exception as ex:
            log_exception(ex, "library_view._export_package_markdown")
            status_text.value = "Falha ao exportar Markdown."
            status_text.color = CORES["erro"]
            if page:
                ds_toast(page, "Erro ao exportar Markdown.", tipo="erro")
                page.update()

    def _export_package_pdf(pkg: dict):
        try:
            export_dir = get_data_dir() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_base = _safe_file_stub(pkg.get("titulo") or "pacote_estudo")
            out_path = export_dir / f"{nome_base}_{stamp}.pdf"
            plain_text = _build_package_plain_text(pkg)
            _write_simple_pdf(out_path, str(pkg.get("titulo") or "Pacote de Estudo"), plain_text)
            status_text.value = f"PDF exportado: {out_path}"
            status_text.color = CORES["sucesso"]
            if page:
                ds_toast(page, "Exportado em PDF.", tipo="sucesso")
                page.update()
        except Exception as ex:
            log_exception(ex, "library_view._export_package_pdf")
            status_text.value = "Falha ao exportar PDF."
            status_text.color = CORES["erro"]
            if page:
                ds_toast(page, "Erro ao exportar PDF.", tipo="erro")
                page.update()

    def _refresh_packages():
        package_list.controls.clear()
        try:
            packs = db.listar_study_packages(user["id"], limite=8)
        except Exception as ex:
            log_exception(ex, "library_view._refresh_packages")
            packs = []
        packs_count_text.value = str(len(packs))
        if not packs:
            package_list.controls.append(ft.Text("Nenhum pacote gerado ainda.", size=11, color=_color("texto_sec", dark)))
            return
        for p in packs:
            p = _as_dict(p)
            dados = _as_dict(p.get("dados"))
            qcount = len(dados.get("questoes") or [])
            fcount = len(dados.get("flashcards") or [])
            package_list.controls.append(ft.Container(
                padding=10, border_radius=8, bgcolor=_color("card", dark),
                content=ft.Column([
                    ft.Row([ft.Column([
                        ft.Text(p.get("titulo", "Pacote"), weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ft.Text(f"{qcount} questoes - {fcount} flashcards", size=11, color=_color("texto_sec", dark)),
                    ], spacing=2, expand=True)]),
                    ft.ResponsiveRow([
                        ft.Container(col={"xs": 12, "md": 4}, content=ft.TextButton("Quiz", icon=ft.Icons.PLAY_ARROW, on_click=lambda _, d=dados: _start_quiz_from_package(d))),
                        ft.Container(col={"xs": 12, "md": 4}, content=ft.TextButton("Cards", icon=ft.Icons.STYLE_OUTLINED, on_click=lambda _, d=dados: _start_flashcards_from_package(d))),
                        ft.Container(col={"xs": 12, "md": 4}, content=ft.TextButton("Plano", icon=ft.Icons.CALENDAR_MONTH_OUTLINED, on_click=lambda _, item=p: _start_plan_from_package(item))),
                        ft.Container(col={"xs": 12, "md": 12}, alignment=ft.Alignment(1, 0),
                                     content=ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ, tooltip="Mais acoes", items=[
                                         ft.PopupMenuItem(text="Exportar .md", icon=ft.Icons.DOWNLOAD_OUTLINED, on_click=lambda _, item=p: _export_package_markdown(item)),
                                         ft.PopupMenuItem(text="Exportar .pdf", icon=ft.Icons.PICTURE_AS_PDF, on_click=lambda _, item=p: _export_package_pdf(item)),
                                     ])),
                    ], run_spacing=6, spacing=6),
                ], spacing=6),
            ))

    async def _generate_package_async(file_id: int, file_name: str):
        if not page:
            return
        status_text.value = f"Gerando pacote: {file_name}..."
        status_text.color = _color("texto_sec", dark)
        upload_ring.visible = True
        page.update()
        try:
            content_txt = await asyncio.to_thread(library_service.get_conteudo_arquivo, file_id)
            if not content_txt.strip():
                status_text.value = "Arquivo sem texto para pacote."
                status_text.color = CORES["warning"]
                return
            chunks = [line.strip() for line in content_txt.splitlines() if line.strip()]
            source_hash = hashlib.sha256(f"{file_name}\n{content_txt[:180000]}".encode("utf-8", errors="ignore")).hexdigest()
            service = create_user_ai_service(user)
            summary = {"titulo": f"Resumo de {file_name}", "resumo_curto": "Resumo indisponivel.", "resumo_estruturado": [], "topicos_principais": [], "definicoes": [], "exemplos": [], "pegadinhas": [], "checklist_de_estudo": [], "sugestoes_flashcards": [], "sugestoes_questoes": [], "resumo": "Resumo indisponivel.", "topicos": []}
            summary_from_cache = False
            if db and user.get("id"):
                cached = db.obter_resumo_por_hash(int(user["id"]), source_hash)
                if isinstance(cached, dict) and cached:
                    summary = cached
                    summary_from_cache = True
                    status_text.value = "Resumo reutilizado do cache. Gerando questoes..."
            questoes = []
            flashcards = []
            if service:
                if not summary_from_cache:
                    if (not is_premium_active(user)) and db and user.get("id"):
                        allowed, _used = db.consumir_limite_diario(int(user["id"]), "study_summary", 2)
                        if not allowed:
                            status_text.value = "Plano Free: limite de 2 resumos/dia atingido."
                            status_text.color = CORES["warning"]
                            show_upgrade_dialog(page, navigate, "No Premium voce gera resumos ilimitados por dia.")
                            return
                    summary = await asyncio.to_thread(service.generate_study_summary, chunks, file_name, 1)
                    if db and user.get("id"):
                        try:
                            db.salvar_resumo_por_hash(int(user["id"]), source_hash, file_name, summary)
                        except Exception as ex:
                            log_exception(ex, "library_view._generate_package_async.save_summary_cache")
                lote_quiz = await asyncio.to_thread(service.generate_quiz_batch, chunks, file_name, "Intermediario", 3, 1)
                for q in lote_quiz or []:
                    questoes.append(_sanitize_payload_texts({"enunciado": q.get("pergunta", ""), "alternativas": q.get("opcoes", []), "correta_index": q.get("correta_index", 0)}))
                flashcards = await asyncio.to_thread(service.generate_flashcards, chunks, 5, 1)
            if not questoes:
                questoes = random.sample(DEFAULT_QUIZ_QUESTIONS, min(3, len(DEFAULT_QUIZ_QUESTIONS)))
            if db and user.get("id"):
                try:
                    if flashcards:
                        db.salvar_flashcards_gerados(int(user["id"]), str(file_name or "Geral"), flashcards, "intermediario")
                    if questoes:
                        from core.repositories.question_progress_repository import QuestionProgressRepository
                        qrepo = QuestionProgressRepository(db)
                        for q in questoes:
                            if isinstance(q, dict):
                                qrepo.register_result(int(user["id"]), q, "mark")
                except Exception as ex:
                    log_exception(ex, "library_view._generate_package_async.integrate_review_flow")
            resumo_curto = str(summary.get("resumo_curto") or summary.get("resumo") or "").strip()
            topicos_principais = summary.get("topicos_principais") or summary.get("topicos") or []
            if not isinstance(topicos_principais, list):
                topicos_principais = []
            pacote = {"resumo": resumo_curto, "topicos": [str(t).strip() for t in topicos_principais if str(t).strip()][:12], "summary_v2": summary, "questoes": questoes, "flashcards": flashcards}
            db.salvar_study_package(user["id"], f"Pacote - {file_name}", file_name, pacote)
            status_text.value = "Pacote gerado e salvo."
            status_text.color = CORES["sucesso"]
            _refresh_packages()
        except Exception as ex:
            log_exception(ex, "library_view._generate_package_async")
            msg = str(ex).lower()
            if "401" in msg or "key" in msg or "auth" in msg:
                status_text.value = "Erro: API Key invalida!"
                ds_toast(page, "Chave de API invalida. Verifique Configuracoes.", tipo="erro")
                show_api_issue_dialog(page, navigate, "auth")
            elif "429" in msg or "quota" in msg:
                status_text.value = "Erro: Cota excedida!"
                ds_toast(page, "Limite gratuito da API excedido.", tipo="erro")
                show_api_issue_dialog(page, navigate, "quota")
            else:
                status_text.value = "Falha tecnica na geracao."
                ds_toast(page, f"Erro na IA: {msg[:40]}...", tipo="erro")
            status_text.color = CORES["erro"]
        finally:
            upload_ring.visible = False
            page.update()

    def _refresh_list():
        try:
            file_list.controls.clear()
            arquivos = library_service.listar_arquivos(user["id"])
            log_event("library_refresh", f"found {len(arquivos)} files")
            files_count_text.value = str(len(arquivos))
            if not arquivos:
                file_list.controls.append(ft.Container(padding=20, alignment=ft.Alignment(0, 0), content=ft.Column([
                    ft.Icon(ft.Icons.LIBRARY_ADD, size=48, color=_color("texto_sec", dark)),
                    ft.Text("Sua biblioteca esta vazia", color=_color("texto_sec", dark)),
                    ft.Text("Faca upload de PDFs para usar nos quizzes", size=12, color=_color("texto_sec", dark)),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
            else:
                for arq in arquivos:
                    nome = arq["nome_arquivo"]
                    date_str = arq.get("data_upload", "")[:10]
                    fid = arq["id"]
                    btn_delete = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=CORES["erro"], tooltip="Excluir", on_click=lambda _, i=fid: _delete_file(i))
                    btn_package = ft.IconButton(icon=ft.Icons.AUTO_AWESOME, tooltip="Gerar pacote", on_click=lambda _, i=fid, n=nome: schedule_ai_task(page, state, _generate_package_async, i, n, message=f"IA gerando pacote: {n}...", status_control=status_text))
                    file_list.controls.append(ft.Container(
                        padding=8, border_radius=8, bgcolor=_color("card", dark),
                        content=ft.Column([ft.Row([
                            ft.Icon(ft.Icons.PICTURE_AS_PDF if nome.endswith(".pdf") else ft.Icons.DESCRIPTION, color=CORES["primaria"]),
                            ft.Column([
                                ft.Text(nome, weight=ft.FontWeight.BOLD, color=_color("texto", dark), max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(f"{date_str} - {arq.get('total_paginas', 0)} paginas", size=11, color=_color("texto_sec", dark)),
                            ], expand=True, spacing=2),
                            btn_package, btn_delete,
                        ], spacing=8)], spacing=4),
                    ))
            if page:
                page.update()
        except Exception as e:
            log_exception(e, "library_view._refresh_list")

    def _delete_file(file_id):
        def _confirmed_delete():
            try:
                library_service.excluir_arquivo(file_id, user["id"])
                status_text.value = "Arquivo removido."
                status_text.color = CORES["sucesso"]
                if page:
                    ds_toast(page, "Arquivo removido com sucesso.", tipo="sucesso")
                _refresh_list()
            except Exception as e:
                status_text.value = f"Erro: {e}"
                status_text.color = CORES["erro"]
                log_exception(e, "library_view._delete_file")
                if page:
                    ds_toast(page, "Falha ao remover arquivo.", tipo="erro")
                    page.update()
        show_confirm_dialog(page, "Excluir arquivo", "Deseja excluir este arquivo da biblioteca?", _confirmed_delete, confirm_label="Excluir")

    async def _upload_files_async():
        guard = state_async_guard(state)

        def _on_start():
            upload_ring.visible = True
            status_text.value = "Abrindo seletor de arquivos..."
            status_text.color = _color("texto_sec", dark)
            page.update()

        def _on_timeout():
            status_text.value = "Tempo esgotado ao buscar arquivos. Tente novamente."
            status_text.color = CORES["warning"]

        def _on_error(ex: Exception):
            log_exception(ex, "library_view._upload_files_async")
            status_text.value = f"Erro no upload: {ex}"
            status_text.color = CORES["erro"]

        def _on_finish():
            upload_ring.visible = False
            page.update()

        async def _run_upload():
            file_paths = await pick_study_files(page)
            if not file_paths:
                status_text.value = ""
                return
            if (not is_premium_active(user)) and len(file_paths) > 1:
                status_text.value = "Plano Free: envie apenas 1 arquivo por vez na Biblioteca."
                status_text.color = CORES["warning"]
                show_upgrade_dialog(page, navigate, "No Premium, o upload na Biblioteca e ilimitado por envio.")
                return
            count = 0
            failed = []
            for path in file_paths:
                try:
                    library_service.adicionar_arquivo(user["id"], path)
                    count += 1
                except Exception as ex_file:
                    failed.append(os.path.basename(normalize_uploaded_file_path(path) or str(path)))
                    log_exception(ex_file, "library_view._upload_files_async.add_file")
            if count <= 0:
                status_text.value = "Falha ao adicionar arquivo(s). Verifique o caminho/permissao do PDF."
                status_text.color = CORES["erro"]
                if page:
                    ds_toast(page, "Nao foi possivel adicionar os PDFs selecionados.", tipo="erro")
                return
            if failed:
                status_text.value = f"{count} arquivo(s) adicionados. Ignorados: {len(failed)}."
                status_text.color = CORES["warning"]
                if page:
                    ds_toast(page, f"{count} arquivo(s) adicionados; {len(failed)} falharam.", tipo="warning")
            else:
                status_text.value = f"{count} arquivo(s) adicionado(s) com sucesso!"
                status_text.color = CORES["sucesso"]
                if page:
                    ds_toast(page, f"{count} arquivo(s) adicionado(s) com sucesso!", tipo="sucesso")
            _refresh_list()

        await guard.run("library.upload.files", _run_upload, timeout_s=300, on_start=_on_start, on_timeout=_on_timeout, on_error=_on_error, on_finish=_on_finish)

    def _upload_click(_):
        if page:
            page.run_task(_upload_files_async)

    _refresh_list()
    _refresh_packages()
    return ft.Container(
        expand=True, bgcolor=_color("fundo", dark), padding=20,
        content=ft.Column([
            ds_section_title("Minha Biblioteca", dark=dark),
            ft.ResponsiveRow(controls=[
                ft.Container(col={"sm": 6, "md": 3}, content=ds_card(dark=dark, padding=12, content=ft.Column([ft.Text("Arquivos", size=12, color=_color("texto_sec", dark)), files_count_text], spacing=4))),
                ft.Container(col={"sm": 6, "md": 3}, content=ds_card(dark=dark, padding=12, content=ft.Column([ft.Text("Pacotes", size=12, color=_color("texto_sec", dark)), packs_count_text], spacing=4))),
            ], spacing=8, run_spacing=8),
            ds_card(dark=dark, padding=12, content=ft.Column([
                ft.ResponsiveRow([
                    ft.Container(col={"xs": 12, "md": 6}, content=ft.Text("Acoes", size=15, weight=ft.FontWeight.W_600, color=_color("texto", dark))),
                    ft.Container(col={"xs": 12, "md": 6}, alignment=ft.Alignment(1, 0), content=ds_btn_primary("Adicionar PDF", icon=ft.Icons.UPLOAD_FILE, on_click=_upload_click, dark=dark)),
                ], run_spacing=8, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([ft.Container(expand=True, content=status_text), upload_ring], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=8)),
            ds_card(dark=dark, padding=12, content=ft.Column([
                ft.Text("Pacotes de Estudo", size=15, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                ft.Container(height=208, content=ft.Column([package_list], scroll=ft.ScrollMode.AUTO)),
            ], spacing=8)),
            ds_card(dark=dark, padding=12, content=ft.Column([
                ft.Text("Arquivos", size=15, weight=ft.FontWeight.W_600, color=_color("texto", dark)),
                ft.Container(height=286, content=file_list),
            ], spacing=8)),
        ], expand=True, spacing=10, scroll=ft.ScrollMode.AUTO),
    )
