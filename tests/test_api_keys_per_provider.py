# -*- coding: utf-8 -*-

from core.database_v2 import Database


def test_api_keys_are_isolated_by_provider(tmp_path):
    db_file = tmp_path / "test_api_keys_per_provider.db"
    db = Database(db_path=str(db_file))
    db.iniciar_banco()
    ok, _msg = db.criar_conta("kuser", "kuser@test.local", "123456", "01/01/2000")
    assert ok

    user = db.fazer_login("kuser@test.local", "123456")
    uid = int(user["id"])

    db.atualizar_provider_ia(uid, "gemini", "gemini-2.5-flash")
    db.atualizar_api_keys(
        uid,
        {
            "gemini": "gem-key-123",
            "openai": "open-key-456",
            "groq": "groq-key-789",
        },
        "gemini",
    )
    u1 = db.fazer_login("kuser@test.local", "123456")
    assert str(u1.get("api_key") or "") == "gem-key-123"
    assert str(u1.get("api_key_gemini") or "") == "gem-key-123"
    assert str(u1.get("api_key_openai") or "") == "open-key-456"
    assert str(u1.get("api_key_groq") or "") == "groq-key-789"

    db.atualizar_provider_ia(uid, "openai", "gpt-4o-mini")
    u2 = db.fazer_login("kuser@test.local", "123456")
    assert str(u2.get("api_key") or "") == "open-key-456"
    assert str(u2.get("api_key_gemini") or "") == "gem-key-123"
    assert str(u2.get("api_key_openai") or "") == "open-key-456"
    assert str(u2.get("api_key_groq") or "") == "groq-key-789"

    db.atualizar_provider_ia(uid, "groq", "llama-3.1-8b-instant")
    db.atualizar_api_key(uid, "groq-key-updated")
    u3 = db.fazer_login("kuser@test.local", "123456")
    assert str(u3.get("api_key") or "") == "groq-key-updated"
    assert str(u3.get("api_key_groq") or "") == "groq-key-updated"
    assert str(u3.get("api_key_openai") or "") == "open-key-456"
