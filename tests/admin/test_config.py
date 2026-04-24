"""Tests for config editor API routes."""

import json

import pytest


class TestConfigGet:
    """GET /api/config returns all config as a dict."""

    def test_get_config_returns_dict(self, client, monkeypatch):
        mock_config = {
            "notify_enabled": True,
            "notify_title": "Custom",
            "worker_llm_timeout_s": 5.0,
            "admin_enabled": True,
        }
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: mock_config,
        )

        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        assert "config" in data
        # Explicit values override defaults
        assert data["config"]["notify_enabled"] is True
        assert data["config"]["notify_title"] == "Custom"
        assert data["config"]["worker_llm_timeout_s"] == 5.0
        # Defaults are present for non-explicit keys
        assert data["config"]["admin_enabled"] is True

    def test_get_config_returns_defaults_when_no_file(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {},
        )

        response = client.get("/api/config")

        assert response.status_code == 200
        config = response.json()["config"]
        # Should include defaults even when no explicit config exists
        assert config["notify_enabled"] is True
        assert config["notify_title"] == "Spellbook"
        assert config["admin_enabled"] is True

    def test_get_config_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/config")
        assert response.status_code == 401

    def test_get_config_returns_observability_defaults(self, client, monkeypatch):
        """``/api/config`` envelope exposes the 7 observability keys with
        their documented defaults when no explicit value is set."""
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {},
        )

        response = client.get("/api/config")

        assert response.status_code == 200
        config = response.json()["config"]
        assert config["worker_llm_observability_retention_hours"] == 24
        assert config["worker_llm_observability_max_rows"] == 10000
        assert config["worker_llm_observability_purge_interval_seconds"] == 300
        assert config["worker_llm_observability_notify_enabled"] is False
        assert config["worker_llm_observability_notify_threshold"] == 0.8
        assert config["worker_llm_observability_notify_window"] == 20
        assert (
            config["worker_llm_observability_notify_eval_interval_seconds"] == 60
        )


