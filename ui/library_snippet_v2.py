import asyncio

import flet as ft

from config import CORES
from core.library_service import LibraryService
from core.ui_route_theme import _color


def _build_library_body(state, navigate, dark: bool):
    page = state.get("page")
    user = state.get("usuario") or {}
    db = state.get("db")
    if not db or not user:
        return ft.Text("Erro: Usuario nao autenticado")

    library_service = LibraryService(db)

    file_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    status_text = ft.Text("", size=12, color=_color("texto_sec", dark))
    upload_ring = ft.ProgressRing(width=20, height=20, visible=False)

    def _refresh_list():
        file_list.controls.clear()
        arquivos = library_service.listar_arquivos(user["id"])

        if not arquivos:
            file_list.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.LIBRARY_ADD, size=48, color=_color("texto_sec", dark)),
                            ft.Text("Sua biblioteca esta vazia", color=_color("texto_sec", dark)),
                            ft.Text("Faca upload de PDFs para usar nos quizzes", size=12, color=_color("texto_sec", dark)),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )
        else:
            for arq in arquivos:
                nome = arq["nome_arquivo"]
                date_str = arq.get("data_upload", "")[:10]
                fid = arq["id"]

                btn_delete = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=CORES["erro"],
                    tooltip="Excluir",
                    on_click=lambda _, i=fid: _delete_file(i),
                )

                file_list.controls.append(
                    ft.Container(
                        padding=10,
                        border_radius=8,
                        bgcolor=_color("card", dark),
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.PICTURE_AS_PDF if nome.endswith(".pdf") else ft.Icons.DESCRIPTION,
                                    color=CORES["primaria"],
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            nome,
                                            weight=ft.FontWeight.BOLD,
                                            color=_color("texto", dark),
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            f"Adicionado em {date_str} - {arq.get('total_paginas', 0)} paginas",
                                            size=12,
                                            color=_color("texto_sec", dark),
                                        ),
                                    ],
                                    expand=True,
                                    spacing=2,
                                ),
                                btn_delete,
                            ]
                        ),
                    )
                )

        if page:
            page.update()

    def _delete_file(file_id):
        try:
            library_service.excluir_arquivo(file_id, user["id"])
            status_text.value = "Arquivo removido."
            status_text.color = CORES["sucesso"]
            _refresh_list()
        except Exception as ex:
            status_text.value = f"Erro: {ex}"
            status_text.color = CORES["erro"]
            if page:
                page.update()

    async def _process_upload(e: ft.FilePickerResultEvent):
        if not e.files:
            return

        upload_ring.visible = True
        status_text.value = "Processando upload..."
        page.update()

        count = 0
        try:
            for f in e.files:
                await asyncio.to_thread(library_service.adicionar_arquivo, user["id"], f.path)
                count += 1

            status_text.value = f"{count} arquivo(s) adicionado(s) com sucesso!"
            status_text.color = CORES["sucesso"]
            _refresh_list()
        except Exception as ex:
            status_text.value = f"Erro no upload: {ex}"
            status_text.color = CORES["erro"]
        finally:
            upload_ring.visible = False
            page.update()

    file_picker = ft.FilePicker(on_result=_process_upload)
    page.overlay.append(file_picker)

    return ft.Container(
        expand=True,
        bgcolor=_color("fundo", dark),
        padding=20,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Minha Biblioteca", size=28, weight=ft.FontWeight.BOLD, color=_color("texto", dark)),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Adicionar PDF",
                            icon=ft.Icons.UPLOAD_FILE,
                            on_click=lambda _: file_picker.pick_files(
                                allow_multiple=True, allowed_extensions=["pdf", "txt", "md"]
                            ),
                            style=ft.ButtonStyle(bgcolor=CORES["primaria"], color="white"),
                        ),
                    ]
                ),
                ft.Text(
                    "Gerencie seus materiais de estudo. Use-os para gerar quizzes personalizados.",
                    size=14,
                    color=_color("texto_sec", dark),
                ),
                ft.Container(height=10),
                ft.Row([status_text, upload_ring]),
                ft.Container(height=10),
                file_list,
            ],
            expand=True,
        ),
        on_mount=lambda _: _refresh_list(),
    )
