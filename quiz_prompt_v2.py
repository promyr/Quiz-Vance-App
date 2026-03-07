# -*- coding: utf-8 -*-
"""
quiz_prompt_v2.py
Novo prompt de geração de questões para o QuizVance.

COMO USAR:
  Substitua o método `_build_quiz_prompt` (ou equivalente) dentro de
  core/ai_service_v2.py pelo conteúdo abaixo, adaptando os parâmetros
  conforme a assinatura já existente no seu AIService.

  O método `generate_quiz_batch` deve chamar `_build_quiz_prompt` para
  montar a mensagem enviada à API. Nada mais muda na camada de chamada.
"""

import json
import textwrap
from typing import Optional


# ---------------------------------------------------------------------------
# Mapa de dificuldade → instrução de profundidade
# ---------------------------------------------------------------------------
_NIVEL_INSTRUCAO = {
    "facil":        "Nível FÁCIL: conceito central direto; distratores erram um detalhe concreto.",
    "intermediario": "Nível INTERMEDIÁRIO: exija relação causa-efeito ou aplicação de conceito; distratores invertem a lógica.",
    "dificil":      "Nível DIFÍCIL: questão-problema com raciocínio de múltiplas etapas; distratores são conclusões parcialmente corretas.",
}

# Máximo de chars por campo (mantém compatibilidade com o parser da UI)
_MAX_PERGUNTA  = 280
_MAX_OPCAO     = 90
_MAX_EXPLIC    = 190


def _build_quiz_prompt(
    chunks: list[str],
    tema: str,
    dificuldade: str,
    qtd: int,
    pagina: int = 1,
    evitar: Optional[list[str]] = None,
) -> str:
    """
    Monta o prompt completo para geração de questões objetivas.

    Parâmetros
    ----------
    chunks      : linhas/parágrafos do material do usuário
    tema        : título/assunto da sessão (ex.: "Direito Constitucional")
    dificuldade : "facil" | "intermediario" | "dificil"
    qtd         : número de questões a gerar (tipicamente 3–10)
    pagina      : índice de lote (evita repetição entre chamadas consecutivas)
    evitar      : lista de enunciados já gerados nesta sessão

    Retorna
    -------
    str : prompt pronto para enviar como `user` message à API
    """
    nivel_str = _NIVEL_INSTRUCAO.get(
        str(dificuldade).lower(),
        _NIVEL_INSTRUCAO["intermediario"],
    )

    # Prepara o trecho: une chunks, limita a ~6 000 chars para não explodir o contexto
    trecho_raw = "\n".join(str(c).strip() for c in (chunks or []) if str(c).strip())
    trecho = trecho_raw[:6000].strip()
    if not trecho:
        trecho = f"Tema: {tema}. Elabore questões com base em conhecimento técnico consolidado sobre este assunto."

    # Histórico de perguntas a evitar
    historico_block = ""
    if evitar:
        itens = "\n".join(f"- {e}" for e in evitar[:20])
        historico_block = f"\nHISTÓRICO (não recrie estas perguntas):\n{itens}\n"

    # Instruções de variação do correta_index para evitar viés posicional
    indices_esperados = ", ".join(str(i % 4) for i in range(qtd))

    prompt = textwrap.dedent(f"""
    Você é um elaborador sênior de questões para concursos públicos brasileiros de alto nível (CESPE, FCC, VUNESP).

    MATERIAL DE ESTUDO:
    \"\"\"
    {trecho}
    \"\"\"

    TEMA DA SESSÃO: {tema}
    {nivel_str}
    LOTE {pagina} — gere EXATAMENTE {qtd} questão(ões) novas.
    {historico_block}
    REGRAS OBRIGATÓRIAS DE CONTEÚDO:
    1. Use exclusivamente o conteúdo do material acima. Nunca invente fatos externos.
    2. Perguntas autônomas: proibido usar "segundo o texto", "conforme o trecho" ou similar.
    3. Proibido decoreba ("O que é X?", "Qual o nome de..."). Exija raciocínio, comparação ou aplicação.
    4. Ignore metadados do material (autor, ISBN, editora, edição, datas de publicação, sumário).
    5. Cada distrator deve usar um conceito real do material, mas aplicado no contexto errado.
    6. Os valores de "correta_index" ao longo das {qtd} questões devem seguir esta sequência sugerida: [{indices_esperados}] — adapte se necessário, mas não repita o mesmo índice em todas.

    REGRAS DE FORMATO (descumprir = questão descartada pelo parser):
    - "pergunta"   → máx {_MAX_PERGUNTA} caracteres, enunciado técnico e direto
    - "opcoes"     → lista com EXATAMENTE 4 itens; máx {_MAX_OPCAO} chars cada; SEM prefixos "A)", "B)" etc.
    - "correta_index" → inteiro 0–3 indicando qual opção em "opcoes" é a correta
    - "explicacao" → máx {_MAX_EXPLIC} chars; cite o conceito-chave que torna a alternativa correta

    SAÍDA — JSON puro, sem markdown, sem texto antes ou depois:
    [
      {{
        "pergunta": "Enunciado técnico",
        "opcoes": ["Opção correta", "Distrator 1", "Distrator 2", "Distrator 3"],
        "correta_index": 0,
        "explicacao": "Razão objetiva da resposta correta."
      }}
    ]
    """).strip()

    return prompt


