"""Tests for ``spellbook.worker_llm.config``."""

import tripwire
import pytest
from dirty_equals import IsStr

from spellbook.worker_llm import config as wl_config


# ``get_worker_config()`` issues one ``config_get`` per key, plus one extra
# read for each of the two conditional keys (``allow_prompt_overrides`` and
# ``read_claude_memory``) when they are set to a concrete value. An empty
# config therefore produces 14 reads; a fully populated config produces 16.
# Tests below pass the appropriate count so tripwire's strict interaction
# tracking stays in balance.
_CALLS_EMPTY = 14
_CALLS_FULL = 16


def _mock_config_get(values: dict, expected_calls: int):
    """Install a tripwire mock for ``spellbook.worker_llm.config.config_get``.

    Pre-loads the FIFO queue with ``expected_calls`` entries that each
    return ``values.get(key)``. Caller must invoke
    ``_assert_config_get_calls(mock, expected_calls)`` after the
    ``with tripwire:`` block so every interaction is asserted.
    """
    mock = tripwire.mock("spellbook.worker_llm.config:config_get")
    fn = lambda key: values.get(key)  # noqa: E731
    for _ in range(expected_calls):
        mock.calls(fn)
    return mock


def _assert_config_get_calls(mock, expected_calls: int) -> None:
    """Consume the recorded interactions with a wildcard string matcher.

    Uses ``in_any_order`` because the test cares about the snapshot
    produced by ``get_worker_config`` rather than the exact per-key read
    sequence.
    """
    with tripwire.in_any_order():
        for _ in range(expected_calls):
            mock.assert_call(args=(IsStr(),), kwargs={})


def test_unconfigured_returns_false():
    mock = _mock_config_get({}, _CALLS_EMPTY)
    with tripwire:
        cfg = wl_config.get_worker_config()
        assert cfg.base_url == ""
        assert cfg.model == ""
        assert wl_config.is_configured(cfg) is False
    _assert_config_get_calls(mock, _CALLS_EMPTY)


def test_configured_reads_all_keys():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
        "worker_llm_api_key": "token-123",
        "worker_llm_timeout_s": 2.0,
        "worker_llm_max_tokens": 256,
        "worker_llm_tool_safety_timeout_s": 0.8,
        "worker_llm_transcript_harvest_mode": "merge",
        "worker_llm_allow_prompt_overrides": False,
        "worker_llm_read_claude_memory": True,
        "worker_llm_feature_transcript_harvest": True,
        "worker_llm_feature_tool_safety": True,
        "worker_llm_feature_roundtable": False,
        "worker_llm_feature_memory_rerank": False,
        "worker_llm_safety_cache_ttl_s": 600,
    }
    mock = _mock_config_get(vals, _CALLS_FULL)
    with tripwire:
        cfg = wl_config.get_worker_config()
        assert cfg.base_url == "http://x/v1"
        assert cfg.model == "m"
        assert cfg.api_key == "token-123"
        assert cfg.timeout_s == 2.0
        assert cfg.max_tokens == 256
        assert cfg.tool_safety_timeout_s == 0.8
        assert cfg.transcript_harvest_mode == "merge"
        assert cfg.allow_prompt_overrides is False
        assert cfg.read_claude_memory is True
        assert cfg.feature_transcript_harvest is True
        assert cfg.feature_tool_safety is True
        assert cfg.feature_roundtable is False
        assert cfg.feature_memory_rerank is False
        assert cfg.safety_cache_ttl_s == 600
        assert wl_config.is_configured(cfg) is True
    _assert_config_get_calls(mock, _CALLS_FULL)


def test_defaults_when_keys_absent():
    mock = _mock_config_get({}, _CALLS_EMPTY)
    with tripwire:
        cfg = wl_config.get_worker_config()
        assert cfg.timeout_s == 10.0
        assert cfg.max_tokens == 1024
        assert cfg.tool_safety_timeout_s == 1.5
        assert cfg.transcript_harvest_mode == "replace"
        assert cfg.allow_prompt_overrides is True
        assert cfg.read_claude_memory is False
        assert cfg.feature_transcript_harvest is False
        assert cfg.feature_roundtable is False
        assert cfg.feature_memory_rerank is False
        assert cfg.feature_tool_safety is False
        assert cfg.safety_cache_ttl_s == 300
    _assert_config_get_calls(mock, _CALLS_EMPTY)


def test_feature_enabled_requires_endpoint():
    # Only feature_roundtable set; the two conditional keys fall through
    # to their else branches, so the empty-path count applies.
    vals = {"worker_llm_feature_roundtable": True}
    mock = _mock_config_get(vals, _CALLS_EMPTY)
    with tripwire:
        assert wl_config.feature_enabled("roundtable") is False
    _assert_config_get_calls(mock, _CALLS_EMPTY)


def test_feature_enabled_requires_feature_flag():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
        "worker_llm_feature_roundtable": False,
    }
    mock = _mock_config_get(vals, _CALLS_EMPTY)
    with tripwire:
        assert wl_config.feature_enabled("roundtable") is False
    _assert_config_get_calls(mock, _CALLS_EMPTY)


