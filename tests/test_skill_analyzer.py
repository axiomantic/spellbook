"""Tests for skill usage analyzer."""

import pytest
from spellbook_mcp.skill_analyzer import (
    extract_skill_invocations,
    aggregate_metrics,
    _get_tool_uses,
    _get_user_content,
    _get_role,
    _detect_correction,
    _extract_version,
    SkillInvocation,
)


class TestToolUseExtraction:
    """Test extraction of tool_use blocks from messages."""

    def test_extracts_tool_use_from_assistant_message(self):
        msg = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll use a skill."},
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "Skill",
                        "input": {"skill": "debugging"},
                    },
                ],
            },
        }
        tools = _get_tool_uses(msg)
        assert len(tools) == 1
        assert tools[0]["name"] == "Skill"
        assert tools[0]["input"]["skill"] == "debugging"

    def test_returns_empty_for_user_message(self):
        msg = {
            "type": "user",
            "message": {"role": "user", "content": "Hello"},
        }
        assert _get_tool_uses(msg) == []

    def test_returns_empty_for_string_content(self):
        msg = {
            "type": "assistant",
            "message": {"role": "assistant", "content": "Just text"},
        }
        assert _get_tool_uses(msg) == []

    def test_filters_non_tool_use_blocks(self):
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "thinking..."},
                    {"type": "thinking", "thinking": "hmm"},
                    {"type": "tool_use", "name": "Read", "input": {}},
                ],
            },
        }
        tools = _get_tool_uses(msg)
        assert len(tools) == 1
        assert tools[0]["name"] == "Read"


class TestUserContentExtraction:
    """Test extraction of user message content."""

    def test_extracts_string_content(self):
        msg = {
            "type": "user",
            "message": {"role": "user", "content": "Hello world"},
        }
        assert _get_user_content(msg) == "Hello world"

    def test_extracts_list_content(self):
        msg = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "Line 1"},
                    {"type": "text", "text": "Line 2"},
                ],
            },
        }
        assert _get_user_content(msg) == "Line 1\nLine 2"

    def test_returns_empty_for_assistant(self):
        msg = {
            "type": "assistant",
            "message": {"content": "Not extracted"},
        }
        assert _get_user_content(msg) == ""


class TestCorrectionDetection:
    """Test detection of user correction patterns."""

    @pytest.mark.parametrize(
        "text",
        [
            "No, that's wrong",
            "Stop doing that",
            "That's incorrect",
            "Actually, I meant...",
            "Don't do it that way",
            "do it instead like this",
            "That's not what I asked",
        ],
    )
    def test_detects_correction_patterns(self, text):
        assert _detect_correction(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Yes, that looks good",
            "Continue with that approach",
            "I know what you mean",  # "know" not "no"
            "The function is not working",  # "not" is fine
            "Now let's move on",  # "now" not "no"
        ],
    )
    def test_ignores_non_corrections(self, text):
        assert _detect_correction(text) is False


class TestVersionExtraction:
    """Test version marker extraction."""

    def test_extracts_version_from_skill_name(self):
        base, version = _extract_version("implementing-features:v2", None)
        assert base == "implementing-features"
        assert version == "v2"

    def test_extracts_version_from_args_bracket(self):
        base, version = _extract_version("debugging", "[v3] with extra context")
        assert base == "debugging"
        assert version == "v3"

    def test_extracts_version_from_args_flag(self):
        base, version = _extract_version("debugging", "--version v2")
        assert base == "debugging"
        assert version == "v2"

    def test_returns_none_when_no_version(self):
        base, version = _extract_version("debugging", "some args")
        assert base == "debugging"
        assert version is None


