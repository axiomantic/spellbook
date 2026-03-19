"""Tests for config editor API routes."""

import json
from unittest.mock import patch, MagicMock

import pytest


class TestConfigGet:
    """GET /api/config returns all config as a dict."""

    def test_get_config_returns_dict(self, client):
        mock_config = {
            "tts_enabled": True,
            "tts_voice": "bf_emma",
            "tts_volume": 0.8,
            "notify_enabled": True,
            "admin_enabled": True,
        }
        with patch(
            "spellbook.admin.routes.config.get_all_config",
            return_value=mock_config,
        ):
            response = client.get("/api/config")
            assert response.status_code == 200
            data = response.json()
            assert "config" in data
            # Explicit values override defaults
            assert data["config"]["tts_enabled"] is True
            assert data["config"]["tts_voice"] == "bf_emma"
            assert data["config"]["tts_volume"] == 0.8
            # Defaults are present for non-explicit keys
            assert data["config"]["notify_title"] == "Spellbook"

    def test_get_config_returns_defaults_when_no_file(self, client):
        with patch(
            "spellbook.admin.routes.config.get_all_config",
            return_value={},
        ):
            response = client.get("/api/config")
            assert response.status_code == 200
            config = response.json()["config"]
            # Should include defaults even when no explicit config exists
            assert config["tts_enabled"] is True
            assert config["tts_voice"] == "af_heart"
            assert config["tts_volume"] == 0.3
            assert config["notify_enabled"] is True
            assert config["notify_title"] == "Spellbook"

    def test_get_config_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/config")
        assert response.status_code == 401


class TestConfigSchema:
    """GET /api/config/schema returns known config keys with metadata."""

    def test_get_schema_returns_keys(self, client):
        response = client.get("/api/config/schema")
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        keys = {k["key"] for k in data["keys"]}
        assert "tts_enabled" in keys
        assert "notify_enabled" in keys
        assert "admin_enabled" in keys
        assert "telemetry_enabled" in keys

    def test_schema_keys_have_type_and_description(self, client):
        response = client.get("/api/config/schema")
        data = response.json()
        for key_info in data["keys"]:
            assert "key" in key_info
            assert "type" in key_info
            assert "description" in key_info
            assert key_info["type"] in ("boolean", "string", "number")

    def test_get_schema_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/config/schema")
        assert response.status_code == 401


class TestConfigUpdate:
    """PUT /api/config/{key} updates a single config key."""

    def test_update_known_key(self, client):
        with patch(
            "spellbook.admin.routes.config.set_config_value"
        ) as mock_set:
            mock_set.return_value = {"status": "ok", "config": {"tts_enabled": False}}
            response = client.put(
                "/api/config/tts_enabled", json={"value": False}
            )
            assert response.status_code == 200
            mock_set.assert_called_once_with("tts_enabled", False)

    def test_update_string_key(self, client):
        with patch(
            "spellbook.admin.routes.config.set_config_value"
        ) as mock_set:
            mock_set.return_value = {
                "status": "ok",
                "config": {"tts_voice": "af_heart"},
            }
            response = client.put(
                "/api/config/tts_voice", json={"value": "af_heart"}
            )
            assert response.status_code == 200
            mock_set.assert_called_once_with("tts_voice", "af_heart")

    def test_update_number_key(self, client):
        with patch(
            "spellbook.admin.routes.config.set_config_value"
        ) as mock_set:
            mock_set.return_value = {
                "status": "ok",
                "config": {"tts_volume": 0.5},
            }
            response = client.put(
                "/api/config/tts_volume", json={"value": 0.5}
            )
            assert response.status_code == 200
            mock_set.assert_called_once_with("tts_volume", 0.5)

    def test_update_unknown_key_returns_404(self, client):
        response = client.put(
            "/api/config/nonexistent_key", json={"value": "test"}
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "CONFIG_KEY_UNKNOWN"

    def test_update_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.put(
            "/api/config/tts_enabled", json={"value": False}
        )
        assert response.status_code == 401


class TestConfigUpdateEvent:
    """Config mutations publish config.updated events to the event bus."""

    def test_event_published_on_update(self, client):
        with patch(
            "spellbook.admin.routes.config.set_config_value"
        ) as mock_set, patch(
            "spellbook.admin.routes.config.event_bus"
        ) as mock_bus:
            mock_set.return_value = {"status": "ok", "config": {"tts_enabled": False}}
            # Make publish a coroutine
            import asyncio

            async def noop(*a, **kw):
                pass

            mock_bus.publish = MagicMock(side_effect=noop)

            response = client.put(
                "/api/config/tts_enabled", json={"value": False}
            )
            assert response.status_code == 200
            mock_bus.publish.assert_called_once()
            event = mock_bus.publish.call_args[0][0]
            assert event.event_type == "config.updated"
            assert event.data["key"] == "tts_enabled"
            assert event.data["value"] is False


class TestConfigBatchUpdate:
    """PUT /api/config (batch) updates multiple keys."""

    def test_batch_update_known_keys(self, client):
        with patch(
            "spellbook.admin.routes.config.batch_set_config"
        ) as mock_batch:
            mock_batch.return_value = {
                "status": "ok",
                "config": {"tts_enabled": False, "notify_enabled": True},
            }
            response = client.put(
                "/api/config",
                json={"updates": {"tts_enabled": False, "notify_enabled": True}},
            )
            assert response.status_code == 200
            mock_batch.assert_called_once_with(
                {"tts_enabled": False, "notify_enabled": True}
            )

    def test_batch_update_rejects_unknown_keys(self, client):
        response = client.put(
            "/api/config",
            json={"updates": {"tts_enabled": False, "bad_key": "value"}},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CONFIG_KEY_UNKNOWN"

    def test_batch_update_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.put(
            "/api/config",
            json={"updates": {"tts_enabled": False}},
        )
        assert response.status_code == 401
