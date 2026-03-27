"""Tests for TTS detection and setup in install.py.

The installer checks whether a Wyoming TTS server is reachable and,
if available, prompts the user to enable TTS. The --yes flag auto-enables
when server is reachable, dry-run skips, and declining sets tts_enabled=False.

When the server is NOT reachable, the installer offers to enable anyway
with a note about starting a Wyoming server.
"""

import json
from pathlib import Path

import bigfoot

# install.py is the top-level script; we import from it directly
from install import check_tts_available, setup_tts, _set_tts_config


# Prompt strings from install.py
_ENABLE_PROMPT = "Wyoming TTS server detected. Enable text-to-speech notifications?"
_INSTALL_PROMPT = "Enable text-to-speech notifications? (Requires a Wyoming TTS server)"

# Print messages from install.py
_TTS_ENABLED_MSG = "TTS enabled"
_TTS_SETTINGS_MSG = "Change settings with tts_session_set or tts_config_set MCP tools"
_TTS_DISABLED_MSG = "TTS disabled. Enable later with tts_config_set MCP tool"
_TTS_SKIPPED_MSG = "TTS skipped. Enable later with tts_config_set MCP tool"


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
    """check_tts_available() returns True iff Wyoming server is reachable."""

    def test_returns_true_when_server_reachable(self, monkeypatch):
        """When Wyoming server accepts connection, return True."""
        from types import SimpleNamespace

        mock_conn = SimpleNamespace(close=lambda: None)
        monkeypatch.setattr("socket.create_connection", lambda *a, **kw: mock_conn)

        assert check_tts_available() is True

    def test_returns_false_when_server_unreachable(self, monkeypatch):
        """When Wyoming server refuses connection, return False."""
        def raise_oserror(*a, **kw):
            raise OSError("Connection refused")

        monkeypatch.setattr("socket.create_connection", raise_oserror)

        assert check_tts_available() is False

    def test_returns_false_on_import_error(self, monkeypatch):
        """When config import fails, return False."""
        def raise_exc(*a, **kw):
            raise Exception("import failed")

        monkeypatch.setattr("socket.create_connection", raise_exc)

        assert check_tts_available() is False


# ---------------------------------------------------------------------------
# setup_tts() - Interactive mode (server available)
# ---------------------------------------------------------------------------


class TestSetupTtsInteractive:
    """setup_tts() in interactive mode should prompt and set config."""

    def test_prompts_user_when_server_available_and_interactive(self):
        """When server is available and running interactively, prompt user."""
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
# setup_tts() - Server not available (offer to enable anyway)
# ---------------------------------------------------------------------------


class TestSetupTtsServerUnavailable:
    """When Wyoming server is not reachable, setup_tts should offer to enable anyway."""

    def test_server_unavailable_offers_enable(self):
        """When server not available interactively, prompt to enable."""
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

    def test_server_unavailable_auto_yes_does_not_auto_enable(self):
        """--yes should NOT auto-enable TTS when server is not available."""
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
