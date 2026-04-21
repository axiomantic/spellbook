"""Tests for the 14 worker_llm entries in the admin config schema.

Also verifies that ``spellbook/core/config.py::CONFIG_DEFAULTS`` carries the
same values so ``config_get`` returns the documented defaults when a key is
absent from the user's ``spellbook.json``.
"""

from spellbook.admin.routes.config import (
    CONFIG_DEFAULTS,
    CONFIG_SCHEMA,
    KNOWN_KEYS,
)
from spellbook.core.config import CONFIG_DEFAULTS as CORE_DEFAULTS


WORKER_KEYS = {
    "worker_llm_base_url",
    "worker_llm_model",
    "worker_llm_api_key",
    "worker_llm_timeout_s",
    "worker_llm_max_tokens",
    "worker_llm_tool_safety_timeout_s",
    "worker_llm_transcript_harvest_mode",
    "worker_llm_allow_prompt_overrides",
    "worker_llm_read_claude_memory",
    "worker_llm_feature_transcript_harvest",
    "worker_llm_feature_roundtable",
    "worker_llm_feature_memory_rerank",
    "worker_llm_feature_tool_safety",
    "worker_llm_safety_cache_ttl_s",
}


def _entry(key: str) -> dict:
    return next(e for e in CONFIG_SCHEMA if e["key"] == key)


def test_all_fourteen_worker_keys_in_admin_schema():
    assert WORKER_KEYS.issubset(KNOWN_KEYS)


def test_fourteen_entries_added():
    # Observability keys also share the ``worker_llm_`` prefix but land under
    # a disjoint ``worker_llm_observability_`` namespace — exclude them here so
    # this assertion stays scoped to the original 14-key core worker_llm set.
    schema_worker_keys = {
        e["key"]
        for e in CONFIG_SCHEMA
        if e["key"].startswith("worker_llm_")
        and not e["key"].startswith("worker_llm_observability_")
    }
    assert schema_worker_keys == WORKER_KEYS
    assert len(schema_worker_keys) == 14


def test_string_defaults():
    assert _entry("worker_llm_base_url")["default"] == ""
    assert _entry("worker_llm_model")["default"] == ""
    assert _entry("worker_llm_api_key")["default"] == ""
    assert _entry("worker_llm_transcript_harvest_mode")["default"] == "replace"


def test_numeric_defaults():
    assert _entry("worker_llm_timeout_s")["default"] == 10.0
    assert _entry("worker_llm_max_tokens")["default"] == 1024
    assert _entry("worker_llm_tool_safety_timeout_s")["default"] == 1.5
    assert _entry("worker_llm_safety_cache_ttl_s")["default"] == 300


def test_read_claude_memory_defaults_false():
    assert _entry("worker_llm_read_claude_memory")["default"] is False


def test_allow_prompt_overrides_defaults_true():
    assert _entry("worker_llm_allow_prompt_overrides")["default"] is True


def test_all_feature_flags_default_false():
    feature_keys = [k for k in WORKER_KEYS if k.startswith("worker_llm_feature_")]
    assert sorted(feature_keys) == sorted(
        [
            "worker_llm_feature_transcript_harvest",
            "worker_llm_feature_roundtable",
            "worker_llm_feature_memory_rerank",
            "worker_llm_feature_tool_safety",
        ]
    )
    for k in feature_keys:
        assert _entry(k)["default"] is False, k


def test_admin_config_defaults_derived_from_schema():
    # CONFIG_DEFAULTS in admin/routes/config.py is derived from CONFIG_SCHEMA.
    for k in WORKER_KEYS:
        assert k in CONFIG_DEFAULTS
        assert CONFIG_DEFAULTS[k] == _entry(k)["default"]


def test_core_config_defaults_carry_all_worker_keys():
    for k in WORKER_KEYS:
        assert k in CORE_DEFAULTS, (
            f"{k} missing from spellbook/core/config.py CONFIG_DEFAULTS"
        )


def test_core_defaults_match_admin_schema_defaults():
    for k in WORKER_KEYS:
        assert CORE_DEFAULTS[k] == _entry(k)["default"], k


def test_every_entry_has_required_fields():
    for k in WORKER_KEYS:
        entry = _entry(k)
        assert set(entry.keys()) == {"key", "type", "description", "default"}
        assert isinstance(entry["description"], str)
        assert entry["description"] != ""


# ---------------------------------------------------------------------------
# 7 observability keys — landed alongside the Worker LLM Observability feature
# (design §7). Ints/floats carry schema type "number"; the single boolean flag
# carries type "boolean". No custom validators.
# ---------------------------------------------------------------------------

OBSERVABILITY_KEYS = {
    "worker_llm_observability_retention_hours",
    "worker_llm_observability_max_rows",
    "worker_llm_observability_purge_interval_seconds",
    "worker_llm_observability_notify_enabled",
    "worker_llm_observability_notify_threshold",
    "worker_llm_observability_notify_window",
    "worker_llm_observability_notify_eval_interval_seconds",
}


def test_all_seven_observability_keys_in_admin_schema():
    assert OBSERVABILITY_KEYS.issubset(KNOWN_KEYS)


def test_seven_observability_entries_added():
    schema_observability_keys = {
        e["key"]
        for e in CONFIG_SCHEMA
        if e["key"].startswith("worker_llm_observability_")
    }
    assert schema_observability_keys == OBSERVABILITY_KEYS
    assert len(schema_observability_keys) == 7


def test_observability_retention_hours_schema():
    e = _entry("worker_llm_observability_retention_hours")
    assert e["type"] == "number"
    assert e["default"] == 24


def test_observability_max_rows_schema():
    e = _entry("worker_llm_observability_max_rows")
    assert e["type"] == "number"
    assert e["default"] == 10000


def test_observability_purge_interval_seconds_schema():
    e = _entry("worker_llm_observability_purge_interval_seconds")
    assert e["type"] == "number"
    assert e["default"] == 300


def test_observability_notify_enabled_schema():
    e = _entry("worker_llm_observability_notify_enabled")
    assert e["type"] == "boolean"
    assert e["default"] is False


def test_observability_notify_threshold_schema():
    e = _entry("worker_llm_observability_notify_threshold")
    assert e["type"] == "number"
    assert e["default"] == 0.8


def test_observability_notify_window_schema():
    e = _entry("worker_llm_observability_notify_window")
    assert e["type"] == "number"
    assert e["default"] == 20


def test_observability_notify_eval_interval_seconds_schema():
    e = _entry("worker_llm_observability_notify_eval_interval_seconds")
    assert e["type"] == "number"
    assert e["default"] == 60


def test_observability_admin_config_defaults_derived_from_schema():
    for k in OBSERVABILITY_KEYS:
        assert k in CONFIG_DEFAULTS
        assert CONFIG_DEFAULTS[k] == _entry(k)["default"]


def test_observability_core_config_defaults_carry_all_keys():
    for k in OBSERVABILITY_KEYS:
        assert k in CORE_DEFAULTS, (
            f"{k} missing from spellbook/core/config.py CONFIG_DEFAULTS"
        )


def test_observability_core_defaults_match_admin_schema_defaults():
    for k in OBSERVABILITY_KEYS:
        assert CORE_DEFAULTS[k] == _entry(k)["default"], k


def test_observability_every_entry_has_required_fields():
    for k in OBSERVABILITY_KEYS:
        entry = _entry(k)
        assert set(entry.keys()) == {"key", "type", "description", "default"}
        assert isinstance(entry["description"], str)
        assert entry["description"] != ""
