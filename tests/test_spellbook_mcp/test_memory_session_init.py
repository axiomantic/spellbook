"""Tests for MEMORY.md regeneration in session_init."""

from unittest.mock import patch, MagicMock

import pytest


class TestSessionInitMemoryRegeneration:
    """session_init calls _regenerate_memory_md for MEMORY.md refresh."""

    def test_calls_regenerate_with_project_path(self):
        """session_init invokes _regenerate_memory_md with project_path."""
        with patch("spellbook.core.config._regenerate_memory_md") as mock_regen, \
             patch("spellbook.core.config.config_get", return_value="none"), \
             patch("spellbook.core.config._get_session_state", return_value={}), \
             patch("spellbook.core.config._add_update_notification"), \
             patch("spellbook.core.config._get_resume_context", return_value={"resume_available": False}), \
             patch("spellbook.core.config._get_repairs", return_value=[]):
            from spellbook.core.config import session_init

            result = session_init(project_path="/Users/alice/project")
            mock_regen.assert_called_once_with("/Users/alice/project")

    def test_skips_when_project_path_none(self):
        """_regenerate_memory_md returns early when project_path is None."""
        from spellbook.core.config import _regenerate_memory_md

        # Should not raise
        _regenerate_memory_md(None)

    def test_fail_open_on_exception(self):
        """_regenerate_memory_md swallows exceptions (fail-open)."""
        with patch(
            "spellbook.memory.bootstrap.regenerate_memory_md_for_project",
            side_effect=RuntimeError("DB corruption"),
        ):
            from spellbook.core.config import _regenerate_memory_md

            # Should not raise
            _regenerate_memory_md("/Users/alice/project")
