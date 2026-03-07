# -*- coding: utf-8 -*-
"""Repositório de usuário — auth, perfil, API keys, preferências de IA."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.database_v2 import Database


class UserRepository:
    """Agrupa operações de usuário: autenticação, perfil e configurações."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    # --- Autenticação ---

    def criar_conta(self, nome: str, identificador: str, senha: str, data_nascimento: str) -> Tuple[bool, str]:
        return self.db.criar_conta(nome, identificador, senha, data_nascimento)

    def fazer_login(self, identificador: str, senha: str) -> Optional[Dict]:
        return self.db.fazer_login(identificador, senha)

    def fazer_login_oauth(self, email: str, nome: str, google_id: str, foto_url: str = "") -> Optional[Dict]:
        return self.db.fazer_login_oauth(email, nome, google_id, foto_url)

    def contar_usuarios(self) -> int:
        return self.db.contar_usuarios()

    def sync_cloud_user(self, backend_user_id: int, email: str, nome: str) -> Optional[Dict]:
        return self.db.sync_cloud_user(backend_user_id, email, nome)

    # --- Perfil e preferências ---

    def atualizar_tema_escuro(self, user_id: int, tema_escuro: bool) -> None:
        self.db.atualizar_tema_escuro(user_id, tema_escuro)

    def marcar_onboarding_visto(self, user_id: int) -> None:
        self.db.marcar_onboarding_visto(user_id)

    def atualizar_identificador(self, user_id: int, novo_identificador: str) -> Tuple[bool, str]:
        return self.db.atualizar_identificador(user_id, novo_identificador)

    def atualizar_meta_diaria(self, user_id: int, meta_questoes: int) -> None:
        self.db.atualizar_meta_diaria(user_id, meta_questoes)

    def atualizar_telemetria_opt_in(self, user_id: int, telemetry_opt_in: bool) -> None:
        self.db.atualizar_telemetria_opt_in(user_id, telemetry_opt_in)

    # --- API Keys e IA ---

    def atualizar_api_key(self, user_id: int, api_key: str) -> None:
        self.db.atualizar_api_key(user_id, api_key)

    def atualizar_api_keys(self, user_id: int, api_keys: Dict[str, Optional[str]], selected_provider: Optional[str] = None) -> None:
        self.db.atualizar_api_keys(user_id, api_keys, selected_provider)

    def atualizar_provider_ia(self, user_id: int, provider: str, model: str) -> None:
        self.db.atualizar_provider_ia(user_id, provider, model)

    def atualizar_economia_ia(self, user_id: int, economia_mode: bool) -> None:
        self.db.atualizar_economia_ia(user_id, economia_mode)

    def sync_ai_preferences(self, user_id: int, provider: Optional[str] = None, model: Optional[str] = None,
                            economia_mode: Optional[bool] = None, api_keys: Optional[Dict[str, Optional[str]]] = None) -> None:
        self.db.sync_ai_preferences(user_id, provider=provider, model=model,
                                    economia_mode=economia_mode, api_keys=api_keys)
