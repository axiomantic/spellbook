"""Tests for Gemini CLI security policy file and installer integration.

Validates:
- hooks/gemini-policy.toml is valid TOML with expected rules
- All deny rules have deny_message fields
- Expected rule IDs cover key security patterns
- Installer creates policy file to correct location
- Installer is idempotent (running twice produces same result)
"""

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

POLICY_FILE = (
    Path(__file__).resolve().parents[2] / "hooks" / "gemini-policy.toml"
)


def _load_policy() -> dict:
    """Load and parse the policy TOML file."""
    return tomllib.loads(POLICY_FILE.read_text(encoding="utf-8"))


def _get_rules() -> list[dict]:
    """Return the list of rule dicts from the policy file."""
    policy = _load_policy()
    return policy.get("rules", [])


# ---------------------------------------------------------------------------
# TOML validity
# ---------------------------------------------------------------------------


class TestPolicyFileIsValidToml:
    """The policy file must parse as valid TOML."""

    def test_file_exists(self):
        assert POLICY_FILE.exists(), f"Policy file not found at {POLICY_FILE}"

    def test_parses_without_error(self):
        policy = _load_policy()
        assert isinstance(policy, dict)

    def test_has_rules_key(self):
        policy = _load_policy()
        assert "rules" in policy, "Policy must have a [[rules]] array"

    def test_rules_is_list(self):
        policy = _load_policy()
        assert isinstance(policy["rules"], list)

    def test_rules_not_empty(self):
        rules = _get_rules()
        assert len(rules) > 0, "Policy must contain at least one rule"


# ---------------------------------------------------------------------------
# Expected rules present
# ---------------------------------------------------------------------------


EXPECTED_RULE_IDS = [
    "SB-BASH-001",   # rm -rf recursive forced deletion
    "SB-BASH-002",   # curl/wget exfiltration
    "SB-BASH-003",   # sudo commands
    "SB-BASH-004",   # credential file access
    "SB-BASH-005",   # spawn_claude_session
    "SB-BASH-006",   # netcat listeners
]


class TestExpectedRulesPresent:
    """All expected rule IDs must exist in the policy file."""

    def test_all_expected_ids_present(self):
        rules = _get_rules()
        actual_ids = {r["id"] for r in rules}
        for expected_id in EXPECTED_RULE_IDS:
            assert expected_id in actual_ids, (
                f"Missing expected rule: {expected_id}"
            )

    def test_each_rule_has_required_fields(self):
        """Every rule must have id, toolName, decision, and priority."""
        rules = _get_rules()
        required_fields = {"id", "toolName", "decision", "priority"}
        for rule in rules:
            for field_name in required_fields:
                assert field_name in rule, (
                    f"Rule {rule.get('id', '<no id>')} missing field: {field_name}"
                )

    def test_each_rule_has_command_regex(self):
        """Every Bash-targeting rule must have a commandRegex field."""
        rules = _get_rules()
        for rule in rules:
            if rule.get("toolName") == "Bash":
                assert "commandRegex" in rule, (
                    f"Bash rule {rule['id']} missing commandRegex"
                )

    def test_no_duplicate_rule_ids(self):
        """Rule IDs must be unique."""
        rules = _get_rules()
        ids = [r["id"] for r in rules]
        assert len(ids) == len(set(ids)), (
            f"Duplicate rule IDs: {[x for x in ids if ids.count(x) > 1]}"
        )


# ---------------------------------------------------------------------------
# Deny rules have messages
# ---------------------------------------------------------------------------


class TestDenyRulesHaveMessages:
    """All rules with decision='deny' must have a deny_message."""

    def test_all_deny_rules_have_deny_message(self):
        rules = _get_rules()
        deny_rules = [r for r in rules if r.get("decision") == "deny"]
        assert len(deny_rules) > 0, "Expected at least one deny rule"
        for rule in deny_rules:
            assert "deny_message" in rule, (
                f"Deny rule {rule['id']} missing deny_message"
            )
            assert len(rule["deny_message"]) > 0, (
                f"Deny rule {rule['id']} has empty deny_message"
            )

    def test_ask_user_rules_exist(self):
        """At least one rule should use ask_user decision (for spawn_claude_session)."""
        rules = _get_rules()
        ask_rules = [r for r in rules if r.get("decision") == "ask_user"]
        assert len(ask_rules) > 0, "Expected at least one ask_user rule"


# ---------------------------------------------------------------------------
# Installer integration
# ---------------------------------------------------------------------------


