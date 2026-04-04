"""Tests for WizardContext and WizardResults dataclasses."""

import pytest


class TestWizardResultsDefaults:
    def test_all_fields_default_to_none_or_skip(self):
        """WizardResults fields default to None (skip sentinel)."""
        from installer.wizard import WizardResults

        results = WizardResults()
        assert results.platforms is None
        assert results.security_selections is None
        assert results.tts_intent is None
        assert results.profile_selection is None

    def test_platforms_can_be_set_to_list(self):
        """WizardResults.platforms accepts a list of strings."""
        from installer.wizard import WizardResults

        results = WizardResults(platforms=["claude_code", "gemini"])
        assert results.platforms == ["claude_code", "gemini"]

    def test_security_selections_can_be_set(self):
        """WizardResults.security_selections accepts a dict."""
        from installer.wizard import WizardResults

        results = WizardResults(security_selections={"crypto": True, "sleuth": False})
        assert results.security_selections == {"crypto": True, "sleuth": False}

    def test_tts_intent_true_false_none(self):
        """WizardResults.tts_intent distinguishes True, False, and None."""
        from installer.wizard import WizardResults

        assert WizardResults(tts_intent=True).tts_intent is True
        assert WizardResults(tts_intent=False).tts_intent is False
        assert WizardResults().tts_intent is None

    def test_profile_selection_values(self):
        """WizardResults.profile_selection: slug, empty string (None choice), or None (skipped)."""
        from installer.wizard import WizardResults

        assert WizardResults(profile_selection="zen").profile_selection == "zen"
        assert WizardResults(profile_selection="").profile_selection == ""
        assert WizardResults().profile_selection is None


class TestWizardContext:
    def test_all_fields_required(self):
        """WizardContext requires all fields at construction."""
        from installer.wizard import WizardContext

        ctx = WizardContext(
            available_platforms=["claude_code"],
            cli_platforms=None,
            unset_security_keys=["security.crypto.enabled"],
            existing_config={},
            security_level=None,
            tts_disabled=False,
            tts_already_configured=False,
            profile_already_configured=False,
            available_profiles=[],
            is_upgrade=False,
            is_interactive=True,
            auto_yes=False,
            no_interactive=False,
            reconfigure=False,
        )
        assert ctx.available_platforms == ["claude_code"]
        assert ctx.cli_platforms is None
        assert ctx.auto_yes is False

    def test_cli_platforms_overrides_available(self):
        """WizardContext.cli_platforms is separate from available_platforms."""
        from installer.wizard import WizardContext

        ctx = WizardContext(
            available_platforms=["claude_code", "gemini"],
            cli_platforms=["gemini"],
            unset_security_keys=[],
            existing_config={},
            security_level=None,
            tts_disabled=False,
            tts_already_configured=False,
            profile_already_configured=False,
            available_profiles=[],
            is_upgrade=False,
            is_interactive=True,
            auto_yes=False,
            no_interactive=False,
            reconfigure=False,
        )
        assert ctx.cli_platforms == ["gemini"]
        assert ctx.available_platforms == ["claude_code", "gemini"]


class TestMatchesUnsetKey:
    def test_bare_id_matches_dotted_key(self):
        """Feature ID 'crypto' matches 'security.crypto.enabled'."""
        from installer.wizard import _matches_unset_key

        assert _matches_unset_key("crypto", ["security.crypto.enabled"]) is True

    def test_no_match_when_absent(self):
        """Feature ID 'sleuth' does not match when not in unset keys."""
        from installer.wizard import _matches_unset_key

        assert _matches_unset_key("sleuth", ["security.crypto.enabled"]) is False

    def test_partial_id_does_not_match(self):
        """Feature ID 'crypt' should not match 'security.crypto.enabled'."""
        from installer.wizard import _matches_unset_key

        assert _matches_unset_key("crypt", ["security.crypto.enabled"]) is False

    def test_multiple_keys(self):
        """Feature ID matches when it appears in any key in the list."""
        from installer.wizard import _matches_unset_key

        keys = ["security.spotlighting.enabled", "security.crypto.enabled"]
        assert _matches_unset_key("spotlighting", keys) is True
        assert _matches_unset_key("crypto", keys) is True
        assert _matches_unset_key("lodo", keys) is False
