import asyncio
from typing import Callable

import flet as ft

import main_v2
from core.database_v2 import Database
from ui.views.review_session_view_v2 import build_review_session_body


class DummyPage:
    def __init__(self, route: str = "/home", width: int = 1280, height: int = 820):
        self.route = route
        self.width = width
        self.height = height
        self.window_width = width
        self.window_height = height
        self.platform = "windows"
        self.theme_mode = ft.ThemeMode.LIGHT
        self.overlay = []
        self.views = []
        self.dialog = None
        self.snack_bar = None
        self.clipboard = ""

    def update(self):
        return None

    def go(self, route: str):
        self.route = str(route or "/home")

    def set_clipboard(self, text: str):
        self.clipboard = str(text or "")

    def launch_url(self, url: str):
        return bool(url)

    def run_task(self, fn: Callable, *args):
        result = fn(*args)
        if asyncio.iscoroutine(result):
            # Evita "coroutine was never awaited" nos testes de montagem.
            result.close()
        return None


def _make_state(tmp_path, monkeypatch):
    monkeypatch.setenv("QUIZVANCE_DATA_DIR", str(tmp_path))
    db = Database()
    db.iniciar_banco()
    user = db.sync_cloud_user(backend_user_id=12345, email="tester@example.com", nome="Tester")
    assert isinstance(user, dict) and int(user.get("id") or 0) > 0
    page = DummyPage()
    return {
        "usuario": user,
        "db": db,
        "backend": None,
        "sounds": None,
        "tema_escuro": False,
        "view_cache": {},
        "last_theme": False,
        "page": page,
    }


def test_route_builders_smoke_all_routes(tmp_path, monkeypatch):
    state = _make_state(tmp_path, monkeypatch)

    def navigate(_route: str):
        return None

    def on_logout(_=None):
        return None

    def toggle_dark(_=None):
        return None

    routes = [
        ("/home", lambda d: main_v2._build_home_body(state, navigate, d)),
        ("/quiz", lambda d: main_v2._build_quiz_body(state, navigate, d)),
        ("/simulado", lambda d: main_v2._build_quiz_body(state, navigate, d)),
        ("/revisao", lambda d: main_v2._build_revisao_body(state, navigate, d)),
        ("/revisao/sessao", lambda d: build_review_session_body(state, navigate, d, modo="sessao")),
        ("/revisao/erros", lambda d: build_review_session_body(state, navigate, d, modo="erros")),
        ("/revisao/marcadas", lambda d: build_review_session_body(state, navigate, d, modo="marcadas")),
        ("/flashcards", lambda d: main_v2._build_flashcards_body(state, navigate, d)),
        ("/open-quiz", lambda d: main_v2._build_open_quiz_body(state, navigate, d)),
        ("/library", lambda d: main_v2._build_library_body(state, navigate, d)),
        ("/study-plan", lambda d: main_v2._build_study_plan_body(state, navigate, d)),
        ("/stats", lambda d: main_v2._build_stats_body(state, navigate, d)),
        ("/profile", lambda d: main_v2._build_profile_body(state, navigate, d)),
        ("/ranking", lambda d: main_v2._build_ranking_body(state, navigate, d)),
        ("/conquistas", lambda d: main_v2._build_conquistas_body(state, navigate, d)),
        ("/plans", lambda d: main_v2._build_plans_body(state, navigate, d)),
        ("/settings", lambda d: main_v2._build_settings_body(state, navigate, d)),
        ("/mais", lambda d: main_v2._ext_build_mais_body(state, navigate, d, on_logout, toggle_dark)),
    ]

    for dark in (False, True):
        for route, builder in routes:
            state["page"].route = route
            control = builder(dark)
            assert control is not None


def test_quiz_state_persists_across_theme_rebuild(tmp_path, monkeypatch):
    state = _make_state(tmp_path, monkeypatch)
    page = state["page"]
    page.route = "/quiz"
    state["quiz_session"] = {
        "questoes": [
            {"enunciado": "Q1", "alternativas": ["A", "B"], "correta_index": 0},
            {"enunciado": "Q2", "alternativas": ["A", "B"], "correta_index": 1},
        ],
        "estado": {"current_idx": 1, "ui_stage": "study", "respostas": {0: 0}, "confirmados": {0}, "puladas": set()},
    }
    main_v2._build_quiz_body(state, lambda _r: None, False)
    main_v2._build_quiz_body(state, lambda _r: None, True)
    assert len(state["quiz_session"]["questoes"]) == 2
    assert int(state["quiz_session"]["estado"].get("current_idx") or 0) == 1


def test_flashcards_state_persists_across_theme_rebuild(tmp_path, monkeypatch):
    state = _make_state(tmp_path, monkeypatch)
    page = state["page"]
    page.route = "/flashcards"
    state["flashcards_session"] = {
        "flashcards": [{"frente": "F1", "verso": "V1"}, {"frente": "F2", "verso": "V2"}],
        "estado": {
            "current_idx": 1,
            "mostrar_verso": True,
            "lembrei": 2,
            "rever": 1,
            "ui_stage": "study",
            "tema_input": "Teste",
            "referencia_input": "Ref",
            "quantidade_value": "10",
        },
    }
    main_v2._build_flashcards_body(state, lambda _r: None, False)
    main_v2._build_flashcards_body(state, lambda _r: None, True)
    assert len(state["flashcards_session"]["flashcards"]) == 2
    assert int(state["flashcards_session"]["estado"].get("current_idx") or 0) == 1
    assert bool(state["flashcards_session"]["estado"].get("mostrar_verso")) is True


def test_open_quiz_runtime_persists_across_theme_rebuild(tmp_path, monkeypatch):
    state = _make_state(tmp_path, monkeypatch)
    page = state["page"]
    page.route = "/open-quiz"
    state["open_quiz_runtime"] = {
        "tema": "Tema teste",
        "resposta": "Resposta teste",
        "etapa": 2,
        "pergunta": "Pergunta teste",
        "gabarito": "Gabarito teste",
        "contexto_gerado": "Contexto teste",
    }
    main_v2._build_open_quiz_body(state, lambda _r: None, False)
    main_v2._build_open_quiz_body(state, lambda _r: None, True)
    runtime = state.get("open_quiz_runtime") or {}
    assert str(runtime.get("tema") or "").strip() == "Tema teste"
    assert int(runtime.get("etapa") or 0) == 2
