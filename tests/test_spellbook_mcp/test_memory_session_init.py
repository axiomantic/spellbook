"""Tests for MEMORY.md regeneration in session_init."""

import bigfoot
from dirty_equals import IsInstance
import pytest


class TestSessionInitMemoryRegeneration:
    """session_init calls _regenerate_memory_md for MEMORY.md refresh."""

    def test_calls_regenerate_with_project_path(self):
        """session_init invokes _regenerate_memory_md with project_path."""
        mock_session_state = bigfoot.mock("spellbook.core.config:_get_session_state")
        mock_session_state.returns({})

        # config_get is called three times: "session_mode", "fun_mode", "profile.default"
        mock_config_get = bigfoot.mock("spellbook.core.config:config_get")
        mock_config_get.returns("none").returns(None).returns(None)

        mock_update_notif = bigfoot.mock("spellbook.core.config:_add_update_notification")
        mock_update_notif.returns(None)

        mock_regen = bigfoot.mock("spellbook.core.config:_regenerate_memory_md")
        mock_regen.returns(None)

        mock_resume = bigfoot.mock("spellbook.core.config:_get_resume_context")
        mock_resume.returns({"resume_available": False})

        mock_admin_url = bigfoot.mock("spellbook.core.config:_get_admin_url")
        mock_admin_url.returns(None)

        mock_repairs = bigfoot.mock("spellbook.core.config:_get_repairs")
        mock_repairs.returns([])

        with bigfoot:
            from spellbook.core.config import session_init
            result = session_init(project_path="/Users/alice/project")

        expected_result = {"mode": {"type": "none"}, "fun_mode": "no", "resume_available": False}
        mock_session_state.assert_call(args=(None,), kwargs={})
        mock_config_get.assert_call(args=("session_mode",), kwargs={})
        mock_config_get.assert_call(args=("fun_mode",), kwargs={})
        mock_update_notif.assert_call(args=(expected_result,), kwargs={})
        mock_regen.assert_call(args=("/Users/alice/project",), kwargs={})
        mock_resume.assert_call(args=(None, "/Users/alice/project"), kwargs={})
        mock_admin_url.assert_call(args=(), kwargs={})
        mock_config_get.assert_call(args=("profile.default",), kwargs={})
        mock_repairs.assert_call(args=(), kwargs={})

    def test_skips_when_project_path_none(self):
        """_regenerate_memory_md returns early when project_path is None."""
        from spellbook.core.config import _regenerate_memory_md

        # Should not raise
        _regenerate_memory_md(None)

    def test_fail_open_on_exception(self):
        """_regenerate_memory_md swallows exceptions (fail-open)."""
        mock_bootstrap = bigfoot.mock(
            "spellbook.memory.bootstrap:regenerate_memory_md_for_project"
        )
        mock_bootstrap.raises(RuntimeError("DB corruption"))

        with bigfoot:
            from spellbook.core.config import _regenerate_memory_md
            # Should not raise
            _regenerate_memory_md("/Users/alice/project")

        mock_bootstrap.assert_call(
            args=("/Users/alice/project",),
            kwargs={},
            raised=IsInstance(RuntimeError),
        )
