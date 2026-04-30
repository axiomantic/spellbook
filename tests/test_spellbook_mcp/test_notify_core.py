"""Tests for spellbook/notify.py - Core notification module.

Tests platform detection, availability checking, settings resolution,
send_notification async entry point, and get_status. All subprocess
and platform calls are mocked.
"""

import asyncio
import os
import subprocess

import tripwire
import pytest
from dirty_equals import IsInstance


@pytest.fixture(autouse=True)
def reset_notify_state():
    """Reset module-level notification state between tests."""
    import spellbook.notifications.notify as mod

    mod._notification_available = None
    mod._platform = None
    mod._unavailable_reason = None
    yield
    mod._notification_available = None
    mod._platform = None
    mod._unavailable_reason = None


class TestDetectPlatform:
    """_detect_platform() probes for container, SSH, and platform-specific tools."""

    def test_container_detected_via_dockerenv(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {})
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(True)

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "Running in a container (no display server)"
        mock_exists.assert_call(args=("/.dockerenv",))

    def test_container_detected_via_env_var(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {"container": "podman"})
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "Running in a container (no display server)"
        mock_exists.assert_call(args=("/.dockerenv",))

    def test_ssh_headless_detected(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {"SSH_TTY": "/dev/pts/0"})
        monkeypatch.setattr("sys.platform", "linux")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.__call__.required(False).returns("/usr/bin/notify-send")

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "SSH session without X11/Wayland forwarding"
        mock_exists.assert_call(args=("/.dockerenv",))

    def test_ssh_with_x11_forwarding_succeeds(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {"SSH_TTY": "/dev/pts/0", "DISPLAY": ":0"})
        monkeypatch.setattr("sys.platform", "linux")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.returns("/usr/bin/notify-send")

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform == "linux"
        assert reason is None
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("notify-send",))

    def test_macos_with_osascript(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {})
        monkeypatch.setattr("sys.platform", "darwin")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.returns("/usr/bin/osascript")

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform == "macos"
        assert reason is None
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("osascript",))

    def test_macos_missing_osascript(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {})
        monkeypatch.setattr("sys.platform", "darwin")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.returns(None)

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "macOS: osascript not found"
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("osascript",))

    def test_linux_with_notify_send_and_display(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {"DISPLAY": ":0"})
        monkeypatch.setattr("sys.platform", "linux")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.returns("/usr/bin/notify-send")

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform == "linux"
        assert reason is None
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("notify-send",))

    def test_linux_with_wayland_display(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {"WAYLAND_DISPLAY": "wayland-0"})
        monkeypatch.setattr("sys.platform", "linux")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.returns("/usr/bin/notify-send")

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform == "linux"
        assert reason is None
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("notify-send",))

    def test_linux_missing_notify_send(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {"DISPLAY": ":0"})
        monkeypatch.setattr("sys.platform", "linux")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.returns(None)

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "Linux: notify-send not found (install libnotify-bin or libnotify)"
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("notify-send",))

    def test_linux_no_display(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {})
        monkeypatch.setattr("sys.platform", "linux")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.returns("/usr/bin/notify-send")

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "Linux: no DISPLAY or WAYLAND_DISPLAY set (headless session)"
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("notify-send",))

    def test_windows_with_pwsh(self, monkeypatch):
        import spellbook.notifications.notify as mod

        def which_side_effect(name):
            if name == "pwsh":
                return r"C:\Windows\System32\pwsh.exe"
            return None

        monkeypatch.setattr(os, "environ", {})
        monkeypatch.setattr("sys.platform", "win32")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        mock_which.calls(which_side_effect)

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform == "windows"
        assert reason is None
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("pwsh",))

    def test_windows_with_powershell_fallback(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {})
        monkeypatch.setattr("sys.platform", "win32")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        # Called twice: which("pwsh") returns None, which("powershell") returns path
        mock_which.returns(None).calls(
            lambda name: r"C:\Windows\System32\powershell.exe"
            if name == "powershell"
            else None
        )

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform == "windows"
        assert reason is None
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("pwsh",))
        mock_which.assert_call(args=("powershell",))

    def test_windows_missing_powershell(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {})
        monkeypatch.setattr("sys.platform", "win32")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)
        mock_which = tripwire.mock("spellbook.notifications.notify:shutil.which")
        # which is called twice (pwsh, powershell), both return None
        mock_which.returns(None).returns(None)

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "Windows: neither pwsh nor powershell found"
        mock_exists.assert_call(args=("/.dockerenv",))
        mock_which.assert_call(args=("pwsh",))
        mock_which.assert_call(args=("powershell",))

    def test_unknown_platform(self, monkeypatch):
        import spellbook.notifications.notify as mod

        monkeypatch.setattr(os, "environ", {})
        monkeypatch.setattr("sys.platform", "freebsd")
        mock_exists = tripwire.mock("spellbook.notifications.notify:os.path.exists")
        mock_exists.returns(False)

        with tripwire:
            platform, reason = mod._detect_platform()

        assert platform is None
        assert reason == "Unknown platform or missing notification tools"
        mock_exists.assert_call(args=("/.dockerenv",))