class TestConfigSchema:
    """GET /api/config/schema returns known config keys with metadata."""

    def test_get_schema_returns_keys(self, client):
        response = client.get("/api/config/schema")
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        keys = {k["key"] for k in data["keys"]}
        assert "notify_enabled" in keys
        assert "admin_enabled" in keys

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

    def test_update_known_key(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda key, value: (calls.append((key, value)) or {"status": "ok", "config": {"notify_enabled": False}}),
        )

        response = client.put(
            "/api/config/notify_enabled", json={"value": False}
        )

        assert response.status_code == 200
        assert calls == [("notify_enabled", False)]

    def test_update_string_key(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda key, value: (calls.append((key, value)) or {"status": "ok", "config": {"notify_title": "Custom"}}),
        )

        response = client.put(
            "/api/config/notify_title", json={"value": "Custom"}
        )

        assert response.status_code == 200
        assert calls == [("notify_title", "Custom")]

    def test_update_number_key(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda key, value: (calls.append((key, value)) or {"status": "ok", "config": {"worker_llm_timeout_s": 5.0}}),
        )

        response = client.put(
            "/api/config/worker_llm_timeout_s", json={"value": 5.0}
        )

        assert response.status_code == 200
        assert calls == [("worker_llm_timeout_s", 5.0)]

    def test_update_unknown_key_returns_404(self, client):
        response = client.put(
            "/api/config/nonexistent_key", json={"value": "test"}
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "CONFIG_KEY_UNKNOWN"

    def test_update_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.put(
            "/api/config/notify_enabled", json={"value": False}
        )
        assert response.status_code == 401


class TestConfigUpdateEvent:
    """Config mutations publish config.updated events to the event bus."""

    def test_event_published_on_update(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda key, value: {"status": "ok", "config": {"notify_enabled": False}},
        )

        captured_events = []

        from spellbook.admin.routes.config import event_bus as real_event_bus

        original_publish = real_event_bus.publish

        async def capture_publish(event):
            captured_events.append(event)
            return await original_publish(event)

        monkeypatch.setattr(real_event_bus, "publish", capture_publish)

        response = client.put(
            "/api/config/notify_enabled", json={"value": False}
        )

        assert response.status_code == 200

        assert len(captured_events) == 1
        event = captured_events[0]
        assert event.event_type == "config.updated"
        assert event.data["key"] == "notify_enabled"
        assert event.data["value"] is False


class TestConfigBatchUpdate:
    """PUT /api/config (batch) updates multiple keys."""

    def test_batch_update_known_keys(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.batch_set_config",
            lambda updates: (
                calls.append(updates)
                or {
                    "status": "ok",
                    "config": {"notify_enabled": False, "admin_enabled": True},
                }
            ),
        )

        response = client.put(
            "/api/config",
            json={"updates": {"notify_enabled": False, "admin_enabled": True}},
        )

        assert response.status_code == 200
        assert calls == [{"notify_enabled": False, "admin_enabled": True}]

    def test_batch_update_rejects_unknown_keys(self, client):
        response = client.put(
            "/api/config",
            json={"updates": {"notify_enabled": False, "bad_key": "value"}},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CONFIG_KEY_UNKNOWN"

    def test_batch_update_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.put(
            "/api/config",
            json={"updates": {"notify_enabled": False}},
        )
        assert response.status_code == 401


class TestHiddenConfigKeys:
    """New schema entries for keys that already live in spellbook.json but were
    previously unreachable through the admin UI."""

    NEW_KEYS = [
        ("fun_mode", False),
        ("persona", ""),
        ("security.spotlighting.enabled", True),
        ("security.spotlighting.tier", "standard"),
        ("security.spotlighting.mcp_wrap", True),
        ("security.spotlighting.custom_prefix", ""),
        ("security.crypto.enabled", True),
        ("security.crypto.keys_dir", "~/.local/spellbook/keys"),
        ("security.crypto.gate_spawn_session", True),
        ("security.crypto.gate_workflow_save", True),
        ("security.crypto.gate_config_writes", False),
        ("security.crypto.auto_sign_on_install", True),
        ("security.sleuth.enabled", False),
        ("security.sleuth.max_content_bytes", 50000),
        ("security.sleuth.max_tokens_per_check", 1024),
        ("security.sleuth.calls_per_session", 50),
        ("security.sleuth.confidence_threshold", 0.8),
        ("security.sleuth.cache_ttl_seconds", 3600),
        ("security.sleuth.timeout_seconds", 5),
        ("security.sleuth.fallback_on_budget_exceeded", "regex_only"),
        ("security.lodo.datasets_dir", "tests/test_security/datasets"),
        ("security.lodo.min_detection_rate", 0.85),
        ("security.lodo.max_false_positive_rate", 0.05),
    ]

    def test_schema_lists_every_new_key_with_a_type(self, client):
        """GET /api/config/schema must advertise each new key."""
        response = client.get("/api/config/schema")
        assert response.status_code == 200
        schema = {k["key"]: k for k in response.json()["keys"]}

        for key, _default in self.NEW_KEYS:
            assert key in schema, f"Missing schema entry for {key!r}"
            assert schema[key]["type"] in ("boolean", "string", "number")
            assert schema[key]["description"]

    def test_defaults_surface_via_get_config(self, client, monkeypatch):
        """An unset key returns the schema default via GET /api/config."""
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {},
        )

        response = client.get("/api/config")
        assert response.status_code == 200
        config = response.json()["config"]

        for key, default in self.NEW_KEYS:
            assert config[key] == default, (
                f"Expected {key}={default!r}, got {config[key]!r}"
            )

    @pytest.mark.parametrize(
        "key,value",
        [
            ("fun_mode", True),
            ("persona", "Tech-lead archetype"),
            ("security.spotlighting.enabled", False),
            ("security.spotlighting.tier", "strict"),
            ("security.crypto.gate_config_writes", True),
            ("security.sleuth.enabled", True),
            ("security.sleuth.max_content_bytes", 100000),
            ("security.sleuth.confidence_threshold", 0.95),
            ("security.lodo.min_detection_rate", 0.9),
        ],
    )
    def test_put_known_new_key_roundtrip(self, client, monkeypatch, key, value):
        """PUT a new key should reach set_config_value with (key, value)."""
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: (calls.append((k, v)) or {"status": "ok", "config": {k: v}}),
        )

        response = client.put(f"/api/config/{key}", json={"value": value})
        assert response.status_code == 200, response.json()
        assert calls == [(key, value)]


