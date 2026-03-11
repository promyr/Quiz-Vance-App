# -*- coding: utf-8 -*-
"""
Testes automatizados do Quiz Vance
"""

from config import CORES, AI_PROVIDERS, DIFICULDADES, NIVEIS, get_level_info
from quiz_prompt_v2 import sanitize_question


# ---------------------------------------------------------------------------
# Smoke: configuracoes basicas
# ---------------------------------------------------------------------------

def test_cores_basicas():
    """Paleta basica de cores deve estar presente."""
    required = ["fundo", "card", "texto", "primaria", "acento", "erro", "sucesso", "warning"]
    for key in required:
        assert key in CORES, f"Cor ausente: {key}"


def test_cores_dark_mode():
    """Versoes dark de cores criticas devem estar presentes."""
    dark_keys = ["fundo_escuro", "card_escuro", "texto_escuro", "texto_sec_escuro"]
    for key in dark_keys:
        assert key in CORES, f"Cor dark ausente: {key}"


# ---------------------------------------------------------------------------
# get_level_info
# ---------------------------------------------------------------------------

def test_level_info_bronze_inicio():
    info = get_level_info(0)
    assert info["atual"]["nome"] == "Bronze"
    assert 0.0 <= info["progresso"] <= 1.0
    assert info["proximo"] is not None


def test_level_info_prata():
    info = get_level_info(600)
    assert info["atual"]["nome"] == "Prata"
    assert info["proximo"]["nome"] == "Ouro"
    assert 0.0 <= info["progresso"] <= 1.0


def test_level_info_diamante_max():
    info = get_level_info(999_999)
    assert info["atual"]["nome"] == "Diamante"
    assert info["proximo"] is None
    assert info["progresso"] == 1.0
    assert info["xp_necessario"] == 0


def test_level_info_progresso_clamped():
    """Progresso nunca deve sair do intervalo [0, 1]."""
    for xp in [0, 1, 499, 500, 501, 2000, 5000, 10000, 10001, 100_000]:
        info = get_level_info(xp)
        assert 0.0 <= info["progresso"] <= 1.0, f"Progresso fora do range para xp={xp}"


def test_level_info_todos_niveis():
    """Cada nivel deve ser alcancavel."""
    pontos = [0, 600, 2500, 6000, 12000]
    nomes = ["Bronze", "Prata", "Ouro", "Platina", "Diamante"]
    for xp, nome in zip(pontos, nomes):
        info = get_level_info(xp)
        assert info["atual"]["nome"] == nome, f"Esperado {nome} para xp={xp}, obtido {info['atual']['nome']}"


# ---------------------------------------------------------------------------
# AI_PROVIDERS
# ---------------------------------------------------------------------------

def test_ai_providers_estrutura():
    """Todos os providers devem ter campos obrigatorios."""
    required_fields = ["name", "models", "default_model", "icon", "color"]
    for provider, data in AI_PROVIDERS.items():
        for field in required_fields:
            assert field in data, f"Provider '{provider}' sem campo '{field}'"


def test_ai_providers_default_model_valido():
    """O default_model de cada provider deve estar na lista de modelos."""
    for provider, data in AI_PROVIDERS.items():
        default = data["default_model"]
        assert default in data["models"], (
            f"Provider '{provider}': default_model '{default}' nao esta em models={data['models']}"
        )


def test_ai_providers_sem_modelos_fantasma():
    """Nenhum modelo deve conter sufixos claramente ficticios."""
    ficticios = ["5.2-chat", "5.1-chat", "5-chat", "gpt-5-mini", "gpt-5-nano", "gemini-3-"]
    for provider, data in AI_PROVIDERS.items():
        for model in data["models"]:
            for frag in ficticios:
                assert frag not in model, (
                    f"Provider '{provider}' contem modelo suspeito/inexistente: '{model}'"
                )


def test_ai_providers_tem_gemini_openai_groq():
    """Os tres providers esperados devem estar presentes."""
    for p in ("gemini", "openai", "groq"):
        assert p in AI_PROVIDERS, f"Provider ausente: {p}"


# ---------------------------------------------------------------------------
# DIFICULDADES
# ---------------------------------------------------------------------------

def test_dificuldades_campos():
    """Cada dificuldade deve ter nome, xp e cor."""
    for nivel, data in DIFICULDADES.items():
        assert "nome" in data, f"Dificuldade '{nivel}' sem 'nome'"
        assert "xp" in data, f"Dificuldade '{nivel}' sem 'xp'"
        assert "cor" in data, f"Dificuldade '{nivel}' sem 'cor'"
        assert isinstance(data["xp"], int) and data["xp"] > 0, f"XP invalido para '{nivel}'"


def test_dificuldades_xp_crescente():
    """XP das dificuldades deve ser crescente: iniciante < intermediario < avancado < mestre."""
    ordem = ["iniciante", "intermediario", "avancado", "mestre"]
    xps = [DIFICULDADES[d]["xp"] for d in ordem if d in DIFICULDADES]
    assert xps == sorted(xps), f"XP das dificuldades nao e crescente: {xps}"


# ---------------------------------------------------------------------------
# NIVEIS
# ---------------------------------------------------------------------------

def test_niveis_sem_gaps():
    """Os niveis nao devem ter lacunas no intervalo de XP."""
    sorted_niveis = sorted(NIVEIS.values(), key=lambda x: x["xp_min"])
    for i in range(len(sorted_niveis) - 1):
        atual = sorted_niveis[i]
        proximo = sorted_niveis[i + 1]
        assert atual["xp_max"] + 1 == proximo["xp_min"], (
            f"Lacuna entre '{atual['nome']}' (max={atual['xp_max']}) "
            f"e '{proximo['nome']}' (min={proximo['xp_min']})"
        )


def test_nivel_maximo_infinito():
    """O nivel mais alto deve ter xp_max == inf."""
    import math
    maximos = [data for data in NIVEIS.values() if math.isinf(data["xp_max"])]
    assert len(maximos) == 1, "Deve haver exatamente um nivel com xp_max infinito"


def test_sanitize_question_nao_corta_opcao_longa():
    """Alternativas longas devem ser preservadas integralmente."""
    opcao_longa = (
        "Alternativa extensa com descricao detalhada, incluindo excecoes, condicionantes, "
        "contexto normativo e consequencias praticas para validar que nao existe corte artificial."
    )
    sanitized = sanitize_question(
        {
            "pergunta": "Qual alternativa descreve corretamente o caso?",
            "subtema": "Teste",
            "opcoes": [
                opcao_longa,
                "Opcao 2",
                "Opcao 3",
                "Opcao 4",
            ],
            "correta_index": 0,
            "explicacao": "Explicacao curta.",
        }
    )
    assert sanitized["opcoes"][0] == opcao_longa
