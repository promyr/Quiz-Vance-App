# -*- coding: utf-8 -*-
"""
AuthRepository — Autenticação, registro, OAuth e gerenciamento de subscription.

Extrai os métodos de autenticação da classe Database monolítica.
Recebe uma instância de Database (ou objeto com .conectar()) como injeção de dependência.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from core.database_v2 import Database


class AuthRepository:
    """Gerencia autenticação, registro e subscription do usuário."""

    def __init__(self, db: "Database") -> None:
        self._db = db

    # ------------------------------------------------------------------
    # helpers internos
    # ------------------------------------------------------------------

    def _conectar(self) -> sqlite3.Connection:
        return self._db.conectar()

    def _hash_password(self, senha: str) -> str:
        return self._db._hash_password(senha)

    def _verify_password(self, senha: str, stored: str) -> bool:
        return self._db._verify_password(senha, stored)

    def _decode_user_ai_keys(self, row_dict: Dict) -> Dict:
        return self._db._decode_user_ai_keys(row_dict)

    def _PWD_SCHEME(self) -> str:
        return self._db._PWD_SCHEME

    def _calcular_idade(self, data_nascimento: str) -> Optional[int]:
        try:
            dt_nasc = datetime.datetime.strptime(data_nascimento, "%d/%m/%Y").date()
            hoje = datetime.date.today()
            return hoje.year - dt_nasc.year - (
                (hoje.month, hoje.day) < (dt_nasc.month, dt_nasc.day)
            )
        except Exception:
            return None

    def _ensure_subscription_row(self, cursor: sqlite3.Cursor, user_id: int) -> None:
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_subscription
            (user_id, plan_code, premium_until, trial_used, trial_started_at, updated_at)
            VALUES (?, 'free', NULL, 0, NULL, CURRENT_TIMESTAMP)
            """,
            (user_id,),
        )

    @staticmethod
    def _normalize_subscription_datetime(value: Optional[str]) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        candidates = [raw]
        if raw.endswith("Z"):
            candidates.append(raw[:-1] + "+00:00")
        for candidate in candidates:
            try:
                dt = datetime.datetime.fromisoformat(candidate)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        return None

    def _row_to_user(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Dict:
        row_dict = dict(row)
        row_dict = self._decode_user_ai_keys(row_dict)
        row_dict["oauth_google"] = 0
        row_dict.update(self.get_subscription_status(int(row_dict["id"])))
        return row_dict

    # ------------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------------

    def criar_conta(
        self, nome: str, identificador: str, senha: str, data_nascimento: str
    ) -> Tuple[bool, str]:
        """Cria nova conta usando ID e data de nascimento."""
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            email = (identificador or "").strip().lower()
            nome = (nome or "").strip()
            senha = senha or ""
            data_nascimento = (data_nascimento or "").strip()
            cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
            if cursor.fetchone():
                return False, "ID ja cadastrado"
            senha_hash = self._hash_password(senha)
            cursor.execute(
                """
                INSERT INTO usuarios (nome, email, senha, idade, data_nascimento, ultima_atividade, onboarding_seen)
                VALUES (?, ?, ?, ?, ?, DATE('now','localtime'), 0)
                """,
                (nome, email, senha_hash, self._calcular_idade(data_nascimento), data_nascimento),
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO user_ai_config (user_id, provider, model) VALUES (?, 'gemini', 'gemini-2.5-flash')",
                (user_id,),
            )
            cursor.execute(
                """
                INSERT INTO user_subscription
                (user_id, plan_code, premium_until, trial_used, trial_started_at, updated_at)
                VALUES (?, 'trial', DATETIME('now', '+1 day'), 1, DATETIME('now'), CURRENT_TIMESTAMP)
                """,
                (user_id,),
            )
            conn.commit()
            return True, "Conta criada com sucesso!"
        except Exception as e:
            return False, f"Erro ao criar conta: {str(e)}"
        finally:
            conn.close()

    def contar_usuarios(self) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        total = cursor.fetchone()[0]
        conn.close()
        return int(total or 0)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def fazer_login(self, identificador: str, senha: str) -> Optional[Dict]:
        """Login tradicional com ID e senha."""
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        email = (identificador or "").strip().lower()
        senha = senha or ""

        _SELECT_USER = """
            SELECT u.*, ai.provider, ai.model, ai.api_key,
                   ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                   ai.economia_mode, ai.telemetry_opt_in
            FROM usuarios u
            LEFT JOIN user_ai_config ai ON u.id = ai.user_id
        """

        def _validate(row: Optional[sqlite3.Row]) -> Optional[Dict]:
            if not row:
                return None
            stored = str(row["senha"] or "")
            if not self._verify_password(senha, stored):
                return None
            # Migração suave: hash legado → hash seguro ao logar
            pwd_scheme = self._PWD_SCHEME()
            if (not stored.startswith(f"{pwd_scheme}$")) and (not stored.startswith("$2")):
                try:
                    cursor.execute(
                        "UPDATE usuarios SET senha = ? WHERE id = ?",
                        (self._hash_password(senha), int(row["id"])),
                    )
                    conn.commit()
                except Exception:
                    pass
            return self._row_to_user(conn, row)

        try:
            cursor.execute(_SELECT_USER + " WHERE lower(u.email) = ? LIMIT 1", (email,))
            user = _validate(cursor.fetchone())
            if user:
                return user
            if "@" not in email:
                cursor.execute(_SELECT_USER + " WHERE lower(u.email) LIKE ? LIMIT 1", (f"{email}@%",))
                user = _validate(cursor.fetchone())
                if user:
                    return user
            cursor.execute(_SELECT_USER + " WHERE lower(u.nome) = ? LIMIT 1", (email,))
            return _validate(cursor.fetchone())
        finally:
            conn.close()

    def fazer_login_oauth(
        self, email: str, nome: str, google_id: str, avatar_url: str = None
    ) -> Optional[Dict]:
        """Login ou cadastro via Google OAuth."""
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        email = (email or "").strip().lower()
        nome = (nome or "").strip()
        try:
            cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                user_id = row["id"]
            else:
                senha_random = self._hash_password(str(google_id or os.urandom(8).hex()))
                cursor.execute(
                    """
                    INSERT INTO usuarios (nome, email, senha, idade, avatar, ultima_atividade, onboarding_seen)
                    VALUES (?, ?, ?, ?, ?, DATE('now','localtime'), 0)
                    """,
                    (nome, email, senha_random, 18, avatar_url or "user"),
                )
                user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO user_ai_config (user_id) VALUES (?)", (user_id,)
                )
                cursor.execute(
                    """
                    INSERT INTO user_subscription
                    (user_id, plan_code, premium_until, trial_used, trial_started_at, updated_at)
                    VALUES (?, 'trial', DATETIME('now', '+1 day'), 1, DATETIME('now'), CURRENT_TIMESTAMP)
                    """,
                    (user_id,),
                )
            cursor.execute(
                "INSERT OR REPLACE INTO oauth_users (user_id, provider, provider_id) VALUES (?, 'google', ?)",
                (user_id, google_id),
            )
            conn.commit()
            cursor.execute(
                """
                SELECT u.*, ai.provider, ai.model, ai.api_key,
                       ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                       ai.economia_mode, ai.telemetry_opt_in
                FROM usuarios u
                LEFT JOIN user_ai_config ai ON u.id = ai.user_id
                WHERE u.id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                rd = dict(row)
                rd = self._decode_user_ai_keys(rd)
                rd["oauth_google"] = 1
                rd.update(self.get_subscription_status(int(rd["id"])))
                return rd
            return None
        finally:
            conn.close()

    def sync_cloud_user(
        self, backend_user_id: int, email: str, nome: str
    ) -> Optional[Dict]:
        """Sincroniza usuário autenticado no backend para cache local."""
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        email_clean = (email or "").strip().lower()
        nome_clean = (nome or "").strip() or (
            email_clean.split("@")[0] if "@" in email_clean else "Usuario"
        )
        if not email_clean:
            conn.close()
            return None
        try:
            cursor.execute(
                "SELECT id FROM usuarios WHERE lower(email) = ? LIMIT 1", (email_clean,)
            )
            row = cursor.fetchone()
            if row:
                user_id = int(row["id"])
                cursor.execute(
                    """
                    UPDATE usuarios
                    SET backend_user_id = ?, nome = ?, email = ?, ultima_atividade = DATE('now','localtime')
                    WHERE id = ?
                    """,
                    (int(backend_user_id or 0), nome_clean, email_clean, user_id),
                )
            else:
                pwd_seed = f"cloud-{int(backend_user_id or 0)}-{os.urandom(8).hex()}"
                cursor.execute(
                    """
                    INSERT INTO usuarios
                    (backend_user_id, nome, email, senha, idade, avatar, ultima_atividade, onboarding_seen)
                    VALUES (?, ?, ?, ?, ?, ?, DATE('now','localtime'), 0)
                    """,
                    (int(backend_user_id or 0), nome_clean, email_clean,
                     self._hash_password(pwd_seed), 18, "user"),
                )
                user_id = int(cursor.lastrowid or 0)
            cursor.execute(
                "INSERT OR IGNORE INTO user_ai_config (user_id, provider, model) VALUES (?, 'gemini', 'gemini-2.5-flash')",
                (user_id,),
            )
            self._ensure_subscription_row(cursor, user_id)
            conn.commit()
            cursor.execute(
                """
                SELECT u.*, ai.provider, ai.model, ai.api_key,
                       ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                       ai.economia_mode, ai.telemetry_opt_in
                FROM usuarios u
                LEFT JOIN user_ai_config ai ON u.id = ai.user_id
                WHERE u.id = ? LIMIT 1
                """,
                (user_id,),
            )
            user_row = cursor.fetchone()
            if not user_row:
                return None
            rd = dict(user_row)
            rd = self._decode_user_ai_keys(rd)
            rd["oauth_google"] = 0
            rd["backend_user_id"] = int(backend_user_id or 0)
            rd.update(self.get_subscription_status(user_id))
            return rd
        except Exception:
            return None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def get_subscription_status(self, user_id: int) -> Dict:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        self._ensure_subscription_row(cursor, user_id)
        conn.commit()
        cursor.execute(
            "SELECT plan_code, premium_until, trial_used, trial_started_at FROM user_subscription WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"plan_code": "free", "premium_active": 0, "premium_until": None, "trial_used": 0}
        premium_until = row["premium_until"]
        premium_active = 0
        if premium_until:
            try:
                dt = datetime.datetime.strptime(str(premium_until), "%Y-%m-%d %H:%M:%S")
                premium_active = 1 if dt > datetime.datetime.now() else 0
            except Exception:
                pass
        return {
            "plan_code": row["plan_code"] or "free",
            "premium_active": int(premium_active),
            "premium_until": premium_until,
            "trial_used": int(row["trial_used"] or 0),
        }

    def sync_subscription_status(
        self, user_id: int, plan_code: str, premium_until: Optional[str], trial_used: int
    ) -> bool:
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            self._ensure_subscription_row(cursor, int(user_id))
            cursor.execute(
                """
                UPDATE user_subscription
                SET plan_code = ?, premium_until = ?, trial_used = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    str(plan_code or "free"),
                    self._normalize_subscription_datetime(premium_until),
                    1 if int(trial_used or 0) else 0,
                    int(user_id),
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def ativar_plano_premium(self, user_id: int, plano: str) -> Tuple[bool, str]:
        dias = 15 if plano == "premium_15" else 30 if plano == "premium_30" else 0
        if dias <= 0:
            return False, "Plano invalido."
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            self._ensure_subscription_row(cursor, user_id)
            cursor.execute(
                """
                UPDATE user_subscription
                SET plan_code = ?,
                    premium_until = CASE
                        WHEN premium_until IS NOT NULL AND DATETIME(premium_until) > DATETIME('now')
                            THEN DATETIME(premium_until, '+' || ? || ' days')
                        ELSE DATETIME('now', '+' || ? || ' days')
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (plano, dias, dias, user_id),
            )
            conn.commit()
            return True, "Plano ativado com sucesso."
        except Exception as ex:
            return False, f"Falha ao ativar plano: {ex}"
        finally:
            conn.close()

    def consumir_limite_diario(self, user_id: int, feature_key: str, limite: int) -> Tuple[bool, int]:
        if limite <= 0:
            return True, 0
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO usage_daily (user_id, feature_key, day_key, used_count, updated_at)
                VALUES (?, ?, DATE('now','localtime'), 0, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, feature_key, day_key) DO NOTHING
                """,
                (user_id, feature_key),
            )
            cursor.execute(
                "SELECT used_count FROM usage_daily WHERE user_id = ? AND feature_key = ? AND day_key = DATE('now','localtime')",
                (user_id, feature_key),
            )
            row = cursor.fetchone()
            used = int((row[0] if row else 0) or 0)
            if used >= limite:
                conn.commit()
                return False, used
            cursor.execute(
                "UPDATE usage_daily SET used_count = used_count + 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND feature_key = ? AND day_key = DATE('now','localtime')",
                (user_id, feature_key),
            )
            conn.commit()
            return True, used + 1
        finally:
            conn.close()

    def obter_uso_diario(self, user_id: int, feature_key: str) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT used_count FROM usage_daily WHERE user_id = ? AND feature_key = ? AND day_key = DATE('now','localtime') LIMIT 1",
                (int(user_id), str(feature_key or "")),
            )
            row = cursor.fetchone()
            return int((row[0] if row else 0) or 0)
        finally:
            conn.close()
