"""Tests for TTS provisioning hook in config_set."""

import asyncio

import bigfoot
import pytest

from spellbook.mcp.tools.config import spellbook_config_set


def _async_return(value):
    """Create an async callable that returns value."""
    async def _fn(*args, **kwargs):
        return value
    return _fn


class TestTtsProvisioningHook:
    """Test that config_set triggers TTS provisioning when tts_enabled is set to True."""

    @pytest.mark.asyncio
    async def test_tts_enabled_true_triggers_provisioning(self):
        mock_cfg_set = bigfoot.mock("spellbook.mcp.tools.config:config_set")
        mock_cfg_set.returns({"status": "ok", "config": {"tts_enabled": True}})

        mock_provision = bigfoot.mock("spellbook.mcp.tools.config:_provision_tts_async")
        mock_provision.calls(_async_return(None))

        async with bigfoot:
            # __wrapped__ bypasses the inject_recovery_context decorator
            result = await spellbook_config_set.__wrapped__("tts_enabled", True)
            # Allow the background task to execute
            await asyncio.sleep(0.05)

        assert result == {"status": "ok", "config": {"tts_enabled": True}}
        mock_cfg_set.assert_call(args=("tts_enabled", True), kwargs={})
        mock_provision.assert_call(args=(), kwargs={})

    @pytest.mark.asyncio
    async def test_tts_enabled_string_true_triggers_provisioning(self):
        mock_cfg_set = bigfoot.mock("spellbook.mcp.tools.config:config_set")
        mock_cfg_set.returns({"status": "ok", "config": {"tts_enabled": "true"}})

        mock_provision = bigfoot.mock("spellbook.mcp.tools.config:_provision_tts_async")
        mock_provision.calls(_async_return(None))

        async with bigfoot:
            result = await spellbook_config_set.__wrapped__("tts_enabled", "true")
            await asyncio.sleep(0.05)

        assert result == {"status": "ok", "config": {"tts_enabled": "true"}}
        mock_cfg_set.assert_call(args=("tts_enabled", "true"), kwargs={})
        mock_provision.assert_call(args=(), kwargs={})

    @pytest.mark.asyncio
    async def test_tts_enabled_false_does_not_trigger(self):
        mock_cfg_set = bigfoot.mock("spellbook.mcp.tools.config:config_set")
        mock_cfg_set.returns({"status": "ok", "config": {"tts_enabled": False}})

        # Do NOT mock _provision_tts_async: if it were called, bigfoot's
        # sandbox would raise UnmockedInteractionError, failing this test.
        async with bigfoot:
            result = await spellbook_config_set.__wrapped__("tts_enabled", False)

        assert result == {"status": "ok", "config": {"tts_enabled": False}}
        mock_cfg_set.assert_call(args=("tts_enabled", False), kwargs={})

    @pytest.mark.asyncio
    async def test_other_key_does_not_trigger(self):
        mock_cfg_set = bigfoot.mock("spellbook.mcp.tools.config:config_set")
        mock_cfg_set.returns({"status": "ok", "config": {"fun_mode": True}})

        # Do NOT mock _provision_tts_async: unmocked call would fail the test.
        async with bigfoot:
            result = await spellbook_config_set.__wrapped__("fun_mode", True)

        assert result == {"status": "ok", "config": {"fun_mode": True}}
        mock_cfg_set.assert_call(args=("fun_mode", True), kwargs={})


class TestProvisionTtsAsync:
    """Test the _provision_tts_async helper directly."""

    @pytest.mark.asyncio
    async def test_successful_provisioning_calls_ensure(self):
        from spellbook.mcp.tools.config import _provision_tts_async

        mock_ensure = bigfoot.mock("spellbook.tts.provisioner:ensure_provisioned")
        mock_ensure.calls(_async_return({
            "status": "ok",
            "detail": "TTS fully provisioned",
            "steps_completed": ["deps", "service"],
        }))

        async with bigfoot:
            # Should complete without error
            await _provision_tts_async()

        mock_ensure.assert_call(args=(), kwargs={})

    @pytest.mark.asyncio
    async def test_provisioning_error_is_logged_not_raised(self):
        from spellbook.mcp.tools.config import _provision_tts_async

        mock_ensure = bigfoot.mock("spellbook.tts.provisioner:ensure_provisioned")
        mock_ensure.calls(_async_return({
            "status": "error",
            "detail": "disk full",
            "steps_completed": [],
        }))

        async with bigfoot:
            # Should not raise even though provisioning "failed"
            await _provision_tts_async()

        mock_ensure.assert_call(args=(), kwargs={})
        bigfoot.log_mock.assert_log(
            "ERROR",
            "TTS provisioning failed: disk full",
            "spellbook.mcp.tools.config",
        )

    @pytest.mark.asyncio
    async def test_provisioning_exception_is_caught(self):
        from spellbook.mcp.tools.config import _provision_tts_async

        async def _blow_up(*args, **kwargs):
            raise RuntimeError("kaboom")

        mock_ensure = bigfoot.mock("spellbook.tts.provisioner:ensure_provisioned")
        mock_ensure.calls(_blow_up)

        async with bigfoot:
            # Should not raise
            await _provision_tts_async()

        mock_ensure.assert_call(args=(), kwargs={})
        bigfoot.log_mock.assert_log(
            "ERROR",
            "TTS provisioning failed",
            "spellbook.mcp.tools.config",
        )
