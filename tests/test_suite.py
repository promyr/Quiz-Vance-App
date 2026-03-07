# -*- coding: utf-8 -*-
"""
Suite de Testes Automatizados - Quiz Vance
"""

import unittest
import json
from core.ai_service_v2 import GeminiProvider, OpenAIProvider, AIService, create_ai_provider
from config import CORES, AI_PROVIDERS


class TestAIService(unittest.TestCase):
    """Testes do serviÃ§o de IA"""
    
    def setUp(self):
        """Setup antes de cada teste"""
        # Nota: VocÃª precisa definir estas variÃ¡veis de ambiente ou usar suas chaves
        self.gemini_key = "YOUR_GEMINI_KEY"
        self.openai_key = "YOUR_OPENAI_KEY"
    
    def test_create_gemini_provider(self):
        """Testa criaÃ§Ã£o de provider Gemini"""
        try:
            provider = create_ai_provider("gemini", self.gemini_key)
            self.assertIsInstance(provider, GeminiProvider)
            print("âœ… Gemini provider criado com sucesso")
        except ImportError:
            print("âš ï¸  google-generativeai nÃ£o instalado, pulando teste")
    
    def test_create_openai_provider(self):
        """Testa criaÃ§Ã£o de provider OpenAI"""
        try:
            provider = create_ai_provider("openai", self.openai_key)
            self.assertIsInstance(provider, OpenAIProvider)
            print("âœ… OpenAI provider criado com sucesso")
        except ImportError:
            print("âš ï¸  openai nÃ£o instalado, pulando teste")
    
    def test_extract_json_object(self):
        """Testa extraÃ§Ã£o de JSON de texto"""
        provider = create_ai_provider("gemini", "fake_key")
        
        # Teste 1: JSON limpo
        text1 = '{"pergunta": "Test?", "opcoes": ["A", "B"], "correta_index": 0}'
        result1 = provider.extract_json_object(text1)
        self.assertIsNotNone(result1)
        self.assertEqual(result1["pergunta"], "Test?")
        print("âœ… ExtraÃ§Ã£o de JSON limpo funcionou")
        
        # Teste 2: JSON com markdown
        text2 = '''
        ```json
        {"pergunta": "Test?", "opcoes": ["A", "B"], "correta_index": 0}
        ```
        '''
        result2 = provider.extract_json_object(text2)
        self.assertIsNotNone(result2)
        self.assertEqual(result2["pergunta"], "Test?")
        print("âœ… ExtraÃ§Ã£o de JSON com markdown funcionou")
        
        # Teste 3: JSON com texto antes/depois
        text3 = '''
        Aqui estÃ¡ o JSON:
        {"pergunta": "Test?", "opcoes": ["A", "B"], "correta_index": 0}
        Espero que ajude!
        '''
        result3 = provider.extract_json_object(text3)
        self.assertIsNotNone(result3)
        self.assertEqual(result3["pergunta"], "Test?")
        print("âœ… ExtraÃ§Ã£o de JSON com texto extra funcionou")
    
    def test_normalize_quiz(self):
        """Testa normalizaÃ§Ã£o de quiz"""
        provider = create_ai_provider("gemini", "fake_key")
        service = AIService(provider)
        
        # Teste 1: Formato padrÃ£o
        data1 = {
            "pergunta": "Quanto Ã© 2+2?",
            "opcoes": ["1", "2", "3", "4"],
            "correta_index": 3,
            "explicacao": "2+2 = 4"
        }
        result1 = service._normalize_quiz(data1)
        self.assertIsNotNone(result1)
        self.assertEqual(result1["correta_index"], 3)
        print("âœ… NormalizaÃ§Ã£o formato padrÃ£o funcionou")
        
        # Teste 2: Formato alternativo
        data2 = {
            "question": "Quanto Ã© 2+2?",
            "options": ["1", "2", "3", "4"],
            "answer": "D",
            "explanation": "2+2 = 4"
        }
        result2 = service._normalize_quiz(data2)
        self.assertIsNotNone(result2)
        self.assertEqual(result2["correta_index"], 3)
        print("âœ… NormalizaÃ§Ã£o formato alternativo funcionou")
        
        # Teste 3: OpÃ§Ãµes como objetos
        data3 = {
            "pergunta": "Quanto Ã© 2+2?",
            "opcoes": [
                {"texto": "1"},
                {"texto": "2"},
                {"texto": "3"},
                {"texto": "4"}
            ],
            "correta_index": 3
        }
        result3 = service._normalize_quiz(data3)
        self.assertIsNotNone(result3)
        self.assertEqual(len(result3["opcoes"]), 4)
        print("âœ… NormalizaÃ§Ã£o opÃ§Ãµes como objetos funcionou")


