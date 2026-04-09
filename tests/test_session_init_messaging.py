"""Integration tests for messaging auto-registration in spellbook_session_init."""


import bigfoot
import pytest
from dirty_equals import IsInstance, IsStr

from spellbook.core.path_utils import GitContext
from spellbook.mcp.tools.config import spellbook_session_init


def _async_returns(value):
    """Create an async callable that returns value, for mocking async functions."""

    async def _fn(*args, **kwargs):
        return value

    return _fn


def _async_raises(exc):
    """Create an async callable that raises exc, for mocking async functions."""

    async def _fn(*args, **kwargs):
        raise exc

    return _fn


class TestSessionInitMessaging:
    """Test the messaging auto-registration block in spellbook_session_init."""

    @pytest.mark.asyncio
    async def test_auto_registers_with_git_alias(self):
        """session_init returns messaging.registered=True with git-derived alias."""
        mock_ctx = bigfoot.mock("spellbook.mcp.tools.config:get_project_path_from_context")
        mock_ctx.calls(_async_returns("/tmp/myrepo"))

        mock_session_id = bigfoot.mock("spellbook.mcp.tools.config:_get_session_id")
        mock_session_id.returns("test-session-1")

        mock_init = bigfoot.mock("spellbook.mcp.tools.config:session_init")
        mock_init.returns({"mode": {"type": "none"}, "fun_mode": "no"})

        mock_git = bigfoot.mock("spellbook.core.path_utils:detect_git_context")
        mock_git.returns(GitContext(branch="main"))

        # derive_messaging_alias runs in asyncio.to_thread; mock it directly
        # so the thread pool call resolves immediately (avoids bigfoot + nested
        # mock deadlocks inside to_thread).
        mock_derive = bigfoot.mock("spellbook.core.path_utils:derive_messaging_alias")
        mock_derive.returns("myrepo-main")

        mock_register = bigfoot.mock(
            "spellbook.messaging.bus:message_bus.register_with_suffix"
        )
        mock_register.calls(_async_returns(("myrepo-main", False)))

        ctx = type("MockCtx", (), {"session_id": "test-session-1"})()

        async with bigfoot:
            result = await spellbook_session_init.fn(ctx)

        assert result["messaging"]["registered"] is True
        assert result["messaging"]["alias"] == "myrepo-main"
        assert result["messaging"]["was_compaction"] is False

        with bigfoot.in_any_order():
            mock_ctx.assert_call(args=(ctx,))
            mock_session_id.assert_call(args=(ctx,))
            mock_init.assert_call(
                args=("test-session-1",),
                kwargs={"continuation_message": None, "project_path": "/tmp/myrepo", "platform": None},
            )
            mock_git.assert_call(args=("/tmp/myrepo",))
            mock_derive.assert_call(
                args=("/tmp/myrepo",),
                kwargs={"session_name": None, "git_context": GitContext(branch="main")},
            )
            mock_register.assert_call(
                kwargs={"base_alias": "myrepo-main", "session_id": "test-session-1", "enable_sse": True},
            )
            bigfoot.log_mock.assert_log("ERROR", IsStr(), "concurrent.futures")

    @pytest.mark.asyncio
    async def test_explicit_session_name_overrides_git(self):
        """Explicit session_name is used for alias derivation."""
        mock_ctx = bigfoot.mock("spellbook.mcp.tools.config:get_project_path_from_context")
        mock_ctx.calls(_async_returns("/tmp/myrepo"))

        mock_session_id = bigfoot.mock("spellbook.mcp.tools.config:_get_session_id")
        mock_session_id.returns("test-session-2")

        mock_init = bigfoot.mock("spellbook.mcp.tools.config:session_init")
        mock_init.returns({"mode": {"type": "none"}, "fun_mode": "no"})

        mock_git = bigfoot.mock("spellbook.core.path_utils:detect_git_context")
        mock_git.returns(GitContext(branch="main"))

        mock_derive = bigfoot.mock("spellbook.core.path_utils:derive_messaging_alias")
        mock_derive.returns("custom-name")

        mock_register = bigfoot.mock(
            "spellbook.messaging.bus:message_bus.register_with_suffix"
        )
        mock_register.calls(_async_returns(("custom-name", False)))

        ctx = type("MockCtx", (), {"session_id": "test-session-2"})()

        async with bigfoot:
            result = await spellbook_session_init.fn(ctx, session_name="custom-name")

        assert result["messaging"]["alias"] == "custom-name"

        with bigfoot.in_any_order():
            mock_ctx.assert_call(args=(ctx,))
            mock_session_id.assert_call(args=(ctx,))
            mock_init.assert_call(
                args=("test-session-2",),
                kwargs={"continuation_message": None, "project_path": "/tmp/myrepo", "platform": None},
            )
            mock_git.assert_call(args=("/tmp/myrepo",))
            mock_derive.assert_call(
                args=("/tmp/myrepo",),
                kwargs={"session_name": "custom-name", "git_context": GitContext(branch="main")},
            )
            mock_register.assert_call(
                kwargs={"base_alias": "custom-name", "session_id": "test-session-2", "enable_sse": True},
            )
            bigfoot.log_mock.assert_log("ERROR", IsStr(), "concurrent.futures")

    @pytest.mark.asyncio
    async def test_continuation_message_passed_through(self):
        """continuation_message is forwarded to core session_init."""
        mock_ctx = bigfoot.mock("spellbook.mcp.tools.config:get_project_path_from_context")
        mock_ctx.calls(_async_returns("/tmp/myrepo"))

        mock_session_id = bigfoot.mock("spellbook.mcp.tools.config:_get_session_id")
        mock_session_id.returns("test-session-3")

        mock_init = bigfoot.mock("spellbook.mcp.tools.config:session_init")
        mock_init.returns({"mode": {"type": "none"}, "fun_mode": "no"})

        mock_git = bigfoot.mock("spellbook.core.path_utils:detect_git_context")
        mock_git.returns(GitContext())

        mock_derive = bigfoot.mock("spellbook.core.path_utils:derive_messaging_alias")
        mock_derive.returns("myrepo")

        mock_register = bigfoot.mock(
            "spellbook.messaging.bus:message_bus.register_with_suffix"
        )
        mock_register.calls(_async_returns(("myrepo", False)))

        ctx = type("MockCtx", (), {"session_id": "test-session-3"})()

        async with bigfoot:
            await spellbook_session_init.fn(
                ctx, continuation_message="where were we?"
            )

        with bigfoot.in_any_order():
            mock_ctx.assert_call(args=(ctx,))
            mock_session_id.assert_call(args=(ctx,))
            mock_init.assert_call(
                args=("test-session-3",),
                kwargs={
                    "continuation_message": "where were we?",
                    "project_path": "/tmp/myrepo",
                    "platform": None,
                },
            )
            mock_git.assert_call(args=("/tmp/myrepo",))
            mock_derive.assert_call(
                args=("/tmp/myrepo",),
                kwargs={"session_name": None, "git_context": GitContext()},
            )
            mock_register.assert_call(
                kwargs={"base_alias": "myrepo", "session_id": "test-session-3", "enable_sse": True},
            )
            bigfoot.log_mock.assert_log("ERROR", IsStr(), "concurrent.futures")

    @pytest.mark.asyncio
    async def test_messaging_failure_degrades_gracefully(self):
        """Bus failure results in registered=False, session still works."""
        mock_ctx = bigfoot.mock("spellbook.mcp.tools.config:get_project_path_from_context")
        mock_ctx.calls(_async_returns("/tmp/myrepo"))

        mock_session_id = bigfoot.mock("spellbook.mcp.tools.config:_get_session_id")
        mock_session_id.returns("test-session-4")

        mock_init = bigfoot.mock("spellbook.mcp.tools.config:session_init")
        mock_init.returns({"mode": {"type": "none"}, "fun_mode": "no"})

        mock_git = bigfoot.mock("spellbook.core.path_utils:detect_git_context")
        mock_git.returns(GitContext(branch="main"))

        mock_derive = bigfoot.mock("spellbook.core.path_utils:derive_messaging_alias")
        mock_derive.returns("myrepo-main")

        mock_register = bigfoot.mock(
            "spellbook.messaging.bus:message_bus.register_with_suffix"
        )
        mock_register.calls(_async_raises(RuntimeError("bus broken")))

        ctx = type("MockCtx", (), {"session_id": "test-session-4"})()

        async with bigfoot:
            result = await spellbook_session_init.fn(ctx)

        # Session init should still succeed
        assert "mode" in result
        assert result["messaging"]["registered"] is False
        assert "bus broken" in result["messaging"]["error"]

        with bigfoot.in_any_order():
            mock_ctx.assert_call(args=(ctx,))
            mock_session_id.assert_call(args=(ctx,))
            mock_init.assert_call(
                args=("test-session-4",),
                kwargs={"continuation_message": None, "project_path": "/tmp/myrepo", "platform": None},
            )
            mock_git.assert_call(args=("/tmp/myrepo",))
            mock_derive.assert_call(
                args=("/tmp/myrepo",),
                kwargs={"session_name": None, "git_context": GitContext(branch="main")},
            )
            mock_register.assert_call(
                kwargs={"base_alias": "myrepo-main", "session_id": "test-session-4", "enable_sse": True},
            )
            bigfoot.log_mock.assert_log("ERROR", IsStr(), "concurrent.futures")
            bigfoot.log_mock.assert_log(
                "WARNING",
                "Messaging auto-register failed: bus broken",
                "spellbook.mcp.tools.config",
            )

    @pytest.mark.asyncio
    async def test_git_failure_still_registers(self):
        """Git context failure falls back to basename alias, still registers."""
        mock_ctx = bigfoot.mock("spellbook.mcp.tools.config:get_project_path_from_context")
        mock_ctx.calls(_async_returns("/tmp/myrepo"))

        mock_session_id = bigfoot.mock("spellbook.mcp.tools.config:_get_session_id")
        mock_session_id.returns("test-session-5")

        mock_init = bigfoot.mock("spellbook.mcp.tools.config:session_init")
        mock_init.returns({"mode": {"type": "none"}, "fun_mode": "no"})

        mock_git = bigfoot.mock("spellbook.core.path_utils:detect_git_context")
        mock_git.raises(FileNotFoundError("git not found"))

        # When git context fails, derive_messaging_alias gets git_context=None
        mock_derive = bigfoot.mock("spellbook.core.path_utils:derive_messaging_alias")
        mock_derive.returns("myrepo")

        mock_register = bigfoot.mock(
            "spellbook.messaging.bus:message_bus.register_with_suffix"
        )
        mock_register.calls(_async_returns(("myrepo", False)))

        ctx = type("MockCtx", (), {"session_id": "test-session-5"})()

        async with bigfoot:
            result = await spellbook_session_init.fn(ctx)

        assert result["messaging"]["registered"] is True
        assert result["messaging"]["alias"] == "myrepo"

        with bigfoot.in_any_order():
            mock_ctx.assert_call(args=(ctx,))
            mock_session_id.assert_call(args=(ctx,))
            mock_init.assert_call(
                args=("test-session-5",),
                kwargs={"continuation_message": None, "project_path": "/tmp/myrepo", "platform": None},
            )
            mock_git.assert_call(
                args=("/tmp/myrepo",),
                raised=IsInstance(FileNotFoundError),
            )
            mock_derive.assert_call(
                args=("/tmp/myrepo",),
                kwargs={"session_name": None, "git_context": None},
            )
            mock_register.assert_call(
                kwargs={"base_alias": "myrepo", "session_id": "test-session-5", "enable_sse": True},
            )
            bigfoot.log_mock.assert_log("ERROR", IsStr(), "concurrent.futures")

    @pytest.mark.asyncio
    async def test_compaction_detected(self):
        """Second init with same session_id reports was_compaction=True."""
        mock_ctx = bigfoot.mock("spellbook.mcp.tools.config:get_project_path_from_context")
        mock_ctx.calls(_async_returns("/tmp/myrepo"))

        mock_session_id = bigfoot.mock("spellbook.mcp.tools.config:_get_session_id")
        mock_session_id.returns("test-session-6")

        mock_init = bigfoot.mock("spellbook.mcp.tools.config:session_init")
        mock_init.returns({"mode": {"type": "none"}, "fun_mode": "no"})

        mock_git = bigfoot.mock("spellbook.core.path_utils:detect_git_context")
        mock_git.returns(GitContext(branch="main"))

        mock_derive = bigfoot.mock("spellbook.core.path_utils:derive_messaging_alias")
        mock_derive.returns("myrepo-main")

        mock_register = bigfoot.mock(
            "spellbook.messaging.bus:message_bus.register_with_suffix"
        )
        mock_register.calls(_async_returns(("myrepo-main", True)))

        ctx = type("MockCtx", (), {"session_id": "test-session-6"})()

        async with bigfoot:
            result = await spellbook_session_init.fn(ctx)

        assert result["messaging"]["was_compaction"] is True

        with bigfoot.in_any_order():
            mock_ctx.assert_call(args=(ctx,))
            mock_session_id.assert_call(args=(ctx,))
            mock_init.assert_call(
                args=("test-session-6",),
                kwargs={"continuation_message": None, "project_path": "/tmp/myrepo", "platform": None},
            )
            mock_git.assert_call(args=("/tmp/myrepo",))
            mock_derive.assert_call(
                args=("/tmp/myrepo",),
                kwargs={"session_name": None, "git_context": GitContext(branch="main")},
            )
            mock_register.assert_call(
                kwargs={"base_alias": "myrepo-main", "session_id": "test-session-6", "enable_sse": True},
            )
            bigfoot.log_mock.assert_log("ERROR", IsStr(), "concurrent.futures")