class TestInstallerCreatesPolicy:
    """The Gemini installer should create the policy file in the right location."""

    def test_install_policy_creates_file(self, tmp_path):
        from installer.platforms.gemini import install_gemini_policy

        policy_dir = tmp_path / ".gemini" / "policies"
        # policy_dir should NOT exist yet
        assert not policy_dir.exists()

        result = install_gemini_policy(
            spellbook_dir=POLICY_FILE.parents[1],
            gemini_config_dir=tmp_path / ".gemini",
            dry_run=False,
        )

        assert result.success
        expected_file = policy_dir / "spellbook-security.toml"
        assert expected_file.exists(), "Policy file should be created"

    def test_install_policy_content_is_valid_toml(self, tmp_path):
        from installer.platforms.gemini import install_gemini_policy

        install_gemini_policy(
            spellbook_dir=POLICY_FILE.parents[1],
            gemini_config_dir=tmp_path / ".gemini",
            dry_run=False,
        )

        installed = tmp_path / ".gemini" / "policies" / "spellbook-security.toml"
        content = installed.read_text(encoding="utf-8")
        policy = tomllib.loads(content)
        assert "rules" in policy

    def test_install_policy_dry_run_no_write(self, tmp_path):
        from installer.platforms.gemini import install_gemini_policy

        result = install_gemini_policy(
            spellbook_dir=POLICY_FILE.parents[1],
            gemini_config_dir=tmp_path / ".gemini",
            dry_run=True,
        )

        assert result.success
        expected_file = tmp_path / ".gemini" / "policies" / "spellbook-security.toml"
        assert not expected_file.exists(), "Dry run should not create file"

    def test_install_policy_creates_directory(self, tmp_path):
        from installer.platforms.gemini import install_gemini_policy

        gemini_dir = tmp_path / ".gemini"
        # Neither .gemini nor .gemini/policies exists
        assert not gemini_dir.exists()

        install_gemini_policy(
            spellbook_dir=POLICY_FILE.parents[1],
            gemini_config_dir=gemini_dir,
            dry_run=False,
        )

        assert (gemini_dir / "policies").is_dir()


class TestInstallerIdempotent:
    """Running the installer twice should produce the same result."""

    def test_running_twice_produces_same_file(self, tmp_path):
        from installer.platforms.gemini import install_gemini_policy

        kwargs = dict(
            spellbook_dir=POLICY_FILE.parents[1],
            gemini_config_dir=tmp_path / ".gemini",
            dry_run=False,
        )

        result1 = install_gemini_policy(**kwargs)
        installed = tmp_path / ".gemini" / "policies" / "spellbook-security.toml"
        content_after_first = installed.read_text(encoding="utf-8")

        result2 = install_gemini_policy(**kwargs)
        content_after_second = installed.read_text(encoding="utf-8")

        assert result1.success
        assert result2.success
        assert content_after_first == content_after_second

    def test_running_twice_no_extra_rules(self, tmp_path):
        from installer.platforms.gemini import install_gemini_policy

        kwargs = dict(
            spellbook_dir=POLICY_FILE.parents[1],
            gemini_config_dir=tmp_path / ".gemini",
            dry_run=False,
        )

        install_gemini_policy(**kwargs)
        installed = tmp_path / ".gemini" / "policies" / "spellbook-security.toml"
        first_policy = tomllib.loads(installed.read_text(encoding="utf-8"))

        install_gemini_policy(**kwargs)
        second_policy = tomllib.loads(installed.read_text(encoding="utf-8"))

        assert len(first_policy["rules"]) == len(second_policy["rules"])


# ---------------------------------------------------------------------------
# GeminiInstaller.install() integration
# ---------------------------------------------------------------------------


class TestGeminiInstallerIntegration:
    """GeminiInstaller.install() should include policy installation."""

    def test_install_includes_policy_result(self, tmp_path):
        """install() should return a result for the policy component."""
        from installer.platforms.gemini import GeminiInstaller

        spellbook_dir = POLICY_FILE.parents[1]
        config_dir = tmp_path / ".gemini"
        config_dir.mkdir(parents=True)

        # Create the extension dir so the installer doesn't bail early
        ext_dir = spellbook_dir / "extensions" / "gemini"

        with patch(
            "installer.platforms.gemini.check_gemini_cli_available",
            return_value=True,
        ), patch(
            "installer.platforms.gemini.link_extension",
            return_value=(True, "extension linked"),
        ), patch(
            "installer.platforms.gemini.install_daemon",
            return_value=(True, "mocked"),
        ):
            installer = GeminiInstaller(
                spellbook_dir, config_dir, "1.0.0", dry_run=False
            )
            results = installer.install()

        policy_results = [r for r in results if r.component == "security_policy"]
        assert len(policy_results) == 1, (
            f"Expected one security_policy result, got: {[r.component for r in results]}"
        )
        assert policy_results[0].success
