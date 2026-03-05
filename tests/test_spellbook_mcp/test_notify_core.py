"""Tests for spellbook_mcp/notify.py - Core notification module.

Tests platform detection, availability checking, settings resolution,
send_notification async entry point, and get_status. All subprocess
and platform calls are mocked.
"""

import asyncio
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_notify_state():
    """Reset module-level notification state between tests."""
    import spellbook_mcp.notify as mod

    mod._notification_available = None
    mod._platform = None
    mod._unavailable_reason = None
    yield
    mod._notification_available = None
    mod._platform = None
    mod._unavailable_reason = None


class TestDetectPlatform:
    """_detect_platform() probes for container, SSH, and platform-specific tools."""

    def test_container_detected_via_dockerenv(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=True):
            with patch.dict(os.environ, {}, clear=True):
                platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "Running in a container (no display server)"

    def test_container_detected_via_env_var(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {"container": "podman"}, clear=True):
                platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "Running in a container (no display server)"

    def test_ssh_headless_detected(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {"SSH_TTY": "/dev/pts/0"}, clear=True):
                with patch("sys.platform", "linux"):
                    with patch("shutil.which", return_value="/usr/bin/notify-send"):
                        platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "SSH session without X11/Wayland forwarding"

    def test_ssh_with_x11_forwarding_succeeds(self):
        import spellbook_mcp.notify as mod

        env = {"SSH_TTY": "/dev/pts/0", "DISPLAY": ":0"}
        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, env, clear=True):
                with patch("sys.platform", "linux"):
                    with patch("shutil.which", return_value="/usr/bin/notify-send"):
                        platform, reason = mod._detect_platform()
        assert platform == "linux"
        assert reason is None

    def test_macos_with_osascript(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.platform", "darwin"):
                    with patch("shutil.which", return_value="/usr/bin/osascript"):
                        platform, reason = mod._detect_platform()
        assert platform == "macos"
        assert reason is None

    def test_macos_missing_osascript(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.platform", "darwin"):
                    with patch("shutil.which", return_value=None):
                        platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "macOS: osascript not found"

    def test_linux_with_notify_send_and_display(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True):
                with patch("sys.platform", "linux"):
                    with patch("shutil.which", return_value="/usr/bin/notify-send"):
                        platform, reason = mod._detect_platform()
        assert platform == "linux"
        assert reason is None

    def test_linux_with_wayland_display(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
                with patch("sys.platform", "linux"):
                    with patch("shutil.which", return_value="/usr/bin/notify-send"):
                        platform, reason = mod._detect_platform()
        assert platform == "linux"
        assert reason is None

    def test_linux_missing_notify_send(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True):
                with patch("sys.platform", "linux"):
                    with patch("shutil.which", return_value=None):
                        platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "Linux: notify-send not found (install libnotify-bin or libnotify)"

    def test_linux_no_display(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.platform", "linux"):
                    with patch("shutil.which", return_value="/usr/bin/notify-send"):
                        platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "Linux: no DISPLAY or WAYLAND_DISPLAY set (headless session)"

    def test_windows_with_pwsh(self):
        import spellbook_mcp.notify as mod

        def which_side_effect(name):
            if name == "pwsh":
                return r"C:\Windows\System32\pwsh.exe"
            return None

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.platform", "win32"):
                    with patch("shutil.which", side_effect=which_side_effect):
                        platform, reason = mod._detect_platform()
        assert platform == "windows"
        assert reason is None

    def test_windows_with_powershell_fallback(self):
        import spellbook_mcp.notify as mod

        def which_side_effect(name):
            if name == "powershell":
                return r"C:\Windows\System32\powershell.exe"
            return None

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.platform", "win32"):
                    with patch("shutil.which", side_effect=which_side_effect):
                        platform, reason = mod._detect_platform()
        assert platform == "windows"
        assert reason is None

    def test_windows_missing_powershell(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.platform", "win32"):
                    with patch("shutil.which", return_value=None):
                        platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "Windows: neither pwsh nor powershell found"

    def test_unknown_platform(self):
        import spellbook_mcp.notify as mod

        with patch("os.path.exists", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.platform", "freebsd"):
                    platform, reason = mod._detect_platform()
        assert platform is None
        assert reason == "Unknown platform or missing notification tools"


class TestCheckAvailability:
    """check_availability() caches detection result."""

    def test_returns_available_on_macos(self):
        import spellbook_mcp.notify as mod

        with patch.object(mod, "_detect_platform", return_value=("macos", None)):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = mod.check_availability()
        assert result["available"] is True
        assert result["platform"] == "macos"
        assert result["reason"] is None

    def test_returns_unavailable_when_detection_fails(self):
        import spellbook_mcp.notify as mod

        with patch.object(mod, "_detect_platform", return_value=(None, "test reason")):
            result = mod.check_availability()
        assert result["available"] is False
        assert result["platform"] is None
        assert result["reason"] == "test reason"

    def test_caches_result_on_second_call(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        # _detect_platform should NOT be called since result is cached
        with patch.object(mod, "_detect_platform") as mock_detect:
            result = mod.check_availability()
        mock_detect.assert_not_called()
        assert result["available"] is True
        assert result["platform"] == "macos"

    def test_macos_permission_test_failure(self):
        import spellbook_mcp.notify as mod

        with patch.object(mod, "_detect_platform", return_value=("macos", None)):
            with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "osascript")):
                result = mod.check_availability()
        assert result["available"] is False
        assert result["platform"] == "macos"
        assert "notification test failed" in result["reason"]

    def test_linux_skips_permission_test(self):
        import spellbook_mcp.notify as mod

        with patch.object(mod, "_detect_platform", return_value=("linux", None)):
            with patch("subprocess.run") as mock_run:
                result = mod.check_availability()
        # Linux does not trigger a test notification (no subprocess.run call)
        mock_run.assert_not_called()
        assert result["available"] is True
        assert result["platform"] == "linux"


class TestResolveSetting:
    """_resolve_setting() follows explicit > session > config > default priority."""

    def test_explicit_value_wins(self):
        import spellbook_mcp.notify as mod

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {"enabled": False}}
            mock_ct.config_get.return_value = False
            result = mod._resolve_setting("enabled", explicit_value=True)
        assert result is True

    def test_session_override_wins_over_config(self):
        import spellbook_mcp.notify as mod

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {"title": "Session Title"}}
            mock_ct.config_get.return_value = "Config Title"
            result = mod._resolve_setting("title")
        assert result == "Session Title"

    def test_config_wins_over_default(self):
        import spellbook_mcp.notify as mod

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = "Custom Title"
            result = mod._resolve_setting("title")
        assert result == "Custom Title"

    def test_falls_back_to_default_enabled(self):
        import spellbook_mcp.notify as mod

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            result = mod._resolve_setting("enabled")
        assert result is True

    def test_falls_back_to_default_title(self):
        import spellbook_mcp.notify as mod

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            result = mod._resolve_setting("title")
        assert result == "Spellbook"


class TestSendNotification:
    """send_notification() is the async entry point."""

    @pytest.mark.asyncio
    async def test_calls_send_sync_when_enabled_and_available(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            mock_ct.NOTIFY_DEFAULT_ENABLED = True
            mock_ct.NOTIFY_DEFAULT_TITLE = "Spellbook"
            with patch.object(mod, "_send_sync") as mock_send:
                with patch("asyncio.to_thread", side_effect=lambda fn, *a: fn(*a)):
                    result = await mod.send_notification(body="test body")
        assert result == {"ok": True}
        mock_send.assert_called_once_with("Spellbook", "test body")

    @pytest.mark.asyncio
    async def test_returns_early_when_disabled(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {"enabled": False}}
            mock_ct.config_get.return_value = None
            result = await mod.send_notification(body="test")
        assert "error" in result
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_returns_early_when_unavailable(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = False
        mod._platform = None
        mod._unavailable_reason = "Missing tools"

        result = await mod.send_notification(body="test")
        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handles_subprocess_error_gracefully(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            mock_ct.NOTIFY_DEFAULT_ENABLED = True
            mock_ct.NOTIFY_DEFAULT_TITLE = "Spellbook"
            with patch.object(
                mod, "_send_sync",
                side_effect=subprocess.CalledProcessError(1, "osascript"),
            ):
                with patch("asyncio.to_thread", side_effect=lambda fn, *a: fn(*a)):
                    result = await mod.send_notification(body="test")
        assert "error" in result
        assert "failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_uses_explicit_title(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = True
        mod._platform = "linux"
        mod._unavailable_reason = None

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            mock_ct.NOTIFY_DEFAULT_ENABLED = True
            mock_ct.NOTIFY_DEFAULT_TITLE = "Spellbook"
            with patch.object(mod, "_send_sync") as mock_send:
                with patch("asyncio.to_thread", side_effect=lambda fn, *a: fn(*a)):
                    result = await mod.send_notification(
                        title="Custom", body="body text"
                    )
        assert result == {"ok": True}
        mock_send.assert_called_once_with("Custom", "body text")


class TestGetStatus:
    """get_status() returns notification availability and settings."""

    def test_status_when_available(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            mock_ct.NOTIFY_DEFAULT_ENABLED = True
            mock_ct.NOTIFY_DEFAULT_TITLE = "Spellbook"
            status = mod.get_status()
        assert status["available"] is True
        assert status["enabled"] is True
        assert status["platform"] == "macos"
        assert status["title"] == "Spellbook"
        assert status["error"] is None

    def test_status_when_not_available(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = False
        mod._platform = None
        mod._unavailable_reason = "Missing tools"

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            mock_ct.NOTIFY_DEFAULT_ENABLED = True
            mock_ct.NOTIFY_DEFAULT_TITLE = "Spellbook"
            status = mod.get_status()
        assert status["available"] is False
        assert status["error"] == "Missing tools"

    def test_status_returns_all_expected_keys(self):
        import spellbook_mcp.notify as mod

        mod._notification_available = True
        mod._platform = "linux"
        mod._unavailable_reason = None

        with patch("spellbook_mcp.notify.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"notify": {}}
            mock_ct.config_get.return_value = None
            mock_ct.NOTIFY_DEFAULT_ENABLED = True
            mock_ct.NOTIFY_DEFAULT_TITLE = "Spellbook"
            status = mod.get_status()
        expected_keys = {"available", "enabled", "platform", "title", "error"}
        assert set(status.keys()) == expected_keys
