"""Tests for ``POST /api/events/publish`` and the admin-app daemon marker."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from spellbook.admin.app import create_admin_app
from spellbook.admin.events import Subsystem, event_bus


def test_publish_endpoint_routes_to_event_bus():
    app = create_admin_app()
    with patch("spellbook.admin.routes.events.publish_sync") as mock_publish:
        with TestClient(app) as client:
            r = client.post(
                "/api/events/publish",
                json={
                    "subsystem": "worker_llm",
                    "event_type": "call_ok",
                    "data": {"task": "transcript_harvest", "latency_ms": 42},
                },
            )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert mock_publish.call_count == 1
    evt = mock_publish.call_args.args[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "call_ok"
    assert evt.data == {"task": "transcript_harvest", "latency_ms": 42}


def test_publish_endpoint_accepts_every_known_subsystem():
    app = create_admin_app()
    with patch("spellbook.admin.routes.events.publish_sync"):
        with TestClient(app) as client:
            for subsystem in Subsystem:
                r = client.post(
                    "/api/events/publish",
                    json={
                        "subsystem": subsystem.value,
                        "event_type": "probe",
                        "data": {},
                    },
                )
                assert r.status_code == 200, subsystem


def test_publish_endpoint_rejects_unknown_subsystem():
    app = create_admin_app()
    with TestClient(app) as client:
        r = client.post(
            "/api/events/publish",
            json={
                "subsystem": "not_a_real_subsystem",
                "event_type": "x",
                "data": {},
            },
        )
    assert r.status_code == 400
    assert r.json() == {
        "detail": "unknown subsystem: 'not_a_real_subsystem' is not a valid Subsystem"
    }


def test_publish_endpoint_rejects_missing_fields():
    app = create_admin_app()
    with TestClient(app) as client:
        r = client.post(
            "/api/events/publish",
            json={"subsystem": "worker_llm"},  # missing event_type, data
        )
    # Pydantic validation error
    assert r.status_code == 422


def test_lifespan_sets_event_bus_in_daemon_true():
    app = create_admin_app()
    assert event_bus._in_daemon is False
    with TestClient(app):
        assert event_bus._in_daemon is True
    assert event_bus._in_daemon is False


def test_lifespan_clears_daemon_marker_on_shutdown():
    app = create_admin_app()
    event_bus._in_daemon = False
    with TestClient(app):
        pass
    assert event_bus._in_daemon is False