class TestSecretMasking:
    """Secret keys (e.g. security.sleuth.api_key) must be masked in GET."""

    def test_set_secret_is_masked(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {"security.sleuth.api_key": "sk-live-supersecret"},
        )
        response = client.get("/api/config")
        assert response.status_code == 200
        config = response.json()["config"]
        assert config["security.sleuth.api_key"] == "***"

    def test_unset_secret_returns_empty_string(self, client, monkeypatch):
        """Secret key with empty stored value is surfaced as "" not the mask."""
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {"security.sleuth.api_key": ""},
        )
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json()["config"]["security.sleuth.api_key"] == ""

    def test_null_stored_secret_returns_empty_string(self, client, monkeypatch):
        """A ``null`` value carried over from legacy configs must not leak or
        mask as ``***``. The user's actual spellbook.json contains
        ``security.sleuth.api_key: null`` at the time this code was written."""
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {"security.sleuth.api_key": None},
        )
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json()["config"]["security.sleuth.api_key"] == ""

    def test_none_default_returns_empty_string(self, client, monkeypatch):
        """A default of None on a secret key should surface as empty, not null."""
        # Simulate the case where the migration stripped the key: only the
        # schema default (empty string) is present.
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {},
        )
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json()["config"]["security.sleuth.api_key"] == ""

    def test_non_secret_values_pass_through(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.get_all_config",
            lambda: {"notify_title": "CustomTitle"},
        )
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json()["config"]["notify_title"] == "CustomTitle"

    def test_schema_flag_is_exposed(self, client):
        """The schema endpoint must carry ``secret: true`` so the frontend can
        render a password input."""
        response = client.get("/api/config/schema")
        entries = {k["key"]: k for k in response.json()["keys"]}
        assert entries["security.sleuth.api_key"].get("secret") is True
        # Non-secret entries should not expose the flag as True
        assert entries["notify_enabled"].get("secret") in (None, False)

    def test_put_secret_accepts_value(self, client, monkeypatch):
        """Writing a secret should go through unmasked -- the admin wrote it."""
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: (calls.append((k, v)) or {"status": "ok", "config": {}}),
        )
        response = client.put(
            "/api/config/security.sleuth.api_key",
            json={"value": "sk-live-xyz"},
        )
        assert response.status_code == 200
        assert calls == [("security.sleuth.api_key", "sk-live-xyz")]


