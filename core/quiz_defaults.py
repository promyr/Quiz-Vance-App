# -*- coding: utf-8 -*-
"""Constantes padrão de quiz — movidas do main_v2.py para evitar import circular."""

DEFAULT_QUIZ_QUESTIONS = [
    {
        "enunciado": "O que e aprendizagem espacada",
        "alternativas": [
            "Tecnica de revisar em intervalos crescentes",
            "Estudar tudo de uma vez",
            "Sempre repetir no mesmo intervalo",
            "Ler apenas uma vez",
        ],
        "correta_index": 0,
    },
    {
        "enunciado": "Qual comando git cria um novo branch",
        "alternativas": ["git branch <nome>", "git checkout -f", "git init", "git commit"],
        "correta_index": 0,
    },
    {
        "enunciado": "Em HTTP, qual codigo indica 'Nao Autorizado'",
        "alternativas": ["200", "301", "401", "500"],
        "correta_index": 2,
    },
    {
        "enunciado": "Qual linguagem Python usa para tipagem opcional",
        "alternativas": ["TypeScript", "mypy/typing", "Flow", "Kotlin"],
        "correta_index": 1,
    },
    {
        "enunciado": "Qual estrutura e usada para filas FIFO",
        "alternativas": ["stack", "queue", "tree", "set"],
        "correta_index": 1,
    },
]
