# -*- coding: utf-8 -*-
"""Testes de regressao para fundacao de UI."""

from __future__ import annotations

import asyncio
import unittest

from core.ui_async_guard import AsyncActionGuard
from core.ui_text_sanitizer import _fix_mojibake_text


class TestUtf8Sanitizer(unittest.TestCase):
    def test_preserva_acentuacao_em_texto_valido(self):
        txt = "Revisão, questões e ação no modo contínuo."
        self.assertEqual(_fix_mojibake_text(txt), txt)

    def test_corrige_mojibake_sem_remover_acentos(self):
        broken = "RevisÃ£o de questÃµes e aÃ§Ã£o rÃ¡pida."
        fixed = _fix_mojibake_text(broken)
        self.assertIn("Revisão", fixed)
        self.assertIn("questões", fixed)
        self.assertIn("ação", fixed)
        self.assertIn("rápida", fixed)


class TestAsyncActionGuard(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_e_cleanup(self):
        guard = AsyncActionGuard()
        events = []

        async def _slow():
            await asyncio.sleep(0.2)

        ok = await guard.run(
            "picker",
            _slow,
            timeout_s=0.05,
            on_timeout=lambda: events.append("timeout"),
            on_finish=lambda: events.append("finish"),
        )
        self.assertFalse(ok)
        self.assertEqual(events, ["timeout", "finish"])
        self.assertFalse(guard.is_running("picker"))

    async def test_bloqueia_execucao_concorrente_mesma_chave(self):
        guard = AsyncActionGuard()
        started = asyncio.Event()
        release = asyncio.Event()
        finish_calls = []

        async def _first():
            started.set()
            await release.wait()

        t1 = asyncio.create_task(
            guard.run("upload", _first, on_finish=lambda: finish_calls.append("t1"))
        )
        await started.wait()
        second = await guard.run("upload", _first, on_finish=lambda: finish_calls.append("t2"))
        self.assertFalse(second)
        release.set()
        await t1
        self.assertEqual(finish_calls, ["t1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
