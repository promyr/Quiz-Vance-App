# -*- coding: utf-8 -*-
"""Classe base para repositórios SQLite do Quiz Vance."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.database_v2 import Database


class BaseRepository:
    """Mixin base que dá acesso a conexão, security e helpers comuns."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    # --- atalhos de infraestrutura ---

    def conectar(self) -> sqlite3.Connection:
        return self.db.conectar()

    def _encrypt_api_key(self, value: Optional[str]) -> Optional[str]:
        return self.db._encrypt_api_key(value)

    def _decrypt_api_key(self, value: Optional[str]) -> Optional[str]:
        return self.db._decrypt_api_key(value)

    def _hash_password(self, senha: str) -> str:
        return self.db._hash_password(senha)

    def _verify_password(self, senha: str, stored: str) -> bool:
        return self.db._verify_password(senha, stored)

    def _legacy_sha256(self, senha: str) -> str:
        return self.db._legacy_sha256(senha)

    def _is_legacy_sha256_hash(self, value: str) -> bool:
        return self.db._is_legacy_sha256_hash(value)

    def _normalize_ai_provider(self, provider: Optional[str]) -> str:
        return self.db._normalize_ai_provider(provider)

    def _decode_user_ai_keys(self, row_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self.db._decode_user_ai_keys(row_dict)