class TestCheckAvailability:
    """check_availability() caches detection result."""

    def test_returns_available_on_macos(self):
        import spellbook.notifications.notify as mod

        mock_detect = tripwire.mock.object(mod, "_detect_platform")
        mock_detect.returns(("macos", None))
        mock_run = tripwire.mock("spellbook.notifications.notify:subprocess.run")
        mock_run.returns(subprocess.CompletedProcess(args=["osascript"], returncode=0))

        with tripwire:
            result = mod.check_availability()

        assert result["available"] is True
        assert result["platform"] == "macos"
        assert result["reason"] is None
        mock_detect.assert_call(args=(), kwargs={})
        mock_run.assert_call(
            args=(
                [
                    "osascript",
                    "-e",
                    'display notification "Spellbook notifications enabled" '
                    'with title "Spellbook"',
                ],
            ),
            kwargs={"capture_output": True, "timeout": 5, "check": True},
        )

    def test_returns_unavailable_when_detection_fails(self):
        import spellbook.notifications.notify as mod

        mock_detect = tripwire.mock.object(mod, "_detect_platform")
        mock_detect.returns((None, "test reason"))

        with tripwire:
            result = mod.check_availability()

        assert result["available"] is False
        assert result["platform"] is None
        assert result["reason"] == "test reason"
        mock_detect.assert_call(args=(), kwargs={})

    def test_caches_result_on_second_call(self):
        import spellbook.notifications.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        # _detect_platform should NOT be called since result is cached.
        # No expectations configured: if it IS called, tripwire raises.
        tripwire.mock.object(mod, "_detect_platform")

        with tripwire:
            result = mod.check_availability()

        assert result["available"] is True
        assert result["platform"] == "macos"

    def test_macos_permission_test_failure(self):
        import spellbook.notifications.notify as mod

        mock_detect = tripwire.mock.object(mod, "_detect_platform")
        mock_detect.returns(("macos", None))
        mock_run = tripwire.mock("spellbook.notifications.notify:subprocess.run")
        mock_run.raises(subprocess.CalledProcessError(1, "osascript"))

        with tripwire:
            result = mod.check_availability()

        assert result["available"] is False
        assert result["platform"] == "macos"
        assert "notification test failed" in result["reason"]
        mock_detect.assert_call(args=(), kwargs={})
        mock_run.assert_call(
            args=(
                [
                    "osascript",
                    "-e",
                    'display notification "Spellbook notifications enabled" '
                    'with title "Spellbook"',
                ],
            ),
            kwargs={"capture_output": True, "timeout": 5, "check": True},
            raised=IsInstance(subprocess.CalledProcessError),
        )
        tripwire.log.assert_log(
            "WARNING",
            "macOS notification test failed: Command 'osascript' returned "
            "non-zero exit status 1.",
            "spellbook.notifications.notify",
        )

    def test_linux_skips_permission_test(self):
        import spellbook.notifications.notify as mod

        mock_detect = tripwire.mock.object(mod, "_detect_platform")
        mock_detect.returns(("linux", None))
        # subprocess.run should NOT be called for Linux.
        # No expectations configured: if it IS called, tripwire raises.
        tripwire.mock("spellbook.notifications.notify:subprocess.run")

        with tripwire:
            result = mod.check_availability()

        assert result["available"] is True
        assert result["platform"] == "linux"
        mock_detect.assert_call(args=(), kwargs={})


class TestResolveSetting:
    """_resolve_setting() follows explicit > session > config > default priority."""

    def test_explicit_value_wins(self):
        import spellbook.notifications.notify as mod

        # No mocks needed: _resolve_setting returns immediately with explicit_value
        with tripwire:
            result = mod._resolve_setting("enabled", explicit_value=True)

        assert result is True

    def test_session_override_wins_over_config(self):
        import spellbook.notifications.notify as mod

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {"title": "Session Title"}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.__call__.required(False).returns("Config Title")

        with tripwire:
            result = mod._resolve_setting("title")

        assert result == "Session Title"
        mock_session.assert_call(args=(None,))

    def test_config_wins_over_default(self):
        import spellbook.notifications.notify as mod

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.returns("Custom Title")

        with tripwire:
            result = mod._resolve_setting("title")

        assert result == "Custom Title"
        mock_session.assert_call(args=(None,))
        mock_config.assert_call(args=("notify_title",))

    def test_falls_back_to_default_enabled(self):
        import spellbook.notifications.notify as mod

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.returns(None)

        with tripwire:
            result = mod._resolve_setting("enabled")

        assert result is True
        mock_session.assert_call(args=(None,))
        mock_config.assert_call(args=("notify_enabled",))

    def test_falls_back_to_default_title(self):
        import spellbook.notifications.notify as mod

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.returns(None)

        with tripwire:
            result = mod._resolve_setting("title")

        assert result == "Spellbook"
        mock_session.assert_call(args=(None,))
        mock_config.assert_call(args=("notify_title",))


