# -*- coding: utf-8 -*-

import unittest

from core.helpers.ai_helpers import (
    resolve_available_provider_keys,
    resolve_provider_switch_options,
)


class _FakeDB:
    def __init__(self, keys):
        self._keys = dict(keys or {})

    def obter_api_keys_ia(self, user_id: int):
        _ = int(user_id)
        return dict(self._keys)


class ProviderSwitchOptionsTest(unittest.TestCase):
    def test_resolve_available_provider_keys_merges_db_keys(self):
        user = {
            "id": 7,
            "provider": "gemini",
            "api_key_gemini": "gem-key-123",
        }
        db = _FakeDB(
            {
                "gemini": "gem-key-123",
                "openai": "open-key-456",
                "groq": "groq-key-789",
            }
        )

        keys = resolve_available_provider_keys(user, db=db)

        self.assertEqual(keys["gemini"], "gem-key-123")
        self.assertEqual(keys["openai"], "open-key-456")
        self.assertEqual(keys["groq"], "groq-key-789")

    def test_provider_switch_options_include_groq_from_local_db(self):
        user = {
            "id": 9,
            "provider": "gemini",
            "api_key_gemini": "gem-key-123",
            "api_key_openai": "open-key-456",
            # Snapshot da view sem Groq; helper deve buscar no banco local.
            "api_key_groq": "",
        }
        db = _FakeDB(
            {
                "gemini": "gem-key-123",
                "openai": "open-key-456",
                "groq": "groq-key-789",
            }
        )

        options = resolve_provider_switch_options(user, db=db)

        self.assertEqual([key for key, _name in options], ["openai", "groq"])
        self.assertTrue(str(options[0][1] or "").strip())
        self.assertTrue(str(options[1][1] or "").strip())


if __name__ == "__main__":
    unittest.main()
