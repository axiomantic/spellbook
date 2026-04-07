"""Tests for extended tts_status with service health fields."""

from pathlib import Path

import bigfoot
import pytest

from spellbook.notifications.tts import get_status


class TestGetStatusServiceFields:
    """Test that get_status includes service health info when TTS service is managed."""

    def test_includes_service_dict_when_deps_installed(self):
        mock_get = bigfoot.mock("spellbook.notifications.tts:config_tools.config_get")
        # Call order in get_status():
        # 1. tts_wyoming_host, 2. tts_wyoming_port (top of get_status)
        # 3-5. _resolve_setting("enabled"/"voice"/"volume") each call config_get
        # 6. tts_deps_installed, 7. tts_service_installed, 8. tts_device
        mock_get.returns(None)       # 1: tts_wyoming_host -> use default
        mock_get.returns(None)       # 2: tts_wyoming_port -> use default
        mock_get.returns(True)       # 3: tts_enabled
        mock_get.returns("af_heart") # 4: tts_voice
        mock_get.returns(0.3)        # 5: tts_volume
        mock_get.returns(True)       # 6: tts_deps_installed
        mock_get.returns(True)       # 7: tts_service_installed
        mock_get.returns("mps")      # 8: tts_device

        mock_session = bigfoot.mock("spellbook.notifications.tts:config_tools._get_session_state")
        mock_session.returns({})     # for enabled
        mock_session.returns({})     # for voice
        mock_session.returns({})     # for volume

        with bigfoot:
            status = get_status()

        # Assert all mock interactions in order
        mock_get.assert_call(args=("tts_wyoming_host",), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_voice",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_volume",), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_get.assert_call(args=("tts_device",), kwargs={})

        assert status == {
            "available": True,
            "enabled": True,
            "server_reachable": False,
            "voice": "af_heart",
            "volume": 0.3,
            "tts_wyoming_host": "127.0.0.1",
            "tts_wyoming_port": 10200,
            "error": None,
            "service": {
                "deps_installed": True,
                "service_installed": True,
                "device": "mps",
                "provisioning": False,
                "data_dir": str(Path.home() / ".local" / "spellbook" / "tts-data"),
                "venv_dir": str(Path.home() / ".local" / "spellbook" / "tts-venv"),
                "log_file": str(Path.home() / ".local" / "spellbook" / "logs" / "tts.log"),
            },
        }

    def test_includes_service_dict_when_only_deps_installed(self):
        mock_get = bigfoot.mock("spellbook.notifications.tts:config_tools.config_get")
        mock_get.returns(None)       # 1: tts_wyoming_host
        mock_get.returns(None)       # 2: tts_wyoming_port
        mock_get.returns(True)       # 3: tts_enabled
        mock_get.returns("af_heart") # 4: tts_voice
        mock_get.returns(0.3)        # 5: tts_volume
        mock_get.returns(True)       # 6: tts_deps_installed
        mock_get.returns(None)       # 7: tts_service_installed (not yet)
        mock_get.returns(None)       # 8: tts_device

        mock_session = bigfoot.mock("spellbook.notifications.tts:config_tools._get_session_state")
        mock_session.returns({})
        mock_session.returns({})
        mock_session.returns({})

        with bigfoot:
            status = get_status()

        mock_get.assert_call(args=("tts_wyoming_host",), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_voice",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_volume",), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_get.assert_call(args=("tts_device",), kwargs={})

        assert status["service"] == {
            "deps_installed": True,
            "service_installed": False,
            "device": "unknown",
            "provisioning": False,
            "data_dir": str(Path.home() / ".local" / "spellbook" / "tts-data"),
            "venv_dir": str(Path.home() / ".local" / "spellbook" / "tts-venv"),
            "log_file": str(Path.home() / ".local" / "spellbook" / "logs" / "tts.log"),
        }

    def test_no_service_dict_when_not_installed(self):
        mock_get = bigfoot.mock("spellbook.notifications.tts:config_tools.config_get")
        mock_get.returns(None)       # 1: tts_wyoming_host
        mock_get.returns(None)       # 2: tts_wyoming_port
        mock_get.returns(None)       # 3: tts_enabled
        mock_get.returns(None)       # 4: tts_voice
        mock_get.returns(None)       # 5: tts_volume
        mock_get.returns(None)       # 6: tts_deps_installed
        mock_get.returns(None)       # 7: tts_service_installed

        mock_session = bigfoot.mock("spellbook.notifications.tts:config_tools._get_session_state")
        mock_session.returns({})
        mock_session.returns({})
        mock_session.returns({})

        with bigfoot:
            status = get_status()

        mock_get.assert_call(args=("tts_wyoming_host",), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_voice",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_volume",), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})

        # When config returns None for all settings, _resolve_setting falls
        # through to defaults: enabled=True, voice="", volume=0.3
        assert status == {
            "available": True,
            "enabled": True,
            "server_reachable": False,
            "voice": "",
            "volume": 0.3,
            "tts_wyoming_host": "127.0.0.1",
            "tts_wyoming_port": 10200,
            "error": None,
        }

    def test_service_device_defaults_to_unknown_when_none(self):
        mock_get = bigfoot.mock("spellbook.notifications.tts:config_tools.config_get")
        mock_get.returns(None)       # 1: tts_wyoming_host
        mock_get.returns(None)       # 2: tts_wyoming_port
        mock_get.returns(True)       # 3: tts_enabled
        mock_get.returns("af_heart") # 4: tts_voice
        mock_get.returns(0.3)        # 5: tts_volume
        mock_get.returns(False)      # 6: tts_deps_installed
        mock_get.returns(True)       # 7: tts_service_installed
        mock_get.returns(None)       # 8: tts_device (None -> "unknown")

        mock_session = bigfoot.mock("spellbook.notifications.tts:config_tools._get_session_state")
        mock_session.returns({})
        mock_session.returns({})
        mock_session.returns({})

        with bigfoot:
            status = get_status()

        mock_get.assert_call(args=("tts_wyoming_host",), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_voice",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_get.assert_call(args=("tts_volume",), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_get.assert_call(args=("tts_device",), kwargs={})

        assert status["service"]["device"] == "unknown"
        assert status["service"]["service_installed"] is True
        assert status["service"]["deps_installed"] is False