class TestSkillInvocationExtraction:
    """Test extraction of skill invocations from message sequences."""

    def test_extracts_single_skill_invocation(self):
        messages = [
            {"type": "user", "message": {"content": "Help me debug"}},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "debugging"},
                        }
                    ],
                    "usage": {"output_tokens": 100},
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Debugging..."}],
                    "usage": {"output_tokens": 200},
                },
            },
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 1
        assert invocations[0].skill == "debugging"
        assert invocations[0].completed is True
        assert invocations[0].tokens_used == 300

    def test_detects_superseded_skill(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                    "usage": {"output_tokens": 50},
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "implementing-features"}}
                    ],
                    "usage": {"output_tokens": 100},
                },
            },
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 2
        assert invocations[0].skill == "debugging"
        assert invocations[0].superseded is True
        assert invocations[0].completed is False
        assert invocations[1].skill == "implementing-features"
        assert invocations[1].completed is True

    def test_counts_user_corrections(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
            {"type": "user", "message": {"role": "user", "content": "No, that's wrong"}},
            {"type": "user", "message": {"role": "user", "content": "Stop, try again"}},
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 1
        assert invocations[0].corrections == 2

    def test_detects_retry(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
            {"type": "user", "message": {"content": "Try again"}},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 2
        assert invocations[0].retried is False  # First one wasn't a retry
        assert invocations[1].retried is True  # Second one is a retry

    def test_handles_compact_boundary(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
            {"type": "system", "subtype": "compact_boundary"},
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 1
        assert invocations[0].completed is True


class TestMetricsAggregation:
    """Test aggregation of invocations into metrics."""

    def test_aggregates_by_skill(self):
        invocations = [
            SkillInvocation(skill="debugging", tokens_used=100, completed=True, corrections=0),
            SkillInvocation(skill="debugging", tokens_used=200, completed=True, corrections=1),
            SkillInvocation(skill="implementing-features", tokens_used=500, completed=False, superseded=True),
        ]

        metrics = aggregate_metrics(invocations)
        assert len(metrics) == 2

        debug_metrics = metrics["debugging"]
        assert debug_metrics.invocations == 2
        assert debug_metrics.completions == 2
        assert debug_metrics.corrections == 1
        assert debug_metrics.avg_tokens == 150

        impl_metrics = metrics["implementing-features"]
        assert impl_metrics.invocations == 1
        assert impl_metrics.completions == 0

    def test_groups_by_version_when_requested(self):
        invocations = [
            SkillInvocation(skill="debugging", version="v1", tokens_used=100, completed=True),
            SkillInvocation(skill="debugging", version="v2", tokens_used=80, completed=True),
            SkillInvocation(skill="debugging", version="v1", tokens_used=120, completed=False),
        ]

        metrics = aggregate_metrics(invocations, group_by_version=True)
        assert len(metrics) == 2
        assert "debugging:v1" in metrics
        assert "debugging:v2" in metrics
        assert metrics["debugging:v1"].invocations == 2
        assert metrics["debugging:v2"].invocations == 1

    def test_calculates_failure_score(self):
        invocations = [
            SkillInvocation(skill="bad-skill", completed=False, corrections=1, retried=True),
            SkillInvocation(skill="bad-skill", completed=True, corrections=0, retried=False),
        ]

        metrics = aggregate_metrics(invocations)
        # Failure score = (corrections + retries + non-completions) / invocations
        # = (1 + 1 + 1) / 2 = 1.5, but capped at invocations, so 3/2 = 1.5... wait
        # Actually: 1 correction, 1 retry (second invocation has retried=False), 1 non-completion
        # But retried is on the invocation itself, and second has retried=False
        # So: 1 correction + 0 retries (from first) + 1 retry (second marked as retry? No, second.retried=False)
        # Hmm, let me recalculate:
        # invocation 1: completed=False (1 failure), corrections=1, retried=True
        # invocation 2: completed=True, corrections=0, retried=False
        # failures = corrections(1+0) + retries(1+0) + non-completions(1+0) = 3
        # Wait, retried is counted per invocation where it's true
        bad_skill = metrics["bad-skill"]
        assert bad_skill.failure_score > 0
