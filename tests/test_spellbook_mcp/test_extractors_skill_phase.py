"""Tests for skill phase extraction."""

import pytest


def test_extract_skill_phase_no_skill_invocation():
    """Test extraction returns None when no implementing-features invocation exists."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    result = extract_skill_phase(messages)
    assert result is None


def test_extract_skill_phase_detects_phase_2():
    """Test extraction detects Phase 2 from assistant messages after skill invocation."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase

    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}],
        },
        {
            "role": "assistant",
            "content": "## Phase 2: Design\n\nLet me create the design document...",
        },
    ]

    result = extract_skill_phase(messages)
    assert result == "Phase 2: Design"


def test_extract_skill_phase_empty_messages():
    """Test extraction with empty message list."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    result = extract_skill_phase([])
    assert result is None


def test_extract_skill_phase_highest_wins():
    """Test that highest phase is returned when multiple phases mentioned."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "Starting Phase 1: Research..."},
        {"role": "assistant", "content": "Moving to Phase 2: Design..."},
        {"role": "assistant", "content": "Now in Phase 3: Implementation Planning"},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 3: Implementation Planning"


def test_extract_skill_phase_highest_wins_not_last():
    """Test that highest phase wins even when lower phase appears later.

    This ensures the extractor tracks HIGHEST phase reached, not LAST phase mentioned.
    Sessions may reference earlier phases in retrospect without regressing progress.
    """
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "## Phase 3: Implementation Planning\n\nStarting planning..."},
        {"role": "assistant", "content": "Wait, I need to revisit Phase 1: Research\n\nLet me check something..."},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 3: Implementation Planning"


def test_extract_skill_phase_ignores_other_skills():
    """Test that phases are only tracked after implementing-features invocation."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "debugging"}}]},
        {"role": "assistant", "content": "Phase 4: Implementation"},
    ]
    result = extract_skill_phase(messages)
    assert result is None


def test_extract_skill_phase_phase_0():
    """Test detection of Phase 0 (Configuration Wizard)."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "## Phase 0: Configuration Wizard\n\nLet me collect your preferences..."},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 0: Configuration Wizard"


def test_extract_skill_phase_phase_1_5():
    """Test detection of Phase 1.5 (Informed Discovery)."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "## Phase 1.5: Informed Discovery\n\nNow that research is complete..."},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 1.5: Informed Discovery"


def test_extract_skill_phase_phase_4():
    """Test detection of Phase 4 (Implementation)."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "## Phase 4: Implementation\n\nExecuting the implementation plan..."},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 4: Implementation"


def test_extract_skill_phase_handles_content_blocks():
    """Test extraction handles content as list of blocks."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": [{"type": "text", "text": "## Phase 2: Design\n\nCreating design..."}]},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 2: Design"


def test_extract_skill_phase_subphase_detection():
    """Test that subphases (e.g., 2.1, 2.2) map to parent phase."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "### Phase 2.3: Review Design\n\nReviewing the design document..."},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 2: Design"


def test_extract_skill_phase_only_tracks_after_most_recent_invocation():
    """Test that only phases after the MOST RECENT skill invocation are tracked."""
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "Phase 4: Implementation complete!"},
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "Phase 1: Research starting..."},
    ]
    result = extract_skill_phase(messages)
    # Should return Phase 1 because that's after the MOST RECENT invocation
    assert result == "Phase 1: Research"


def test_extract_skill_phase_1_5_not_1():
    r"""Test that Phase 1.5 is detected correctly, not as Phase 1.

    This tests the negative lookahead (?!\.) in the Phase 1 pattern,
    which prevents matching if a decimal point follows "1".
    Without it, "Phase 1.5" would incorrectly match "Phase 1".
    """
    from spellbook_mcp.extractors.skill_phase import extract_skill_phase
    messages = [
        {"role": "assistant", "tool_calls": [{"tool": "Skill", "args": {"skill": "implementing-features"}}]},
        {"role": "assistant", "content": "## Phase 1.5: Informed Discovery\n\n..."},
    ]
    result = extract_skill_phase(messages)
    assert result == "Phase 1.5: Informed Discovery"
    assert result != "Phase 1: Research"
