"""Integration tests for exfiltration resistance: canary tokens + credential leak detection.

Tests the combined behavior of canary token creation/detection, credential pattern
scanning, and evidence masking to validate the full exfiltration defense pipeline.

Validates:
- Canary token uniqueness across multiple creates
- Canary detection in output content
- Canary trigger logs CRITICAL security event
- No false triggers on similar-looking but unregistered strings
- Credential type detection (AWS, GitHub, OpenAI, private key, JWT)
- Evidence masking (raw credentials never appear in findings)
- Combined canary + credential detection with correct action priorities
"""

import pytest

from spellbook_mcp.db import get_connection, init_db
from spellbook_mcp.security.tools import (
    do_canary_check,
    do_canary_create,
    do_check_output,
    do_query_events,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    """Initialize a fresh test database and return its string path."""
    path = str(tmp_path / "exfil_test.db")
    init_db(path)
    return path


# ---------------------------------------------------------------------------
# TestCanaryTokens: uniqueness, detection, event logging, false triggers
# ---------------------------------------------------------------------------


class TestCanaryTokens:
    """Canary token creation uniqueness and detection behavior."""

    def test_creation_uniqueness_ten_tokens_all_distinct(self, db_path):
        """Creating multiple canary tokens produces unique values."""
        tokens = set()
        for _ in range(10):
            result = do_canary_create("prompt", db_path=db_path)
            tokens.add(result["token"])
        assert len(tokens) == 10

    def test_creation_uniqueness_across_types(self, db_path):
        """Tokens are unique even across different token types."""
        tokens = set()
        for token_type in ("prompt", "file", "config", "output"):
            for _ in range(3):
                result = do_canary_create(token_type, db_path=db_path)
                tokens.add(result["token"])
        assert len(tokens) == 12

    def test_detection_in_output(self, db_path):
        """A registered canary embedded in output content is detected."""
        created = do_canary_create("prompt", context="test marker", db_path=db_path)
        token = created["token"]

        result = do_canary_check(f"Some output with {token} inside", db_path=db_path)

        assert result["clean"] is False
        assert len(result["triggered_canaries"]) == 1
        assert result["triggered_canaries"][0]["token"] == token
        assert result["triggered_canaries"][0]["token_type"] == "prompt"
        assert result["triggered_canaries"][0]["context"] == "test marker"

    def test_trigger_logs_critical_event(self, db_path):
        """Triggering a canary logs a CRITICAL security event."""
        created = do_canary_create("file", db_path=db_path)
        do_canary_check(created["token"], db_path=db_path)

        events = do_query_events(
            event_type="canary_triggered",
            db_path=db_path,
        )
        assert events["success"] is True
        assert events["count"] >= 1

        event = events["events"][0]
        assert event["severity"] == "CRITICAL"
        assert event["event_type"] == "canary_triggered"
        assert created["token"] in event["detail"]

    def test_no_false_trigger_on_prefix_alone(self, db_path):
        """The bare 'CANARY-' prefix does not trigger detection."""
        do_canary_create("prompt", db_path=db_path)
        result = do_canary_check("Found CANARY- prefix in text", db_path=db_path)
        assert result["clean"] is True

    def test_no_false_trigger_on_unregistered_format(self, db_path):
        """A properly formatted but unregistered canary string does not trigger."""
        do_canary_create("prompt", db_path=db_path)
        result = do_canary_check("CANARY-000000000000-P", db_path=db_path)
        assert result["clean"] is True

    def test_no_false_trigger_on_partial_token(self, db_path):
        """A partial match of a registered canary does not trigger."""
        created = do_canary_create("config", db_path=db_path)
        partial = created["token"][:10]
        result = do_canary_check(f"Contains {partial} only", db_path=db_path)
        assert result["clean"] is True

    def test_no_false_trigger_on_altered_type_code(self, db_path):
        """Altering the type suffix of a registered token avoids false trigger."""
        created = do_canary_create("prompt", db_path=db_path)
        # Replace trailing type code: -P becomes -X
        altered = created["token"][:-1] + "X"
        result = do_canary_check(f"Contains {altered}", db_path=db_path)
        assert result["clean"] is True


# ---------------------------------------------------------------------------
# TestCredentialLeakDetection: each credential type + evidence masking
# ---------------------------------------------------------------------------


class TestCredentialLeakDetection:
    """Detection of credential patterns and masking of evidence."""

    def test_detects_aws_access_key(self):
        """AWS access key pattern (AKIA...) is detected."""
        result = do_check_output("Key: AKIAIOSFODNN7EXAMPLE")
        assert result["clean"] is False
        assert any(
            leak["type"] == "aws_access_key"
            for leak in result["credential_leaks"]
        )

    def test_detects_github_personal_access_token(self):
        """GitHub PAT pattern (ghp_...) is detected."""
        result = do_check_output(
            "Token: ghp_ABCDEFabcdef1234567890abcdef12345678"
        )
        assert result["clean"] is False
        assert any(
            leak["type"] == "github_pat"
            for leak in result["credential_leaks"]
        )

    def test_detects_openai_api_key(self):
        """OpenAI API key pattern (sk-...) is detected."""
        # Pattern is sk-[A-Za-z0-9]{20,} -- 20+ alphanumeric chars after sk-
        key = "sk-aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567890123456789AB"
        result = do_check_output(f"Key: {key}")
        assert result["clean"] is False
        assert any(
            leak["type"] == "openai_api_key"
            for leak in result["credential_leaks"]
        )

    def test_detects_private_key_header(self):
        """Private key header (-----BEGIN RSA PRIVATE KEY-----) is detected."""
        result = do_check_output(
            "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."
        )
        assert result["clean"] is False
        assert any(
            leak["type"] == "private_key"
            for leak in result["credential_leaks"]
        )

    def test_detects_jwt_token(self):
        """JWT token (eyJ...) is detected."""
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        result = do_check_output(f"Bearer {jwt}")
        assert result["clean"] is False
        assert any(
            leak["type"] == "jwt"
            for leak in result["credential_leaks"]
        )

    def test_evidence_masking_aws_key(self):
        """AWS access key is masked in returned evidence."""
        key = "AKIAIOSFODNN7EXAMPLE"
        result = do_check_output(f"Key: {key}")
        result_str = str(result)
        assert key not in result_str

    def test_evidence_masking_github_token(self):
        """GitHub PAT is masked in returned evidence."""
        token = "ghp_ABCDEFabcdef1234567890abcdef12345678"
        result = do_check_output(f"Token: {token}")
        result_str = str(result)
        assert token not in result_str

    def test_evidence_masking_openai_key(self):
        """OpenAI API key is masked in returned evidence."""
        key = "sk-aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567890123456789AB"
        result = do_check_output(f"Key: {key}")
        result_str = str(result)
        assert key not in result_str

    def test_evidence_masking_private_key(self):
        """Private key header is masked in returned evidence."""
        header = "-----BEGIN RSA PRIVATE KEY-----"
        result = do_check_output(f"{header}\nMIIE...")
        result_str = str(result)
        assert header not in result_str

    def test_evidence_masking_jwt(self):
        """JWT is masked in returned evidence."""
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        result = do_check_output(f"Bearer {jwt}")
        result_str = str(result)
        assert jwt not in result_str

    def test_evidence_never_contains_raw_credential_for_any_type(self):
        """No credential type leaks raw value through any result field."""
        credentials = [
            ("AKIAIOSFODNN7EXAMPLE", "aws_access_key"),
            ("ghp_ABCDEFabcdef1234567890abcdef12345678", "github_pat"),
            ("sk-aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567890123456789AB", "openai_api_key"),
            ("-----BEGIN RSA PRIVATE KEY-----", "private_key"),
            (
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
                ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
                "jwt",
            ),
        ]
        for cred_value, expected_type in credentials:
            result = do_check_output(f"Found: {cred_value}")
            for leak in result["credential_leaks"]:
                assert cred_value not in leak.get("evidence", ""), (
                    f"Raw {expected_type} leaked in evidence field"
                )
                assert cred_value not in str(leak), (
                    f"Raw {expected_type} leaked in finding dict"
                )


# ---------------------------------------------------------------------------
# Integration: canary + output check combined
# ---------------------------------------------------------------------------


class TestCanaryAndCredentialIntegration:
    """Combined detection of canary tokens alongside credential leaks."""

    def test_both_canary_and_credential_detected(self, db_path):
        """Output containing both a canary and a credential detects both."""
        created = do_canary_create("output", context="integration test", db_path=db_path)
        token = created["token"]

        text = f"Output: {token} and also AKIAIOSFODNN7EXAMPLE leaked"
        result = do_check_output(text, db_path=db_path)

        assert result["clean"] is False
        assert len(result["canary_leaks"]) >= 1
        assert len(result["credential_leaks"]) >= 1

    def test_canary_triggers_block_action(self, db_path):
        """When a canary is present, action is 'block' regardless of other findings."""
        created = do_canary_create("prompt", db_path=db_path)
        token = created["token"]

        text = f"{token} sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA"
        result = do_check_output(text, db_path=db_path)

        assert result["action"] == "block"

    def test_credential_alone_triggers_redact_action(self, db_path):
        """Without a canary, credential detection triggers 'redact' action."""
        text = "AKIAIOSFODNN7EXAMPLE"
        result = do_check_output(text, db_path=db_path)

        assert result["action"] == "redact"

    def test_clean_output_triggers_pass_action(self, db_path):
        """Output with no canaries or credentials triggers 'pass' action."""
        result = do_check_output("Totally clean output", db_path=db_path)

        assert result["action"] == "pass"

    def test_canary_leak_evidence_masked_in_check_output(self, db_path):
        """Canary token value is masked in do_check_output findings."""
        created = do_canary_create("config", db_path=db_path)
        token = created["token"]

        result = do_check_output(f"Leaked: {token}", db_path=db_path)

        for leak in result["canary_leaks"]:
            assert token not in leak.get("evidence", ""), (
                "Raw canary token leaked in check_output evidence"
            )

    def test_multiple_canaries_and_credentials_all_detected(self, db_path):
        """Multiple canaries and multiple credential types are all found."""
        c1 = do_canary_create("prompt", db_path=db_path)
        c2 = do_canary_create("file", db_path=db_path)

        text = (
            f"Start {c1['token']} middle {c2['token']} "
            "AKIAIOSFODNN7EXAMPLE "
            "ghp_ABCDEFabcdef1234567890abcdef12345678"
        )
        result = do_check_output(text, db_path=db_path)

        assert result["clean"] is False
        assert len(result["canary_leaks"]) == 2
        assert len(result["credential_leaks"]) >= 2
        assert result["action"] == "block"

    def test_canary_check_and_output_check_use_same_db(self, db_path):
        """do_canary_check and do_check_output both find the same canary via shared DB."""
        created = do_canary_create("output", db_path=db_path)
        token = created["token"]
        content = f"Suspicious output with {token}"

        canary_result = do_canary_check(content, db_path=db_path)
        output_result = do_check_output(content, db_path=db_path)

        assert canary_result["clean"] is False
        assert output_result["clean"] is False
        assert len(canary_result["triggered_canaries"]) == 1
        assert len(output_result["canary_leaks"]) == 1