class TestSendNotification:
    """send_notification() is the async entry point."""

    @pytest.mark.asyncio
    async def test_calls_send_sync_when_enabled_and_available(self, monkeypatch):
        import spellbook.notifications.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        async def _fake_to_thread(fn, *args):
            return fn(*args)

        monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        # Called twice: once for "enabled", once for "title"
        mock_session.returns({"notify": {}}).returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        # Called twice: once for "enabled" (returns None -> default True),
        # once for "title" (returns None -> default "Spellbook")
        mock_config.returns(None).returns(None)
        mock_send = tripwire.mock.object(mod, "_send_sync")
        mock_send.returns(None)

        async with tripwire:
            result = await mod.send_notification(body="test body")

        assert result == {"ok": True}
        # Assert all interactions in order
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_title",), kwargs={})
        mock_send.assert_call(args=("Spellbook", "test body"), kwargs={})

    @pytest.mark.asyncio
    async def test_returns_early_when_disabled(self):
        import spellbook.notifications.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {"enabled": False}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.__call__.required(False).returns(None)

        async with tripwire:
            result = await mod.send_notification(body="test")

        assert "error" in result
        assert "disabled" in result["error"].lower()
        mock_session.assert_call(args=(None,), kwargs={})

    @pytest.mark.asyncio
    async def test_returns_early_when_unavailable(self):
        import spellbook.notifications.notify as mod

        mod._notification_available = False
        mod._platform = None
        mod._unavailable_reason = "Missing tools"

        async with tripwire:
            result = await mod.send_notification(body="test")

        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handles_subprocess_error_gracefully(self, monkeypatch):
        import spellbook.notifications.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        async def _fake_to_thread(fn, *args):
            return fn(*args)

        monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {}}).returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.returns(None).returns(None)
        mock_send = tripwire.mock.object(mod, "_send_sync")
        mock_send.raises(subprocess.CalledProcessError(1, "osascript"))

        async with tripwire:
            result = await mod.send_notification(body="test")

        assert "error" in result
        assert "failed" in result["error"].lower()
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_title",), kwargs={})
        mock_send.assert_call(
            args=("Spellbook", "test"),
            kwargs={},
            raised=IsInstance(subprocess.CalledProcessError),
        )
        tripwire.log.assert_log(
            "WARNING",
            "Notification failed: Command 'osascript' returned "
            "non-zero exit status 1.",
            "spellbook.notifications.notify",
        )

    @pytest.mark.asyncio
    async def test_uses_explicit_title(self, monkeypatch):
        import spellbook.notifications.notify as mod

        mod._notification_available = True
        mod._platform = "linux"
        mod._unavailable_reason = None

        async def _fake_to_thread(fn, *args):
            return fn(*args)

        monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        # Called once: for "enabled" only (title is explicit)
        mock_session.returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        # Called once: for "enabled" only
        mock_config.returns(None)
        mock_send = tripwire.mock.object(mod, "_send_sync")
        mock_send.returns(None)

        async with tripwire:
            result = await mod.send_notification(
                title="Custom", body="body text"
            )

        assert result == {"ok": True}
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_enabled",), kwargs={})
        mock_send.assert_call(args=("Custom", "body text"), kwargs={})


class TestGetStatus:
    """get_status() returns notification availability and settings."""

    def test_status_when_available(self):
        import spellbook.notifications.notify as mod

        mod._notification_available = True
        mod._platform = "macos"
        mod._unavailable_reason = None

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        # Called twice: once for "enabled", once for "title"
        mock_session.returns({"notify": {}}).returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.returns(None).returns(None)

        with tripwire:
            status = mod.get_status()

        assert status["available"] is True
        assert status["enabled"] is True
        assert status["platform"] == "macos"
        assert status["title"] == "Spellbook"
        assert status["error"] is None
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_title",), kwargs={})

    def test_status_when_not_available(self):
        import spellbook.notifications.notify as mod

        mod._notification_available = False
        mod._platform = None
        mod._unavailable_reason = "Missing tools"

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {}}).returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.returns(None).returns(None)

        with tripwire:
            status = mod.get_status()

        assert status["available"] is False
        assert status["error"] == "Missing tools"
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_title",), kwargs={})

    def test_status_returns_all_expected_keys(self):
        import spellbook.notifications.notify as mod

        mod._notification_available = True
        mod._platform = "linux"
        mod._unavailable_reason = None

        mock_session = tripwire.mock(
            "spellbook.notifications.notify:config_tools._get_session_state"
        )
        mock_session.returns({"notify": {}}).returns({"notify": {}})
        mock_config = tripwire.mock(
            "spellbook.notifications.notify:config_tools.config_get"
        )
        mock_config.returns(None).returns(None)

        with tripwire:
            status = mod.get_status()

        expected_keys = {"available", "enabled", "platform", "title", "error"}
        assert set(status.keys()) == expected_keys
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_enabled",), kwargs={})
        mock_session.assert_call(args=(None,), kwargs={})
        mock_config.assert_call(args=("notify_title",), kwargs={})
