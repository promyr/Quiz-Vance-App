# -*- coding: utf-8 -*-
"""Testes unitarios do smoke go-live."""

import unittest
from unittest.mock import patch

from scripts import smoke_go_live


class SmokeGoLiveTest(unittest.TestCase):
    def test_online_smoke_requires_ready_by_default(self):
        def _fake_request(_base_url: str, _method: str, path: str, payload=None):
            if path == "/health":
                return {"ok": True}
            if path == "/health/ready":
                raise RuntimeError("HTTP 404 /health/ready: not found")
            return {}

        with patch("scripts.smoke_go_live._request", side_effect=_fake_request):
            with self.assertRaises(RuntimeError):
                smoke_go_live._run_backend_online_smoke(
                    "https://example.test",
                    full=False,
                    allow_missing_ready=False,
                )

    def test_online_smoke_can_skip_missing_ready_with_flag(self):
        def _fake_request(_base_url: str, _method: str, path: str, payload=None):
            if path == "/health":
                return {"ok": True}
            if path == "/health/ready":
                raise RuntimeError("HTTP 404 /health/ready: not found")
            return {}

        with patch("scripts.smoke_go_live._request", side_effect=_fake_request):
            logs = smoke_go_live._run_backend_online_smoke(
                "https://example.test",
                full=False,
                allow_missing_ready=True,
            )
        self.assertIn("OK /health", logs)
        self.assertIn("SKIP /health/ready (endpoint indisponivel)", logs)


if __name__ == "__main__":
    unittest.main()
