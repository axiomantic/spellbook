"""Tests for persona extraction."""

import pytest


def test_extract_persona_fun_mode():
    """Test extracting fun mode persona from messages."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {
            "role": "assistant",
            "content": "SESSION MODE: Fun mode active\nPERSONA: Grizzled Detective\nCONTEXT: 1940s noir"
        }
    ]

    result = extract_persona(messages)
    assert result == "fun:Grizzled Detective"


def test_extract_persona_tarot_mode():
    """Test extracting tarot mode marker."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {
            "role": "assistant",
            "content": "SESSION MODE: Tarot mode active (roundtable dialogue)"
        }
    ]

    result = extract_persona(messages)
    assert result == "tarot"


def test_extract_persona_standard():
    """Test extraction with standard mode."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"}
    ]

    result = extract_persona(messages)
    assert result is None


def test_extract_persona_empty_messages():
    """Test extraction with empty message list."""
    from spellbook_mcp.extractors.persona import extract_persona

    result = extract_persona([])
    assert result is None


def test_extract_persona_handles_missing_content():
    """Test extraction handles messages without content field."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {"role": "assistant", "timestamp": "2026-01-16T10:00:00Z"}
    ]

    result = extract_persona(messages)
    assert result is None


def test_extract_persona_handles_none_content():
    """Test extraction handles messages with None content."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {"role": "assistant", "timestamp": "2026-01-16T10:00:00Z", "content": None}
    ]

    result = extract_persona(messages)
    assert result is None


def test_extract_persona_handles_list_content():
    """Test extraction handles structured content blocks."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "SESSION MODE: Fun mode active"},
                {"type": "text", "text": "PERSONA: Zen Master"}
            ]
        }
    ]

    result = extract_persona(messages)
    assert result == "fun:Zen Master"


def test_extract_persona_tarot_case_insensitive():
    """Test tarot mode detection is case insensitive."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {
            "role": "assistant",
            "content": "SESSION MODE: TAROT MODE ACTIVE (roundtable)"
        }
    ]

    result = extract_persona(messages)
    assert result == "tarot"


def test_extract_persona_takes_latest():
    """Test that latest persona wins when multiple found."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {
            "role": "assistant",
            "content": "SESSION MODE: Fun mode active\nPERSONA: Grizzled Detective"
        },
        {
            "role": "assistant",
            "content": "SESSION MODE: Fun mode active\nPERSONA: Zen Master"
        }
    ]

    result = extract_persona(messages)
    assert result == "fun:Zen Master"


def test_extract_persona_fun_mode_overrides_tarot():
    """Test that fun mode persona overrides tarot if found later."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {
            "role": "assistant",
            "content": "SESSION MODE: Tarot mode active"
        },
        {
            "role": "assistant",
            "content": "PERSONA: Nature Documentary Narrator"
        }
    ]

    result = extract_persona(messages)
    assert result == "fun:Nature Documentary Narrator"


def test_extract_persona_strips_whitespace():
    """Test that persona name is properly trimmed."""
    from spellbook_mcp.extractors.persona import extract_persona

    messages = [
        {
            "role": "assistant",
            "content": "PERSONA:   Dramatic Chef   \nCONTEXT: kitchen"
        }
    ]

    result = extract_persona(messages)
    assert result == "fun:Dramatic Chef"
