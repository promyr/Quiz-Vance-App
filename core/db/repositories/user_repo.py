# -*- coding: utf-8 -*-
"""
UserRepository — Perfil, configurações de IA, API keys e tema do usuário.
"""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from core.database_v2 import Database


class UserRepository:
    """Gerencia perfil, configurações de IA, API keys e preferências do usuário."""

    def __init__(self, db: "Database") -> None:
        self._db = db

    def _conectar(self) -> sqlite3.Connection:
        return self._db.conectar()

    def _normalize_ai_provider(self, provider: Optional[str]) -> str:
        return self._db._normalize_ai_provider(provider)

    def _encrypt_api_key(self, v: Optional[str]) -> Optional[str]:
        return self._db._encrypt_api_key(v)

    def _decrypt_api_key(self, v: Optional[str]) -> Optional[str]:
        return self._db._decrypt_api_key(v)

    # ------------------------------------------------------------------
    # Perfil
    # ------------------------------------------------------------------

    def atualizar_tema_escuro(self, user_id: int, tema_escuro: bool) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios SET tema_escuro = ? WHERE id = ?",
            (1 if tema_escuro else 0, user_id),
        )
        conn.commit()
        conn.close()

    def marcar_onboarding_visto(self, user_id: int) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET onboarding_seen = 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

    def atualizar_identificador(self, user_id: int, novo_identificador: str) -> Tuple[bool, str]:
        """Atualiza o ID (campo email) do usuário com validação de unicidade."""
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            novo_id = (novo_identificador or "").strip().lower()
            if not novo_id:
                return False, "ID nao pode ficar vazio."
            cursor.execute(
                "SELECT id FROM usuarios WHERE lower(email) = ? AND id <> ?", (novo_id, user_id)
            )
            if cursor.fetchone():
                return False, "Este ID ja esta em uso por outra conta."
            cursor.execute("UPDATE usuarios SET email = ? WHERE id = ?", (novo_id, user_id))
            if cursor.rowcount == 0:
                return False, "Usuario nao encontrado."
            conn.commit()
            return True, "ID atualizado com sucesso."
        except Exception as ex:
            return False, f"Erro ao atualizar ID: {str(ex)}"
        finally:
            conn.close()

    def atualizar_meta_diaria(self, user_id: int, meta: int) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios SET meta_questoes_diaria = ? WHERE id = ?",
            (max(1, int(meta or 20)), user_id),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Configurações de IA e API keys
    # ------------------------------------------------------------------

    def atualizar_api_key(self, user_id: int, api_key: str) -> None:
        """Atualiza API key do provider ativo (mantém compatibilidade legado)."""
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key) VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)",
            (int(user_id),),
        )
        cursor.execute(
            "SELECT provider, api_key_gemini, api_key_openai, api_key_groq FROM user_ai_config WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        )
        row = cursor.fetchone()
        provider = self._normalize_ai_provider(row["provider"] if row else "gemini")
        keys: Dict[str, Optional[str]] = {
            "gemini": self._decrypt_api_key(row["api_key_gemini"] if row else None),
            "openai": self._decrypt_api_key(row["api_key_openai"] if row else None),
            "groq": self._decrypt_api_key(row["api_key_groq"] if row else None),
        }
        keys[provider] = (str(api_key).strip() if api_key is not None else None) or None
        cursor.execute(
            "UPDATE user_ai_config SET api_key = ?, api_key_gemini = ?, api_key_openai = ?, api_key_groq = ? WHERE user_id = ?",
            (
                self._encrypt_api_key(keys.get(provider)),
                self._encrypt_api_key(keys.get("gemini")),
                self._encrypt_api_key(keys.get("openai")),
                self._encrypt_api_key(keys.get("groq")),
                int(user_id),
            ),
        )
        conn.commit()
        conn.close()

    def atualizar_api_keys(
        self, user_id: int, api_keys: Dict[str, Optional[str]], selected_provider: Optional[str] = None
    ) -> None:
        """Atualiza chaves de todos os providers e define api_key ativa."""
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key) VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)",
            (int(user_id),),
        )
        cursor.execute("SELECT provider FROM user_ai_config WHERE user_id = ? LIMIT 1", (int(user_id),))
        row = cursor.fetchone()
        provider = self._normalize_ai_provider(
            selected_provider or (row["provider"] if row else "gemini")
        )
        keys_clean: Dict[str, Optional[str]] = {}
        for p in ("gemini", "openai", "groq"):
            raw = (api_keys or {}).get(p)
            keys_clean[p] = (str(raw).strip() if raw is not None else "") or None
        cursor.execute(
            "UPDATE user_ai_config SET api_key = ?, api_key_gemini = ?, api_key_openai = ?, api_key_groq = ? WHERE user_id = ?",
            (
                self._encrypt_api_key(keys_clean.get(provider)),
                self._encrypt_api_key(keys_clean.get("gemini")),
                self._encrypt_api_key(keys_clean.get("openai")),
                self._encrypt_api_key(keys_clean.get("groq")),
                int(user_id),
            ),
        )
        conn.commit()
        conn.close()

    def atualizar_provider_ia(self, user_id: int, provider: str, model: str) -> None:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key) VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)",
            (user_id,),
        )
        provider_clean = self._normalize_ai_provider(provider)
        model_clean = str(model or "").strip() or "gemini-2.5-flash"
        cursor.execute(
            "SELECT api_key_gemini, api_key_openai, api_key_groq FROM user_ai_config WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        )
        row = cursor.fetchone()
        keys = {
            "gemini": self._decrypt_api_key(row["api_key_gemini"] if row else None),
            "openai": self._decrypt_api_key(row["api_key_openai"] if row else None),
            "groq": self._decrypt_api_key(row["api_key_groq"] if row else None),
        }
        cursor.execute(
            "UPDATE user_ai_config SET provider = ?, model = ?, api_key = ? WHERE user_id = ?",
            (provider_clean, model_clean, self._encrypt_api_key(keys.get(provider_clean)), user_id),
        )
        conn.commit()
        conn.close()

    def atualizar_economia_ia(self, user_id: int, economia_mode: bool) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key) VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)",
            (user_id,),
        )
        cursor.execute(
            "UPDATE user_ai_config SET economia_mode = ? WHERE user_id = ?",
            (1 if economia_mode else 0, user_id),
        )
        conn.commit()
        conn.close()

    def salvar_telemetry_opt_in(self, user_id: int, opt_in: bool) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO user_ai_config (user_id, provider, model) VALUES (?, 'gemini', 'gemini-2.5-flash')",
            (user_id,),
        )
        cursor.execute(
            "UPDATE user_ai_config SET telemetry_opt_in = ? WHERE user_id = ?",
            (1 if opt_in else 0, user_id),
        )
        conn.commit()
        conn.close()
