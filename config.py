# -*- coding: utf-8 -*-
"""
Configuracoes do Quiz Vance
"""

import os

CORES = {
    "primaria": "#6366F1",
    "primaria_escura": "#4F46E5",
    "primaria_clara": "#818CF8",
    "acento": "#10B981",
    "acento_escura": "#059669",
    "acento_clara": "#34D399",
    "fundo": "#F9FAFB",
    "fundo_escuro": "#161616",
    "card": "#FFFFFF",
    "card_escuro": "#232323",
    "texto": "#111827",
    "texto_escuro": "#F3F4F6",
    "texto_sec": "#6B7280",
    "texto_sec_escuro": "#B3B3B3",
    "erro": "#EF4444",
    "sucesso": "#10B981",
    "warning": "#F59E0B",
    "info": "#3B82F6",
    "bronze": "#CD7F32",
    "prata": "#C0C0C0",
    "ouro": "#FFD700",
    "diamante": "#B9F2FF",
    "mestre": "#A855F7",
    "platina": "#E5E7EB",
}

AI_PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
        ],
        "default_model": "gemini-2.5-flash",
        "icon": "g_translate",
        "color": "#4285F4",
    },
    "openai": {
        "name": "OpenAI GPT",
        "models": [
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4o",
            "gpt-4o-mini",
        ],
        "default_model": "gpt-4.1-mini",
        "icon": "psychology",
        "color": "#10A37F",
    },
    "groq": {
        "name": "Groq",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen-qwq-32b",
            "deepseek-r1-distill-llama-70b",
        ],
        "default_model": "llama-3.3-70b-versatile",
        "icon": "bolt",
        "color": "#F55036",
    },
}

GOOGLE_OAUTH = {
    "enabled": bool(os.getenv("GOOGLE_OAUTH_ENABLED", "").strip().lower() in ("1", "true", "yes")),
    "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
    "redirect_uri": os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8550/auth/callback"),
    "scopes": [
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
}

NIVEIS = {
    "Bronze": {"xp_min": 0, "xp_max": 500, "nome": "Bronze", "cor": "bronze"},
    "Prata": {"xp_min": 501, "xp_max": 2000, "nome": "Prata", "cor": "prata"},
    "Ouro": {"xp_min": 2001, "xp_max": 5000, "nome": "Ouro", "cor": "ouro"},
    "Platina": {"xp_min": 5001, "xp_max": 10000, "nome": "Platina", "cor": "platina"},
    "Diamante": {"xp_min": 10001, "xp_max": float("inf"), "nome": "Diamante", "cor": "diamante"},
}

def get_level_info(xp: int):
    """Retorna info do nivel atual com base no XP."""
    nivel_atual = None
    proximo_nivel = None
    
    # Encontrar nivel atual
    for key, data in NIVEIS.items():
        if data["xp_min"] <= xp <= data["xp_max"]:
            nivel_atual = data
            break
            
    # Fallback se nao encontrar (devia ser impossivel com inf)
    if not nivel_atual:
        nivel_atual = NIVEIS["Diamante"]
        
    # Encontrar proximo nivel
    sorted_levels = sorted(NIVEIS.values(), key=lambda x: x["xp_min"])
    current_idx = sorted_levels.index(nivel_atual)
    
    if current_idx < len(sorted_levels) - 1:
        proximo_nivel = sorted_levels[current_idx + 1]
        xp_necessario = proximo_nivel["xp_min"] - xp
        progresso = (xp - nivel_atual["xp_min"]) / (nivel_atual["xp_max"] - nivel_atual["xp_min"])
    else:
        # Nivel maximo
        proximo_nivel = None
        xp_necessario = 0
        progresso = 1.0
        
    return {
        "atual": nivel_atual,
        "proximo": proximo_nivel,
        "xp_necessario": xp_necessario,
        "progresso": max(0.0, min(1.0, progresso))
    }

CONQUISTAS = [
    {
        "codigo": "primeira_questao",
        "titulo": "Primeira Questao",
        "descricao": "Complete sua primeira questao",
        "icone": "flag",
        "xp_bonus": 50,
        "criterio_tipo": "total_questoes",
        "criterio_valor": 1,
    },
    {
        "codigo": "10_questoes",
        "titulo": "Iniciante",
        "descricao": "Complete 10 questoes",
        "icone": "emoji_events",
        "xp_bonus": 100,
        "criterio_tipo": "total_questoes",
        "criterio_valor": 10,
    },
    {
        "codigo": "50_questoes",
        "titulo": "Estudante",
        "descricao": "Complete 50 questoes",
        "icone": "school",
        "xp_bonus": 250,
        "criterio_tipo": "total_questoes",
        "criterio_valor": 50,
    },
    {
        "codigo": "100_questoes",
        "titulo": "Dedicado",
        "descricao": "Complete 100 questoes",
        "icone": "workspace_premium",
        "xp_bonus": 500,
        "criterio_tipo": "total_questoes",
        "criterio_valor": 100,
    },
    {
        "codigo": "streak_3",
        "titulo": "Consistente",
        "descricao": "Mantenha uma sequencia de 3 dias",
        "icone": "local_fire_department",
        "xp_bonus": 150,
        "criterio_tipo": "streak",
        "criterio_valor": 3,
    },
    {
        "codigo": "streak_7",
        "titulo": "Comprometido",
        "descricao": "Mantenha uma sequencia de 7 dias",
        "icone": "whatshot",
        "xp_bonus": 350,
        "criterio_tipo": "streak",
        "criterio_valor": 7,
    },
    {
        "codigo": "nivel_mestre",
        "titulo": "Mestre Supremo",
        "descricao": "Alcance o nivel Mestre",
        "icone": "stars",
        "xp_bonus": 1000,
        "criterio_tipo": "nivel",
        "criterio_valor": "diamante",
    },
]

DIFICULDADES = {
    "iniciante": {"nome": "Iniciante", "xp": 30, "cor": "#10B981"},
    "intermediario": {"nome": "Intermediario", "xp": 50, "cor": "#F59E0B"},
    "avancado": {"nome": "Avancado", "xp": 80, "cor": "#EF4444"},
    "mestre": {"nome": "Mestre", "xp": 120, "cor": "#A855F7"},
}

CATEGORIAS = [
    "Geral",
    "Direito",
    "Concursos",
    "TI",
    "Medicina",
    "Engenharia",
    "Administracao",
    "Marketing",
    "Idiomas",
    "Matematica",
    "Historia",
    "Geografia",
]



