# -*- coding: utf-8 -*-
"""
LoginView - versao estavel para Flet 0.80.x
"""

import asyncio
import threading
import os
import flet as ft

from config import CORES, GOOGLE_OAUTH
from core.auth_service import authenticate_with_google
from core.error_monitor import log_exception


class LoginView(ft.View):
    def __init__(self, page, database, on_login_success, backend=None):
        super().__init__(route="/login")
        self._page = page
        self.db = database
        self.backend = backend
        self.on_login_success = on_login_success
        self.tema_escuro = page.theme_mode == ft.ThemeMode.DARK
        self.modo_atual = "login"
        self.autenticando_google = False
        self.auth_busy = False
        # Modo padrao: autenticacao somente online (backend).
        self.online_only_auth = str(os.getenv("QUIZVANCE_AUTH_MODE") or "online").strip().lower() != "hybrid"
        self.google_login_enabled = bool(GOOGLE_OAUTH.get("enabled", False)) and (not self.online_only_auth)
        self._prev_keyboard_handler = getattr(self._page, "on_keyboard_event", None)

        self._criar_componentes()
        self._construir_interface()
        self._page.on_keyboard_event = self._on_keyboard_event

    def _criar_componentes(self):
        # Login
        self.email_login = ft.TextField(
            label="ID",
            hint_text="seu_id",
            width=360,
            prefix_icon=ft.Icons.PERSON,
            autofocus=True,
        )
        self.senha_login = ft.TextField(
            label="Senha",
            password=True,
            can_reveal_password=True,
            width=360,
            prefix_icon=ft.Icons.LOCK,
        )

        # Cadastro
        self.nome_cad = ft.TextField(label="Nome completo", width=360, prefix_icon=ft.Icons.PERSON)
        self.email_cad = ft.TextField(label="ID", width=360, prefix_icon=ft.Icons.PERSON)
        self.senha_cad = ft.TextField(
            label="Senha",
            password=True,
            can_reveal_password=True,
            width=360,
            prefix_icon=ft.Icons.LOCK,
        )
        self.idade_cad = ft.TextField(
            label="Data de nascimento",
            hint_text="DD/MM/AAAA",
            width=360,
            keyboard_type=ft.KeyboardType.DATETIME,
            prefix_icon=ft.Icons.CAKE,
        )
        self.idade_cad.on_change = self._on_data_nascimento_change

        self.email_login.on_submit = self._submit_login_id
        self.senha_login.on_submit = self._submit_login
        self.nome_cad.on_submit = self._submit_cadastro_nome
        self.email_cad.on_submit = self._submit_cadastro_email
        self.senha_cad.on_submit = self._submit_cadastro_senha
        self.idade_cad.on_submit = self._submit_cadastro

        self.loading = ft.Column(
            controls=[
                ft.ProgressRing(width=36, height=36),
                ft.Text("Autenticando com Google...", size=13),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            visible=False,
        )
        self.login_feedback = ft.Text("", visible=False, size=12, text_align=ft.TextAlign.CENTER)
        self.cadastro_feedback = ft.Text("", visible=False, size=12, text_align=ft.TextAlign.CENTER)

    def _construir_interface(self):
        bg_color = CORES["fundo_escuro"] if self.tema_escuro else CORES["fundo"]
        card_color = CORES["card_escuro"] if self.tema_escuro else CORES["card"]
        text_color = CORES["texto_escuro"] if self.tema_escuro else CORES["texto"]
        muted_color = CORES["texto_sec_escuro"] if self.tema_escuro else CORES["texto_sec"]
        border_color = "#374151" if self.tema_escuro else "#E5E7EB"

        # Responsivo real para desktop/mobile
        screen_w = float(getattr(self._page, "width", None) or getattr(self._page, "window_width", 1024) or 1024)
        screen_h = float(getattr(self._page, "height", None) or getattr(self._page, "window_height", 820) or 820)
        compact = screen_w < 860
        mobile = screen_w < 520
        short_height = screen_h < 760

        content_w = min(560, screen_w - (16 if mobile else (24 if compact else 120)))
        logo_w = min(520 if compact else 760, screen_w - (24 if mobile else (40 if compact else 160)))

        if mobile:
            logo_h = 60 if short_height else 72
        elif short_height:
            logo_h = 86
        elif compact:
            logo_h = 104
        else:
            logo_h = 240

        root_padding = 6 if mobile else (10 if compact else 24)
        field_width = max(240 if mobile else 280, content_w - (18 if mobile else (24 if compact else 40)))

        self.login_button = ft.ElevatedButton(
            "Entrar",
            icon=ft.Icons.LOGIN,
            width=field_width,
            height=42 if mobile else 44,
            on_click=self._acao_login,
            style=ft.ButtonStyle(
                bgcolor=CORES["primaria"],
                color="white",
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )

        self.container_login = ft.Column(
            controls=[
                ft.Text("Bem-vindo de volta!", size=22 if mobile else (30 if compact else 34), weight=ft.FontWeight.BOLD, color=text_color),
                ft.Text("Entre para continuar", size=13 if mobile else 14, color=muted_color),
                ft.Container(height=2 if mobile else 6),
                ft.ElevatedButton(
                    "Continuar com Google" if self.google_login_enabled else "Continuar com Google (em breve)",
                    icon=ft.Icons.ACCOUNT_CIRCLE,
                    width=field_width,
                    height=40 if mobile else 42,
                    on_click=self._login_google,
                    disabled=not self.google_login_enabled,
                    style=ft.ButtonStyle(
                        bgcolor=card_color,
                        color=text_color,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
                ft.Text("ou acesso manual", size=10 if mobile else 11, color=muted_color),
                self.email_login,
                self.senha_login,
                self.login_feedback,
                self.login_button,
                ft.Row(
                    controls=[
                        ft.Text("Sem conta?", color=muted_color),
                        ft.TextButton("Cadastre-se", on_click=self._trocar_para_cadastro),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6 if compact else 8,
            visible=True,
        )

        self.cadastro_button = ft.ElevatedButton(
            "Criar conta",
            icon=ft.Icons.PERSON_ADD,
            width=field_width,
            height=42 if mobile else 44,
            on_click=self._acao_cadastro,
            style=ft.ButtonStyle(
                bgcolor=CORES["primaria"],
                color="white",
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )

        self.container_cadastro = ft.Column(
            controls=[
                ft.Text("Criar conta", size=22 if mobile else (30 if compact else 34), weight=ft.FontWeight.BOLD, color=text_color),
                ft.Text("Comece sua jornada", size=12 if mobile else 13, color=muted_color),
                ft.Container(height=2 if mobile else 6),
                ft.ElevatedButton(
                    "Cadastrar com Google" if self.google_login_enabled else "Cadastrar com Google (em breve)",
                    icon=ft.Icons.ACCOUNT_CIRCLE,
                    width=field_width,
                    height=40 if mobile else 42,
                    on_click=self._login_google,
                    disabled=not self.google_login_enabled,
                    style=ft.ButtonStyle(
                        bgcolor=card_color,
                        color=text_color,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
                ft.Text("ou preencha seus dados", size=10 if mobile else 11, color=muted_color),
                self.nome_cad,
                self.email_cad,
                self.senha_cad,
                self.idade_cad,
                self.cadastro_feedback,
                self.cadastro_button,
                ft.Row(
                    controls=[
                        ft.Text("Ja tem conta", color=muted_color),
                        ft.TextButton("Fazer login", on_click=self._trocar_para_login),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6 if compact else 8,
            visible=False,
        )

        for field in [
            self.email_login,
            self.senha_login,
            self.nome_cad,
            self.email_cad,
            self.senha_cad,
            self.idade_cad,
        ]:
            field.width = field_width

        self.botao_modo_login = ft.TextButton("Entrar", on_click=self._trocar_para_login)
        self.botao_modo_cadastro = ft.TextButton("Criar conta", on_click=self._trocar_para_cadastro)

        hero_logo = ft.Container(
            width=logo_w,
            height=logo_h,
            alignment=ft.Alignment(0, 0),
            content=ft.Image(
                src=os.path.join("assets", "logo_quizvance.png"),
                width=logo_w,
                height=logo_h,
                fit="contain",
            ),
        )

        auth_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.botao_modo_login, self.botao_modo_cadastro],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=14,
                    ),
                    ft.Container(height=2 if mobile else 6),
                    self.container_login,
                    self.container_cadastro,
                    self.loading,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8 if compact else 10,
            ),
            width=content_w,
            padding=14 if mobile else (18 if compact else 24),
            border_radius=16 if mobile else (18 if compact else 22),
            bgcolor=card_color,
            border=ft.Border.all(1, border_color),
            shadow=ft.BoxShadow(blur_radius=32, spread_radius=1, color=ft.Colors.with_opacity(0.16, "#000000")),
        )

        self.botao_modo_login.style = ft.ButtonStyle(
            bgcolor=CORES["primaria"] if self.modo_atual == "login" else "transparent",
            color="white" if self.modo_atual == "login" else muted_color,
            shape=ft.RoundedRectangleBorder(radius=999),
            padding=ft.Padding(14 if compact else 18, 8 if compact else 10, 14 if compact else 18, 8 if compact else 10),
        )
        self.botao_modo_cadastro.style = ft.ButtonStyle(
            bgcolor=CORES["primaria"] if self.modo_atual == "cadastro" else "transparent",
            color="white" if self.modo_atual == "cadastro" else muted_color,
            shape=ft.RoundedRectangleBorder(radius=999),
            padding=ft.Padding(14 if compact else 18, 8 if compact else 10, 14 if compact else 18, 8 if compact else 10),
        )

        layout = ft.Column(
            controls=[hero_logo, auth_card],
            alignment=ft.MainAxisAlignment.START if compact else ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0 if compact else 12,
        )

        root = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=layout,
                        alignment=ft.Alignment(0, 0),
                        padding=ft.padding.only(bottom=2 if compact else 12),
                    )
                ],
                spacing=0,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=root_padding, vertical=2 if compact else root_padding),
            expand=True,
            bgcolor="#EEF2FF" if not self.tema_escuro else bg_color,
        )

        self.controls.clear()
        self.controls.append(ft.SafeArea(expand=True, content=root))
        self._aplicar_estilo_modo()

    def _aplicar_estilo_modo(self):
        ativo = ft.ButtonStyle(bgcolor=CORES["primaria"], color="white")
        inativo = ft.ButtonStyle(bgcolor="transparent", color=CORES["texto_sec"])
        if self.modo_atual == "cadastro":
            self.container_login.visible = False
            self.container_cadastro.visible = True
            self.botao_modo_login.style = inativo
            self.botao_modo_cadastro.style = ativo
        else:
            self.container_login.visible = True
            self.container_cadastro.visible = False
            self.botao_modo_login.style = ativo
            self.botao_modo_cadastro.style = inativo

    def _trocar_para_cadastro(self, e):
        self.modo_atual = "cadastro"
        self._aplicar_estilo_modo()
        self.update()

    def _trocar_para_login(self, e):
        self.modo_atual = "login"
        self._aplicar_estilo_modo()
        self.update()

    def _acao_login(self, e):
        try:
            if self.auth_busy:
                return
            email = (self.email_login.value or "").strip()
            senha = self.senha_login.value or ""
            self.login_feedback.visible = False
            self.login_feedback.value = ""
            self.login_feedback.update()
            self.cadastro_feedback.visible = False
            self.cadastro_feedback.value = ""

            if not email or not senha:
                self._set_login_feedback("Preencha ID e senha para entrar.", "warning")
                self._mostrar_toast("Preencha todos os campos", "warning")
                return

            if not (self.backend and self.backend.enabled()):
                self._set_login_feedback("Backend offline. Login disponivel apenas online.", "erro")
                self._mostrar_toast("Conecte-se a internet para entrar.", "warning")
                return

            self._set_auth_busy(True)
            self._set_login_feedback("Validando credenciais...", "info")
            self._page.run_task(self._acao_login_async, email, senha)
        except Exception as ex:
            log_exception(ex, "login_view._acao_login")
            self._set_auth_busy(False)
            self._set_login_feedback("Erro interno ao tentar login.", "erro")
            self._mostrar_toast("Erro interno no login. Veja os logs do aplicativo", "erro")

    async def _acao_login_async(self, email: str, senha: str):
        try:
            migrated_from_local = False
            try:
                b = await asyncio.to_thread(self.backend.login, email, senha)
            except Exception as ex_backend:
                if self.online_only_auth:
                    self._set_login_feedback(f"Falha no login online: {ex_backend}", "erro")
                    self._mostrar_toast("Nao foi possivel autenticar online. Verifique conexao e tente novamente.", "erro")
                    return
                # Compatibilidade: contas legadas podiam existir apenas no SQLite local.
                try:
                    legacy_user = await asyncio.to_thread(self.db.fazer_login, email, senha)
                except Exception:
                    legacy_user = None

                if not legacy_user:
                    self._set_login_feedback(f"Falha no login online: {ex_backend}", "erro")
                    self._mostrar_toast("ID ou senha incorretos, ou backend indisponivel.", "erro")
                    return

                self._set_login_feedback("Conta local encontrada. Sincronizando no backend...", "info")
                legacy_name = str(legacy_user.get("nome") or email.split("@")[0]).strip()
                try:
                    b = await asyncio.to_thread(self.backend.register, legacy_name, email, senha)
                    migrated_from_local = True
                except Exception:
                    try:
                        b = await asyncio.to_thread(self.backend.login, email, senha)
                        migrated_from_local = True
                    except Exception as ex_sync:
                        # Fallback controlado para contas antigas: entra local e sincroniza depois.
                        legacy_user["backend_user_id"] = int(
                            legacy_user.get("backend_user_id") or legacy_user.get("id") or 0
                        )
                        self._set_login_feedback(
                            f"Conta local carregada (sincronizacao pendente): {ex_sync}",
                            "warning",
                        )
                        self._mostrar_toast(
                            "Conta antiga local detectada. Login liberado em modo de compatibilidade.",
                            "warning",
                        )
                        self.on_login_success(legacy_user)
                        return

            usuario = await asyncio.to_thread(
                self.db.sync_cloud_user,
                int(b.get("user_id") or 0),
                str(b.get("email_id") or email).lower(),
                str(b.get("name") or email.split("@")[0]),
            )
            if not usuario:
                self._set_login_feedback("Falha ao sincronizar perfil local.", "erro")
                self._mostrar_toast("Nao foi possivel preparar seu perfil neste dispositivo.", "erro")
                return

            usuario["backend_user_id"] = int(b.get("user_id") or 0)
            usuario["plan_code"] = b.get("plan_code", usuario.get("plan_code", "free"))
            usuario["premium_active"] = 1 if b.get("premium_active") else 0
            usuario["premium_until"] = b.get("premium_until")
            try:
                remote_cfg = await asyncio.to_thread(self.backend.get_user_settings, int(usuario["backend_user_id"]))
                provider = str(remote_cfg.get("provider") or usuario.get("provider") or "gemini")
                model = str(remote_cfg.get("model") or usuario.get("model") or "gemini-2.5-flash")
                api_key = remote_cfg.get("api_key", usuario.get("api_key"))
                economia_mode = bool(remote_cfg.get("economia_mode"))
                telemetry_opt_in = bool(remote_cfg.get("telemetry_opt_in"))
                # Restore per-provider keys from backend
                remote_key_gemini = remote_cfg.get("api_key_gemini")
                remote_key_openai = remote_cfg.get("api_key_openai")
                remote_key_groq = remote_cfg.get("api_key_groq")
                ok_cfg = await asyncio.to_thread(
                    self.db.sync_ai_preferences,
                    int(usuario.get("id") or 0),
                    provider,
                    model,
                    api_key,
                    economia_mode,
                    telemetry_opt_in,
                )
                if ok_cfg:
                    provider_norm = str(provider or "gemini").strip().lower()
                    if provider_norm not in {"gemini", "openai", "groq"}:
                        provider_norm = "gemini"
                    usuario["provider"] = provider
                    usuario["model"] = model
                    usuario["api_key"] = api_key
                    usuario[f"api_key_{provider_norm}"] = api_key
                    usuario["economia_mode"] = 1 if economia_mode else 0
                    usuario["telemetry_opt_in"] = 1 if telemetry_opt_in else 0
                # Sync per-provider keys into local DB and state
                per_provider_keys = {}
                if remote_key_gemini:
                    per_provider_keys["gemini"] = str(remote_key_gemini).strip()
                if remote_key_openai:
                    per_provider_keys["openai"] = str(remote_key_openai).strip()
                if remote_key_groq:
                    per_provider_keys["groq"] = str(remote_key_groq).strip()
                if per_provider_keys:
                    try:
                        await asyncio.to_thread(
                            self.db.atualizar_api_keys,
                            int(usuario.get("id") or 0),
                            per_provider_keys,
                            provider_norm if ok_cfg else None,
                        )
                        for p, k in per_provider_keys.items():
                            usuario[f"api_key_{p}"] = k
                        # Update active key if missing
                        if not usuario.get("api_key") and per_provider_keys.get(provider_norm if ok_cfg else "gemini"):
                            usuario["api_key"] = per_provider_keys.get(provider_norm if ok_cfg else "gemini")
                    except Exception as ex_keys:
                        log_exception(ex_keys, "login_view._acao_login_async.sync_per_provider_keys")
            except Exception as ex_cfg:
                log_exception(ex_cfg, "login_view._acao_login_async.sync_remote_settings")
            try:
                backend_uid = int(usuario.get("backend_user_id") or 0)
                local_uid = int(usuario.get("id") or 0)
                if backend_uid > 0 and local_uid > 0:
                    summary = await asyncio.to_thread(self.backend.get_quiz_stats_summary, backend_uid)
                    cloud_total = int((summary or {}).get("total_questoes") or 0)
                    cloud_acertos = int((summary or {}).get("total_acertos") or 0)
                    cloud_xp = int((summary or {}).get("total_xp") or 0)
                    cloud_today_q = int((summary or {}).get("today_questoes") or 0)
                    cloud_today_a = int((summary or {}).get("today_acertos") or 0)
                    await asyncio.to_thread(
                        self.db.sync_cloud_quiz_totals,
                        local_uid,
                        cloud_total,
                        cloud_acertos,
                        cloud_xp,
                        cloud_today_q,
                        cloud_today_a,
                    )
                    usuario["total_questoes"] = max(int(usuario.get("total_questoes") or 0), cloud_total)
                    usuario["acertos"] = max(int(usuario.get("acertos") or 0), cloud_acertos)
                    usuario["xp"] = max(int(usuario.get("xp") or 0), cloud_xp)
            except Exception as ex_stats:
                log_exception(ex_stats, "login_view._acao_login_async.sync_remote_quiz_stats")
            if migrated_from_local:
                self._mostrar_toast("Conta local antiga sincronizada com sucesso.", "sucesso")
            self._set_login_feedback("Login realizado. Entrando...", "sucesso")
            self.on_login_success(usuario)
        except Exception as ex:
            log_exception(ex, "login_view._acao_login_async")
            self._set_login_feedback("Erro interno ao tentar login.", "erro")
            self._mostrar_toast("Erro interno no login. Veja os logs do aplicativo", "erro")
        finally:
            self._set_auth_busy(False)

    def _submit_login(self, e):
        self._acao_login(e)

    def _submit_login_id(self, e):
        self._focar_campo(self.senha_login)

    def _acao_cadastro(self, e):
        try:
            if self.auth_busy:
                return
            nome = (self.nome_cad.value or "").strip()
            identificador = (self.email_cad.value or "").strip()
            senha = self.senha_cad.value or ""
            data_nascimento = (self.idade_cad.value or "").strip()
            self.cadastro_feedback.visible = False
            self.cadastro_feedback.value = ""

            if not all([nome, identificador, senha, data_nascimento]):
                self._set_cadastro_feedback("Preencha todos os campos.", "warning")
                self._mostrar_toast("Preencha todos os campos", "warning")
                return

            try:
                import datetime
                nascimento = datetime.datetime.strptime(data_nascimento, "%d/%m/%Y").date()
                hoje = datetime.date.today()
                idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
                if idade < 13:
                    self._set_cadastro_feedback("Idade minima: 13 anos.", "warning")
                    self._mostrar_toast("Idade minima: 13 anos", "warning")
                    return
            except ValueError:
                self._set_cadastro_feedback("Data invalida. Use DD/MM/AAAA.", "warning")
                self._mostrar_toast("Data invalida. Use DD/MM/AAAA", "warning")
                return

            if len(senha) < 6:
                self._set_cadastro_feedback("Senha deve ter no minimo 6 caracteres.", "warning")
                self._mostrar_toast("Senha deve ter no minimo 6 caracteres", "warning")
                return

            if not (self.backend and self.backend.enabled()):
                self._set_cadastro_feedback("Backend offline. Nao foi possivel criar conta online.", "erro")
                self._mostrar_toast("Cadastro de novas contas requer backend online.", "warning")
                return
            self._set_auth_busy(True)
            self._set_cadastro_feedback("Criando conta online...", "info")
            self._page.run_task(self._acao_cadastro_async, nome, identificador, senha)
        except Exception as ex:
            log_exception(ex, "login_view._acao_cadastro")
            self._set_auth_busy(False)
            self._set_cadastro_feedback(f"Erro interno no cadastro: {ex}", "erro")
            self._mostrar_toast("Erro interno no cadastro. Veja os logs do aplicativo", "erro")

    async def _acao_cadastro_async(self, nome: str, identificador: str, senha: str):
        try:
            try:
                b = await asyncio.to_thread(self.backend.register, nome, identificador, senha)
            except Exception as ex_backend:
                self._set_cadastro_feedback(f"Falha no cadastro online: {ex_backend}", "erro")
                self._mostrar_toast(f"Falha no cadastro online: {ex_backend}", "erro")
                return

            usuario = await asyncio.to_thread(
                self.db.sync_cloud_user,
                int(b.get("user_id") or 0),
                str(b.get("email_id") or identificador).lower(),
                str(b.get("name") or nome),
            )
            if not usuario:
                self._set_cadastro_feedback("Conta online criada, mas falhou ao sincronizar no dispositivo.", "erro")
                self._mostrar_toast("Conta criada online. Tente fazer login novamente.", "warning")
                return

            self._set_cadastro_feedback("Conta criada com sucesso.", "sucesso")
            self._mostrar_toast("Conta criada com sucesso. Clique em 'Fazer login' para continuar.", "sucesso")
            self.senha_cad.value = ""
            self.idade_cad.value = ""
            self._trocar_para_login(None)
            self.login_feedback.value = "Conta criada! Use seu ID e senha para entrar."
            self.login_feedback.color = CORES["sucesso"]
            self.login_feedback.visible = True
            self.update()
        except Exception as ex:
            log_exception(ex, "login_view._acao_cadastro_async")
            self._set_cadastro_feedback(f"Erro interno no cadastro: {ex}", "erro")
            self._mostrar_toast("Erro interno no cadastro. Veja os logs do aplicativo", "erro")
        finally:
            self._set_auth_busy(False)

    def _submit_cadastro(self, e):
        self._acao_cadastro(e)

    def _submit_cadastro_nome(self, e):
        self._focar_campo(self.email_cad)

    def _submit_cadastro_email(self, e):
        self._focar_campo(self.senha_cad)

    def _submit_cadastro_senha(self, e):
        self._focar_campo(self.idade_cad)

    def _focar_campo(self, campo):
        try:
            self._page.run_task(campo.focus)
        except Exception:
            pass

    def _on_data_nascimento_change(self, e):
        valor = e.control.value or ""
        apenas_numeros = "".join(ch for ch in valor if ch.isdigit())[:8]
        partes = []
        if len(apenas_numeros) >= 2:
            partes.append(apenas_numeros[:2])
        else:
            partes.append(apenas_numeros)
        if len(apenas_numeros) >= 4:
            partes.append(apenas_numeros[2:4])
        elif len(apenas_numeros) > 2:
            partes.append(apenas_numeros[2:])
        if len(apenas_numeros) > 4:
            partes.append(apenas_numeros[4:8])
        formatado = "/".join([p for p in partes if p])
        if formatado != valor:
            self.idade_cad.value = formatado
            self.idade_cad.update()

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        # Fluxo de autenticacao exige acao explicita por botao.
        if callable(self._prev_keyboard_handler):
            self._prev_keyboard_handler(e)

    def _login_google(self, e):
        if self.auth_busy:
            return
        if self.online_only_auth:
            self._mostrar_toast("Login Google indisponivel no modo online-only atual.", "warning")
            return
        if not self.google_login_enabled:
            self._mostrar_toast("Login com Google temporariamente desativado.", "info")
            return

        if self.autenticando_google:
            return

        # Validacao rapida para evitar erro 401 com client_id placeholder
        client_id = GOOGLE_OAUTH.get("client_id", "")
        if not client_id or "YOUR_CLIENT_ID" in client_id or "apps.googleusercontent.com" not in client_id:
            self._mostrar_toast("Configure um client_id OAuth valido em config.py antes de usar Google Login.", "warning")
            log_exception(Exception("google_oauth_placeholder"), "login_view._login_google")
            return

        self.autenticando_google = True
        self.container_login.visible = False
        self.container_cadastro.visible = False
        self.loading.visible = True
        self.update()

        def auth_thread():
            try:
                result = authenticate_with_google(
                    GOOGLE_OAUTH["client_id"],
                    GOOGLE_OAUTH["redirect_uri"],
                    GOOGLE_OAUTH["scopes"],
                )
                if result:
                    user_info = result["user_info"]
                    usuario = self.db.fazer_login_oauth(
                        email=user_info["email"],
                        nome=user_info.get("name", ""),
                        google_id=user_info.get("id", ""),
                        avatar_url=user_info.get("picture", ""),
                    )
                    if usuario:
                        self._page.run_thread(lambda: self.on_login_success(usuario))
                    else:
                        self._page.run_thread(lambda: self._mostrar_toast("Erro ao autenticar com Google", "erro"))
                else:
                    self._page.run_thread(lambda: self._mostrar_toast("Autenticacao cancelada", "warning"))
            except Exception as ex:
                print(f"[LOGIN] Erro Google OAuth: {ex}")
                log_exception(ex, "login_view._login_google")
                self._page.run_thread(lambda: self._mostrar_toast("Erro na autenticacao Google", "erro"))
            finally:
                self.autenticando_google = False
                self.loading.visible = False
                if self.modo_atual == "login":
                    self.container_login.visible = True
                else:
                    self.container_cadastro.visible = True
                self._page.run_thread(lambda: self.update())

        threading.Thread(target=auth_thread, daemon=True).start()

    def _set_login_feedback(self, msg: str, tipo: str):
        cores = {
            "sucesso": CORES["sucesso"],
            "erro": CORES["erro"],
            "warning": CORES["warning"],
            "info": CORES["info"],
        }
        self.login_feedback.value = msg
        self.login_feedback.color = cores.get(tipo, CORES["info"])
        self.login_feedback.visible = True
        self.update()

    def _set_cadastro_feedback(self, msg: str, tipo: str):
        cores = {
            "sucesso": CORES["sucesso"],
            "erro": CORES["erro"],
            "warning": CORES["warning"],
            "info": CORES["info"],
        }
        self.cadastro_feedback.value = msg
        self.cadastro_feedback.color = cores.get(tipo, CORES["info"])
        self.cadastro_feedback.visible = True
        self.update()

    def _set_auth_busy(self, busy: bool):
        self.auth_busy = bool(busy)
        controls = [
            self.login_button,
            self.cadastro_button,
            self.botao_modo_login,
            self.botao_modo_cadastro,
            self.email_login,
            self.senha_login,
            self.nome_cad,
            self.email_cad,
            self.senha_cad,
            self.idade_cad,
        ]
        for control in controls:
            try:
                control.disabled = self.auth_busy
            except Exception:
                pass
        try:
            self.update()
        except Exception:
            pass

    def _mostrar_toast(self, msg: str, tipo: str):
        cores = {
            "sucesso": CORES["sucesso"],
            "erro": CORES["erro"],
            "warning": CORES["warning"],
            "info": CORES["info"],
        }
        sb = ft.SnackBar(
            content=ft.Text(msg, color="white"),
            bgcolor=cores.get(tipo, CORES["info"]),
            show_close_icon=True,
            duration=2500,
        )
        # Compatibilidade entre versoes de Flet.
        try:
            self._page.show_snack_bar(sb)
            return
        except Exception:
            pass
        try:
            self._page.open(sb)
            return
        except Exception:
            pass
        self._page.snack_bar = sb
        self._page.snack_bar.open = True
        self._page.update()








