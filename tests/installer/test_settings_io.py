"""Tests for installer.components._settings_io."""

import json

import pytest

from installer.components._settings_io import read_settings


def test_read_settings_returns_empty_when_file_absent(tmp_path):
    assert read_settings(tmp_path / "missing.json") == {}


def test_read_settings_returns_empty_when_file_empty(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("", encoding="utf-8")
    assert read_settings(p) == {}


def test_read_settings_returns_empty_when_file_whitespace_only(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("   \n\t\n", encoding="utf-8")
    assert read_settings(p) == {}


def test_read_settings_returns_dict_when_object(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": {"PreToolUse": []}}), encoding="utf-8")
    assert read_settings(p) == {"hooks": {"PreToolUse": []}}


@pytest.mark.parametrize(
    "payload",
    [
        "null",
        "[]",
        '["item"]',
        "42",
        '"a string"',
        "true",
        "false",
    ],
    ids=["null", "empty_array", "array", "number", "string", "true", "false"],
)
def test_read_settings_returns_empty_for_non_object_top_level(tmp_path, payload):
    p = tmp_path / "settings.json"
    p.write_text(payload, encoding="utf-8")
    assert read_settings(p) == {}


def test_read_settings_raises_on_malformed_json(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not valid", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_settings(p)