def test_feature_enabled_happy():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
        "worker_llm_feature_roundtable": True,
    }
    mock = _mock_config_get(vals, _CALLS_EMPTY)
    with tripwire:
        assert wl_config.feature_enabled("roundtable") is True
    _assert_config_get_calls(mock, _CALLS_EMPTY)


def test_feature_enabled_all_four_features():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
        "worker_llm_feature_transcript_harvest": True,
        "worker_llm_feature_roundtable": True,
        "worker_llm_feature_memory_rerank": True,
        "worker_llm_feature_tool_safety": True,
    }
    # Four feature_enabled() calls, each issuing an empty-path get_worker_config.
    n = _CALLS_EMPTY * 4
    mock = _mock_config_get(vals, n)
    with tripwire:
        assert wl_config.feature_enabled("transcript_harvest") is True
        assert wl_config.feature_enabled("roundtable") is True
        assert wl_config.feature_enabled("memory_rerank") is True
        assert wl_config.feature_enabled("tool_safety") is True
    _assert_config_get_calls(mock, n)


def test_unknown_feature_raises_value_error():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
    }
    mock = _mock_config_get(vals, _CALLS_EMPTY)
    with tripwire:
        with pytest.raises(ValueError) as excinfo:
            wl_config.feature_enabled("nonexistent")
        assert str(excinfo.value) == "Unknown worker-llm feature: nonexistent"
    _assert_config_get_calls(mock, _CALLS_EMPTY)


def test_is_configured_no_model_returns_false():
    vals = {"worker_llm_base_url": "http://x/v1", "worker_llm_model": ""}
    mock = _mock_config_get(vals, _CALLS_EMPTY)
    with tripwire:
        cfg = wl_config.get_worker_config()
        assert wl_config.is_configured(cfg) is False
    _assert_config_get_calls(mock, _CALLS_EMPTY)


def test_is_configured_no_base_url_returns_false():
    vals = {"worker_llm_base_url": "", "worker_llm_model": "m"}
    mock = _mock_config_get(vals, _CALLS_EMPTY)
    with tripwire:
        cfg = wl_config.get_worker_config()
        assert wl_config.is_configured(cfg) is False
    _assert_config_get_calls(mock, _CALLS_EMPTY)


class TestObservabilityCoreDefaults:
    """The 7 ``worker_llm_observability_*`` keys carry well-known defaults
    in ``spellbook/core/config.py::CONFIG_DEFAULTS`` so ``config_get`` can
    serve them to the purge loop and threshold evaluator without the user
    having to set each one explicitly in ``spellbook.json``.
    """

    def test_retention_hours_default(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        assert CONFIG_DEFAULTS["worker_llm_observability_retention_hours"] == 24
        assert isinstance(
            CONFIG_DEFAULTS["worker_llm_observability_retention_hours"], int
        )

    def test_max_rows_default(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        assert CONFIG_DEFAULTS["worker_llm_observability_max_rows"] == 10000
        assert isinstance(
            CONFIG_DEFAULTS["worker_llm_observability_max_rows"], int
        )

    def test_purge_interval_seconds_default(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        assert (
            CONFIG_DEFAULTS["worker_llm_observability_purge_interval_seconds"]
            == 300
        )
        assert isinstance(
            CONFIG_DEFAULTS["worker_llm_observability_purge_interval_seconds"], int
        )

    def test_notify_enabled_default(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        assert (
            CONFIG_DEFAULTS["worker_llm_observability_notify_enabled"] is False
        )
        # bool check: must be a bool, not 0/1 int. `is False` already asserts
        # this but we keep the explicit isinstance for symmetry with the
        # numeric cases below.
        assert isinstance(
            CONFIG_DEFAULTS["worker_llm_observability_notify_enabled"], bool
        )

    def test_notify_threshold_default(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        assert (
            CONFIG_DEFAULTS["worker_llm_observability_notify_threshold"] == 0.8
        )
        assert isinstance(
            CONFIG_DEFAULTS["worker_llm_observability_notify_threshold"], float
        )

    def test_notify_window_default(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        assert CONFIG_DEFAULTS["worker_llm_observability_notify_window"] == 20
        assert isinstance(
            CONFIG_DEFAULTS["worker_llm_observability_notify_window"], int
        )

    def test_notify_eval_interval_seconds_default(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        assert (
            CONFIG_DEFAULTS[
                "worker_llm_observability_notify_eval_interval_seconds"
            ]
            == 60
        )
        assert isinstance(
            CONFIG_DEFAULTS[
                "worker_llm_observability_notify_eval_interval_seconds"
            ],
            int,
        )

    def test_all_seven_observability_keys_present(self):
        from spellbook.core.config import CONFIG_DEFAULTS

        expected = {
            "worker_llm_observability_retention_hours",
            "worker_llm_observability_max_rows",
            "worker_llm_observability_purge_interval_seconds",
            "worker_llm_observability_notify_enabled",
            "worker_llm_observability_notify_threshold",
            "worker_llm_observability_notify_window",
            "worker_llm_observability_notify_eval_interval_seconds",
        }
        observability_keys = {
            k for k in CONFIG_DEFAULTS if k.startswith("worker_llm_observability_")
        }
        assert observability_keys == expected