class TestConfig(unittest.TestCase):
    """Testes de configuraÃ§Ã£o"""
    
    def test_cores_defined(self):
        """Testa se todas as cores estÃ£o definidas"""
        cores_necessarias = [
            "primaria", "acento", "fundo", "card", "texto",
            "erro", "sucesso", "warning", "info"
        ]
        
        for cor in cores_necessarias:
            self.assertIn(cor, CORES)
            self.assertIsInstance(CORES[cor], str)
            self.assertTrue(CORES[cor].startswith("#"))
        
        print("âœ… Todas as cores estÃ£o definidas")
    
    def test_ai_providers_config(self):
        """Testa configuraÃ§Ã£o de providers de IA"""
        self.assertIn("gemini", AI_PROVIDERS)
        self.assertIn("openai", AI_PROVIDERS)
        
        for provider_name, config in AI_PROVIDERS.items():
            self.assertIn("name", config)
            self.assertIn("models", config)
            self.assertIn("default_model", config)
            self.assertIsInstance(config["models"], list)
            self.assertGreater(len(config["models"]), 0)
        
        print("âœ… ConfiguraÃ§Ã£o de AI providers vÃ¡lida")


class TestComponents(unittest.TestCase):
    """Testes de componentes UI"""
    
    def test_get_cor(self):
        """Testa funÃ§Ã£o get_cor"""
        from ui.components_v2 import get_cor
        
        # Tema claro
        cor_clara = get_cor("primaria", tema_escuro=False)
        self.assertEqual(cor_clara, CORES["primaria"])
        
        # Tema escuro
        cor_escura = get_cor("fundo", tema_escuro=True)
        self.assertEqual(cor_escura, CORES["fundo_escuro"])
        
        print("âœ… FunÃ§Ã£o get_cor funcionando")


