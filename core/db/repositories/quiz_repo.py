# -*- coding: utf-8 -*-
"""
QuizRepository — Cache de questões, histórico do usuário, filtros salvos e notas.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from core.database_v2 import Database


class QuizRepository:
    """Gerencia cache de questões, histórico do usuário, filtros salvos e notas."""

    def __init__(self, db: "Database") -> None:
        self._db = db

    def _conectar(self) -> sqlite3.Connection:
        return self._db.conectar()

    # ------------------------------------------------------------------
    # Hash
    # ------------------------------------------------------------------

    def _question_hash(self, question: Dict) -> str:
        base = {
            "enunciado": question.get("enunciado", ""),
            "alternativas": question.get("alternativas", []),
            "correta_index": question.get("correta_index", question.get("correta", 0)),
        }
        return hashlib.sha256(
            json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    # ------------------------------------------------------------------
    # Cache de questões (banco_questoes)
    # ------------------------------------------------------------------

    def salvar_questao_cache(self, tema: str, dificuldade: str, questao: Dict) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO banco_questoes (tema, dificuldade, dados_json) VALUES (?, ?, ?)",
            (
                str((tema or "Geral").strip() or "Geral"),
                str((dificuldade or "intermediario").strip() or "intermediario"),
                json.dumps(questao, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()

    def listar_questoes_cache(self, tema: str, dificuldade: str, limite: int = 10) -> List[Dict]:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT dados_json FROM banco_questoes WHERE lower(tema) = lower(?) AND lower(dificuldade) = lower(?) ORDER BY created_at DESC LIMIT ?",
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

    # ------------------------------------------------------------------
    # Histórico do usuário (questoes_usuario)
    # ------------------------------------------------------------------

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
        conn = self._conectar()
        cursor = conn.cursor()
        try:
            qhash = self._question_hash(question)
            cursor.execute(
                "SELECT favorita, marcado_erro, tentativas, acertos, erros, revisao_nivel FROM questoes_usuario WHERE user_id = ? AND qhash = ?",
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
                dias = [1, 3, 7, 14, 30][revisao_nivel]
                proxima_revisao_expr = f"DATETIME('now', '+{dias} days')"
                last_result = "correct"
            elif tentativa_correta is False:
                tentativas += 1
                erros += 1
                revisao_nivel = 0
                mark = 1
                proxima_revisao_expr = "DATETIME('now', '+1 day')"
                last_result = "wrong"

            pr_sql = proxima_revisao_expr or "NULL"
            review_level = int(revisao_nivel or 0)

            cursor.execute(
                f"""
                INSERT INTO questoes_usuario
                (user_id, qhash, dados_json, tema, dificuldade, favorita, marcado_erro,
                 tentativas, acertos, erros, revisao_nivel, proxima_revisao, ultima_pratica,
                 marked_for_review, next_review_at, review_level, last_attempt_at, last_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {pr_sql}, CURRENT_TIMESTAMP,
                        ?, {pr_sql}, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(user_id, qhash) DO UPDATE SET
                    dados_json = excluded.dados_json, tema = excluded.tema,
                    dificuldade = excluded.dificuldade, favorita = excluded.favorita,
                    marcado_erro = excluded.marcado_erro, tentativas = excluded.tentativas,
                    acertos = excluded.acertos, erros = excluded.erros,
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
                    user_id, qhash, json.dumps(question, ensure_ascii=False),
                    tema or "Geral", dificuldade or "intermediario",
                    fav, mark, tentativas, acertos, erros, revisao_nivel,
                    mark, review_level, last_result,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def listar_questoes_usuario(self, user_id: int, modo: str = "all", limite: int = 20) -> List[Dict]:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        where = "user_id = ?"
        if modo == "favoritas":
            where += " AND favorita = 1"
        elif modo == "erradas":
            where += " AND (marcado_erro = 1 OR erros > acertos)"
        elif modo == "nao_resolvidas":
            where += " AND tentativas = 0"
        order = "ultima_pratica DESC"
        if modo == "erradas":
            order = "CASE WHEN proxima_revisao IS NULL THEN 1 WHEN DATETIME(proxima_revisao) <= DATETIME('now') THEN 0 ELSE 1 END, DATETIME(proxima_revisao) ASC, ultima_pratica DESC"
        cursor.execute(
            f"SELECT dados_json, tema, dificuldade, favorita, marcado_erro, tentativas, acertos, erros, revisao_nivel, proxima_revisao FROM questoes_usuario WHERE {where} ORDER BY {order} LIMIT ?",
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
                "tema": row["tema"], "dificuldade": row["dificuldade"],
                "favorita": bool(row["favorita"]), "marcado_erro": bool(row["marcado_erro"]),
                "tentativas": int(row["tentativas"] or 0), "acertos": int(row["acertos"] or 0),
                "erros": int(row["erros"] or 0), "revisao_nivel": int(row["revisao_nivel"] or 0),
                "proxima_revisao": row["proxima_revisao"],
            }
            result.append(q)
        return result

    # ------------------------------------------------------------------
    # Filtros salvos
    # ------------------------------------------------------------------

    def salvar_filtro_quiz(self, user_id: int, nome: str, filtro: Dict) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO quiz_filtros_salvos (user_id, nome, filtro_json) VALUES (?, ?, ?)",
            (user_id, nome, json.dumps(filtro, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def listar_filtros_quiz(self, user_id: int) -> List[Dict]:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, nome, filtro_json, created_at FROM quiz_filtros_salvos WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
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
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quiz_filtros_salvos WHERE id = ? AND user_id = ?", (filtro_id, user_id))
        conn.commit()
        conn.close()

    def renomear_filtro_quiz(self, filtro_id: int, user_id: int, novo_nome: str) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE quiz_filtros_salvos SET nome = ? WHERE id = ? AND user_id = ?",
            (str(novo_nome or "").strip(), int(filtro_id), int(user_id)),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Notas em questões
    # ------------------------------------------------------------------

    def salvar_nota_questao(self, user_id: int, question: Dict, nota: str) -> None:
        qhash = self._question_hash(question)
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO questoes_notas (user_id, qhash, nota, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(user_id, qhash) DO UPDATE SET nota = excluded.nota, updated_at = CURRENT_TIMESTAMP",
            (user_id, qhash, nota or ""),
        )
        conn.commit()
        conn.close()

    def obter_nota_questao(self, user_id: int, question: Dict) -> str:
        qhash = self._question_hash(question)
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT nota FROM questoes_notas WHERE user_id = ? AND qhash = ?", (user_id, qhash))
        row = cursor.fetchone()
        conn.close()
        return str(row[0]) if row and row[0] is not None else ""

    # ------------------------------------------------------------------
    # Query genérica
    # ------------------------------------------------------------------

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Executa SELECT genérico e retorna lista de dicts."""
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
