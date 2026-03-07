# -*- coding: utf-8 -*-
"""
Database V2.0 - Quiz Vance

Sistema de banco de dados SQLite com suporte a:
- AutenticaÃ§Ã£o tradicional e OAuth
- Multi-provider de IA
- Sistema de gamificaÃ§Ã£o completo
"""

import sqlite3
import datetime
import json
import hashlib
import os
import threading
from typing import Optional, Dict, List, Tuple, Any
from core.app_paths import ensure_runtime_dirs, get_db_path
from core.database_security import DatabaseSecurity
from core.repositories.user_repository import UserRepository
from core.repositories.gamification_repository import GamificationRepository
from core.repositories.plan_repository import PlanRepository
from core.repositories.quiz_repository import QuizRepository
from core.repositories.session_repository import SessionRepository
# Novos repositórios especializados por domínio
from core.db.repositories.auth_repo import AuthRepository
from core.db.repositories.user_repo import UserRepository as UserSettingsRepo
from core.db.repositories.stats_repo import StatsRepository
from core.db.repositories.quiz_repo import QuizRepository as QuizDataRepo
from core.db.repositories.review_repo import ReviewRepository


class _PooledConnection:
    """Proxy de conexão que ignora close() para permitir reutilização thread-local."""

    __slots__ = ("_real",)

    def __init__(self, real_conn: sqlite3.Connection) -> None:
        object.__setattr__(self, "_real", real_conn)

    # --- proxy transparente de leitura ---
    def __getattr__(self, name: str):
        return getattr(self._real, name)

    # --- proxy transparente de escrita (necessário para row_factory etc.) ---
    def __setattr__(self, name: str, value) -> None:
        if name == "_real":
            object.__setattr__(self, name, value)
        else:
            setattr(self._real, name, value)

    def close(self) -> None:  # noqa: D401
        """Fecha a conexão real. Em cenários de pool, uma nova será aberta sob demanda."""
        try:
            self._real.close()
        except Exception:
            pass

    def real_close(self) -> None:
        """Fecha a conexão real (usado no shutdown)."""
        try:
            self._real.close()
        except Exception:
            pass


