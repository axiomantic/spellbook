"""Tests for TTS detection and setup in install.py.

Task 16: The installer should detect whether kokoro is importable and,
if available, prompt the user to enable TTS. The --yes flag auto-enables,
dry-run skips, and declining sets tts_enabled=False.

When kokoro is NOT installed, the installer should offer to install it
rather than silently skipping.

Note: check_tts_available() now checks kokoro in the daemon venv by
shelling out to the daemon venv Python, not by importing in-process.
Tests mock get_daemon_python and subprocess.run accordingly.
"""

import json
import subprocess
import sys
from pathlib import Path

import bigfoot

# install.py is the top-level script; we import from it directly
from install import check_tts_available, setup_tts, _set_tts_config


_FAKE_PYTHON_STR = "/fake/daemon-venv/bin/python"
_KOKORO_IMPORT_CMD = [_FAKE_PYTHON_STR, "-c", "import kokoro"]

# Prompt strings from install.py
_ENABLE_PROMPT = "Kokoro TTS detected. Enable text-to-speech notifications?"
_INSTALL_PROMPT = "Install text-to-speech notifications? (Kokoro TTS, ~500MB download)"

# Print messages from install.py (for TTS enabled path)
_TTS_ENABLED_MSG = "TTS enabled (voice: af_heart, volume: 0.3)"
_TTS_SETTINGS_MSG = "Change settings with tts_session_set or tts_config_set MCP tools"
_TTS_DISABLED_MSG = "TTS disabled. Enable later with tts_config_set MCP tool"
_TTS_INSTALLED_MSG = "TTS fully installed and enabled"
_TTS_INSTALL_FAILED_MSG = "TTS installation failed. Install manually:"
_TTS_INSTALL_INFO_MSG = "Install TTS deps into daemon venv via installer.components.mcp"
_TTS_SKIPPED_MSG = (
    "TTS skipped. Install later via installer.components.mcp.install_tts_to_daemon_venv()"
)


class _FakePath:
    """Minimal Path-like object for testing."""

    def __init__(self, path_str, exists=True):
        self._path = path_str
        self._exists = exists

    def exists(self):
        return self._exists

    def __str__(self):
        return self._path


class _FakeResult:
    """Minimal subprocess result for testing."""

    def __init__(self, returncode):
        self.returncode = returncode


def _mock_print_side_effects():
    """Set up optional print mocks that may be called 0+ times.

    Returns dict of mock proxies for assertion.
    """
    ps = bigfoot.mock("install:print_success")
    ps.__call__.required(False).returns(None)
    pi = bigfoot.mock("install:print_info")
    for _ in range(6):
        pi.__call__.required(False).returns(None)
    return {"print_success": ps, "print_info": pi}


# ---------------------------------------------------------------------------
# check_tts_available()
# ---------------------------------------------------------------------------


class TestCheckTtsAvailable:
    """check_tts_available() returns True iff kokoro is importable in daemon venv."""

    def test_returns_true_when_kokoro_importable(self):
        """When daemon venv exists and kokoro imports successfully, return True."""
        fake_python = _FakePath(_FAKE_PYTHON_STR, exists=True)
        fake_result = _FakeResult(returncode=0)

        mock_gdp = bigfoot.mock("installer.components.mcp:get_daemon_python")
        mock_gdp.returns(fake_python)
        mock_run = bigfoot.mock("install:subprocess.run")
        mock_run.returns(fake_result)

        with bigfoot:
            assert check_tts_available() is True

        mock_gdp.assert_call(args=(), kwargs={})
        mock_run.assert_call(
            args=(_KOKORO_IMPORT_CMD,),
            kwargs={"capture_output": True, "timeout": 30},
        )

    def test_returns_false_when_kokoro_not_importable(self):
        """When daemon venv exists but kokoro import fails, return False."""
        fake_python = _FakePath(_FAKE_PYTHON_STR, exists=True)
        fake_result = _FakeResult(returncode=1)

        mock_gdp = bigfoot.mock("installer.components.mcp:get_daemon_python")
        mock_gdp.returns(fake_python)
        mock_run = bigfoot.mock("install:subprocess.run")
        mock_run.returns(fake_result)

        with bigfoot:
            assert check_tts_available() is False

        mock_gdp.assert_call(args=(), kwargs={})
        mock_run.assert_call(
            args=(_KOKORO_IMPORT_CMD,),
            kwargs={"capture_output": True, "timeout": 30},
        )

    def test_returns_false_when_daemon_venv_missing(self):
        """When daemon venv Python does not exist, return False."""
        fake_python = _FakePath(_FAKE_PYTHON_STR, exists=False)

        mock_gdp = bigfoot.mock("installer.components.mcp:get_daemon_python")
        mock_gdp.returns(fake_python)

        with bigfoot:
            assert check_tts_available() is False

        mock_gdp.assert_call(args=(), kwargs={})


