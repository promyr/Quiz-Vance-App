# -*- coding: utf-8 -*-
"""Camada de seguranca para credenciais no banco local."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

try:
    import bcrypt as _bcrypt  # type: ignore
except Exception:
    _bcrypt = None

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except Exception:
    Fernet = None
    InvalidToken = Exception


class DatabaseSecurity:
    PWD_SCHEME = "pbkdf2_sha256"
    PWD_ITERS = 210_000
    API_KEY_PREFIX = "enc1:"

    def __init__(self, db_path: str):
        self.db_path = str(db_path or "")

    def _api_key_cipher(self):
        if Fernet is None:
            return None
        seed = "|".join(
            [
                str(os.getenv("COMPUTERNAME") or ""),
                str(os.getenv("USERNAME") or ""),
                self.db_path,
            ]
        ).encode("utf-8", errors="ignore")
        salt = b"quizvance-local-api-key-salt-v1"
        raw_key = hashlib.pbkdf2_hmac("sha256", seed, salt, 180_000, dklen=32)
        return Fernet(base64.urlsafe_b64encode(raw_key))

    def encrypt_api_key(self, value: Optional[str]) -> Optional[str]:
        plain = str(value or "").strip()
        if not plain:
            return None
        if plain.startswith(self.API_KEY_PREFIX):
            return plain
        cipher = self._api_key_cipher()
        if cipher is None:
            return plain
        try:
            token = cipher.encrypt(plain.encode("utf-8")).decode("utf-8")
            return f"{self.API_KEY_PREFIX}{token}"
        except Exception:
            return plain

    def decrypt_api_key(self, value: Optional[str]) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        if not raw.startswith(self.API_KEY_PREFIX):
            return raw
        token = raw[len(self.API_KEY_PREFIX):].strip()
        if not token:
            return None
        cipher = self._api_key_cipher()
        if cipher is None:
            return None
        try:
            return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return None
        except Exception:
            return None

    @staticmethod
    def legacy_sha256(senha: str) -> str:
        return hashlib.sha256((senha or "").encode()).hexdigest()

    @staticmethod
    def is_legacy_sha256_hash(value: str) -> bool:
        v = str(value or "").strip().lower()
        if len(v) != 64:
            return False
        return all(ch in "0123456789abcdef" for ch in v)

    def hash_password(self, senha: str) -> str:
        pwd = (senha or "").encode("utf-8")
        if _bcrypt is not None:
            try:
                return _bcrypt.hashpw(pwd, _bcrypt.gensalt(rounds=12)).decode("utf-8")
            except Exception:
                pass
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", pwd, salt, self.PWD_ITERS)
        salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
        dig_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"{self.PWD_SCHEME}${self.PWD_ITERS}${salt_b64}${dig_b64}"

    def verify_password(self, senha: str, stored: str) -> bool:
        raw_pwd = senha or ""
        value = str(stored or "").strip()
        if not value:
            return False

        if value.startswith("$2"):
            if _bcrypt is None:
                return False
            try:
                return bool(_bcrypt.checkpw(raw_pwd.encode("utf-8"), value.encode("utf-8")))
            except Exception:
                return False

        if value.startswith(f"{self.PWD_SCHEME}$"):
            try:
                _scheme, iters_s, salt_b64, digest_b64 = value.split("$", 3)
                iters = int(iters_s)
                salt_raw = base64.urlsafe_b64decode(salt_b64 + "=" * (-len(salt_b64) % 4))
                digest_raw = base64.urlsafe_b64decode(digest_b64 + "=" * (-len(digest_b64) % 4))
                probe = hashlib.pbkdf2_hmac(
                    "sha256",
                    raw_pwd.encode("utf-8"),
                    salt_raw,
                    max(50_000, iters),
                )
                return hmac.compare_digest(probe, digest_raw)
            except Exception:
                return False

        if self.is_legacy_sha256_hash(value):
            return hmac.compare_digest(self.legacy_sha256(raw_pwd), value.lower())

        return hmac.compare_digest(raw_pwd, value)