class Database:
    """Gerenciador de banco de dados SQLite"""
    _PWD_SCHEME = DatabaseSecurity.PWD_SCHEME
    _PWD_ITERS = DatabaseSecurity.PWD_ITERS
    _API_KEY_PREFIX = DatabaseSecurity.API_KEY_PREFIX
    _AI_KEY_PROVIDERS = ("gemini", "openai", "groq")
    
    def __init__(self, db_path: Optional[str] = None):
        ensure_runtime_dirs()
        self.db_path = db_path or str(get_db_path())
        self._security = DatabaseSecurity(self.db_path)
        self._local = threading.local()
        # Repositórios legados (API organizada por domínio)
        self.users = UserRepository(self)
        self.gamification = GamificationRepository(self)
        self.plans = PlanRepository(self)
        self.quizzes = QuizRepository(self)
        self.sessions = SessionRepository(self)
        # Novos repositórios especializados (core/db/repositories/)
        self.auth = AuthRepository(self)
        self.user_settings = UserSettingsRepo(self)
        self.stats = StatsRepository(self)
        self.quiz_data = QuizDataRepo(self)
        self.review = ReviewRepository(self)
    def conectar(self) -> sqlite3.Connection:
        """Retorna conexão thread-local reutilizável (pooled)."""
        conn: Optional[_PooledConnection] = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                # verifica se a conexão real ainda está viva
                conn._real.execute("SELECT 1")
                return conn  # type: ignore[return-value]
            except Exception:
                try:
                    conn.real_close()
                except Exception:
                    pass
                self._local.conn = None
        real = sqlite3.connect(self.db_path, check_same_thread=False)
        pooled = _PooledConnection(real)
        self._local.conn = pooled
        return pooled  # type: ignore[return-value]

    def shutdown(self) -> None:
        """Fecha a conexão thread-local real (usar na saída do app)."""
        conn: Optional[_PooledConnection] = getattr(self._local, "conn", None)
        if conn is not None:
            conn.real_close()
            self._local.conn = None

    def _api_key_cipher(self):
        return self._security._api_key_cipher()

    def _encrypt_api_key(self, value: Optional[str]) -> Optional[str]:
        return self._security.encrypt_api_key(value)

    def _decrypt_api_key(self, value: Optional[str]) -> Optional[str]:
        return self._security.decrypt_api_key(value)

    def _normalize_ai_provider(self, provider: Optional[str]) -> str:
        value = str(provider or "").strip().lower()
        return value if value in self._AI_KEY_PROVIDERS else "gemini"

    def _decode_user_ai_keys(self, row_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Decodifica chaves por provider e resolve api_key ativa com fallback legado."""
        provider = self._normalize_ai_provider(row_dict.get("provider"))
        keys: Dict[str, Optional[str]] = {}
        for p in self._AI_KEY_PROVIDERS:
            keys[p] = self._decrypt_api_key(row_dict.get(f"api_key_{p}"))
        legacy_key = self._decrypt_api_key(row_dict.get("api_key"))
        if (not any(bool(v) for v in keys.values())) and legacy_key:
            keys[provider] = legacy_key
        for p in self._AI_KEY_PROVIDERS:
            row_dict[f"api_key_{p}"] = keys.get(p)
        row_dict["api_key"] = keys.get(provider) or legacy_key
        return row_dict

    def _legacy_sha256(self, senha: str) -> str:
        return self._security.legacy_sha256(senha)

    def _is_legacy_sha256_hash(self, value: str) -> bool:
        return self._security.is_legacy_sha256_hash(value)

    def _hash_password(self, senha: str) -> str:
        """Hash seguro de senha (bcrypt quando disponível; fallback PBKDF2)."""
        return self._security.hash_password(senha)

    def _verify_password(self, senha: str, stored: str) -> bool:
        return self._security.verify_password(senha, stored)
    
    def iniciar_banco(self):
        """Cria todas as tabelas necessÃ¡rias"""
        conn = self.conectar()
        cursor = conn.cursor()
        
        # Tabela de usuÃ¡rios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backend_user_id INTEGER,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                idade INTEGER,
                data_nascimento TEXT,
                avatar TEXT DEFAULT 'user',
                tema_escuro INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0,
                nivel TEXT DEFAULT 'Bronze',
                acertos INTEGER DEFAULT 0,
                total_questoes INTEGER DEFAULT 0,
                streak_dias INTEGER DEFAULT 0,
                ultima_atividade DATE,
                onboarding_seen INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._migrar_schema(cursor)
        
        # Tabela de configuraÃ§Ã£o de IA por usuÃ¡rio
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_ai_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT DEFAULT 'gemini',
                model TEXT DEFAULT 'gemini-2.5-flash',
                economia_mode INTEGER DEFAULT 0,
                telemetry_opt_in INTEGER DEFAULT 0,
                api_key TEXT,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id)
            )
        """)
        cursor.execute("PRAGMA table_info(user_ai_config)")
        ai_cols = {row[1] for row in cursor.fetchall()}
        if "economia_mode" not in ai_cols:
            cursor.execute("ALTER TABLE user_ai_config ADD COLUMN economia_mode INTEGER DEFAULT 0")
        if "telemetry_opt_in" not in ai_cols:
            cursor.execute("ALTER TABLE user_ai_config ADD COLUMN telemetry_opt_in INTEGER DEFAULT 0")
        if "api_key_gemini" not in ai_cols:
            cursor.execute("ALTER TABLE user_ai_config ADD COLUMN api_key_gemini TEXT")
        if "api_key_openai" not in ai_cols:
            cursor.execute("ALTER TABLE user_ai_config ADD COLUMN api_key_openai TEXT")
        if "api_key_groq" not in ai_cols:
            cursor.execute("ALTER TABLE user_ai_config ADD COLUMN api_key_groq TEXT")
        
        # Tabela de OAuth
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                access_token TEXT,
                refresh_token TEXT,
                token_expires DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (provider, provider_id)
            )
        """)
        
        # Tabela de histÃ³rico de XP
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_xp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                xp_ganho INTEGER NOT NULL,
                motivo TEXT,
                data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)
        
        # Tabela de questÃµes erradas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questoes_erros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dados_json TEXT NOT NULL,
                corrigido INTEGER DEFAULT 0,
                data_erro DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)
        
        # Tabela de conquistas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conquistas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT,
                icone TEXT,
                xp_bonus INTEGER DEFAULT 0,
                criterio_tipo TEXT,
                criterio_valor INTEGER
            )
        """)
        
        # Tabela de conquistas do usuÃ¡rio
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuario_conquistas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                conquista_id INTEGER NOT NULL,
                data_conquista DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                FOREIGN KEY (conquista_id) REFERENCES conquistas (id),
                UNIQUE (user_id, conquista_id)
            )
        """)
        
        # Tabela de tempo de estudo
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estudo_tempo_diario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                materia TEXT NOT NULL,
                dia DATE NOT NULL,
                segundos_estudo INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id, materia, dia)
            )
        """)
        
        # Tabela de biblioteca de PDFs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS biblioteca_pdfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                nome_arquivo TEXT NOT NULL,
                caminho_arquivo TEXT NOT NULL,
                categoria TEXT DEFAULT 'Geral',
                total_paginas INTEGER DEFAULT 0,
                data_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
                ultimo_uso DATETIME,
                vezes_usado INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)
        
        # Tabela de cache de questÃµes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banco_questoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tema TEXT NOT NULL,
                dificuldade TEXT NOT NULL,
                dados_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questoes_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                qhash TEXT NOT NULL,
                dados_json TEXT NOT NULL,
                tema TEXT DEFAULT 'Geral',
                dificuldade TEXT DEFAULT 'intermediario',
                favorita INTEGER DEFAULT 0,
                marcado_erro INTEGER DEFAULT 0,
                tentativas INTEGER DEFAULT 0,
                acertos INTEGER DEFAULT 0,
                erros INTEGER DEFAULT 0,
                revisao_nivel INTEGER DEFAULT 0,
                proxima_revisao DATETIME,
                ultima_pratica DATETIME DEFAULT CURRENT_TIMESTAMP,
                marked_for_review INTEGER DEFAULT 0,
                next_review_at DATETIME,
                review_level INTEGER DEFAULT 0,
                last_attempt_at DATETIME,
                last_result TEXT,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id, qhash)
            )
        """)

        # Revisao inteligente (Prompt 5): flashcards com agenda de revisao
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                card_hash TEXT NOT NULL,
                frente TEXT NOT NULL,
                verso TEXT NOT NULL,
                tema TEXT DEFAULT 'Geral',
                dificuldade TEXT DEFAULT 'intermediario',
                revisao_nivel INTEGER DEFAULT 0,
                proxima_revisao DATETIME,
                ultima_revisao_em DATETIME,
                total_revisoes INTEGER DEFAULT 0,
                total_acertos INTEGER DEFAULT 0,
                total_erros INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id, card_hash)
            )
        """)

        # Revisao inteligente (Prompt 5): historico de sessoes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_type TEXT DEFAULT 'daily',
                status TEXT DEFAULT 'in_progress',
                total_items INTEGER DEFAULT 0,
                acertos INTEGER DEFAULT 0,
                erros INTEGER DEFAULT 0,
                puladas INTEGER DEFAULT 0,
                total_time_ms INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                finished_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_session_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_ref TEXT,
                resultado TEXT,
                is_correct INTEGER,
                response_time_ms INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES review_sessions (id)
            )
        """)

        # Modo prova/simulado (Prompt 6)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mock_exam_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filtro_snapshot_json TEXT,
                progress_json TEXT,
                total_questoes INTEGER DEFAULT 0,
                tempo_total_s INTEGER DEFAULT 0,
                modo TEXT DEFAULT 'timed',
                status TEXT DEFAULT 'in_progress',
                acertos INTEGER DEFAULT 0,
                erros INTEGER DEFAULT 0,
                puladas INTEGER DEFAULT 0,
                score_pct REAL DEFAULT 0,
                tempo_gasto_s INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                finished_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mock_exam_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                ordem INTEGER DEFAULT 0,
                qhash TEXT,
                meta_json TEXT,
                resposta_index INTEGER,
                correta_index INTEGER,
                resultado TEXT,
                tempo_ms INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES mock_exam_sessions (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_filtros_salvos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                filtro_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_plan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                objetivo TEXT,
                data_prova TEXT,
                tempo_diario_min INTEGER DEFAULT 90,
                status TEXT DEFAULT 'ativo',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_plan_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                dia TEXT NOT NULL,
                tema TEXT NOT NULL,
                atividade TEXT NOT NULL,
                duracao_min INTEGER DEFAULT 60,
                prioridade INTEGER DEFAULT 1,
                concluido INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES study_plan_runs (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                source_nome TEXT,
                dados_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_summary_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_hash TEXT NOT NULL,
                topic TEXT DEFAULT '',
                summary_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id, source_hash)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questoes_notas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                qhash TEXT NOT NULL,
                nota TEXT DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id, qhash)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estudo_progresso_diario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dia DATE NOT NULL,
                questoes_respondidas INTEGER DEFAULT 0,
                acertos INTEGER DEFAULT 0,
                flashcards_revisados INTEGER DEFAULT 0,
                discursivas_corrigidas INTEGER DEFAULT 0,
                tempo_segundos INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id, dia)
            )
        """)

        # Monetizacao / assinatura
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_subscription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                plan_code TEXT DEFAULT 'free',
                premium_until DATETIME,
                trial_used INTEGER DEFAULT 0,
                trial_started_at DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature_key TEXT NOT NULL,
                day_key DATE NOT NULL,
                used_count INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id),
                UNIQUE (user_id, feature_key, day_key)
            )
        """)

        # Fila local para sincronizacao assíncrona de estatisticas no backend.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats_sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id)
            )
        """)
        
        conn.commit()
        conn.close()
        
        # Popular conquistas padrÃ£o
        self._popular_conquistas()
        self._garantir_admin_padrao()

    def _migrar_schema(self, cursor):
        """Aplica migracoes em bancos antigos sem perder dados."""
        cursor.execute("PRAGMA table_info(usuarios)")
        colunas = {row[1] for row in cursor.fetchall()}
        if "backend_user_id" not in colunas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN backend_user_id INTEGER")
        if "data_nascimento" not in colunas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
        if "meta_questoes_diaria" not in colunas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN meta_questoes_diaria INTEGER DEFAULT 20")
        if "onboarding_seen" not in colunas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN onboarding_seen INTEGER DEFAULT 1")
        cursor.execute("PRAGMA table_info(questoes_usuario)")
        q_cols = {row[1] for row in cursor.fetchall()}
        if q_cols:
            if "revisao_nivel" not in q_cols:
                cursor.execute("ALTER TABLE questoes_usuario ADD COLUMN revisao_nivel INTEGER DEFAULT 0")
            if "proxima_revisao" not in q_cols:
                cursor.execute("ALTER TABLE questoes_usuario ADD COLUMN proxima_revisao DATETIME")
            if "marked_for_review" not in q_cols:
                cursor.execute("ALTER TABLE questoes_usuario ADD COLUMN marked_for_review INTEGER DEFAULT 0")
            if "next_review_at" not in q_cols:
                cursor.execute("ALTER TABLE questoes_usuario ADD COLUMN next_review_at DATETIME")
            if "review_level" not in q_cols:
                cursor.execute("ALTER TABLE questoes_usuario ADD COLUMN review_level INTEGER DEFAULT 0")
            if "last_attempt_at" not in q_cols:
                cursor.execute("ALTER TABLE questoes_usuario ADD COLUMN last_attempt_at DATETIME")
            if "last_result" not in q_cols:
                cursor.execute("ALTER TABLE questoes_usuario ADD COLUMN last_result TEXT")
        cursor.execute("PRAGMA table_info(mock_exam_sessions)")
        ms_cols = {row[1] for row in cursor.fetchall()}
        if ms_cols and "progress_json" not in ms_cols:
            cursor.execute("ALTER TABLE mock_exam_sessions ADD COLUMN progress_json TEXT")
        cursor.execute("PRAGMA table_info(mock_exam_items)")
        mi_cols = {row[1] for row in cursor.fetchall()}
        if mi_cols and "meta_json" not in mi_cols:
            cursor.execute("ALTER TABLE mock_exam_items ADD COLUMN meta_json TEXT")
    
    def _popular_conquistas(self):
        """Popula conquistas padrÃ£o se nÃ£o existirem"""
        from config import CONQUISTAS
        
        conn = self.conectar()
        cursor = conn.cursor()
        
        for conquista in CONQUISTAS:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO conquistas 
                    (codigo, titulo, descricao, icone, xp_bonus, criterio_tipo, criterio_valor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    conquista['codigo'],
                    conquista['titulo'],
                    conquista['descricao'],
                    conquista['icone'],
                    conquista['xp_bonus'],
                    conquista['criterio_tipo'],
                    conquista['criterio_valor']
                ))
            except Exception:
                pass
        
        conn.commit()
        conn.close()

    def _garantir_admin_padrao(self):
        """Nao cria credenciais padrao por seguranca."""
        return

    def atualizar_tema_escuro(self, user_id: int, tema_escuro: bool):
        """Atualiza preferencia de tema do usuario."""
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios SET tema_escuro = ? WHERE id = ?",
            (1 if tema_escuro else 0, user_id),
        )
        conn.commit()
        conn.close()

    def marcar_onboarding_visto(self, user_id: int):
        """Marca a tela de boas-vindas como concluida para o usuario."""
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios SET onboarding_seen = 1 WHERE id = ?",
            (user_id,),
        )
        conn.commit()
        conn.close()

    def criar_conta(self, nome: str, identificador: str, senha: str, data_nascimento: str) -> Tuple[bool, str]:
        """Cria nova conta usando ID e data de nascimento."""
        conn = self.conectar()
        cursor = conn.cursor()
        
        try:
            email = (identificador or "").strip().lower()
            nome = (nome or "").strip()
            senha = senha or ""
            data_nascimento = (data_nascimento or "").strip()

            # Verificar se email jÃ¡ existe
            cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
            if cursor.fetchone():
                conn.close()
                return False, "ID ja cadastrado"
            
            # Hash seguro com sal e iteracoes.
            senha_hash = self._hash_password(senha)
            
            # Inserir usuÃ¡rio
            cursor.execute("""
                INSERT INTO usuarios (nome, email, senha, idade, data_nascimento, ultima_atividade, onboarding_seen)
                VALUES (?, ?, ?, ?, ?, DATE('now','localtime'), 0)
            """, (nome, email, senha_hash, self._calcular_idade(data_nascimento), data_nascimento))
            
            user_id = cursor.lastrowid
            
            # Criar configuraÃ§Ã£o de IA padrÃ£o
            cursor.execute("""
                INSERT INTO user_ai_config (user_id, provider, model)
                VALUES (?, 'gemini', 'gemini-2.5-flash')
            """, (user_id,))

            # Trial de premium por 1 dia para novos usuarios
            cursor.execute(
                """
                INSERT INTO user_subscription
                (user_id, plan_code, premium_until, trial_used, trial_started_at, updated_at)
                VALUES (?, 'trial', DATETIME('now', '+1 day'), 1, DATETIME('now'), CURRENT_TIMESTAMP)
                """,
                (user_id,),
            )
            
            conn.commit()
            conn.close()
            return True, "Conta criada com sucesso!"
            
        except Exception as e:
            conn.close()
            return False, f"Erro ao criar conta: {str(e)}"
    
    def fazer_login(self, identificador: str, senha: str) -> Optional[Dict]:
        """Login tradicional com ID e senha."""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        email = (identificador or "").strip().lower()
        senha = senha or ""

        def _row_to_user(row: sqlite3.Row) -> Dict:
            row_dict = dict(row)
            row_dict = self._decode_user_ai_keys(row_dict)
            row_dict["oauth_google"] = 0
            row_dict.update(self.get_subscription_status(int(row_dict["id"])))
            return row_dict

        def _validate_row(row: Optional[sqlite3.Row]) -> Optional[Dict]:
            if not row:
                return None
            stored = str(row["senha"] or "")
            if not self._verify_password(senha, stored):
                return None

            # Migracao suave: hash legado (SHA/plain) -> hash seguro ao logar.
            if (not stored.startswith(f"{self._PWD_SCHEME}$")) and (not stored.startswith("$2")):
                try:
                    cursor.execute(
                        "UPDATE usuarios SET senha = ? WHERE id = ?",
                        (self._hash_password(senha), int(row["id"])),
                    )
                    conn.commit()
                except Exception:
                    pass
            return _row_to_user(row)

        # 1) Prioridade absoluta: ID definido pelo usuario (campo email no schema atual)
        cursor.execute(
            """
            SELECT u.*,
                   ai.provider, ai.model, ai.api_key, ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                   ai.economia_mode, ai.telemetry_opt_in
            FROM usuarios u
            LEFT JOIN user_ai_config ai ON u.id = ai.user_id
            WHERE lower(u.email) = ?
            LIMIT 1
            """,
            (email,),
        )
        user_by_email = _validate_row(cursor.fetchone())
        if user_by_email:
            conn.close()
            return user_by_email

        # 2) Fallback: ID curto (parte antes do @ do email)
        if "@" not in email:
            cursor.execute(
                """
                SELECT u.*,
                       ai.provider, ai.model, ai.api_key, ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                       ai.economia_mode, ai.telemetry_opt_in
                FROM usuarios u
                LEFT JOIN user_ai_config ai ON u.id = ai.user_id
                WHERE lower(u.email) LIKE ?
                LIMIT 1
                """,
                (f"{email}@%",),
            )
            user_by_short = _validate_row(cursor.fetchone())
            if user_by_short:
                conn.close()
                return user_by_short

        # 3) Fallback opcional: login por nome
        cursor.execute(
            """
            SELECT u.*,
                   ai.provider, ai.model, ai.api_key, ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                   ai.economia_mode, ai.telemetry_opt_in
            FROM usuarios u
            LEFT JOIN user_ai_config ai ON u.id = ai.user_id
            WHERE lower(u.nome) = ?
            LIMIT 1
            """,
            (email,),
        )
        user_by_name = _validate_row(cursor.fetchone())
        conn.close()
        return user_by_name

    def _calcular_idade(self, data_nascimento: str) -> Optional[int]:
        """Calcula idade aproximada para manter compatibilidade do campo legado."""
        try:
            dt_nasc = datetime.datetime.strptime(data_nascimento, "%d/%m/%Y").date()
            hoje = datetime.date.today()
            return hoje.year - dt_nasc.year - ((hoje.month, hoje.day) < (dt_nasc.month, dt_nasc.day))
        except Exception:
            return None

    def contar_usuarios(self) -> int:
        """Retorna quantidade total de usuÃ¡rios cadastrados."""
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        total = cursor.fetchone()[0]
        conn.close()
        return int(total or 0)
    
    def fazer_login_oauth(
        self,
        email: str,
        nome: str,
        google_id: str,
        avatar_url: str = None
    ) -> Optional[Dict]:
        """Login ou cadastro via Google OAuth"""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        email = (email or "").strip().lower()
        nome = (nome or "").strip()
        
        # Verificar se usuÃ¡rio existe
        cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
        row = cursor.fetchone()
        
        if row:
            user_id = row['id']
        else:
            # Criar novo usuÃ¡rio
            senha_random = self._hash_password(str(google_id or os.urandom(8).hex()))
            cursor.execute("""
                INSERT INTO usuarios (nome, email, senha, idade, avatar, ultima_atividade, onboarding_seen)
                VALUES (?, ?, ?, ?, ?, DATE('now','localtime'), 0)
            """, (nome, email, senha_random, 18, avatar_url or 'user'))
            
            user_id = cursor.lastrowid
            
            # Criar configuraÃ§Ã£o de IA
            cursor.execute("""
                INSERT INTO user_ai_config (user_id)
                VALUES (?)
            """, (user_id,))
            cursor.execute(
                """
                INSERT INTO user_subscription
                (user_id, plan_code, premium_until, trial_used, trial_started_at, updated_at)
                VALUES (?, 'trial', DATETIME('now', '+1 day'), 1, DATETIME('now'), CURRENT_TIMESTAMP)
                """,
                (user_id,),
            )
        
        # Salvar/atualizar OAuth info
        cursor.execute("""
            INSERT OR REPLACE INTO oauth_users (user_id, provider, provider_id)
            VALUES (?, 'google', ?)
        """, (user_id, google_id))
        
        conn.commit()
        
        # Retornar dados do usuÃ¡rio
        cursor.execute("""
            SELECT u.*, 
                   ai.provider, ai.model, ai.api_key, ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                   ai.economia_mode, ai.telemetry_opt_in
            FROM usuarios u
            LEFT JOIN user_ai_config ai ON u.id = ai.user_id
            WHERE u.id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            row_dict = dict(row)
            row_dict = self._decode_user_ai_keys(row_dict)
            row_dict["oauth_google"] = 1
            row_dict.update(self.get_subscription_status(int(row_dict["id"])))
            return row_dict
        return None

    def sync_cloud_user(self, backend_user_id: int, email: str, nome: str) -> Optional[Dict]:
        """
        Sincroniza um usuario autenticado no backend para uso local (cache/perfil),
        sem usar autenticacao local por senha.
        """
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        email_clean = (email or "").strip().lower()
        nome_clean = (nome or "").strip() or (email_clean.split("@")[0] if "@" in email_clean else "Usuario")
        if not email_clean:
            conn.close()
            return None

        try:
            cursor.execute("SELECT id FROM usuarios WHERE lower(email) = ? LIMIT 1", (email_clean,))
            row = cursor.fetchone()
            if row:
                user_id = int(row["id"])
                cursor.execute(
                    """
                    UPDATE usuarios
                    SET backend_user_id = ?,
                        nome = ?,
                        email = ?,
                        ultima_atividade = DATE('now','localtime')
                    WHERE id = ?
                    """,
                    (int(backend_user_id or 0), nome_clean, email_clean, user_id),
                )
            else:
                pwd_seed = f"cloud-{int(backend_user_id or 0)}-{os.urandom(8).hex()}"
                senha_random = self._hash_password(pwd_seed)
                cursor.execute(
                    """
                    INSERT INTO usuarios (backend_user_id, nome, email, senha, idade, avatar, ultima_atividade, onboarding_seen)
                    VALUES (?, ?, ?, ?, ?, ?, DATE('now','localtime'), 0)
                    """,
                    (int(backend_user_id or 0), nome_clean, email_clean, senha_random, 18, "user"),
                )
                user_id = int(cursor.lastrowid or 0)

            cursor.execute(
                """
                INSERT OR IGNORE INTO user_ai_config (user_id, provider, model)
                VALUES (?, 'gemini', 'gemini-2.5-flash')
                """,
                (user_id,),
            )
            self._ensure_subscription_row(cursor, user_id)
            conn.commit()

            cursor.execute(
                """
                SELECT u.*,
                       ai.provider, ai.model, ai.api_key, ai.api_key_gemini, ai.api_key_openai, ai.api_key_groq,
                       ai.economia_mode, ai.telemetry_opt_in
                FROM usuarios u
                LEFT JOIN user_ai_config ai ON u.id = ai.user_id
                WHERE u.id = ?
                LIMIT 1
                """,
                (user_id,),
            )
            user_row = cursor.fetchone()
            if not user_row:
                return None
            row_dict = dict(user_row)
            row_dict = self._decode_user_ai_keys(row_dict)
            row_dict["oauth_google"] = 0
            row_dict["backend_user_id"] = int(backend_user_id or 0)
            row_dict.update(self.get_subscription_status(user_id))
            return row_dict
        except Exception:
            return None
        finally:
            conn.close()

    def _ensure_subscription_row(self, cursor, user_id: int):
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
                dt = datetime.datetime.strptime(raw, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        return None

    def sync_subscription_status(
        self,
        user_id: int,
        plan_code: str,
        premium_until: Optional[str],
        trial_used: int,
    ) -> bool:
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            self._ensure_subscription_row(cursor, int(user_id))
            normalized_until = self._normalize_subscription_datetime(premium_until)
            cursor.execute(
                """
                UPDATE user_subscription
                SET plan_code = ?,
                    premium_until = ?,
                    trial_used = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    str(plan_code or "free"),
                    normalized_until,
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

    def get_subscription_status(self, user_id: int) -> Dict:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        self._ensure_subscription_row(cursor, user_id)
        conn.commit()
        cursor.execute(
            """
            SELECT plan_code, premium_until, trial_used, trial_started_at
            FROM user_subscription
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {
                "plan_code": "free",
                "premium_active": 0,
                "premium_until": None,
                "trial_used": 0,
            }
        premium_until = row["premium_until"]
        premium_active = 0
        if premium_until:
            try:
                dt = datetime.datetime.strptime(str(premium_until), "%Y-%m-%d %H:%M:%S")
                premium_active = 1 if dt > datetime.datetime.now() else 0
            except Exception:
                premium_active = 0
        return {
            "plan_code": row["plan_code"] or "free",
            "premium_active": int(premium_active),
            "premium_until": premium_until,
            "trial_used": int(row["trial_used"] or 0),
        }

    def ativar_plano_premium(self, user_id: int, plano: str) -> Tuple[bool, str]:
        dias = 15 if plano == "premium_15" else 30 if plano == "premium_30" else 0
        if dias <= 0:
            return False, "Plano invalido."
        conn = self.conectar()
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
        conn = self.conectar()
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
                """
                SELECT used_count
                FROM usage_daily
                WHERE user_id = ? AND feature_key = ? AND day_key = DATE('now','localtime')
                """,
                (user_id, feature_key),
            )
            row = cursor.fetchone()
            used = int((row[0] if row else 0) or 0)
            if used >= limite:
                conn.commit()
                return False, used
            cursor.execute(
                """
                UPDATE usage_daily
                SET used_count = used_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND feature_key = ? AND day_key = DATE('now','localtime')
                """,
                (user_id, feature_key),
            )
            conn.commit()
            return True, used + 1
        finally:
            conn.close()

    def obter_uso_diario(self, user_id: int, feature_key: str) -> int:
        """Retorna o consumo do recurso no dia atual sem incrementar uso."""
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT used_count
                FROM usage_daily
                WHERE user_id = ? AND feature_key = ? AND day_key = DATE('now','localtime')
                LIMIT 1
                """,
                (int(user_id), str(feature_key or "")),
            )
            row = cursor.fetchone()
            return int((row[0] if row else 0) or 0)
        finally:
            conn.close()
    
    def atualizar_api_key(self, user_id: int, api_key: str):
        """Atualiza API key do provider ativo (mantem compatibilidade legado)."""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key)
            VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)
            """,
            (int(user_id),),
        )
        cursor.execute(
            """
            SELECT provider, api_key_gemini, api_key_openai, api_key_groq
            FROM user_ai_config
            WHERE user_id = ?
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cursor.fetchone()
        provider = self._normalize_ai_provider((row["provider"] if row else "gemini"))
        keys: Dict[str, Optional[str]] = {}
        if row:
            keys["gemini"] = self._decrypt_api_key(row["api_key_gemini"])
            keys["openai"] = self._decrypt_api_key(row["api_key_openai"])
            keys["groq"] = self._decrypt_api_key(row["api_key_groq"])
        else:
            keys = {"gemini": None, "openai": None, "groq": None}
        keys[provider] = (str(api_key).strip() if api_key is not None else None) or None
        encrypted_active = self._encrypt_api_key(keys.get(provider))
        cursor.execute(
            """
            UPDATE user_ai_config
            SET api_key = ?,
                api_key_gemini = ?,
                api_key_openai = ?,
                api_key_groq = ?
            WHERE user_id = ?
            """,
            (
                encrypted_active,
                self._encrypt_api_key(keys.get("gemini")),
                self._encrypt_api_key(keys.get("openai")),
                self._encrypt_api_key(keys.get("groq")),
                int(user_id),
            ),
        )
        conn.commit()
        conn.close()

    def atualizar_api_keys(self, user_id: int, api_keys: Dict[str, Optional[str]], selected_provider: Optional[str] = None):
        """Atualiza chaves de todos os providers e define api_key ativa para o provider selecionado."""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key)
            VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)
            """,
            (int(user_id),),
        )
        cursor.execute(
            "SELECT provider FROM user_ai_config WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        )
        row = cursor.fetchone()
        provider = self._normalize_ai_provider(selected_provider or (row["provider"] if row else "gemini"))
        keys_clean: Dict[str, Optional[str]] = {}
        for p in self._AI_KEY_PROVIDERS:
            raw = (api_keys or {}).get(p)
            txt = str(raw).strip() if raw is not None else ""
            keys_clean[p] = txt or None
        encrypted_active = self._encrypt_api_key(keys_clean.get(provider))
        cursor.execute(
            """
            UPDATE user_ai_config
            SET api_key = ?,
                api_key_gemini = ?,
                api_key_openai = ?,
                api_key_groq = ?
            WHERE user_id = ?
            """,
            (
                encrypted_active,
                self._encrypt_api_key(keys_clean.get("gemini")),
                self._encrypt_api_key(keys_clean.get("openai")),
                self._encrypt_api_key(keys_clean.get("groq")),
                int(user_id),
            ),
        )
        conn.commit()
        conn.close()
    
    def atualizar_provider_ia(self, user_id: int, provider: str, model: str):
        """Atualiza configuraÃ§Ã£o de IA do usuÃ¡rio"""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key)
            VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)
            """,
            (user_id,),
        )
        provider_clean = self._normalize_ai_provider(provider)
        model_clean = str(model or "").strip() or "gemini-2.5-flash"
        cursor.execute(
            """
            SELECT api_key_gemini, api_key_openai, api_key_groq
            FROM user_ai_config
            WHERE user_id = ?
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cursor.fetchone()
        keys: Dict[str, Optional[str]] = {"gemini": None, "openai": None, "groq": None}
        if row:
            keys["gemini"] = self._decrypt_api_key(row["api_key_gemini"])
            keys["openai"] = self._decrypt_api_key(row["api_key_openai"])
            keys["groq"] = self._decrypt_api_key(row["api_key_groq"])
        active_key = keys.get(provider_clean)
        cursor.execute("""
            UPDATE user_ai_config
            SET provider = ?, model = ?, api_key = ?
            WHERE user_id = ?
        """, (provider_clean, model_clean, self._encrypt_api_key(active_key), user_id))
        
        conn.commit()
        conn.close()
    
    def registrar_ganho_xp(self, user_id: int, xp: int, motivo: str = ""):
        """Registra ganho de XP"""
        conn = self.conectar()
        cursor = conn.cursor()
        
        # Inserir no histÃ³rico
        cursor.execute("""
            INSERT INTO historico_xp (user_id, xp_ganho, motivo)
            VALUES (?, ?, ?)
        """, (user_id, xp, motivo))
        
        # Atualizar XP total
        cursor.execute("""
            UPDATE usuarios
            SET xp = xp + ?,
                ultima_atividade = DATE('now','localtime')
            WHERE id = ?
        """, (xp, user_id))
        
        conn.commit()
        conn.close()

    def registrar_resultado_quiz(self, user_id: int, acertos: int, total: int, xp: int):
        """Atualiza estatisticas de quiz e XP."""
        conn = self.conectar()
        cursor = conn.cursor()
        novo_streak = self._calcular_streak(cursor, user_id)
        cursor.execute("""
            UPDATE usuarios
            SET xp = xp + ?,
                acertos = acertos + ?,
                total_questoes = total_questoes + ?,
                streak_dias = ?,
                ultima_atividade = DATE('now','localtime')
            WHERE id = ?
        """, (xp, acertos, total, novo_streak, user_id))
        cursor.execute(
            """
            INSERT INTO historico_xp (user_id, xp_ganho, motivo)
            VALUES (?, ?, ?)
            """,
            (user_id, xp, f"Quiz {acertos}/{total}"),
        )
        self._registrar_progresso_diario_cursor(
            cursor,
            user_id,
            questoes=max(0, int(total or 0)),
            acertos=max(0, int(acertos or 0)),
        )
        conn.commit()
        conn.close()

    def registrar_resposta_quiz_tempo_real(self, user_id: int, correta: bool, xp_por_acerto: int = 10) -> Dict:
        """Persistencia incremental por resposta confirmada em modo treino."""
        conn = self.conectar()
        cursor = conn.cursor()
        acertos_delta = 1 if bool(correta) else 0
        xp_delta = int(max(0, xp_por_acerto)) if acertos_delta else 0
        novo_streak = self._calcular_streak(cursor, int(user_id))
        cursor.execute(
            """
            UPDATE usuarios
            SET xp = xp + ?,
                acertos = acertos + ?,
                total_questoes = total_questoes + 1,
                streak_dias = ?,
                ultima_atividade = DATE('now','localtime')
            WHERE id = ?
            """,
            (xp_delta, acertos_delta, novo_streak, int(user_id)),
        )
        if xp_delta > 0:
            cursor.execute(
                """
                INSERT INTO historico_xp (user_id, xp_ganho, motivo)
                VALUES (?, ?, ?)
                """,
                (int(user_id), xp_delta, "Quiz tempo real"),
            )
        self._registrar_progresso_diario_cursor(
            cursor,
            int(user_id),
            questoes=1,
            acertos=acertos_delta,
        )
        conn.commit()
        conn.close()
        return {
            "xp_ganho": xp_delta,
            "acertos_delta": acertos_delta,
            "questoes_delta": 1,
            "streak_dias": int(novo_streak),
        }

    def sync_cloud_quiz_totals(
        self,
        user_id: int,
        total_questoes: int,
        total_acertos: int,
        total_xp: Optional[int] = None,
        today_questoes: Optional[int] = None,
        today_acertos: Optional[int] = None,
    ) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT xp, acertos, total_questoes FROM usuarios WHERE id = ?", (int(user_id),))
            row = cursor.fetchone()
            if not row:
                return
            xp_local = int(row[0] or 0)
            acertos_local = int(row[1] or 0)
            total_local = int(row[2] or 0)
            xp_cloud = int(total_xp or 0) if total_xp is not None else xp_local
            acertos_cloud = int(total_acertos or 0)
            total_cloud = int(total_questoes or 0)
            cursor.execute(
                """
                UPDATE usuarios
                SET xp = ?,
                    acertos = ?,
                    total_questoes = ?
                WHERE id = ?
                """,
                (
                    max(0, max(xp_local, xp_cloud)),
                    max(0, max(acertos_local, acertos_cloud)),
                    max(0, max(total_local, total_cloud)),
                    int(user_id),
                ),
            )
            should_sync_daily = today_questoes is not None or today_acertos is not None
            if should_sync_daily:
                cloud_q = max(0, int(today_questoes or 0))
                cloud_a = max(0, int(today_acertos or 0))
                if cloud_a > cloud_q:
                    cloud_a = cloud_q
                cursor.execute(
                    """
                    SELECT questoes_respondidas, acertos
                    FROM estudo_progresso_diario
                    WHERE user_id = ? AND dia = DATE('now','localtime')
                    """,
                    (int(user_id),),
                )
                daily_row = cursor.fetchone()
                if daily_row:
                    local_q = int(daily_row[0] or 0)
                    local_a = int(daily_row[1] or 0)
                    merged_q = max(local_q, cloud_q)
                    merged_a = min(merged_q, max(local_a, cloud_a))
                    cursor.execute(
                        """
                        UPDATE estudo_progresso_diario
                        SET questoes_respondidas = ?,
                            acertos = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND dia = DATE('now','localtime')
                        """,
                        (merged_q, merged_a, int(user_id)),
                    )
                elif cloud_q > 0 or cloud_a > 0:
                    cursor.execute(
                        """
                        INSERT INTO estudo_progresso_diario
                            (user_id, dia, questoes_respondidas, acertos, flashcards_revisados, discursivas_corrigidas, tempo_segundos, updated_at)
                        VALUES (?, DATE('now','localtime'), ?, ?, 0, 0, 0, CURRENT_TIMESTAMP)
                        """,
                        (int(user_id), cloud_q, min(cloud_q, cloud_a)),
                    )
            conn.commit()
        finally:
            conn.close()

    def enqueue_quiz_stats_event(self, user_id: int, event_id: str, payload: Dict[str, Any]) -> bool:
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO stats_sync_queue (user_id, event_id, payload_json)
                VALUES (?, ?, ?)
                """,
                (int(user_id), str(event_id or "").strip(), json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()
            return bool(cursor.rowcount)
        finally:
            conn.close()

    def list_pending_quiz_stats_events(self, user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        conn = self.conectar()
        cursor = conn.cursor()
        lim = max(1, min(int(limit or 200), 1000))
        try:
            cursor.execute(
                """
                SELECT id, event_id, payload_json
                FROM stats_sync_queue
                WHERE user_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (int(user_id), lim),
            )
            rows = cursor.fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                rid = int(row[0])
                event_id = str(row[1] or "")
                try:
                    payload = json.loads(str(row[2] or "{}"))
                except Exception:
                    payload = {}
                out.append({"id": rid, "event_id": event_id, "event": payload})
            return out
        finally:
            conn.close()

    def delete_pending_quiz_stats_events(self, ids: List[int]) -> int:
        ids_norm = [int(i) for i in (ids or []) if int(i or 0) > 0]
        if not ids_norm:
            return 0
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            placeholders = ",".join("?" for _ in ids_norm)
            cursor.execute(f"DELETE FROM stats_sync_queue WHERE id IN ({placeholders})", tuple(ids_norm))
            deleted = int(cursor.rowcount or 0)
            conn.commit()
            return deleted
        finally:
            conn.close()

    def atualizar_identificador(self, user_id: int, novo_identificador: str) -> Tuple[bool, str]:
        """Atualiza o ID (campo email) do usuario com validacao de unicidade."""
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            novo_id = (novo_identificador or "").strip().lower()
            if not novo_id:
                return False, "ID nao pode ficar vazio."

            cursor.execute(
                "SELECT id FROM usuarios WHERE lower(email) = ? AND id <> ?",
                (novo_id, user_id),
            )
            if cursor.fetchone():
                return False, "Este ID ja esta em uso por outra conta."

            cursor.execute(
                "UPDATE usuarios SET email = ? WHERE id = ?",
                (novo_id, user_id),
            )
            if cursor.rowcount == 0:
                return False, "Usuario nao encontrado."

            conn.commit()
            return True, "ID atualizado com sucesso."
        except Exception as ex:
            return False, f"Erro ao atualizar ID: {str(ex)}"
        finally:
            conn.close()

    def atualizar_economia_ia(self, user_id: int, economia_mode: bool):
        """Atualiza modo economia da IA do usuario."""
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key)
            VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)
            """,
            (user_id,),
        )
        cursor.execute(
            """
            UPDATE user_ai_config
            SET economia_mode = ?
            WHERE user_id = ?
            """,
            (1 if economia_mode else 0, user_id),
        )
        conn.commit()
        conn.close()

    def _calcular_streak(self, cursor, user_id: int) -> int:
        cursor.execute(
            "SELECT streak_dias, ultima_atividade FROM usuarios WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return 1
        streak_atual = int(row[0] or 0)
        ultima = row[1]
        hoje = datetime.date.today()
        if not ultima:
            return max(1, streak_atual)
        try:
            ultima_data = datetime.datetime.strptime(str(ultima), "%Y-%m-%d").date()
        except ValueError:
            return max(1, streak_atual)
        if ultima_data == hoje:
            return max(1, streak_atual)
        if ultima_data == (hoje - datetime.timedelta(days=1)):
            return max(1, streak_atual + 1)
        return 1

    def _registrar_progresso_diario_cursor(
        self,
        cursor,
        user_id: int,
        questoes: int = 0,
        acertos: int = 0,
        flashcards: int = 0,
        discursivas: int = 0,
        tempo_segundos: int = 0,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO estudo_progresso_diario
                (user_id, dia, questoes_respondidas, acertos, flashcards_revisados, discursivas_corrigidas, tempo_segundos, updated_at)
            VALUES (?, DATE('now','localtime'), ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, dia) DO UPDATE SET
                questoes_respondidas = estudo_progresso_diario.questoes_respondidas + excluded.questoes_respondidas,
                acertos = estudo_progresso_diario.acertos + excluded.acertos,
                flashcards_revisados = estudo_progresso_diario.flashcards_revisados + excluded.flashcards_revisados,
                discursivas_corrigidas = estudo_progresso_diario.discursivas_corrigidas + excluded.discursivas_corrigidas,
                tempo_segundos = estudo_progresso_diario.tempo_segundos + excluded.tempo_segundos,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                max(0, int(questoes or 0)),
                max(0, int(acertos or 0)),
                max(0, int(flashcards or 0)),
                max(0, int(discursivas or 0)),
                max(0, int(tempo_segundos or 0)),
            ),
        )

    def registrar_progresso_diario(
        self,
        user_id: int,
        questoes: int = 0,
        acertos: int = 0,
        flashcards: int = 0,
        discursivas: int = 0,
        tempo_segundos: int = 0,
    ) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        self._registrar_progresso_diario_cursor(
            cursor,
            user_id,
            questoes=questoes,
            acertos=acertos,
            flashcards=flashcards,
            discursivas=discursivas,
            tempo_segundos=tempo_segundos,
        )
        novo_streak = self._calcular_streak(cursor, user_id)
        cursor.execute(
            """
            UPDATE usuarios
            SET streak_dias = ?, ultima_atividade = DATE('now','localtime')
            WHERE id = ?
            """,
            (novo_streak, user_id),
        )
        conn.commit()
        conn.close()

    def obter_progresso_diario(self, user_id: int) -> Dict:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT meta_questoes_diaria, streak_dias
            FROM usuarios
            WHERE id = ?
            """,
            (user_id,),
        )
        user_row = cursor.fetchone()
        meta = int((user_row["meta_questoes_diaria"] if user_row else 20) or 20)
        streak = int((user_row["streak_dias"] if user_row else 0) or 0)
        cursor.execute(
            """
            SELECT questoes_respondidas, acertos, flashcards_revisados, discursivas_corrigidas, tempo_segundos
            FROM estudo_progresso_diario
            WHERE user_id = ? AND dia = DATE('now','localtime')
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        feitos = int((row["questoes_respondidas"] if row else 0) or 0)
        acertos = int((row["acertos"] if row else 0) or 0)
        return {
            "meta_questoes": max(5, meta),
            "questoes_respondidas": feitos,
            "acertos": acertos,
            "flashcards_revisados": int((row["flashcards_revisados"] if row else 0) or 0),
            "discursivas_corrigidas": int((row["discursivas_corrigidas"] if row else 0) or 0),
            "tempo_segundos": int((row["tempo_segundos"] if row else 0) or 0),
            "progresso_meta": min(1.0, feitos / max(1, meta)),
            "streak_dias": streak,
        }

    def obter_resumo_estatisticas(self, user_id: int) -> Dict:
        """Retorna resumo consolidado para Home/Estatisticas."""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT xp, nivel, acertos, total_questoes, streak_dias, meta_questoes_diaria
                FROM usuarios
                WHERE id = ?
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        progresso = self.obter_progresso_diario(int(user_id))
        revisoes = self.revisoes_pendentes(int(user_id))

        xp = int((row["xp"] if row else 0) or 0)
        nivel = str((row["nivel"] if row else "Bronze") or "Bronze")
        acertos_total = int((row["acertos"] if row else 0) or 0)
        total_questoes = int((row["total_questoes"] if row else 0) or 0)
        streak = int((row["streak_dias"] if row else 0) or 0)
        meta = int((row["meta_questoes_diaria"] if row else 20) or 20)
        taxa_total = (acertos_total / total_questoes * 100.0) if total_questoes > 0 else 0.0

        return {
            "xp": xp,
            "nivel": nivel,
            "acertos_total": acertos_total,
            "total_questoes": total_questoes,
            "taxa_total": taxa_total,
            "streak_dias": streak,
            "meta_questoes": max(5, meta),
            "progresso_diario": progresso,
            "revisoes_pendentes": int(revisoes or 0),
        }
    
    def obter_dados_grafico(self, user_id: int, dias: int = 7) -> Tuple[List[Dict], int]:
        """ObtÃ©m dados para grÃ¡fico de XP"""
        conn = self.conectar()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DATE(data_hora) as dia, SUM(xp_ganho) as xp
            FROM historico_xp
            WHERE user_id = ? AND data_hora >= DATE('now','localtime', '-' || ? || ' days')
            GROUP BY DATE(data_hora)
            ORDER BY dia ASC
        """, (user_id, dias))
        
        resultados = cursor.fetchall()
        conn.close()
        
        # Preencher todos os dias
        dados = []
        total_xp = 0
        hoje = datetime.date.today()
        
        data_dict = {r[0]: r[1] for r in resultados}
        
        for i in range(dias - 1, -1, -1):
            dia = (hoje - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            xp = data_dict.get(dia, 0)
            total_xp += xp
            
            # Label do dia
            if dias <= 7:
                label = ["Seg", "Ter", "Qua", "Qui", "Sex", "SÃ¡b", "Dom"][
                    datetime.datetime.strptime(dia, "%Y-%m-%d").weekday()
                ]
            else:
                label = f"{dia.split('-')[2]}/{dia.split('-')[1]}"
            
            dados.append({"dia": label, "xp": xp})
        
        return dados, total_xp
    
    # Adicionar mais mÃ©todos conforme necessÃ¡rio...
    
    def obter_ranking(self, periodo: str = "Geral") -> List[Dict]:
        """ObtÃ©m ranking de usuÃ¡rios"""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if periodo == "Hoje":
            cursor.execute(
                """
                SELECT
                    u.nome,
                    u.avatar,
                    u.nivel,
                    u.xp,
                    u.acertos,
                    u.total_questoes,
                    COALESCE((
                        SELECT SUM(epd.tempo_segundos)
                        FROM estudo_progresso_diario epd
                        WHERE epd.user_id = u.id
                          AND epd.dia = DATE('now','localtime')
                    ), 0) AS segundos_estudo
                FROM usuarios u
                WHERE u.ultima_atividade = DATE('now','localtime')
                ORDER BY u.xp DESC
                LIMIT 50
                """
            )
        else:
            cursor.execute(
                """
                SELECT
                    u.nome,
                    u.avatar,
                    u.nivel,
                    u.xp,
                    u.acertos,
                    u.total_questoes,
                    COALESCE((
                        SELECT SUM(epd.tempo_segundos)
                        FROM estudo_progresso_diario epd
                        WHERE epd.user_id = u.id
                    ), 0) AS segundos_estudo
                FROM usuarios u
                ORDER BY u.xp DESC
                LIMIT 50
                """
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        ranking = []
        for row in rows:
            user_dict = dict(row)
            # Calcular mÃ©tricas
            total = int(user_dict.get("total_questoes") or 0)
            acertos = int(user_dict.get("acertos") or 0)
            segundos_estudo = int(user_dict.pop("segundos_estudo", 0) or 0)
            user_dict["taxa_acerto"] = (acertos / total * 100) if total > 0 else 0
            user_dict["horas_estudo"] = round(segundos_estudo / 3600.0, 2)
            user_dict["pontuacao"] = int(user_dict.get("xp") or 0)
            ranking.append(user_dict)
        
        return ranking

    def execute_query(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict]:
        """Executa SELECT generico e retorna lista de dicts."""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _flashcard_hash(self, card: Dict) -> str:
        base = {
            "frente": str(card.get("frente") or "").strip(),
            "verso": str(card.get("verso") or "").strip(),
            "tema": str(card.get("tema") or "Geral").strip(),
        }
        payload = json.dumps(base, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def salvar_flashcards_gerados(self, user_id: int, tema: str, cards: List[Dict], dificuldade: str = "intermediario") -> int:
        if not cards:
            return 0
        conn = self.conectar()
        cursor = conn.cursor()
        added = 0
        for card in cards:
            frente = str(card.get("frente") or "").strip()
            verso = str(card.get("verso") or "").strip()
            if not frente or not verso:
                continue
            card_hash = self._flashcard_hash({"frente": frente, "verso": verso, "tema": tema})
            cursor.execute(
                """
                INSERT INTO flashcards
                (user_id, card_hash, frente, verso, tema, dificuldade, revisao_nivel, proxima_revisao, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, DATETIME('now', '+1 day'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, card_hash) DO UPDATE SET
                    frente = excluded.frente,
                    verso = excluded.verso,
                    tema = excluded.tema,
                    dificuldade = excluded.dificuldade,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    card_hash,
                    frente,
                    verso,
                    str(tema or "Geral"),
                    str(dificuldade or "intermediario"),
                ),
            )
            added += 1
        conn.commit()
        conn.close()

    def sync_ai_preferences(
        self,
        user_id: int,
        provider: str,
        model: str,
        api_key: Optional[str],
        economia_mode: bool,
        telemetry_opt_in: bool,
    ) -> bool:
        """Sincroniza preferencias de IA vindas do backend para cache local."""
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            provider_clean = self._normalize_ai_provider(provider)
            model_clean = str(model or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key, telemetry_opt_in)
                VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL, 0)
                """,
                (int(user_id),),
            )
            cursor.execute(
                """
                SELECT api_key_gemini, api_key_openai, api_key_groq
                FROM user_ai_config
                WHERE user_id = ?
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            keys: Dict[str, Optional[str]] = {"gemini": None, "openai": None, "groq": None}
            if row:
                keys["gemini"] = self._decrypt_api_key(row["api_key_gemini"])
                keys["openai"] = self._decrypt_api_key(row["api_key_openai"])
                keys["groq"] = self._decrypt_api_key(row["api_key_groq"])
            if api_key is not None:
                txt = str(api_key).strip()
                keys[provider_clean] = txt or None
            active_key = keys.get(provider_clean)
            cursor.execute(
                """
                UPDATE user_ai_config
                SET provider = ?,
                    model = ?,
                    api_key = ?,
                    api_key_gemini = ?,
                    api_key_openai = ?,
                    api_key_groq = ?,
                    economia_mode = ?,
                    telemetry_opt_in = ?
                WHERE user_id = ?
                """,
                (
                    provider_clean,
                    model_clean,
                    self._encrypt_api_key(active_key),
                    self._encrypt_api_key(keys.get("gemini")),
                    self._encrypt_api_key(keys.get("openai")),
                    self._encrypt_api_key(keys.get("groq")),
                    1 if bool(economia_mode) else 0,
                    1 if bool(telemetry_opt_in) else 0,
                    int(user_id),
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def atualizar_telemetria_opt_in(self, user_id: int, telemetry_opt_in: bool):
        """Atualiza consentimento de telemetria anonima (opt-in)."""
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_ai_config (user_id, provider, model, economia_mode, api_key)
            VALUES (?, 'gemini', 'gemini-2.5-flash', 0, NULL)
            """,
            (user_id,),
        )
        cursor.execute(
            """
            UPDATE user_ai_config
            SET telemetry_opt_in = ?
            WHERE user_id = ?
            """,
            (1 if telemetry_opt_in else 0, user_id),
        )
        conn.commit()
        conn.close()

    def registrar_revisao_flashcard(self, user_id: int, card: Dict, lembrei: bool) -> None:
        card_hash = self._flashcard_hash(card)
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, revisao_nivel, total_revisoes, total_acertos, total_erros
            FROM flashcards
            WHERE user_id = ? AND card_hash = ?
            LIMIT 1
            """,
            (user_id, card_hash),
        )
        row = cursor.fetchone()
        if not row:
            self.salvar_flashcards_gerados(user_id, str(card.get("tema") or "Geral"), [card], str(card.get("dificuldade") or "intermediario"))
            cursor.execute(
                """
                SELECT id, revisao_nivel, total_revisoes, total_acertos, total_erros
                FROM flashcards
                WHERE user_id = ? AND card_hash = ?
                LIMIT 1
                """,
                (user_id, card_hash),
            )
            row = cursor.fetchone()
        if not row:
            conn.close()
            return

        nivel_atual = int(row["revisao_nivel"] or 0)
        total_rev = int(row["total_revisoes"] or 0) + 1
        total_acertos = int(row["total_acertos"] or 0) + (1 if lembrei else 0)
        total_erros = int(row["total_erros"] or 0) + (0 if lembrei else 1)

        intervalos = [1, 2, 4, 7, 14, 30, 60, 120, 180]
        if lembrei:
            novo_nivel = min(len(intervalos) - 1, nivel_atual + 1)
            dias = intervalos[novo_nivel]
        else:
            novo_nivel = max(0, nivel_atual - 1)
            dias = 1

        cursor.execute(
            """
            UPDATE flashcards
            SET revisao_nivel = ?,
                proxima_revisao = DATETIME('now', '+' || ? || ' days'),
                ultima_revisao_em = CURRENT_TIMESTAMP,
                total_revisoes = ?,
                total_acertos = ?,
                total_erros = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (novo_nivel, dias, total_rev, total_acertos, total_erros, int(row["id"])),
        )
        conn.commit()
        conn.close()

    def iniciar_review_session(self, user_id: int, session_type: str, total_items: int) -> int:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO review_sessions (user_id, session_type, status, total_items, created_at)
            VALUES (?, ?, 'in_progress', ?, CURRENT_TIMESTAMP)
            """,
            (user_id, str(session_type or "daily"), int(max(0, total_items))),
        )
        sid = int(cursor.lastrowid or 0)
        conn.commit()
        conn.close()
        return sid

    def registrar_review_session_item(
        self,
        session_id: int,
        item_type: str,
        item_ref: str,
        resultado: str,
        is_correct: Optional[bool],
        response_time_ms: int = 0,
    ) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO review_session_items
            (session_id, item_type, item_ref, resultado, is_correct, response_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                int(session_id),
                str(item_type or "question"),
                str(item_ref or ""),
                str(resultado or ""),
                None if is_correct is None else (1 if is_correct else 0),
                int(max(0, response_time_ms or 0)),
            ),
        )
        conn.commit()
        conn.close()

    def finalizar_review_session(self, session_id: int, acertos: int, erros: int, puladas: int, total_time_ms: int) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE review_sessions
            SET status = 'finished',
                acertos = ?,
                erros = ?,
                puladas = ?,
                total_time_ms = ?,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                int(max(0, acertos)),
                int(max(0, erros)),
                int(max(0, puladas)),
                int(max(0, total_time_ms)),
                int(session_id),
            ),
        )
        conn.commit()
        conn.close()

    def criar_mock_exam_session(
        self,
        user_id: int,
        filtro_snapshot: Dict,
        total_questoes: int,
        tempo_total_s: int,
        modo: str = "timed",
    ) -> int:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO mock_exam_sessions
            (user_id, filtro_snapshot_json, progress_json, total_questoes, tempo_total_s, modo, status, created_at)
            VALUES (?, ?, NULL, ?, ?, ?, 'in_progress', CURRENT_TIMESTAMP)
            """,
            (
                int(user_id),
                json.dumps(filtro_snapshot or {}, ensure_ascii=False),
                int(max(0, total_questoes)),
                int(max(0, tempo_total_s)),
                str(modo or "timed"),
            ),
        )
        sid = int(cursor.lastrowid or 0)
        conn.commit()
        conn.close()
        return sid

    def registrar_mock_exam_item(
        self,
        session_id: int,
        ordem: int,
        question: Dict,
        meta: Optional[Dict],
        resposta_index: Optional[int],
        correta_index: Optional[int],
        tempo_ms: int = 0,
    ) -> None:
        resultado = "skip"
        if resposta_index is not None and correta_index is not None:
            resultado = "correct" if int(resposta_index) == int(correta_index) else "wrong"
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO mock_exam_items
            (session_id, ordem, qhash, meta_json, resposta_index, correta_index, resultado, tempo_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                int(session_id),
                int(max(0, ordem)),
                self._question_hash(question),
                json.dumps(meta or {}, ensure_ascii=False),
                None if resposta_index is None else int(resposta_index),
                None if correta_index is None else int(correta_index),
                resultado,
                int(max(0, tempo_ms or 0)),
            ),
        )
        conn.commit()
        conn.close()

    def salvar_mock_exam_progresso(self, session_id: int, current_idx: int, respostas: Dict[int, Optional[int]]) -> None:
        payload = {
            "current_idx": int(max(0, current_idx or 0)),
            "respostas": {str(k): (None if v is None else int(v)) for k, v in (respostas or {}).items()},
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") + "Z",
        }
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE mock_exam_sessions
            SET progress_json = ?
            WHERE id = ?
            """,
            (json.dumps(payload, ensure_ascii=False), int(session_id)),
        )
        conn.commit()
        conn.close()

    def finalizar_mock_exam_session(
        self,
        session_id: int,
        acertos: int,
        erros: int,
        puladas: int,
        score_pct: float,
        tempo_gasto_s: int,
    ) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE mock_exam_sessions
            SET status = 'finished',
                acertos = ?,
                erros = ?,
                puladas = ?,
                score_pct = ?,
                tempo_gasto_s = ?,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                int(max(0, acertos)),
                int(max(0, erros)),
                int(max(0, puladas)),
                float(max(0.0, min(100.0, score_pct))),
                int(max(0, tempo_gasto_s)),
                int(session_id),
            ),
        )
        conn.commit()
        conn.close()

    def contar_simulados_hoje(self, user_id: int) -> int:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM mock_exam_sessions
            WHERE user_id = ? AND DATE(created_at, 'localtime') = DATE('now','localtime')
            """,
            (int(user_id),),
        )
        total = cursor.fetchone()[0]
        conn.close()
        return int(total or 0)

    def listar_historico_simulados(self, user_id: int, limite: int = 20) -> List[Dict]:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, modo, status, total_questoes, acertos, erros, puladas, score_pct,
                   tempo_total_s, tempo_gasto_s, created_at, finished_at
            FROM mock_exam_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(user_id), int(max(1, limite))),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def contadores_revisao(self, user_id: int) -> Dict[str, int]:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM flashcards
            WHERE user_id = ?
              AND proxima_revisao IS NOT NULL
              AND DATETIME(proxima_revisao) <= DATETIME('now')
            """,
            (int(user_id),),
        )
        flashcards_pendentes = int((cursor.fetchone() or [0])[0] or 0)

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM questoes_usuario
            WHERE user_id = ?
              AND proxima_revisao IS NOT NULL
              AND DATETIME(proxima_revisao) <= DATETIME('now')
            """,
            (int(user_id),),
        )
        questoes_pendentes = int((cursor.fetchone() or [0])[0] or 0)

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM questoes_usuario
            WHERE user_id = ? AND marcado_erro = 1
            """,
            (int(user_id),),
        )
        questoes_marcadas = int((cursor.fetchone() or [0])[0] or 0)

        conn.close()
        return {
            "flashcards_pendentes": flashcards_pendentes,
            "questoes_pendentes": questoes_pendentes,
            "questoes_marcadas": questoes_marcadas,
        }

    def _question_hash(self, question: Dict) -> str:
        base = {
            "enunciado": question.get("enunciado", ""),
            "alternativas": question.get("alternativas", []),
            "correta_index": question.get("correta_index", question.get("correta", 0)),
        }
        payload = json.dumps(base, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def salvar_questao_cache(self, tema: str, dificuldade: str, questao: Dict) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO banco_questoes (tema, dificuldade, dados_json)
            VALUES (?, ?, ?)
            """,
            (
                str((tema or "Geral").strip() or "Geral"),
                str((dificuldade or "intermediario").strip() or "intermediario"),
                json.dumps(questao, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()

    def listar_questoes_cache(self, tema: str, dificuldade: str, limite: int = 10) -> List[Dict]:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT dados_json
            FROM banco_questoes
            WHERE lower(tema) = lower(?)
              AND lower(dificuldade) = lower(?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (
                str((tema or "Geral").strip() or "Geral"),
                str((dificuldade or "intermediario").strip() or "intermediario"),
                int(max(1, limite)),
            ),
        )
        rows = cursor.fetchall()
        conn.close()
        out = []
        for row in rows:
            try:
                out.append(json.loads(row["dados_json"] or "{}"))
            except Exception:
                continue
        return out

    def registrar_questao_usuario(
        self,
        user_id: int,
        question: Dict,
        tema: str = "Geral",
        dificuldade: str = "intermediario",
        tentativa_correta: Optional[bool] = None,
        favorita: Optional[bool] = None,
        marcado_erro: Optional[bool] = None,
    ) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            qhash = self._question_hash(question)
            cursor.execute(
                """
                SELECT favorita, marcado_erro, tentativas, acertos, erros, revisao_nivel
                FROM questoes_usuario
                WHERE user_id = ? AND qhash = ?
                """,
                (user_id, qhash),
            )
            row = cursor.fetchone()

            fav = int(bool(favorita)) if favorita is not None else (row[0] if row else 0)
            mark = int(bool(marcado_erro)) if marcado_erro is not None else (row[1] if row else 0)
            tentativas = row[2] if row else 0
            acertos = row[3] if row else 0
            erros = row[4] if row else 0
            revisao_nivel = row[5] if row else 0
            proxima_revisao_expr = None
            last_result = None

            if tentativa_correta is True:
                tentativas += 1
                acertos += 1
                mark = 0
                revisao_nivel = min(4, int(revisao_nivel or 0) + 1)
                dias_map = [1, 3, 7, 14, 30]
                dias = dias_map[revisao_nivel]
                proxima_revisao_expr = f"DATETIME('now', '+{dias} days')"
                last_result = "correct"
            elif tentativa_correta is False:
                tentativas += 1
                erros += 1
                revisao_nivel = 0
                mark = 1
                proxima_revisao_expr = "DATETIME('now', '+1 day')"
                last_result = "wrong"

            proxima_revisao_sql = proxima_revisao_expr or "NULL"
            next_review_sql = proxima_revisao_sql
            review_level = int(revisao_nivel or 0)

            cursor.execute(
                f"""
                INSERT INTO questoes_usuario
                (user_id, qhash, dados_json, tema, dificuldade, favorita, marcado_erro, tentativas, acertos, erros,
                 revisao_nivel, proxima_revisao, ultima_pratica, marked_for_review, next_review_at, review_level, last_attempt_at, last_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {proxima_revisao_sql}, CURRENT_TIMESTAMP, ?, {next_review_sql}, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(user_id, qhash) DO UPDATE SET
                    dados_json = excluded.dados_json,
                    tema = excluded.tema,
                    dificuldade = excluded.dificuldade,
                    favorita = excluded.favorita,
                    marcado_erro = excluded.marcado_erro,
                    tentativas = excluded.tentativas,
                    acertos = excluded.acertos,
                    erros = excluded.erros,
                    revisao_nivel = excluded.revisao_nivel,
                    proxima_revisao = COALESCE(excluded.proxima_revisao, questoes_usuario.proxima_revisao),
                    ultima_pratica = CURRENT_TIMESTAMP,
                    marked_for_review = excluded.marked_for_review,
                    next_review_at = COALESCE(excluded.next_review_at, questoes_usuario.next_review_at),
                    review_level = excluded.review_level,
                    last_attempt_at = CURRENT_TIMESTAMP,
                    last_result = COALESCE(excluded.last_result, questoes_usuario.last_result)
                """,
                (
                    user_id,
                    qhash,
                    json.dumps(question, ensure_ascii=False),
                    tema or "Geral",
                    dificuldade or "intermediario",
                    fav,
                    mark,
                    tentativas,
                    acertos,
                    erros,
                    revisao_nivel,
                    mark,
                    review_level,
                    last_result,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def listar_questoes_usuario(self, user_id: int, modo: str = "all", limite: int = 20) -> List[Dict]:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        where = "user_id = ?"
        if modo == "favoritas":
            where += " AND favorita = 1"
        elif modo == "erradas":
            where += " AND (marcado_erro = 1 OR erros > acertos)"
        elif modo == "nao_resolvidas":
            where += " AND tentativas = 0"

        order_by = "ultima_pratica DESC"
        if modo == "erradas":
            order_by = "CASE WHEN proxima_revisao IS NULL THEN 1 WHEN DATETIME(proxima_revisao) <= DATETIME('now') THEN 0 ELSE 1 END, DATETIME(proxima_revisao) ASC, ultima_pratica DESC"

        cursor.execute(
            f"""
            SELECT dados_json, tema, dificuldade, favorita, marcado_erro, tentativas, acertos, erros, revisao_nivel, proxima_revisao
            FROM questoes_usuario
            WHERE {where}
            ORDER BY {order_by}
            LIMIT ?
            """,
            (user_id, int(max(1, limite))),
        )
        rows = cursor.fetchall()
        conn.close()

        result = []
        for row in rows:
            try:
                q = json.loads(row["dados_json"] or "{}")
            except Exception:
                continue
            q["_meta"] = {
                "tema": row["tema"],
                "dificuldade": row["dificuldade"],
                "favorita": bool(row["favorita"]),
                "marcado_erro": bool(row["marcado_erro"]),
                "tentativas": int(row["tentativas"] or 0),
                "acertos": int(row["acertos"] or 0),
                "erros": int(row["erros"] or 0),
                "revisao_nivel": int(row["revisao_nivel"] or 0),
                "proxima_revisao": row["proxima_revisao"],
            }
            result.append(q)
        return result

    def salvar_filtro_quiz(self, user_id: int, nome: str, filtro: Dict) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO quiz_filtros_salvos (user_id, nome, filtro_json)
            VALUES (?, ?, ?)
            """,
            (user_id, nome, json.dumps(filtro, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def atualizar_meta_diaria(self, user_id: int, meta_questoes: int):
        """Atualiza meta diaria de questoes do usuario."""
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios SET meta_questoes_diaria = ? WHERE id = ?",
            (int(max(5, min(200, meta_questoes))), user_id),
        )
        conn.commit()
        conn.close()

    def listar_filtros_quiz(self, user_id: int) -> List[Dict]:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nome, filtro_json, created_at
            FROM quiz_filtros_salvos
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        out = []
        for row in rows:
            try:
                filtro = json.loads(row["filtro_json"] or "{}")
            except Exception:
                filtro = {}
            out.append({"id": row["id"], "nome": row["nome"], "filtro": filtro, "created_at": row["created_at"]})
        return out

    def excluir_filtro_quiz(self, filtro_id: int, user_id: int) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quiz_filtros_salvos WHERE id = ? AND user_id = ?", (filtro_id, user_id))
        conn.commit()
        conn.close()

    def renomear_filtro_quiz(self, filtro_id: int, user_id: int, novo_nome: str) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE quiz_filtros_salvos SET nome = ? WHERE id = ? AND user_id = ?",
            (str(novo_nome or "").strip(), int(filtro_id), int(user_id)),
        )
        conn.commit()
        conn.close()

    def topicos_revisao(self, user_id: int, limite: int = 3) -> List[Dict]:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tema, SUM(erros) AS erros_total, SUM(acertos) AS acertos_total, SUM(tentativas) AS tentativas_total
            FROM questoes_usuario
            WHERE user_id = ?
            GROUP BY tema
            HAVING tentativas_total > 0
            ORDER BY (erros_total - acertos_total) DESC, erros_total DESC, tentativas_total DESC
            LIMIT ?
            """,
            (user_id, int(max(1, limite))),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def revisoes_pendentes(self, user_id: int) -> int:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM questoes_usuario
            WHERE user_id = ?
              AND proxima_revisao IS NOT NULL
              AND DATETIME(proxima_revisao) <= DATETIME('now')
            """,
            (user_id,),
        )
        total = cursor.fetchone()[0]
        conn.close()
        return int(total or 0)

    def sugerir_estudo_agora(self, user_id: int) -> Dict:
        topicos = self.topicos_revisao(user_id, limite=1)
        if topicos:
            tema = topicos[0].get("tema") or "Geral"
            return {
                "topic": tema,
                "difficulty": "intermediario",
                "count": 5,
                "session_mode": "erradas",
                "reason": f"Maior necessidade atual: {tema}",
            }
        return {
            "topic": "Geral",
            "difficulty": "intermediario",
            "count": 5,
            "session_mode": "nova",
            "reason": "Comece uma sessao nova para gerar historico.",
        }

    def salvar_plano_semanal(
        self,
        user_id: int,
        objetivo: str,
        data_prova: str,
        tempo_diario_min: int,
        itens: List[Dict],
    ) -> int:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE study_plan_runs SET status = 'arquivado'
            WHERE user_id = ? AND status = 'ativo'
            """,
            (user_id,),
        )
        cursor.execute(
            """
            INSERT INTO study_plan_runs (user_id, objetivo, data_prova, tempo_diario_min, status)
            VALUES (?, ?, ?, ?, 'ativo')
            """,
            (user_id, objetivo, data_prova, int(max(30, tempo_diario_min))),
        )
        plan_id = int(cursor.lastrowid or 0)
        for item in itens:
            cursor.execute(
                """
                INSERT INTO study_plan_items (plan_id, dia, tema, atividade, duracao_min, prioridade, concluido)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    str(item.get("dia") or "Dia"),
                    str(item.get("tema") or "Geral"),
                    str(item.get("atividade") or "Resolver questoes"),
                    int(item.get("duracao_min") or 60),
                    int(item.get("prioridade") or 1),
                    1 if item.get("concluido") else 0,
                ),
            )
        conn.commit()
        conn.close()
        return plan_id

    def obter_plano_ativo(self, user_id: int) -> Dict:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM study_plan_runs
            WHERE user_id = ? AND status = 'ativo'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        plan = cursor.fetchone()
        if not plan:
            conn.close()
            return {"plan": None, "itens": []}
        cursor.execute(
            """
            SELECT *
            FROM study_plan_items
            WHERE plan_id = ?
            ORDER BY id ASC
            """,
            (plan["id"],),
        )
        itens = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return {"plan": dict(plan), "itens": itens}

    def marcar_item_plano(self, item_id: int, concluido: bool) -> None:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE study_plan_items SET concluido = ? WHERE id = ?",
            (1 if concluido else 0, item_id),
        )
        conn.commit()
        conn.close()

    def salvar_study_package(self, user_id: int, titulo: str, source_nome: str, dados: Dict) -> int:
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_packages (user_id, titulo, source_nome, dados_json)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, titulo, source_nome, json.dumps(dados, ensure_ascii=False)),
        )
        package_id = int(cursor.lastrowid or 0)
        conn.commit()
        conn.close()
        return package_id

    def listar_study_packages(self, user_id: int, limite: int = 20) -> List[Dict]:
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, titulo, source_nome, dados_json, created_at
            FROM study_packages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, int(max(1, limite))),
        )
        rows = cursor.fetchall()
        conn.close()
        out = []
        for row in rows:
            try:
                dados = json.loads(row["dados_json"] or "{}")
            except Exception:
                dados = {}
            out.append(
                {
                    "id": row["id"],
                    "titulo": row["titulo"],
                    "source_nome": row["source_nome"],
                    "dados": dados,
                    "created_at": row["created_at"],
                }
            )
        return out

    def obter_resumo_por_hash(self, user_id: int, source_hash: str) -> Optional[Dict]:
        if not source_hash:
            return None
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT summary_json
            FROM study_summary_cache
            WHERE user_id = ? AND source_hash = ?
            LIMIT 1
            """,
            (int(user_id), str(source_hash)),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        try:
            data = json.loads(row["summary_json"] or "{}")
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def salvar_resumo_por_hash(self, user_id: int, source_hash: str, topic: str, summary: Dict) -> None:
        if not source_hash or not isinstance(summary, dict):
            return
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_summary_cache
            (user_id, source_hash, topic, summary_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, source_hash) DO UPDATE SET
                topic = excluded.topic,
                summary_json = excluded.summary_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(user_id),
                str(source_hash),
                str(topic or ""),
                json.dumps(summary, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()

    def salvar_nota_questao(self, user_id: int, question: Dict, nota: str) -> None:
        qhash = self._question_hash(question)
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO questoes_notas (user_id, qhash, nota, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, qhash) DO UPDATE SET
                nota = excluded.nota,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, qhash, nota or ""),
        )
        conn.commit()
        conn.close()

    def obter_nota_questao(self, user_id: int, question: Dict) -> str:
        qhash = self._question_hash(question)
        conn = self.conectar()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nota FROM questoes_notas WHERE user_id = ? AND qhash = ?",
            (user_id, qhash),
        )
        row = cursor.fetchone()
        conn.close()
        return str(row[0]) if row and row[0] is not None else ""


# Nao criar instancia global em import para evitar inicializacao prematura
# (especialmente no Android empacotado).