# ---------------------------------------------------------------------------
# setup_tts() - Interactive mode (kokoro available)
# ---------------------------------------------------------------------------


class TestSetupTtsInteractive:
    """setup_tts() in interactive mode should prompt and set config."""

    def test_prompts_user_when_kokoro_available_and_interactive(self):
        """When kokoro is available and running interactively, prompt user."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(True)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_ENABLE_PROMPT,),
                kwargs={"default": True, "auto_yes": False},
            )
            mock_config.assert_call(args=(True,), kwargs={})
            prints["print_success"].assert_call(args=(_TTS_ENABLED_MSG,), kwargs={})
            prints["print_info"].assert_call(args=(_TTS_SETTINGS_MSG,), kwargs={})

    def test_enables_tts_when_user_accepts(self):
        """When user answers 'y', tts_enabled should be set to True."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(True)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_ENABLE_PROMPT,),
                kwargs={"default": True, "auto_yes": False},
            )
            mock_config.assert_call(args=(True,), kwargs={})
            prints["print_success"].assert_call(args=(_TTS_ENABLED_MSG,), kwargs={})
            prints["print_info"].assert_call(args=(_TTS_SETTINGS_MSG,), kwargs={})

    def test_disables_tts_when_user_declines(self):
        """When user declines, tts_enabled should be set to False."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(False)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_ENABLE_PROMPT,),
                kwargs={"default": True, "auto_yes": False},
            )
            mock_config.assert_call(args=(False,), kwargs={})
            prints["print_info"].assert_call(args=(_TTS_DISABLED_MSG,), kwargs={})


# ---------------------------------------------------------------------------
# setup_tts() - Auto-yes mode
# ---------------------------------------------------------------------------


class TestSetupTtsAutoYes:
    """setup_tts() with auto_yes=True should enable without prompting."""

    def test_auto_yes_enables_tts_without_prompt(self):
        """--yes flag should auto-enable TTS without user input."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(True)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=True)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_ENABLE_PROMPT,),
                kwargs={"default": True, "auto_yes": True},
            )
            mock_config.assert_call(args=(True,), kwargs={})
            prints["print_success"].assert_call(args=(_TTS_ENABLED_MSG,), kwargs={})
            prints["print_info"].assert_call(args=(_TTS_SETTINGS_MSG,), kwargs={})


# ---------------------------------------------------------------------------
# setup_tts() - EOFError and edge cases
# ---------------------------------------------------------------------------