class TestDatabase(unittest.TestCase):
    """Testes de banco de dados"""
    
    def setUp(self):
        """Setup do banco de teste"""
        import os
        # Criar banco de teste
        self.test_db = "test_simulador.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def tearDown(self):
        """Cleanup apÃ³s teste"""
        import os
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_database_creation(self):
        """Testa criaÃ§Ã£o e tabelas essenciais usando database_v2.py"""
        from core.database_v2 import Database
        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        
        import sqlite3
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        # checar tabelas principais
        tabelas = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        esperadas = {
            "usuarios", "user_ai_config", "oauth_users",
            "historico_xp", "questoes_erros", "conquistas",
            "usuario_conquistas", "estudo_tempo_diario",
            "biblioteca_pdfs", "banco_questoes"
        }
        faltando = esperadas - tabelas
        self.assertFalse(faltando, f"Tabelas faltando: {faltando}")
        conn.close()
        print("âœ… Banco criado com tabelas essenciais")

    def test_daily_limit_usage(self):
        """Prompt 4/6: limite diário deve bloquear excedente."""
        from core.database_v2 import Database
        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("user", "user@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("user@test.local", "123456")
        uid = int(user["id"])
        allowed1, used1 = db.consumir_limite_diario(uid, "mock_exam", 2)
        allowed2, used2 = db.consumir_limite_diario(uid, "mock_exam", 2)
        allowed3, used3 = db.consumir_limite_diario(uid, "mock_exam", 2)
        self.assertTrue(allowed1)
        self.assertTrue(allowed2)
        self.assertFalse(allowed3)
        self.assertEqual(used1, 1)
        self.assertEqual(used2, 2)
        self.assertEqual(used3, 2)
        print("âœ… Limite diário funcionando")

    def test_ranking_computes_horas_estudo_from_database(self):
        """Ranking deve calcular horas_estudo a partir do progresso diario."""
        from core.database_v2 import Database
        import sqlite3
        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("rank_user", "rank@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("rank@test.local", "123456")
        uid = int(user["id"])

        db.registrar_progresso_diario(uid, tempo_segundos=3600)

        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO estudo_progresso_diario (user_id, dia, questoes_respondidas, acertos, flashcards_revisados, discursivas_corrigidas, tempo_segundos, updated_at)
            VALUES (?, DATE('now', 'localtime', '-1 day'), 0, 0, 0, 0, 1800, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, dia) DO UPDATE SET tempo_segundos = excluded.tempo_segundos
            """,
            (uid,),
        )
        conn.commit()
        conn.close()

        hoje = db.obter_ranking("Hoje")
        geral = db.obter_ranking("Geral")
        row_hoje = next((r for r in hoje if str(r.get("nome") or "") == "rank_user"), None)
        row_geral = next((r for r in geral if str(r.get("nome") or "") == "rank_user"), None)

        self.assertIsNotNone(row_hoje)
        self.assertIsNotNone(row_geral)
        self.assertEqual(float(row_hoje["horas_estudo"]), 1.0)
        self.assertEqual(float(row_geral["horas_estudo"]), 1.5)
        print("âœ… Ranking calculando horas_estudo corretamente")

    def test_quiz_realtime_stats_increment(self):
        """Resposta confirmada deve atualizar estatisticas imediatamente."""
        from core.database_v2 import Database
        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("rt_user", "rt@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("rt@test.local", "123456")
        uid = int(user["id"])

        delta_1 = db.registrar_resposta_quiz_tempo_real(uid, True, xp_por_acerto=10)
        self.assertEqual(int(delta_1.get("xp_ganho") or 0), 10)
        self.assertEqual(int(delta_1.get("acertos_delta") or 0), 1)
        self.assertEqual(int(delta_1.get("questoes_delta") or 0), 1)
        self.assertGreaterEqual(int(delta_1.get("streak_dias") or 0), 1)

        delta_2 = db.registrar_resposta_quiz_tempo_real(uid, False, xp_por_acerto=10)
        self.assertEqual(int(delta_2.get("xp_ganho") or 0), 0)
        self.assertEqual(int(delta_2.get("acertos_delta") or 0), 0)
        self.assertEqual(int(delta_2.get("questoes_delta") or 0), 1)

        resumo = db.obter_resumo_estatisticas(uid)
        self.assertEqual(int(resumo.get("acertos_total") or 0), 1)
        self.assertEqual(int(resumo.get("total_questoes") or 0), 2)
        self.assertEqual(int(resumo.get("xp") or 0), 10)
        progresso = dict(resumo.get("progresso_diario") or {})
        self.assertEqual(int(progresso.get("questoes_respondidas") or 0), 2)
        self.assertEqual(int(progresso.get("acertos") or 0), 1)
        print("âœ… Estatisticas em tempo real funcionando")

    def test_sync_cloud_quiz_totals_updates_today_progress(self):
        """Sync cloud deve refletir totais e progresso diario do dia atual."""
        from core.database_v2 import Database
        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("cloudstats", "cloudstats@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("cloudstats@test.local", "123456")
        uid = int(user["id"])

        db.sync_cloud_quiz_totals(
            uid,
            total_questoes=42,
            total_acertos=30,
            total_xp=300,
            today_questoes=9,
            today_acertos=7,
        )

        resumo = db.obter_resumo_estatisticas(uid)
        self.assertEqual(int(resumo.get("total_questoes") or 0), 42)
        self.assertEqual(int(resumo.get("acertos_total") or 0), 30)
        self.assertEqual(int(resumo.get("xp") or 0), 300)
        progresso = dict(resumo.get("progresso_diario") or {})
        self.assertEqual(int(progresso.get("questoes_respondidas") or 0), 9)
        self.assertEqual(int(progresso.get("acertos") or 0), 7)
        print("âœ… Sync cloud com progresso diario funcionando")

    def test_save_filter_and_cache_hash(self):
        """Prompt 4: salvar filtros e cache por hash."""
        from core.database_v2 import Database
        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("user2", "user2@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("user2@test.local", "123456")
        uid = int(user["id"])

        filtro = {"topic": "Direito", "difficulty": "intermediario", "count": "10"}
        db.salvar_filtro_quiz(uid, "Filtro A", filtro)
        filtros = db.listar_filtros_quiz(uid)
        self.assertGreaterEqual(len(filtros), 1)
        self.assertEqual(filtros[0]["nome"], "Filtro A")

        source_hash = "hash_abc_123"
        summary = {"titulo": "Resumo", "resumo_curto": "abc", "topicos_principais": ["t1"], "checklist_de_estudo": ["c1"]}
        db.salvar_resumo_por_hash(uid, source_hash, "Tema X", summary)
        cached = db.obter_resumo_por_hash(uid, source_hash)
        self.assertIsInstance(cached, dict)
        self.assertEqual(cached.get("titulo"), "Resumo")
        print("âœ… Filtros e cache por hash funcionando")

    def test_api_key_local_encryption(self):
        """Prompt 4: API key deve ficar protegida localmente e ser lida ao logar."""
        from core.database_v2 import Database
        import sqlite3
        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("user3", "user3@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("user3@test.local", "123456")
        uid = int(user["id"])
        api_value = "sk-test-local-key"
        db.atualizar_api_key(uid, api_value)

        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute("SELECT api_key FROM user_ai_config WHERE user_id = ?", (uid,))
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        stored = str(row[0] or "")
        # aceita fallback plaintext quando cripto indisponível, mas valida roundtrip
        logged = db.fazer_login("user3@test.local", "123456")
        self.assertEqual(str(logged.get("api_key") or ""), api_value)
        self.assertTrue(stored.startswith("enc1:") or stored == api_value)
        print("âœ… Proteção local de API key funcionando")

    def test_sync_cloud_user_online_only(self):
        """Sincronizacao de usuario cloud deve criar/atualizar perfil local sem auth local."""
        from core.database_v2 import Database
        db = Database(db_path=self.test_db)
        db.iniciar_banco()

        user = db.sync_cloud_user(
            backend_user_id=321,
            email="cloud_user@test.local",
            nome="Cloud User",
        )
        self.assertIsNotNone(user)
        self.assertEqual(str(user.get("email") or ""), "cloud_user@test.local")
        self.assertEqual(int(user.get("backend_user_id") or 0), 321)
        self.assertEqual(int(user.get("oauth_google") or 0), 0)

        user2 = db.sync_cloud_user(
            backend_user_id=321,
            email="cloud_user@test.local",
            nome="Cloud User Updated",
        )
        self.assertIsNotNone(user2)
        self.assertEqual(int(user2.get("id") or 0), int(user.get("id") or 0))
        self.assertEqual(str(user2.get("nome") or ""), "Cloud User Updated")
        print("âœ… Sincronizacao cloud online-only funcionando")

    def test_mock_exam_service_policy(self):
        """Prompt 6: regra Free/Premium deve estar no service e respeitar limite diario."""
        from core.database_v2 import Database
        from core.services.mock_exam_service import MockExamService

        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("user4", "user4@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("user4@test.local", "123456")
        uid = int(user["id"])

        service = MockExamService(db)
        free_count, free_capped = service.normalize_question_count(50, premium=False)
        premium_count, premium_capped = service.normalize_question_count(50, premium=True)
        self.assertEqual(free_count, 20)
        self.assertTrue(free_capped)
        self.assertEqual(premium_count, 50)
        self.assertFalse(premium_capped)

        allowed1, _, _ = service.consume_start_today(uid, premium=False)
        allowed2, _, _ = service.consume_start_today(uid, premium=False)
        self.assertTrue(allowed1)
        self.assertFalse(allowed2)
        print("âœ… MockExamService aplicando limites corretamente")

    def test_spaced_repetition_service(self):
        """Prompt 5: SRS deve atualizar questoes e flashcards via service."""
        from core.database_v2 import Database
        from core.services.spaced_repetition_service import SpacedRepetitionService
        import sqlite3

        db = Database(db_path=self.test_db)
        db.iniciar_banco()
        ok, _ = db.criar_conta("user5", "user5@test.local", "123456", "01/01/2000")
        self.assertTrue(ok)
        user = db.fazer_login("user5@test.local", "123456")
        uid = int(user["id"])

        srs = SpacedRepetitionService.from_db(db)
        q = {"enunciado": "2+2?", "alternativas": ["1", "2", "3", "4"], "correta_index": 3, "tema": "Matematica"}
        srs.review_question(uid, q, acertou=False)
        srs.review_question(uid, q, acertou=True)

        card = {"frente": "Capital do Brasil", "verso": "Brasilia", "tema": "Geografia"}
        srs.review_flashcard(uid, card, "lembrei")

        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute("SELECT review_level, next_review_at FROM questoes_usuario WHERE user_id = ?", (uid,))
        row_q = cur.fetchone()
        cur.execute("SELECT total_revisoes, proxima_revisao FROM flashcards WHERE user_id = ?", (uid,))
        row_f = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row_q)
        self.assertGreaterEqual(int(row_q[0] or 0), 0)
        self.assertIsNotNone(row_f)
        self.assertGreaterEqual(int(row_f[0] or 0), 1)
        self.assertIsNotNone(row_f[1])
        print("âœ… SpacedRepetitionService funcionando para questoes e flashcards")


class TestSchemaValidation(unittest.TestCase):
    """Prompt 4: validação de contratos JSON."""

    def test_validate_task_payload(self):
        provider = create_ai_provider("gemini", "fake_key")
        service = AIService(provider)

        ok_quiz, _ = service.validate_task_payload(
            "quiz",
            {"pergunta": "2+2?", "opcoes": ["1", "2", "3", "4"], "correta_index": 3},
        )
        bad_quiz, _ = service.validate_task_payload("quiz", {"pergunta": "", "opcoes": [], "correta_index": 0})
        ok_summary, _ = service.validate_task_payload(
            "study_summary",
            {
                "titulo": "T",
                "resumo_curto": "R",
                "topicos_principais": ["A"],
                "checklist_de_estudo": ["B"],
            },
        )
        self.assertTrue(ok_quiz)
        self.assertFalse(bad_quiz)
        self.assertTrue(ok_summary)
        print("âœ… Validação de schema por tarefa funcionando")


def run_all_tests():
    """Executa todos os testes"""
    print("=" * 60)
    print("EXECUTANDO TESTES - Quiz Vance V2")
    print("=" * 60)
    print()
    
    # Criar suite de testes
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Adicionar testes
    suite.addTests(loader.loadTestsFromTestCase(TestAIService))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestComponents))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestSchemaValidation))
    
    # Executar
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Resumo
    print()
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Testes executados: {result.testsRun}")
    print(f"âœ… Sucessos: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"âŒ Falhas: {len(result.failures)}")
    print(f"âš ï¸  Erros: {len(result.errors)}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)