class TestTranscriptHarvestModeValidator:
    """worker_llm_transcript_harvest_mode accepts only replace|merge|skip."""

    def test_accepts_replace(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda key, value: {"status": "ok", "config": {key: value}},
        )
        response = client.put(
            "/api/config/worker_llm_transcript_harvest_mode",
            json={"value": "replace"},
        )
        assert response.status_code == 200

    def test_accepts_merge(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda key, value: {"status": "ok", "config": {key: value}},
        )
        response = client.put(
            "/api/config/worker_llm_transcript_harvest_mode",
            json={"value": "merge"},
        )
        assert response.status_code == 200

    def test_accepts_skip(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda key, value: {"status": "ok", "config": {key: value}},
        )
        response = client.put(
            "/api/config/worker_llm_transcript_harvest_mode",
            json={"value": "skip"},
        )
        assert response.status_code == 200

    def test_rejects_typo(self, client):
        response = client.put(
            "/api/config/worker_llm_transcript_harvest_mode",
            json={"value": "replce"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "CONFIG_VALUE_INVALID"
        assert "worker_llm_transcript_harvest_mode" in data["error"]["message"]

    def test_rejects_non_string(self, client):
        response = client.put(
            "/api/config/worker_llm_transcript_harvest_mode",
            json={"value": 123},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_batch_rejects_typo(self, client, monkeypatch):
        # Even mixed with a valid key, a bad transcript_harvest_mode must
        # reject the whole batch.
        monkeypatch.setattr(
            "spellbook.admin.routes.config.batch_set_config",
            lambda updates: {"status": "ok", "config": {}},
        )
        response = client.put(
            "/api/config",
            json={
                "updates": {
                    "notify_enabled": False,
                    "worker_llm_transcript_harvest_mode": "replce",
                }
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"


class TestSecretRoundTripSafe:
    """Secret keys must not be overwritten when the client echoes the mask.

    The failure mode this guards: ``GET /api/config`` masks secret values as
    ``"***"``. If an admin frontend reads the full config, edits an unrelated
    field, and PUTs the whole object back, the masked ``"***"`` would
    otherwise clobber the real stored secret. The PUT handler treats an
    incoming value of exactly ``"***"`` on a ``secret: True`` key as a
    no-op for that key, preserving the existing stored value.
    """

    def test_put_mask_preserves_existing_secret(self, client, monkeypatch):
        """PUT with value=='***' on a secret key must NOT call set_config_value."""
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: (calls.append((k, v)) or {"status": "ok", "config": {}}),
        )
        response = client.put(
            "/api/config/security.sleuth.api_key",
            json={"value": "***"},
        )
        assert response.status_code == 200
        assert response.json().get("preserved") is True
        # The write helper must not have been invoked.
        assert calls == []

    def test_put_non_mask_value_writes_normally(self, client, monkeypatch):
        """PUT with a real (non-mask) value on a secret key writes through."""
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: (calls.append((k, v)) or {"status": "ok", "config": {}}),
        )
        response = client.put(
            "/api/config/security.sleuth.api_key",
            json={"value": "sk-new-value"},
        )
        assert response.status_code == 200
        assert calls == [("security.sleuth.api_key", "sk-new-value")]

    def test_put_empty_string_clears_secret(self, client, monkeypatch):
        """Empty string is a valid clear signal; empty != mask and must write."""
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: (calls.append((k, v)) or {"status": "ok", "config": {}}),
        )
        response = client.put(
            "/api/config/security.sleuth.api_key",
            json={"value": ""},
        )
        assert response.status_code == 200
        assert calls == [("security.sleuth.api_key", "")]

    def test_batch_mask_on_secret_is_dropped(self, client, monkeypatch):
        """Batch PUT with mask on a secret key drops that key; others write."""
        captured = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.batch_set_config",
            lambda updates: (captured.append(updates) or {"status": "ok", "config": {}}),
        )
        response = client.put(
            "/api/config",
            json={
                "updates": {
                    "security.sleuth.api_key": "***",  # masked echo, must be dropped
                    "notify_enabled": False,
                }
            },
        )
        assert response.status_code == 200
        body = response.json()
        # The secret key was preserved (not written).
        assert "security.sleuth.api_key" in body.get("preserved", [])
        # Only the non-secret non-mask key was written.
        assert captured == [{"notify_enabled": False}]
        assert body["updated"] == ["notify_enabled"]

    def test_batch_all_masks_is_noop_write(self, client, monkeypatch):
        """Batch PUT containing only masked secrets writes nothing and 200s."""
        captured = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.batch_set_config",
            lambda updates: (captured.append(updates) or {"status": "ok", "config": {}}),
        )
        response = client.put(
            "/api/config",
            json={
                "updates": {
                    "security.sleuth.api_key": "***",
                    "worker_llm_api_key": "***",
                }
            },
        )
        assert response.status_code == 200
        # The write helper must not be invoked when nothing needs writing.
        assert captured == []
        body = response.json()
        assert body["updated"] == []
        assert set(body["preserved"]) == {
            "security.sleuth.api_key",
            "worker_llm_api_key",
        }

    def test_non_secret_key_mask_literal_passes_through(self, client, monkeypatch):
        """A non-secret key receiving the literal '***' writes normally.

        The round-trip guard is scoped to secret keys only; a non-secret
        string key has no reason to be masked on GET, so '***' is a real
        user-supplied value for it.
        """
        calls = []
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: (calls.append((k, v)) or {"status": "ok", "config": {}}),
        )
        response = client.put(
            "/api/config/notify_title",
            json={"value": "***"},
        )
        assert response.status_code == 200
        assert calls == [("notify_title", "***")]


