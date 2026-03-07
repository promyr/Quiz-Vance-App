# -*- coding: utf-8 -*-
"""
services/spaced_repetition.py

Serviço de Revisão Espaçada baseado no algoritmo simplificado SM-2.
Gerencia agendamentos de revisão para a tabela `questoes_usuario`.

Estrutura SM-2:
  - revisao_nivel 0-1: intervalo = 1 dia
  - revisao_nivel 2:   intervalo = 6 dias
  - revisao_nivel > 2: intervalo = anterior * fator_facilitacao (≥ 2.5)
  - Fator base >= 1.3; aumenta com acertos, diminui com erros.
"""

import datetime
import json
import hashlib
from typing import Optional, List, Dict


# Intervalos base em dias por nível
_INTERVALOS_BASE = {0: 1, 1: 1, 2: 6}
_EFICIENCIA_INICIAL = 2.5
_EFICIENCIA_MIN = 1.3


def _qhash(questao: dict) -> str:
    """Hash estável da questão para indexação."""
    chave = str(questao.get("enunciado") or questao.get("pergunta") or "").strip().lower()
    return hashlib.md5(chave.encode("utf-8")).hexdigest()


def _prox_revisao(nivel: int, dias_atual: Optional[int] = None, ef: float = _EFICIENCIA_INICIAL) -> datetime.datetime:
    """Calcula a data/hora da próxima revisão."""
    if nivel <= 0:
        intervalo = 1
    elif nivel == 1:
        intervalo = 1
    elif nivel == 2:
        intervalo = 6
    else:
        base = dias_atual or 6
        intervalo = max(1, round(base * max(ef, _EFICIENCIA_MIN)))
    return datetime.datetime.now() + datetime.timedelta(days=intervalo)


