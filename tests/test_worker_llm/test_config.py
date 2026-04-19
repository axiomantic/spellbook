"""Tests for ``spellbook.worker_llm.config``."""

from unittest.mock import patch

import pytest

from spellbook.worker_llm import config as wl_config


def _patched_get(values: dict):
    return lambda key: values.get(key)


def test_unconfigured_returns_false():
    with patch("spellbook.worker_llm.config.config_get", _patched_get({})):
        cfg = wl_config.get_worker_config()
        assert cfg.base_url == ""
        assert cfg.model == ""
        assert wl_config.is_configured(cfg) is False


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
    }
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
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
        assert wl_config.is_configured(cfg) is True


def test_defaults_when_keys_absent():
    with patch("spellbook.worker_llm.config.config_get", _patched_get({})):
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


def test_feature_enabled_requires_endpoint():
    vals = {"worker_llm_feature_roundtable": True}  # no base_url
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
        assert wl_config.feature_enabled("roundtable") is False


def test_feature_enabled_requires_feature_flag():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
        "worker_llm_feature_roundtable": False,
    }
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
        assert wl_config.feature_enabled("roundtable") is False


def test_feature_enabled_happy():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
        "worker_llm_feature_roundtable": True,
    }
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
        assert wl_config.feature_enabled("roundtable") is True


def test_feature_enabled_all_four_features():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
        "worker_llm_feature_transcript_harvest": True,
        "worker_llm_feature_roundtable": True,
        "worker_llm_feature_memory_rerank": True,
        "worker_llm_feature_tool_safety": True,
    }
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
        assert wl_config.feature_enabled("transcript_harvest") is True
        assert wl_config.feature_enabled("roundtable") is True
        assert wl_config.feature_enabled("memory_rerank") is True
        assert wl_config.feature_enabled("tool_safety") is True


def test_unknown_feature_raises_value_error():
    vals = {
        "worker_llm_base_url": "http://x/v1",
        "worker_llm_model": "m",
    }
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
        with pytest.raises(ValueError) as excinfo:
            wl_config.feature_enabled("nonexistent")
        assert str(excinfo.value) == "Unknown worker-llm feature: nonexistent"


def test_is_configured_no_model_returns_false():
    vals = {"worker_llm_base_url": "http://x/v1", "worker_llm_model": ""}
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
        cfg = wl_config.get_worker_config()
        assert wl_config.is_configured(cfg) is False


def test_is_configured_no_base_url_returns_false():
    vals = {"worker_llm_base_url": "", "worker_llm_model": "m"}
    with patch("spellbook.worker_llm.config.config_get", _patched_get(vals)):
        cfg = wl_config.get_worker_config()
        assert wl_config.is_configured(cfg) is False
