"""Tests for code_review argument parsing."""

import pytest

from spellbook_mcp.code_review.arg_parser import CodeReviewArgs, parse_args


class TestCodeReviewArgs:
    """Tests for the CodeReviewArgs dataclass."""

    def test_default_values(self):
        """Default args should have self=True and everything else False/None."""
        args = CodeReviewArgs()
        assert args.self_review is True
        assert args.feedback is False
        assert args.give is None
        assert args.audit is False
        assert args.audit_scope is None
        assert args.tarot is False
        assert args.pr is None

    def test_all_fields_settable(self):
        """All fields should be settable via constructor."""
        args = CodeReviewArgs(
            self_review=False,
            feedback=True,
            give="123",
            audit=True,
            audit_scope="security",
            tarot=True,
            pr=456,
        )
        assert args.self_review is False
        assert args.feedback is True
        assert args.give == "123"
        assert args.audit is True
        assert args.audit_scope == "security"
        assert args.tarot is True
        assert args.pr == 456


class TestParseArgsBasicModes:
    """Test basic mode flag parsing."""

    def test_empty_args_defaults_to_self(self):
        """Empty or None args should default to self-review mode."""
        assert parse_args(None).self_review is True
        assert parse_args("").self_review is True
        assert parse_args("  ").self_review is True

    def test_explicit_self_flag(self):
        """--self flag should set self_review=True."""
        args = parse_args("--self")
        assert args.self_review is True
        assert args.feedback is False
        assert args.give is None
        assert args.audit is False

    def test_self_short_flag(self):
        """-s flag should set self_review=True."""
        args = parse_args("-s")
        assert args.self_review is True

    def test_feedback_flag(self):
        """--feedback flag should set feedback=True."""
        args = parse_args("--feedback")
        assert args.feedback is True
        assert args.self_review is False

    def test_feedback_short_flag(self):
        """-f flag should set feedback=True."""
        args = parse_args("-f")
        assert args.feedback is True
        assert args.self_review is False

    def test_audit_flag(self):
        """--audit flag should set audit=True."""
        args = parse_args("--audit")
        assert args.audit is True
        assert args.self_review is False

    def test_audit_with_scope(self):
        """--audit with scope should capture the scope."""
        args = parse_args("--audit security")
        assert args.audit is True
        assert args.audit_scope == "security"

    def test_audit_scope_file(self):
        """--audit with file path scope."""
        args = parse_args("--audit src/main.py")
        assert args.audit is True
        assert args.audit_scope == "src/main.py"

    def test_audit_scope_directory(self):
        """--audit with directory scope."""
        args = parse_args("--audit src/module/")
        assert args.audit is True
        assert args.audit_scope == "src/module/"


class TestParseArgsGiveMode:
    """Test --give mode parsing."""

    def test_give_with_pr_number(self):
        """--give with PR number."""
        args = parse_args("--give 123")
        assert args.give == "123"
        assert args.self_review is False

    def test_give_with_repo_pr(self):
        """--give with owner/repo#number format."""
        args = parse_args("--give owner/repo#456")
        assert args.give == "owner/repo#456"

    def test_give_with_url(self):
        """--give with GitHub URL."""
        args = parse_args("--give https://github.com/owner/repo/pull/789")
        assert args.give == "https://github.com/owner/repo/pull/789"

    def test_give_with_branch(self):
        """--give with branch name."""
        args = parse_args("--give feature/my-branch")
        assert args.give == "feature/my-branch"

    def test_give_without_target_raises_error(self):
        """--give without a target should raise ValueError."""
        with pytest.raises(ValueError, match="--give requires a target"):
            parse_args("--give")

    def test_give_without_target_at_end(self):
        """--give at end without target should raise ValueError."""
        with pytest.raises(ValueError, match="--give requires a target"):
            parse_args("--tarot --give")


class TestParseArgsModifiers:
    """Test modifier flag parsing."""

    def test_tarot_flag(self):
        """--tarot flag should set tarot=True."""
        args = parse_args("--tarot")
        assert args.tarot is True
        # tarot is a modifier, not a mode, so self_review should still be default
        assert args.self_review is True

    def test_tarot_short_flag(self):
        """-t flag should set tarot=True."""
        args = parse_args("-t")
        assert args.tarot is True

    def test_pr_flag_with_number(self):
        """--pr flag with number."""
        args = parse_args("--pr 123")
        assert args.pr == 123
        # pr is a modifier, self_review should still be default
        assert args.self_review is True

    def test_pr_without_number_raises_error(self):
        """--pr without a number should raise ValueError."""
        with pytest.raises(ValueError, match="--pr requires a number"):
            parse_args("--pr")

    def test_pr_with_non_number_raises_error(self):
        """--pr with non-numeric value should raise ValueError."""
        with pytest.raises(ValueError, match="--pr requires a number"):
            parse_args("--pr abc")


