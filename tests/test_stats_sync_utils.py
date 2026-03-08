# -*- coding: utf-8 -*-

from core.sync_utils import resolve_consumed_event_ids


def _events(*ids: str) -> list[dict]:
    return [{"event_id": eid} for eid in ids]


def test_resolve_consumed_event_ids_uses_explicit_backend_list():
    events = _events("e1", "e2", "e3")
    resp = {"consumed_event_ids": ["e2", "e3"]}
    assert resolve_consumed_event_ids(resp, events) == ["e2", "e3"]


def test_resolve_consumed_event_ids_ignores_unknown_ids():
    events = _events("e1", "e2")
    resp = {"consumed_event_ids": ["x", "e2", "x", "e1"]}
    assert resolve_consumed_event_ids(resp, events) == ["e2", "e1"]


def test_resolve_consumed_event_ids_falls_back_to_full_ack():
    events = _events("e1", "e2", "e3")
    resp = {"processed": 2, "duplicated": 1, "received": 3}
    assert resolve_consumed_event_ids(resp, events) == ["e1", "e2", "e3"]


def test_resolve_consumed_event_ids_does_not_delete_on_partial_ack():
    events = _events("e1", "e2", "e3")
    resp = {"processed": 1, "duplicated": 0, "received": 3}
    assert resolve_consumed_event_ids(resp, events) == []


def test_resolve_consumed_event_ids_does_not_delete_on_ambiguous_response():
    events = _events("e1", "e2")
    resp = {"ok": True}
    assert resolve_consumed_event_ids(resp, events) == []

