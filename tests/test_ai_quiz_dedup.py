# -*- coding: utf-8 -*-

from core.ai_service_v2 import AIProvider, AIService


class _DummyProvider(AIProvider):
    def __init__(self):
        super().__init__(api_key="dummy", model="dummy")

    def generate_text(self, prompt: str):
        return None

    def extract_json_object(self, text):
        return None

    def extract_json_list(self, text):
        return None


def _q(pergunta: str, correta: str, distractor: str = "Distrator") -> dict:
    return {
        "pergunta": pergunta,
        "opcoes": [
            f"A. {distractor} 1",
            f"B. {correta}",
            f"C. {distractor} 2",
            f"D. {distractor} 3",
        ],
        "correta_index": 1,
        "explicacao": "ok",
    }


def test_normalize_quiz_batch_payload_reduces_rephrased_duplicates():
    service = AIService(_DummyProvider())
    raw = [
        _q(
            "Sobre a relevancia economica da Amazonia Azul para o comercio exterior, o texto afirma que:",
            "Aproximadamente 95% do comercio exterior brasileiro ocorre por via maritima.",
        ),
        _q(
            "Sobre a importancia economica da Amazonia Azul para o comercio exterior brasileiro, o texto destaca que:",
            "O transporte maritimo responde por cerca de 95% das exportacoes e importacoes.",
        ),
        _q(
            "Qual foi a alteracao significativa na extensao da Amazonia Azul consolidada em 2025?",
            "Reconhecimento da ampliacao da plataforma continental na Margem Equatorial.",
        ),
        _q(
            "Qual foi o impacto do reconhecimento da ONU, em 2025, para a dimensao da Amazonia Azul?",
            "Ampliacao da plataforma continental na Margem Equatorial em cerca de 360 mil km2.",
        ),
        _q(
            "Qual aspecto ambiental reforca a importancia da Amazonia Azul?",
            "Biodiversidade marinha com recifes e manguezais relevantes ao clima.",
        ),
        _q(
            "Qual a relevancia energetica da Amazonia Azul para o Brasil?",
            "Reservas no leito marinho sustentam grande parte da producao de petroleo e gas.",
        ),
    ]
    out = service._normalize_quiz_batch_payload(raw, limit=10)
    assert len(out) <= 4


def test_normalize_quiz_batch_payload_limits_repeated_numeric_facts():
    service = AIService(_DummyProvider())
    raw = [
        _q("No texto, qual percentual do comercio exterior ocorre por mar?", "95% do comercio exterior ocorre por transporte maritimo."),
        _q("Segundo o material, qual percentual das exportacoes depende do transporte maritimo?", "Cerca de 95% das exportacoes e importacoes dependem do modal maritimo."),
        _q("Qual numero representa a participacao do modal maritimo no comercio exterior brasileiro?", "95% de participacao no comercio exterior."),
        _q("Qual dado percentual sintetiza a relevancia maritima no comercio exterior?", "Participacao de 95% no fluxo de comercio exterior."),
    ]
    out = service._normalize_quiz_batch_payload(raw, limit=10)
    assert len(out) <= 1


def test_normalize_quiz_batch_payload_blocks_semantic_rephrase_same_concept():
    service = AIService(_DummyProvider())
    raw = [
        _q(
            "No material, qual o papel da Amazonia Azul no comercio exterior brasileiro?",
            "O transporte maritimo sustenta a maior parcela das exportacoes e importacoes do pais.",
        ),
        _q(
            "Segundo o texto, por que a Amazonia Azul e estrategica para a balanca comercial do Brasil?",
            "As rotas maritimas concentram grande parte do fluxo comercial externo brasileiro.",
        ),
        _q(
            "Qual aspecto ambiental reforca a relevancia da Amazonia Azul?",
            "A biodiversidade marinha inclui recifes e manguezais importantes para o equilibrio climatico.",
        ),
    ]
    out = service._normalize_quiz_batch_payload(raw, limit=10)
    assert len(out) <= 2


def test_normalize_quiz_batch_payload_limits_repeated_question_template():
    service = AIService(_DummyProvider())
    raw = [
        _q(
            "Qual e o papel da Amazonia Azul na economia brasileira?",
            "Sustenta parcela relevante das exportacoes e importacoes por transporte maritimo.",
        ),
        _q(
            "Qual e o papel da Amazonia Azul para a soberania nacional?",
            "Consolida presenca estrategica e jurisdicao maritima do Brasil.",
        ),
        _q(
            "Qual e o papel da Amazonia Azul na protecao ambiental costeira?",
            "Abriga biodiversidade sensivel e regula processos climaticos marinhos.",
        ),
        _q(
            "Como o reconhecimento internacional da plataforma continental impacta o Brasil?",
            "Amplia a area sob jurisdicao e reforca planejamento estrategico nacional.",
        ),
    ]
    out = service._normalize_quiz_batch_payload(raw, limit=10)
    papel_count = sum(1 for q in out if str(q.get("pergunta", "")).lower().startswith("qual e o papel"))
    assert papel_count <= 1


def test_normalize_quiz_batch_payload_limits_topic_bucket_concentration():
    service = AIService(_DummyProvider())
    raw = [
        _q(
            "Qual e a importancia economica da Amazonia Azul para o comercio exterior?",
            "A maior parte do fluxo exportador usa rotas maritimas conectadas a portos nacionais.",
        ),
        _q(
            "Sobre o comercio exterior brasileiro, qual papel da Amazonia Azul?",
            "Corredores maritimos reduzem custo logistico e sustentam cadeia de suprimentos internacional.",
        ),
        _q(
            "Qual fator economico reforca o valor da Amazonia Azul para o Brasil?",
            "Movimentacao portuaria maritima gera receita e competitividade para setores produtivos.",
        ),
        _q(
            "Como a biodiversidade da Amazonia Azul contribui para o equilibrio ambiental?",
            "Ecossistemas marinhos como recifes e manguezais ajudam na regulacao climatica.",
        ),
        _q(
            "Qual elemento energetico destaca a relevancia da Amazonia Azul?",
            "Reservas marinhas sustentam parte expressiva da producao nacional de petroleo e gas.",
        ),
    ]
    out = service._normalize_quiz_batch_payload(raw, limit=10)
    economia_count = sum(
        1
        for q in out
        if any(token in str(q.get("pergunta", "")).lower() for token in ("econom", "comerc", "export", "import"))
    )
    assert economia_count <= 2


def test_is_metadata_question_detects_editorial_classification_patterns():
    service = AIService(_DummyProvider())
    assert service._is_metadata_question(
        "A publicacao 'Mentalidade Maritima' se classifica, de acordo com o EMA - 411, como uma publicacao:"
    )
    assert service._is_metadata_question(
        "O objetivo central da publicacao 'Mentalidade Maritima', conforme sua introducao, e:"
    )


def test_is_metadata_question_keeps_content_question():
    service = AIService(_DummyProvider())
    assert not service._is_metadata_question(
        "Como a biodiversidade marinha da Amazonia Azul contribui para o equilibrio ambiental brasileiro?"
    )