class TestSetupTtsEdgeCases:
    """setup_tts() handles EOFError and prompt_yn integration."""

    def test_eof_error_does_not_crash(self):
        """EOFError during prompt_yn should not crash setup_tts."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        # Simulate prompt_yn returning False (as it does on EOFError)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(False)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_ENABLE_PROMPT,),
                kwargs={"default": True, "auto_yes": False},
            )
            mock_config.assert_call(args=(False,), kwargs={})
            prints["print_info"].assert_call(args=(_TTS_DISABLED_MSG,), kwargs={})

    def test_calls_prompt_yn_with_correct_arguments(self):
        """setup_tts should call prompt_yn with default=True and auto_yes forwarded."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(True)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_ENABLE_PROMPT,),
                kwargs={"default": True, "auto_yes": False},
            )
            mock_config.assert_call(args=(True,), kwargs={})
            prints["print_success"].assert_call(args=(_TTS_ENABLED_MSG,), kwargs={})
            prints["print_info"].assert_call(args=(_TTS_SETTINGS_MSG,), kwargs={})

    def test_calls_prompt_yn_with_auto_yes_forwarded(self):
        """setup_tts should forward auto_yes=True to prompt_yn."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(True)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=True)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_ENABLE_PROMPT,),
                kwargs={"default": True, "auto_yes": True},
            )
            mock_config.assert_call(args=(True,), kwargs={})
            prints["print_success"].assert_call(args=(_TTS_ENABLED_MSG,), kwargs={})
            prints["print_info"].assert_call(args=(_TTS_SETTINGS_MSG,), kwargs={})


# ---------------------------------------------------------------------------
# setup_tts() - Dry-run and skip cases
# ---------------------------------------------------------------------------


class TestSetupTtsSkipCases:
    """setup_tts() should skip TTS setup in certain conditions."""

    def test_dry_run_skips_tts(self):
        """In dry_run mode, TTS setup should be skipped entirely."""
        bigfoot.mock("install:check_tts_available").__call__.required(False).returns(True)
        bigfoot.mock("install:_set_tts_config").__call__.required(False).returns(None)

        with bigfoot:
            setup_tts(dry_run=True, auto_yes=False)

    def test_existing_config_skips_prompt(self):
        """When tts_enabled is already set in config, skip prompting."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(True)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(True)
        bigfoot.mock("install:prompt_yn").__call__.required(False).returns(True)
        bigfoot.mock("install:_set_tts_config").__call__.required(False).returns(None)
        mock_pi = bigfoot.mock("install:print_info")
        mock_pi.__call__.required(False).returns(None)

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_pi.assert_call(
                args=("TTS already configured (enabled=True)",), kwargs={},
            )

    def test_existing_disabled_config_skips_prompt(self):
        """When tts_enabled=False in config, skip prompting."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(False)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(False)
        bigfoot.mock("install:prompt_yn").__call__.required(False).returns(True)
        bigfoot.mock("install:_set_tts_config").__call__.required(False).returns(None)

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})


# ---------------------------------------------------------------------------
# setup_tts() - Kokoro not installed (offer to install)
# ---------------------------------------------------------------------------


class TestSetupTtsInstallOffer:
    """When kokoro is not installed, setup_tts should offer to install it."""

    def test_kokoro_unavailable_offers_install_interactive(self):
        """When kokoro not available interactively, prompt to install."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(False)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(False)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        mock_pi = bigfoot.mock("install:print_info")
        mock_pi.__call__.required(False).returns(None)

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_INSTALL_PROMPT,),
                kwargs={"default": False, "auto_yes": False},
            )
            mock_config.assert_call(args=(False,), kwargs={})
            mock_pi.assert_call(args=(_TTS_SKIPPED_MSG,), kwargs={})

    def test_kokoro_unavailable_non_interactive_sets_disabled(self):
        """In non-interactive mode, kokoro unavailable sets tts_enabled=False."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(False)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(False)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        mock_pi = bigfoot.mock("install:print_info")
        mock_pi.__call__.required(False).returns(None)

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_INSTALL_PROMPT,),
                kwargs={"default": False, "auto_yes": False},
            )
            mock_config.assert_call(args=(False,), kwargs={})
            mock_pi.assert_call(args=(_TTS_SKIPPED_MSG,), kwargs={})

    def test_kokoro_unavailable_auto_yes_does_not_auto_install(self):
        """--yes should NOT auto-install heavy TTS deps."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(False)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(False)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        mock_pi = bigfoot.mock("install:print_info")
        mock_pi.__call__.required(False).returns(None)

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=True)

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            # Key assertion: auto_yes=False is passed to prompt_yn, not True
            mock_prompt.assert_call(
                args=(_INSTALL_PROMPT,),
                kwargs={"default": False, "auto_yes": False},
            )
            mock_config.assert_call(args=(False,), kwargs={})
            mock_pi.assert_call(args=(_TTS_SKIPPED_MSG,), kwargs={})

    def test_kokoro_install_success_enables_tts(self):
        """When user accepts install and it succeeds, enable TTS."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(False)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(True)
        mock_install = bigfoot.mock("install:_install_tts_deps")
        mock_install.returns(True)
        mock_preload = bigfoot.mock("install:_preload_tts_model")
        mock_preload.returns(None)
        mock_config = bigfoot.mock("install:_set_tts_config")
        mock_config.returns(None)
        prints = _mock_print_side_effects()

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False, spellbook_dir=Path("/fake"))

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_INSTALL_PROMPT,),
                kwargs={"default": False, "auto_yes": False},
            )
            mock_install.assert_call(args=(Path("/fake"),), kwargs={})
            mock_preload.assert_call(args=(Path("/fake"),), kwargs={})
            mock_config.assert_call(args=(True,), kwargs={})
            prints["print_success"].assert_call(args=(_TTS_INSTALLED_MSG,), kwargs={})
            prints["print_info"].assert_call(
                args=("  Packages: kokoro, soundfile, sounddevice, spacy, misaki",), kwargs={},
            )
            prints["print_info"].assert_call(
                args=("  Models: Kokoro-82M (HuggingFace), en_core_web_sm (spacy)",), kwargs={},
            )
            prints["print_info"].assert_call(
                args=("  Voice: af_heart, Volume: 0.3",), kwargs={},
            )
            prints["print_info"].assert_call(
                args=("  Change settings with tts_session_set or tts_config_set MCP tools",),
                kwargs={},
            )

    def test_kokoro_install_failure_shows_error(self):
        """When install fails, show error message."""
        mock_cfg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cfg.returns(None)
        mock_check = bigfoot.mock("install:check_tts_available")
        mock_check.returns(False)
        mock_prompt = bigfoot.mock("install:prompt_yn")
        mock_prompt.returns(True)
        mock_install = bigfoot.mock("install:_install_tts_deps")
        mock_install.returns(False)
        bigfoot.mock("install:_set_tts_config").__call__.required(False).returns(None)
        mock_error = bigfoot.mock("install:print_error")
        mock_error.returns(None)
        mock_pi = bigfoot.mock("install:print_info")
        mock_pi.__call__.required(False).returns(None)

        with bigfoot:
            setup_tts(dry_run=False, auto_yes=False, spellbook_dir=Path("/fake"))

        with bigfoot.in_any_order():
            mock_cfg.assert_call(args=("tts_enabled",), kwargs={})
            mock_check.assert_call(args=(), kwargs={})
            mock_prompt.assert_call(
                args=(_INSTALL_PROMPT,),
                kwargs={"default": False, "auto_yes": False},
            )
            mock_install.assert_call(args=(Path("/fake"),), kwargs={})
            mock_error.assert_call(args=(_TTS_INSTALL_FAILED_MSG,), kwargs={})
            mock_pi.assert_call(args=(_TTS_INSTALL_INFO_MSG,), kwargs={})


# ---------------------------------------------------------------------------
# _set_tts_config() direct test
# ---------------------------------------------------------------------------


class TestSetTtsConfig:
    """_set_tts_config() persists the tts_enabled config value."""

    def test_writes_tts_enabled_to_config(self, tmp_path, monkeypatch):
        """Calling _set_tts_config writes tts_enabled to the config file."""
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")
        monkeypatch.setattr("spellbook.core.config.CONFIG_LOCK_PATH", tmp_path / "config.lock")

        mock_gcp = bigfoot.mock("spellbook.core.config:get_config_path")
        mock_gcp.returns(config_file)

        with bigfoot:
            _set_tts_config(True)

        mock_gcp.assert_call(args=(), kwargs={})
        data = json.loads(config_file.read_text())
        assert data["tts_enabled"] is True

    def test_writes_tts_disabled_to_config(self, tmp_path, monkeypatch):
        """Calling _set_tts_config(False) writes tts_enabled=False."""
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")
        monkeypatch.setattr("spellbook.core.config.CONFIG_LOCK_PATH", tmp_path / "config.lock")

        mock_gcp = bigfoot.mock("spellbook.core.config:get_config_path")
        mock_gcp.returns(config_file)

        with bigfoot:
            _set_tts_config(False)

        mock_gcp.assert_call(args=(), kwargs={})
        data = json.loads(config_file.read_text())
        assert data["tts_enabled"] is False