# ---------------------------------------------------------------------------
# Validador pós-parse: checa integridade de cada questão antes de retornar
# para a UI. Use no método generate_quiz_batch logo após o json.loads().
# ---------------------------------------------------------------------------

def validate_question(q: dict) -> bool:
    """
    Retorna True se a questão está íntegra o suficiente para exibição.
    Questões inválidas devem ser descartadas silenciosamente (não crashar).
    """
    try:
        pergunta = str(q.get("pergunta") or "").strip()
        opcoes   = q.get("opcoes") or []
        cidx     = q.get("correta_index")
        explicac = str(q.get("explicacao") or "").strip()

        if not pergunta or len(pergunta) > _MAX_PERGUNTA + 40:  # tolera 40 chars extra
            return False
        if not isinstance(opcoes, list) or len(opcoes) != 4:
            return False
        if any(len(str(o)) > _MAX_OPCAO + 20 for o in opcoes):  # tolera 20 chars extra
            return False
        if not isinstance(cidx, int) or not (0 <= cidx <= 3):
            return False
        # Garante que a opção correta não está em branco
        if not str(opcoes[cidx]).strip():
            return False
        return True
    except Exception:
        return False


def sanitize_question(q: dict) -> dict:
    """
    Trunca campos que excedem os limites sem descartar a questão.
    Chame após validate_question retornar True.
    """
    q["pergunta"]  = str(q.get("pergunta") or "")[:_MAX_PERGUNTA]
    q["opcoes"]    = [str(o)[:_MAX_OPCAO] for o in (q.get("opcoes") or [])]
    q["explicacao"] = str(q.get("explicacao") or "")[:_MAX_EXPLIC]
    # Remove prefixos "A) B) C) D)" se o modelo insistir em colocá-los
    import re
    q["opcoes"] = [re.sub(r"^[A-Da-d][).]\s*", "", o).strip() for o in q["opcoes"]]
    return q


# ---------------------------------------------------------------------------
# Exemplo de integração no AIService (pseudocódigo):
#
#   from core.quiz_prompt_v2 import _build_quiz_prompt, validate_question, sanitize_question
#
#   def generate_quiz_batch(self, chunks, tema, dificuldade, qtd, pagina=1, evitar=None):
#       prompt = _build_quiz_prompt(chunks, tema, dificuldade, qtd, pagina, evitar)
#       raw = self.provider.complete(prompt)          # chamada à API
#       try:
#           items = json.loads(raw)
#       except Exception:
#           items = _try_extract_json_list(raw)       # fallback regex
#       result = []
#       for item in (items or []):
#           if validate_question(item):
#               result.append(sanitize_question(item))
#       return result
# ---------------------------------------------------------------------------
