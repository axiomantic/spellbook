"""Tests for Audio and Notification Configuration section in AGENTS.spellbook.md.

Task 17: The installable template should include an Audio and Notification
Configuration section between Session Resume and Project Knowledge, referencing
the audio-notifications skill for TTS (kokoro) and OS notification details.
"""

from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "AGENTS.spellbook.md"

SECTION_HEADING = "## Audio and Notification Configuration"


class TestAudioNotificationSection:
    """AGENTS.spellbook.md should contain an Audio and Notification Configuration section."""

    def _read_template(self) -> str:
        return TEMPLATE_PATH.read_text(encoding="utf-8")

    def _get_section(self, content: str) -> str:
        """Extract the Audio and Notification Configuration section text."""
        start = content.index(SECTION_HEADING)
        next_section = content.index("\n## ", start + 1)
        return content[start:next_section]

    def test_section_exists(self):
        """The template should have an Audio and Notification Configuration section."""
        content = self._read_template()
        assert SECTION_HEADING in content

    def test_section_after_session_resume(self):
        """Audio and Notification Configuration should appear after Session Resume."""
        content = self._read_template()
        resume_pos = content.index("## Session Resume")
        section_pos = content.index(SECTION_HEADING)
        assert section_pos > resume_pos

    def test_section_before_project_knowledge(self):
        """Audio and Notification Configuration should appear before Project Knowledge."""
        content = self._read_template()
        section_pos = content.index(SECTION_HEADING)
        project_knowledge_pos = content.index("## Project Knowledge (AGENTS.md)")
        assert section_pos < project_knowledge_pos

    def test_references_audio_notifications_skill(self):
        """The section should reference the audio-notifications skill."""
        content = self._read_template()
        section = self._get_section(content)
        assert "audio-notifications" in section

    def test_mentions_tts_kokoro(self):
        """The section should mention TTS and kokoro."""
        content = self._read_template()
        section = self._get_section(content)
        assert "TTS" in section
        assert "kokoro" in section

    def test_mentions_os_notifications(self):
        """The section should mention OS notification configuration."""
        content = self._read_template()
        section = self._get_section(content)
        assert "notification" in section.lower()

    def test_skill_listed_in_key_references(self):
        """The audio-notifications skill should appear in the Key Skill References."""
        content = self._read_template()
        refs_start = content.index("## Key Skill References")
        next_section = content.index("\n## ", refs_start + 1)
        refs_section = content[refs_start:next_section]
        assert "audio-notifications" in refs_section