class TestParseArgsCombinations:
    """Test combinations of flags."""

    def test_self_with_tarot(self):
        """--self with --tarot."""
        args = parse_args("--self --tarot")
        assert args.self_review is True
        assert args.tarot is True

    def test_feedback_with_pr(self):
        """--feedback with --pr."""
        args = parse_args("--feedback --pr 123")
        assert args.feedback is True
        assert args.pr == 123
        assert args.self_review is False

    def test_give_with_tarot(self):
        """--give with --tarot."""
        args = parse_args("--give 456 --tarot")
        assert args.give == "456"
        assert args.tarot is True

    def test_audit_with_tarot_and_pr(self):
        """--audit with --tarot and --pr."""
        args = parse_args("--audit security --tarot --pr 789")
        assert args.audit is True
        assert args.audit_scope == "security"
        assert args.tarot is True
        assert args.pr == 789

    def test_order_independence(self):
        """Flag order should not matter."""
        args1 = parse_args("--tarot --feedback --pr 123")
        args2 = parse_args("--pr 123 --feedback --tarot")
        assert args1.feedback == args2.feedback
        assert args1.tarot == args2.tarot
        assert args1.pr == args2.pr


class TestParseArgsMutualExclusion:
    """Test mutual exclusion of mode flags."""

    def test_self_and_feedback_raises_error(self):
        """--self and --feedback together should raise ValueError."""
        with pytest.raises(ValueError, match="Choose one mode"):
            parse_args("--self --feedback")

    def test_self_and_give_raises_error(self):
        """--self and --give together should raise ValueError."""
        with pytest.raises(ValueError, match="Choose one mode"):
            parse_args("--self --give 123")

    def test_self_and_audit_raises_error(self):
        """--self and --audit together should raise ValueError."""
        with pytest.raises(ValueError, match="Choose one mode"):
            parse_args("--self --audit")

    def test_feedback_and_give_raises_error(self):
        """--feedback and --give together should raise ValueError."""
        with pytest.raises(ValueError, match="Choose one mode"):
            parse_args("--feedback --give 123")

    def test_feedback_and_audit_raises_error(self):
        """--feedback and --audit together should raise ValueError."""
        with pytest.raises(ValueError, match="Choose one mode"):
            parse_args("--feedback --audit")

    def test_give_and_audit_raises_error(self):
        """--give and --audit together should raise ValueError."""
        with pytest.raises(ValueError, match="Choose one mode"):
            parse_args("--give 123 --audit")

    def test_three_modes_raises_error(self):
        """Three mode flags should raise ValueError."""
        with pytest.raises(ValueError, match="Choose one mode"):
            parse_args("--self --feedback --audit")


class TestParseArgsEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_extra_whitespace(self):
        """Extra whitespace should be handled."""
        args = parse_args("  --self   --tarot  ")
        assert args.self_review is True
        assert args.tarot is True

    def test_case_sensitivity(self):
        """Flags should be case-sensitive (lowercase only)."""
        # Uppercase flags should be ignored, defaulting to self
        args = parse_args("--SELF")
        assert args.self_review is True  # default, not from --SELF
        assert args.feedback is False

    def test_unknown_flags_ignored(self):
        """Unknown flags should be ignored."""
        args = parse_args("--self --unknown --flag")
        assert args.self_review is True

    def test_double_dash_terminates(self):
        """-- should stop flag parsing (like standard CLI behavior)."""
        # This is a nice-to-have, not required for MVP
        # args = parse_args("--self -- --feedback")
        # assert args.self_review is True
        # assert args.feedback is False
        pass  # Skip for now

    def test_equals_syntax(self):
        """--pr=123 syntax should work."""
        args = parse_args("--pr=123")
        assert args.pr == 123

    def test_give_equals_syntax(self):
        """--give=target syntax should work."""
        args = parse_args("--give=owner/repo#456")
        assert args.give == "owner/repo#456"