class SpacedRepetitionService:
    """
    Serviço que encapsula operações de revisão espaçada.
    Requer instância de `core.database_v2.Database`.
    """

    def __init__(self, db):
        self.db = db

    # ──────────────────────────────────────────────────────────────
    # Registro de resultado
    # ──────────────────────────────────────────────────────────────

    def registrar_resultado(
        self,
        user_id: int,
        questao: dict,
        acertou: bool,
        tema: str = "Geral",
        dificuldade: str = "intermediario",
    ) -> None:
        """
        Registra o resultado de uma questão e atualiza o agendamento SRS.
        Se a questão não existir em `questoes_usuario`, ela é criada.
        """
        qh = _qhash(questao)
        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()

            # Garantir que a questão existe
            cur.execute(
                "SELECT * FROM questoes_usuario WHERE user_id=? AND qhash=?",
                (user_id, qh),
            )
            row = cur.fetchone()

            if row is None:
                # Inserir nova entrada
                dados = json.dumps(questao, ensure_ascii=False)
                cur.execute(
                    """
                    INSERT INTO questoes_usuario
                    (user_id, qhash, dados_json, tema, dificuldade,
                     tentativas, acertos, erros, revisao_nivel, proxima_revisao, ultima_pratica)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, 0, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        user_id, qh, dados, tema, dificuldade,
                        1 if acertou else 0,
                        0 if acertou else 1,
                        _prox_revisao(1 if acertou else 0).strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
            else:
                nivel_atual = int(row["revisao_nivel"] or 0)
                tentativas  = int(row["tentativas"] or 0) + 1
                acertos_row = int(row["acertos"] or 0) + (1 if acertou else 0)
                erros_row   = int(row["erros"] or 0) + (0 if acertou else 1)

                # Calcular novo nível
                if acertou:
                    novo_nivel = nivel_atual + 1
                else:
                    novo_nivel = max(0, nivel_atual - 1)

                # Calcular eficiência (simplificado)
                ef = round(
                    (acertos_row / tentativas) * (_EFICIENCIA_INICIAL - _EFICIENCIA_MIN)
                    + _EFICIENCIA_MIN,
                    2,
                )

                # Dias do último intervalo (em dias, aproximado)
                ultima = row["ultima_pratica"]
                dias_decorridos = None
                if ultima:
                    try:
                        dt_ult = datetime.datetime.strptime(str(ultima), "%Y-%m-%d %H:%M:%S")
                        dias_decorridos = max(1, (datetime.datetime.now() - dt_ult).days)
                    except Exception:
                        dias_decorridos = None

                prox = _prox_revisao(novo_nivel, dias_decorridos, ef)

                cur.execute(
                    """
                    UPDATE questoes_usuario
                    SET tentativas=?, acertos=?, erros=?, revisao_nivel=?,
                        proxima_revisao=?, ultima_pratica=CURRENT_TIMESTAMP,
                        marcado_erro=?
                    WHERE user_id=? AND qhash=?
                    """,
                    (
                        tentativas, acertos_row, erros_row, novo_nivel,
                        prox.strftime("%Y-%m-%d %H:%M:%S"),
                        1 if not acertou else row["marcado_erro"],
                        user_id, qh,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

    # ──────────────────────────────────────────────────────────────
    # Consultas
    # ──────────────────────────────────────────────────────────────

    def questoes_para_revisao_hoje(self, user_id: int, limite: int = 30) -> List[Dict]:
        """Retorna questões cujo proxima_revisao <= agora."""
        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dados_json, tema, dificuldade, revisao_nivel, acertos, erros
                FROM questoes_usuario
                WHERE user_id=? AND proxima_revisao IS NOT NULL
                  AND DATETIME(proxima_revisao) <= DATETIME('now')
                ORDER BY proxima_revisao ASC
                LIMIT ?
                """,
                (user_id, limite),
            )
            rows = cur.fetchall()
            resultado = []
            for r in rows:
                try:
                    q = json.loads(r["dados_json"])
                    q["_srs"] = {
                        "tema": r["tema"],
                        "nivel": r["revisao_nivel"],
                        "acertos": r["acertos"],
                        "erros":   r["erros"],
                    }
                    resultado.append(q)
                except Exception:
                    pass
            return resultado
        finally:
            conn.close()

    def questoes_por_tema(self, user_id: int, tema: str, limite: int = 20) -> List[Dict]:
        """Retorna questões de um tema específico para revisão."""
        conn = self.db.conectar()
        try:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dados_json, tema, revisao_nivel, acertos, erros
                FROM questoes_usuario
                WHERE user_id=? AND tema=?
                ORDER BY proxima_revisao ASC NULLS FIRST
                LIMIT ?
                """,
                (user_id, tema, limite),
            )
            rows = cur.fetchall()
            resultado = []
            for r in rows:
                try:
                    q = json.loads(r["dados_json"])
                    q["_srs"] = {"tema": r["tema"], "nivel": r["revisao_nivel"]}
                    resultado.append(q)
                except Exception:
                    pass
            return resultado
        finally:
            conn.close()

    def total_pendentes_hoje(self, user_id: int) -> int:
        """Número de questões com revisão pendente para hoje."""
        conn = self.db.conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FROM questoes_usuario
                WHERE user_id=? AND proxima_revisao IS NOT NULL
                  AND DATETIME(proxima_revisao) <= DATETIME('now')
                """,
                (user_id,),
            )
            return int((cur.fetchone() or [0])[0])
        finally:
            conn.close()

    def temas_com_pendencias(self, user_id: int) -> List[Dict]:
        """Retorna lista de temas com quantidade de pendências."""
        conn = self.db.conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT tema, COUNT(*) as total
                FROM questoes_usuario
                WHERE user_id=? AND proxima_revisao IS NOT NULL
                  AND DATETIME(proxima_revisao) <= DATETIME('now')
                GROUP BY tema
                ORDER BY total DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            return [{"tema": r[0], "total": r[1]} for r in rows]
        finally:
            conn.close()

    def registrar_favorita(self, user_id: int, questao: dict, favorita: bool) -> None:
        """Marca/desmarca questão como favorita."""
        qh = _qhash(questao)
        conn = self.db.conectar()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE questoes_usuario SET favorita=? WHERE user_id=? AND qhash=?",
                (1 if favorita else 0, user_id, qh),
            )
            conn.commit()
        finally:
            conn.close()