class TestNumericConfigValidation:
    """Numeric config keys reject out-of-range or wrong-type values.

    Follow-up to the transcript_harvest_mode / session_mode enum validators:
    range-check the numeric knobs that drive observability, retention, and
    timeout behavior. An operator typing ``notify_threshold=1.5`` or
    ``retention_hours=0`` would otherwise silently disable or corrupt the
    feature — those must fail at config-set time.
    """

    # ------------------------------------------------------------------
    # Unit-interval: 0.0 <= x <= 1.0
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("value", [0.0, 0.5, 0.8, 1.0])
    def test_notify_threshold_accepts_valid(self, client, monkeypatch, value):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: {"status": "ok", "config": {k: v}},
        )
        response = client.put(
            "/api/config/worker_llm_observability_notify_threshold",
            json={"value": value},
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("value", [-0.1, 1.1, 2.0, -1])
    def test_notify_threshold_rejects_out_of_range(self, client, value):
        response = client.put(
            "/api/config/worker_llm_observability_notify_threshold",
            json={"value": value},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_notify_threshold_rejects_string(self, client):
        response = client.put(
            "/api/config/worker_llm_observability_notify_threshold",
            json={"value": "0.8"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_notify_threshold_rejects_bool(self, client):
        """``True`` is an ``int`` subclass; reject it explicitly."""
        response = client.put(
            "/api/config/worker_llm_observability_notify_threshold",
            json={"value": True},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    # ------------------------------------------------------------------
    # Positive integers (>= 1)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "key",
        [
            "worker_llm_observability_max_rows",
            "hook_observability_max_rows",
            "worker_llm_observability_notify_window",
            "worker_llm_max_tokens",
            "worker_llm_queue_max_depth",
        ],
    )
    def test_positive_int_accepts_one_and_large(self, client, monkeypatch, key):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: {"status": "ok", "config": {k: v}},
        )
        for good in (1, 10_000):
            response = client.put(
                f"/api/config/{key}",
                json={"value": good},
            )
            assert response.status_code == 200, (key, good, response.json())

    @pytest.mark.parametrize(
        "key",
        [
            "worker_llm_observability_max_rows",
            "hook_observability_max_rows",
            "worker_llm_observability_notify_window",
            "worker_llm_max_tokens",
            "worker_llm_queue_max_depth",
        ],
    )
    def test_positive_int_rejects_zero_and_negative(self, client, key):
        for bad in (0, -1):
            response = client.put(
                f"/api/config/{key}",
                json={"value": bad},
            )
            assert response.status_code == 400, (key, bad, response.json())
            assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_positive_int_rejects_float(self, client):
        """Row caps / token caps are ints; reject ``10.5``."""
        response = client.put(
            "/api/config/worker_llm_max_tokens",
            json={"value": 10.5},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_positive_int_rejects_bool(self, client):
        response = client.put(
            "/api/config/worker_llm_max_tokens",
            json={"value": True},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    # ------------------------------------------------------------------
    # Positive numbers (int or float, > 0)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "key",
        [
            "worker_llm_observability_retention_hours",
            "hook_observability_retention_hours",
            "worker_llm_observability_purge_interval_seconds",
            "hook_observability_purge_interval_seconds",
            "worker_llm_observability_notify_eval_interval_seconds",
            "worker_llm_timeout_s",
            "worker_llm_tool_safety_timeout_s",
            "worker_llm_tool_safety_cold_threshold_s",
            "worker_llm_safety_cache_ttl_s",
        ],
    )
    def test_positive_number_accepts_small_float(self, client, monkeypatch, key):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.set_config_value",
            lambda k, v: {"status": "ok", "config": {k: v}},
        )
        for good in (0.5, 1, 24, 3600.0):
            response = client.put(
                f"/api/config/{key}",
                json={"value": good},
            )
            assert response.status_code == 200, (key, good, response.json())

    @pytest.mark.parametrize(
        "key",
        [
            "worker_llm_observability_retention_hours",
            "worker_llm_timeout_s",
            "worker_llm_tool_safety_timeout_s",
            "worker_llm_safety_cache_ttl_s",
        ],
    )
    def test_positive_number_rejects_zero_and_negative(self, client, key):
        for bad in (0, 0.0, -0.5, -1):
            response = client.put(
                f"/api/config/{key}",
                json={"value": bad},
            )
            assert response.status_code == 400, (key, bad, response.json())
            assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_positive_number_rejects_string(self, client):
        response = client.put(
            "/api/config/worker_llm_timeout_s",
            json={"value": "10"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_positive_number_rejects_bool(self, client):
        response = client.put(
            "/api/config/worker_llm_timeout_s",
            json={"value": False},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    # ------------------------------------------------------------------
    # Batch path honors the same validators.
    # ------------------------------------------------------------------

    def test_batch_rejects_out_of_range_threshold(self, client, monkeypatch):
        """A bad numeric in a mixed batch rejects the whole batch atomically."""
        monkeypatch.setattr(
            "spellbook.admin.routes.config.batch_set_config",
            lambda updates: {"status": "ok", "config": {}},
        )
        response = client.put(
            "/api/config",
            json={
                "updates": {
                    "notify_enabled": False,
                    "worker_llm_observability_notify_threshold": 1.5,
                }
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"

    def test_batch_rejects_zero_max_rows(self, client, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.routes.config.batch_set_config",
            lambda updates: {"status": "ok", "config": {}},
        )
        response = client.put(
            "/api/config",
            json={"updates": {"worker_llm_observability_max_rows": 0}},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CONFIG_VALUE_INVALID"
