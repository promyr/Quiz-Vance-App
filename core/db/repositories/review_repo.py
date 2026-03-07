# -*- coding: utf-8 -*-
"""
ReviewRepository — Sessões de revisão, mock exams (simulados), flashcards e plano semanal.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from core.database_v2 import Database


class ReviewRepository:
    """Gerencia revisões, sessões de flashcards, simulados (mock exam) e plano semanal."""

    def __init__(self, db: "Database") -> None:
        self._db = db

    def _conectar(self) -> sqlite3.Connection:
        return self._db.conectar()

    def _flashcard_hash(self, card: Dict) -> str:
        import hashlib
        base = {
            "frente": str(card.get("frente") or "").strip(),
            "verso": str(card.get("verso") or "").strip(),
            "tema": str(card.get("tema") or "Geral").strip(),
        }
        return hashlib.sha256(
            json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def _question_hash(self, question: Dict) -> str:
        import hashlib
        base = {
            "enunciado": question.get("enunciado", ""),
            "alternativas": question.get("alternativas", []),
            "correta_index": question.get("correta_index", question.get("correta", 0)),
        }
        return hashlib.sha256(
            json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    # ------------------------------------------------------------------
    # Flashcards
    # ------------------------------------------------------------------

    def salvar_flashcards_gerados(
        self, user_id: int, tema: str, cards: List[Dict], dificuldade: str = "intermediario"
    ) -> int:
        if not cards:
            return 0
        conn = self._conectar()
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
                (user_id, card_hash, frente, verso, tema, dificuldade, revisao_nivel,
                 proxima_revisao, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, DATETIME('now', '+1 day'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, card_hash) DO UPDATE SET
                    frente = excluded.frente, verso = excluded.verso,
                    tema = excluded.tema, dificuldade = excluded.dificuldade,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, card_hash, frente, verso, str(tema or "Geral"), str(dificuldade or "intermediario")),
            )
            added += 1
        conn.commit()
        conn.close()
        return added

    def registrar_revisao_flashcard(self, user_id: int, card: Dict, lembrei: bool) -> None:
        card_hash = self._flashcard_hash(card)
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, revisao_nivel, total_revisoes, total_acertos, total_erros FROM flashcards WHERE user_id = ? AND card_hash = ? LIMIT 1",
            (user_id, card_hash),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            self.salvar_flashcards_gerados(user_id, str(card.get("tema") or "Geral"), [card], str(card.get("dificuldade") or "intermediario"))
            conn = self._conectar()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, revisao_nivel, total_revisoes, total_acertos, total_erros FROM flashcards WHERE user_id = ? AND card_hash = ? LIMIT 1",
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
            SET revisao_nivel = ?, proxima_revisao = DATETIME('now', '+' || ? || ' days'),
                ultima_revisao_em = CURRENT_TIMESTAMP, total_revisoes = ?,
                total_acertos = ?, total_erros = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (novo_nivel, dias, total_rev, total_acertos, total_erros, int(row["id"])),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Review Sessions (sessões de revisão)
    # ------------------------------------------------------------------

    def iniciar_review_session(self, user_id: int, session_type: str, total_items: int) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO review_sessions (user_id, session_type, status, total_items, created_at) VALUES (?, ?, 'in_progress', ?, CURRENT_TIMESTAMP)",
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
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO review_session_items (session_id, item_type, item_ref, resultado, is_correct, response_time_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (
                int(session_id), str(item_type or "question"), str(item_ref or ""),
                str(resultado or ""), None if is_correct is None else (1 if is_correct else 0),
                int(max(0, response_time_ms or 0)),
            ),
        )
        conn.commit()
        conn.close()

    def finalizar_review_session(
        self, session_id: int, acertos: int, erros: int, puladas: int, total_time_ms: int
    ) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE review_sessions SET status = 'finished', acertos = ?, erros = ?, puladas = ?, total_time_ms = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(max(0, acertos)), int(max(0, erros)), int(max(0, puladas)), int(max(0, total_time_ms)), int(session_id)),
        )
        conn.commit()
        conn.close()

    def contadores_revisao(self, user_id: int) -> Dict[str, int]:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM flashcards WHERE user_id = ? AND proxima_revisao IS NOT NULL AND DATETIME(proxima_revisao) <= DATETIME('now')",
            (int(user_id),),
        )
        fc = int((cursor.fetchone() or [0])[0] or 0)
        cursor.execute(
            "SELECT COUNT(*) FROM questoes_usuario WHERE user_id = ? AND proxima_revisao IS NOT NULL AND DATETIME(proxima_revisao) <= DATETIME('now')",
            (int(user_id),),
        )
        qp = int((cursor.fetchone() or [0])[0] or 0)
        cursor.execute(
            "SELECT COUNT(*) FROM questoes_usuario WHERE user_id = ? AND marcado_erro = 1",
            (int(user_id),),
        )
        qm = int((cursor.fetchone() or [0])[0] or 0)
        conn.close()
        return {"flashcards_pendentes": fc, "questoes_pendentes": qp, "questoes_marcadas": qm}

    def topicos_revisao(self, user_id: int, limite: int = 3) -> List[Dict]:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tema, SUM(erros) AS erros_total, SUM(acertos) AS acertos_total, SUM(tentativas) AS tentativas_total
            FROM questoes_usuario WHERE user_id = ?
            GROUP BY tema HAVING tentativas_total > 0
            ORDER BY (erros_total - acertos_total) DESC, erros_total DESC, tentativas_total DESC
            LIMIT ?
            """,
            (user_id, int(max(1, limite))),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def revisoes_pendentes(self, user_id: int) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM questoes_usuario WHERE user_id = ? AND proxima_revisao IS NOT NULL AND DATETIME(proxima_revisao) <= DATETIME('now')",
            (user_id,),
        )
        total = cursor.fetchone()[0]
        conn.close()
        return int(total or 0)

    def sugerir_estudo_agora(self, user_id: int) -> Dict:
        topicos = self.topicos_revisao(user_id, limite=1)
        if topicos:
            tema = topicos[0].get("tema") or "Geral"
            return {"topic": tema, "difficulty": "intermediario", "count": 5, "session_mode": "erradas", "reason": f"Maior necessidade atual: {tema}"}
        return {"topic": "Geral", "difficulty": "intermediario", "count": 5, "session_mode": "nova", "reason": "Comece uma sessao nova para gerar historico."}

    # ------------------------------------------------------------------
    # Mock Exam (Simulado)
    # ------------------------------------------------------------------

    def criar_mock_exam_session(
        self, user_id: int, filtro_snapshot: Dict, total_questoes: int, tempo_total_s: int, modo: str = "timed"
    ) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO mock_exam_sessions (user_id, filtro_snapshot_json, progress_json, total_questoes, tempo_total_s, modo, status, created_at) VALUES (?, ?, NULL, ?, ?, ?, 'in_progress', CURRENT_TIMESTAMP)",
            (int(user_id), json.dumps(filtro_snapshot or {}, ensure_ascii=False), int(max(0, total_questoes)), int(max(0, tempo_total_s)), str(modo or "timed")),
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
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO mock_exam_items (session_id, ordem, qhash, meta_json, resposta_index, correta_index, resultado, tempo_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (
                int(session_id), int(max(0, ordem)), self._question_hash(question),
                json.dumps(meta or {}, ensure_ascii=False),
                None if resposta_index is None else int(resposta_index),
                None if correta_index is None else int(correta_index),
                resultado, int(max(0, tempo_ms or 0)),
            ),
        )
        conn.commit()
        conn.close()

    def salvar_mock_exam_progresso(
        self, session_id: int, current_idx: int, respostas: Dict[int, Optional[int]]
    ) -> None:
        payload = {
            "current_idx": int(max(0, current_idx or 0)),
            "respostas": {str(k): (None if v is None else int(v)) for k, v in (respostas or {}).items()},
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") + "Z",
        }
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE mock_exam_sessions SET progress_json = ? WHERE id = ?",
            (json.dumps(payload, ensure_ascii=False), int(session_id)),
        )
        conn.commit()
        conn.close()

    def finalizar_mock_exam_session(
        self, session_id: int, acertos: int, erros: int, puladas: int, score_pct: float, tempo_gasto_s: int
    ) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE mock_exam_sessions SET status = 'finished', acertos = ?, erros = ?, puladas = ?, score_pct = ?, tempo_gasto_s = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(max(0, acertos)), int(max(0, erros)), int(max(0, puladas)), float(max(0.0, min(100.0, score_pct))), int(max(0, tempo_gasto_s)), int(session_id)),
        )
        conn.commit()
        conn.close()

    def contar_simulados_hoje(self, user_id: int) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM mock_exam_sessions WHERE user_id = ? AND DATE(created_at, 'localtime') = DATE('now','localtime')",
            (int(user_id),),
        )
        total = cursor.fetchone()[0]
        conn.close()
        return int(total or 0)

    def listar_historico_simulados(self, user_id: int, limite: int = 20) -> List[Dict]:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, modo, status, total_questoes, acertos, erros, puladas, score_pct, tempo_total_s, tempo_gasto_s, created_at, finished_at FROM mock_exam_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (int(user_id), int(max(1, limite))),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    # ------------------------------------------------------------------
    # Plano semanal de estudos
    # ------------------------------------------------------------------

    def salvar_plano_semanal(
        self, user_id: int, objetivo: str, data_prova: str, tempo_diario_min: int, itens: List[Dict]
    ) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE study_plan_runs SET status = 'arquivado' WHERE user_id = ? AND status = 'ativo'",
            (user_id,),
        )
        cursor.execute(
            "INSERT INTO study_plan_runs (user_id, objetivo, data_prova, tempo_diario_min, status) VALUES (?, ?, ?, ?, 'ativo')",
            (user_id, objetivo, data_prova, int(max(30, tempo_diario_min))),
        )
        plan_id = int(cursor.lastrowid or 0)
        for item in itens:
            cursor.execute(
                "INSERT INTO study_plan_items (plan_id, dia, tema, atividade, duracao_min, prioridade, concluido) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (plan_id, str(item.get("dia") or "Dia"), str(item.get("tema") or "Geral"), str(item.get("atividade") or "Resolver questoes"), int(item.get("duracao_min") or 60), int(item.get("prioridade") or 1), 1 if item.get("concluido") else 0),
            )
        conn.commit()
        conn.close()
        return plan_id

    def obter_plano_ativo(self, user_id: int) -> Dict:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM study_plan_runs WHERE user_id = ? AND status = 'ativo' ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        plan = cursor.fetchone()
        if not plan:
            conn.close()
            return {"plan": None, "itens": []}
        cursor.execute("SELECT * FROM study_plan_items WHERE plan_id = ? ORDER BY id ASC", (plan["id"],))
        itens = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return {"plan": dict(plan), "itens": itens}

    def marcar_item_plano(self, item_id: int, concluido: bool) -> None:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE study_plan_items SET concluido = ? WHERE id = ?", (1 if concluido else 0, item_id))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Study Packages & Resumos
    # ------------------------------------------------------------------

    def salvar_study_package(self, user_id: int, titulo: str, source_nome: str, dados: Dict) -> int:
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO study_packages (user_id, titulo, source_nome, dados_json) VALUES (?, ?, ?, ?)",
            (user_id, titulo, source_nome, json.dumps(dados, ensure_ascii=False)),
        )
        package_id = int(cursor.lastrowid or 0)
        conn.commit()
        conn.close()
        return package_id

    def listar_study_packages(self, user_id: int, limite: int = 20) -> List[Dict]:
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, titulo, source_nome, dados_json, created_at FROM study_packages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
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
            out.append({"id": row["id"], "titulo": row["titulo"], "source_nome": row["source_nome"], "dados": dados, "created_at": row["created_at"]})
        return out

    def obter_resumo_por_hash(self, user_id: int, source_hash: str) -> Optional[Dict]:
        if not source_hash:
            return None
        conn = self._conectar()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT summary_json FROM study_summary_cache WHERE user_id = ? AND source_hash = ? LIMIT 1",
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
        conn = self._conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_summary_cache (user_id, source_hash, topic, summary_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, source_hash) DO UPDATE SET
                topic = excluded.topic, summary_json = excluded.summary_json, updated_at = CURRENT_TIMESTAMP
            """,
            (int(user_id), str(source_hash), str(topic or ""), json.dumps(summary, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
