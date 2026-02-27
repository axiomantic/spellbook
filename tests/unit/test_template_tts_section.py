"""Tests for TTS Configuration section in CLAUDE.spellbook.md.

Task 17: The installable template should include a TTS Configuration section
between Session Resume and Encyclopedia, documenting available MCP tools
and usage patterns.
"""

from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "CLAUDE.spellbook.md"


class TestTtsConfigurationSection:
    """CLAUDE.spellbook.md should contain a TTS Configuration section."""

    def _read_template(self) -> str:
        return TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_section_exists(self):
        """The template should have a '## TTS Configuration' section."""
        content = self._read_template()
        assert "## TTS Configuration" in content

    def test_section_after_session_resume(self):
        """TTS Configuration should appear after Session Resume."""
        content = self._read_template()
        resume_pos = content.index("## Session Resume")
        tts_pos = content.index("## TTS Configuration")
        assert tts_pos > resume_pos

    def test_section_before_encyclopedia(self):
        """TTS Configuration should appear before Encyclopedia."""
        content = self._read_template()
        tts_pos = content.index("## TTS Configuration")
        encyclopedia_pos = content.index("## Encyclopedia")
        assert tts_pos < encyclopedia_pos

    def test_documents_kokoro_speak(self):
        """The section should document the kokoro_speak tool."""
        content = self._read_template()
        # Extract the TTS section
        tts_start = content.index("## TTS Configuration")
        # Find next h2 section
        next_section = content.index("\n## ", tts_start + 1)
        tts_section = content[tts_start:next_section]
        assert "kokoro_speak" in tts_section

    def test_documents_kokoro_status(self):
        """The section should document the kokoro_status tool."""
        content = self._read_template()
        tts_start = content.index("## TTS Configuration")
        next_section = content.index("\n## ", tts_start + 1)
        tts_section = content[tts_start:next_section]
        assert "kokoro_status" in tts_section

    def test_documents_tts_session_set(self):
        """The section should document the tts_session_set tool."""
        content = self._read_template()
        tts_start = content.index("## TTS Configuration")
        next_section = content.index("\n## ", tts_start + 1)
        tts_section = content[tts_start:next_section]
        assert "tts_session_set" in tts_section

    def test_documents_tts_config_set(self):
        """The section should document the tts_config_set tool."""
        content = self._read_template()
        tts_start = content.index("## TTS Configuration")
        next_section = content.index("\n## ", tts_start + 1)
        tts_section = content[tts_start:next_section]
        assert "tts_config_set" in tts_section

    def test_mentions_session_mute_unmute(self):
        """The section should explain per-session mute/unmute."""
        content = self._read_template()
        tts_start = content.index("## TTS Configuration")
        next_section = content.index("\n## ", tts_start + 1)
        tts_section = content[tts_start:next_section].lower()
        assert "session" in tts_section
        assert "mute" in tts_section or "enabled=false" in tts_section

    def test_mentions_auto_notifications(self):
        """The section should describe auto-notification behavior."""
        content = self._read_template()
        tts_start = content.index("## TTS Configuration")
        next_section = content.index("\n## ", tts_start + 1)
        tts_section = content[tts_start:next_section].lower()
        assert "pretooluse" in tts_section or "posttooluse" in tts_section or "hook" in tts_section
