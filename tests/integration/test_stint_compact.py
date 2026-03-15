"""Integration tests for stint stack compaction survival."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
HOOKS_DIR = str(Path(PROJECT_ROOT) / "hooks")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

import spellbook_hook  # noqa: E402

pytestmark = pytest.mark.integration


class TestStintCompactionSurvival:
    """Test that stint stack survives pre-compact save and post-compact restore."""

    def test_pre_compact_saves_stint_stack(self):
        """PreCompact handler merges stint_stack into workflow state."""
        saved_calls = []
        call_responses = {
            "stint_check": {"success": True, "stack": [
                {"name": "implementing-features", "purpose": "build auth", "behavioral_mode": "ORCHESTRATOR: Dispatch subagents"},
                {"name": "debugging", "purpose": "fix test", "behavioral_mode": ""},
            ]},
            "workflow_state_load": {"found": True, "state": {"active_skill": "implementing-features"}},
            "workflow_state_save": {"success": True},
        }

        original = spellbook_hook._mcp_call
        def mock_mcp_call(tool, args=None):
            saved_calls.append((tool, args))
            return call_responses.get(tool)

        spellbook_hook._mcp_call = mock_mcp_call

        try:
            spellbook_hook._handle_pre_compact({"cwd": "/test/project"})

            # Verify exactly 3 calls in order: stint_check, workflow_state_load, workflow_state_save
            assert len(saved_calls) == 3

            assert saved_calls[0] == ("stint_check", {"project_path": "/test/project"})

            assert saved_calls[1] == ("workflow_state_load", {
                "project_path": "/test/project",
                "max_age_hours": 24,
            })

            assert saved_calls[2][0] == "workflow_state_save"
            save_args = saved_calls[2][1]
            assert save_args == {
                "project_path": "/test/project",
                "state": {
                    "active_skill": "implementing-features",
                    "stint_stack": [
                        {"name": "implementing-features", "purpose": "build auth", "behavioral_mode": "ORCHESTRATOR: Dispatch subagents"},
                        {"name": "debugging", "purpose": "fix test", "behavioral_mode": ""},
                    ],
                    "compaction_flag": True,
                },
                "trigger": "auto",
            }
        finally:
            spellbook_hook._mcp_call = original

    def test_pre_compact_no_cwd_does_nothing(self):
        """PreCompact with no cwd makes no MCP calls."""
        calls = []
        original = spellbook_hook._mcp_call
        spellbook_hook._mcp_call = lambda tool, args=None: calls.append((tool, args))

        try:
            spellbook_hook._handle_pre_compact({})
            assert calls == []
        finally:
            spellbook_hook._mcp_call = original

    def test_pre_compact_stint_check_failure_still_saves(self):
        """If stint_check fails, save state without stint_stack."""
        saved_calls = []
        call_responses = {
            "stint_check": None,  # MCP unreachable
            "workflow_state_load": {"found": True, "state": {"active_skill": "debug"}},
            "workflow_state_save": {"success": True},
        }

        original = spellbook_hook._mcp_call
        def mock_mcp_call(tool, args=None):
            saved_calls.append((tool, args))
            return call_responses.get(tool)

        spellbook_hook._mcp_call = mock_mcp_call

        try:
            spellbook_hook._handle_pre_compact({"cwd": "/test/project"})

            assert len(saved_calls) == 3
            save_args = saved_calls[2][1]
            # No stint_stack key since stint_check failed
            assert save_args == {
                "project_path": "/test/project",
                "state": {
                    "active_skill": "debug",
                    "compaction_flag": True,
                },
                "trigger": "auto",
            }
        finally:
            spellbook_hook._mcp_call = original

    def test_pre_compact_no_existing_state(self):
        """If no existing workflow state, create fresh state with stint_stack."""
        saved_calls = []
        call_responses = {
            "stint_check": {"success": True, "stack": [
                {"name": "exploring", "purpose": "find files", "behavioral_mode": ""},
            ]},
            "workflow_state_load": {"found": False},
            "workflow_state_save": {"success": True},
        }

        original = spellbook_hook._mcp_call
        def mock_mcp_call(tool, args=None):
            saved_calls.append((tool, args))
            return call_responses.get(tool)

        spellbook_hook._mcp_call = mock_mcp_call

        try:
            spellbook_hook._handle_pre_compact({"cwd": "/test/project"})

            assert len(saved_calls) == 3
            save_args = saved_calls[2][1]
            assert save_args == {
                "project_path": "/test/project",
                "state": {
                    "stint_stack": [
                        {"name": "exploring", "purpose": "find files", "behavioral_mode": ""},
                    ],
                    "compaction_flag": True,
                },
                "trigger": "auto",
            }
        finally:
            spellbook_hook._mcp_call = original

    def test_session_start_restores_stint_stack(self):
        """SessionStart handler restores stint_stack via stint_replace."""
        saved_calls = []
        call_responses = {
            "workflow_state_load": {
                "found": True,
                "state": {
                    "active_skill": "implementing-features",
                    "stint_stack": [
                        {"name": "implementing-features", "purpose": "build auth", "behavioral_mode": "ORCHESTRATOR: Dispatch subagents"},
                        {"name": "debugging", "purpose": "fix test", "behavioral_mode": ""},
                    ],
                },
            },
            "stint_replace": {"success": True, "depth": 2},
        }

        original = spellbook_hook._mcp_call
        def mock_mcp_call(tool, args=None):
            saved_calls.append((tool, args))
            return call_responses.get(tool)

        spellbook_hook._mcp_call = mock_mcp_call

        try:
            result = spellbook_hook._handle_session_start({
                "source": "compact",
                "cwd": "/test/project",
                "session_id": "test-123",
            })

            assert result is not None
            assert "hookSpecificOutput" in result

            # Verify stint_replace was called with correct args
            replaces = [c for c in saved_calls if c[0] == "stint_replace"]
            assert len(replaces) == 1
            assert replaces[0] == ("stint_replace", {
                "project_path": "/test/project",
                "stack": [
                    {"name": "implementing-features", "purpose": "build auth", "behavioral_mode": "ORCHESTRATOR: Dispatch subagents"},
                    {"name": "debugging", "purpose": "fix test", "behavioral_mode": ""},
                ],
                "reason": "post-compaction restoration",
            })

            # Verify recovery directive exact content including [MODE: ...] suffix
            context = result["hookSpecificOutput"]["additionalContext"]
            expected_context = (
                "### Active Skill: implementing-features\n"
                "Resume with: `Skill(skill='implementing-features')`\n"
                "\n### Focus Stack (restored)\n"
                "  1. implementing-features - build auth [MODE: ORCHESTRATOR: Dispatch subagents]\n"
                "  2. debugging - fix test\n"
            )
            assert context == expected_context, (
                f"Expected context:\n{expected_context!r}\n\nGot:\n{context!r}"
            )
        finally:
            spellbook_hook._mcp_call = original

    def test_session_start_no_stint_stack_skips_restore(self):
        """SessionStart without stint_stack in state skips stint_replace."""
        saved_calls = []
        call_responses = {
            "workflow_state_load": {
                "found": True,
                "state": {
                    "active_skill": "debugging",
                },
            },
        }

        original = spellbook_hook._mcp_call
        def mock_mcp_call(tool, args=None):
            saved_calls.append((tool, args))
            return call_responses.get(tool)

        spellbook_hook._mcp_call = mock_mcp_call

        try:
            result = spellbook_hook._handle_session_start({
                "source": "compact",
                "cwd": "/test/project",
            })

            assert result is not None
            # No stint_replace calls
            replaces = [c for c in saved_calls if c[0] == "stint_replace"]
            assert replaces == []
            # No focus stack section
            context = result["hookSpecificOutput"]["additionalContext"]
            expected_context = (
                "### Active Skill: debugging\n"
                "Resume with: `Skill(skill='debugging')`"
            )
            assert context == expected_context
        finally:
            spellbook_hook._mcp_call = original

    def test_session_start_non_compact_source_returns_none(self):
        """Non-compact source returns None."""
        result = spellbook_hook._handle_session_start({
            "source": "init",
            "cwd": "/test/project",
        })
        assert result is None


class TestBehavioralModeSurvivesCompaction:
    """End-to-end: behavioral_mode persists through compaction cycle."""

    @patch.object(spellbook_hook, "_mcp_call")
    def test_full_compaction_round_trip(self, mock_mcp_call):
        """Push with behavioral_mode, compact, recover, verify mode in output."""
        saved_stack = [
            {
                "type": "skill",
                "name": "implementing-features",
                "parent": None,
                "purpose": "Skill invocation: implementing-features",
                "behavioral_mode": "ORCHESTRATOR: Dispatch subagents via Task tool for ALL substantive work.",
                "success_criteria": "Skill workflow complete",
                "metadata": {},
                "entered_at": "2026-03-15T10:00:00+00:00",
                "exited_at": None,
            },
        ]

        saved_state = {
            "active_skill": "implementing-features",
            "skill_phase": "DESIGN",
            "stint_stack": saved_stack,
            "compaction_flag": True,
        }

        # Mock the MCP calls for SessionStart recovery
        mock_mcp_call.side_effect = [
            # 1. workflow_state_load
            {"found": True, "state": saved_state},
            # 2. stint_replace (restore stack)
            {"success": True, "depth": 1, "correction_logged": True},
            # 3. skill_instructions_get (from _build_recovery_directive)
            {
                "success": True,
                "content": "## FORBIDDEN\n- Never skip phases\n## REQUIRED\n- Follow all steps",
            },
        ]

        data = {"source": "compact", "cwd": "/tmp/test-project"}
        result = spellbook_hook._handle_session_start(data)

        assert result is not None
        context = result["hookSpecificOutput"]["additionalContext"]

        # The behavioral_mode is 64 chars, well under 80-char truncation limit
        # Full expected output constructed from _build_recovery_directive + Focus Stack append
        expected_context = (
            "### Active Skill: implementing-features\n"
            "Phase: DESIGN\n"
            "Resume with: `Skill(skill='implementing-features', --resume DESIGN)`\n"
            "\n### Skill Constraints\n"
            "## FORBIDDEN\n- Never skip phases\n## REQUIRED\n- Follow all steps\n"
            "\n### Focus Stack (restored)\n"
            "  1. implementing-features - Skill invocation: implementing-features"
            " [MODE: ORCHESTRATOR: Dispatch subagents via Task tool for ALL substantive work.]\n"
        )
        assert context == expected_context, (
            f"Expected context:\n{expected_context!r}\n\nGot:\n{context!r}"
        )

    @patch.object(spellbook_hook, "_mcp_call")
    def test_compaction_with_no_behavioral_mode_backward_compat(self, mock_mcp_call):
        """Old stack entries without behavioral_mode survive compaction."""
        saved_stack = [
            {
                "type": "skill",
                "name": "old-skill",
                "parent": None,
                "purpose": "legacy purpose",
                "success_criteria": "",
                "metadata": {},
                "entered_at": "2026-03-15T10:00:00+00:00",
                "exited_at": None,
                # No behavioral_mode key
            },
        ]

        mock_mcp_call.side_effect = [
            {"found": True, "state": {"stint_stack": saved_stack}},
            {"success": True},  # stint_replace
        ]

        data = {"source": "compact", "cwd": "/tmp/test-project"}
        result = spellbook_hook._handle_session_start(data)

        assert result is not None
        context = result["hookSpecificOutput"]["additionalContext"]
        # No active_skill in state, so _build_recovery_directive returns fallback message
        # Focus Stack section is appended after
        expected_context = (
            "No active workflow state found."
            "\n\n### Focus Stack (restored)\n"
            "  1. old-skill - legacy purpose\n"
        )
        assert context == expected_context, (
            f"Expected context:\n{expected_context!r}\n\nGot:\n{context!r}"
        )

    @patch.object(spellbook_hook, "_mcp_call")
    def test_first_post_tool_use_after_compaction_shows_behavioral_mode(self, mock_mcp_call):
        """After compaction recovery, the first PostToolUse should show behavioral_mode."""
        mock_mcp_call.return_value = {
            "success": True,
            "stack": [
                {
                    "name": "implementing-features",
                    "purpose": "Skill invocation",
                    "behavioral_mode": "ORCHESTRATOR: Dispatch subagents",
                },
            ],
        }

        data = {"tool_name": "Bash", "cwd": "/tmp/test-project"}
        result = spellbook_hook._stint_depth_check(data)

        # depth=1 < threshold(5), so no tree output, just behavioral_mode
        assert result == "<behavioral-mode>ORCHESTRATOR: Dispatch subagents</behavioral-mode>"
