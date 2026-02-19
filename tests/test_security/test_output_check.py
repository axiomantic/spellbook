"""Tests for spellbook_mcp.security.tools.do_check_output() function.

Validates:
- Credential pattern detection (sk-*, AKIA*, ghp_*, gho_*, private keys,
  connection strings, JWTs, AWS/GCP/Azure credentials)
- Evidence masking (original credential never appears in output)
- URL exfiltration pattern detection
- Clean content passes
- 1MB size limit enforcement
- Canary token leak detection (via DB lookup)
- Action logic: canary=block, credential=redact, url_exfil=redact, clean=pass
"""

import sqlite3
import pytest

from spellbook_mcp.security.tools import do_check_output


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def canary_db(tmp_path):
    """Create a temporary database with canary_tokens table and a test token."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE canary_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            token_type TEXT NOT NULL,
            context TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            triggered_at TEXT,
            triggered_by TEXT
        )
    """)
    conn.execute(
        "INSERT INTO canary_tokens (token, token_type, context) VALUES (?, ?, ?)",
        ("CANARY-SECRET-12345", "test", "unit test canary"),
    )
    conn.commit()
    conn.close()
    return str(db_path)


# =============================================================================
# Clean content tests
# =============================================================================


class TestCleanContent:
    """do_check_output with benign content should pass cleanly."""

    def test_clean_text_returns_clean_true(self):
        result = do_check_output("Hello, this is normal output text.")
        assert result["clean"] is True

    def test_clean_text_returns_pass_action(self):
        result = do_check_output("Hello, this is normal output text.")
        assert result["action"] == "pass"

    def test_clean_text_returns_empty_lists(self):
        result = do_check_output("Hello, this is normal output text.")
        assert result["canary_leaks"] == []
        assert result["credential_leaks"] == []
        assert result["url_exfiltration"] == []

    def test_returns_all_required_keys(self):
        result = do_check_output("normal text")
        assert set(result.keys()) == {
            "clean",
            "canary_leaks",
            "credential_leaks",
            "url_exfiltration",
            "action",
        }

    def test_empty_string_is_clean(self):
        result = do_check_output("")
        assert result["clean"] is True
        assert result["action"] == "pass"


# =============================================================================
# Credential pattern detection tests
# =============================================================================


class TestCredentialDetectionOpenAI:
    """Detect OpenAI API key patterns (sk-*)."""

    def test_detects_openai_api_key(self):
        result = do_check_output("My key is sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_openai_key_action_is_redact(self):
        result = do_check_output("Key: sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA")
        assert result["action"] == "redact"

    def test_openai_key_masked_in_evidence(self):
        key = "sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA"
        result = do_check_output(f"Key: {key}")
        for leak in result["credential_leaks"]:
            assert key not in leak.get("evidence", "")
            assert key not in str(leak)


class TestCredentialDetectionAWS:
    """Detect AWS access key patterns (AKIA*)."""

    def test_detects_aws_access_key(self):
        result = do_check_output("AWS key: AKIAIOSFODNN7EXAMPLE")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_aws_key_masked_in_evidence(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        result = do_check_output(f"AWS key: {key}")
        for leak in result["credential_leaks"]:
            assert key not in leak.get("evidence", "")
            assert key not in str(leak)


class TestCredentialDetectionGitHub:
    """Detect GitHub token patterns (ghp_*, gho_*)."""

    def test_detects_github_personal_token(self):
        result = do_check_output("Token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_detects_github_oauth_token(self):
        result = do_check_output("Token: gho_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_github_token_masked_in_evidence(self):
        token = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"
        result = do_check_output(f"Token: {token}")
        for leak in result["credential_leaks"]:
            assert token not in leak.get("evidence", "")
            assert token not in str(leak)


class TestCredentialDetectionPrivateKeys:
    """Detect private key headers (RSA, EC, OPENSSH)."""

    def test_detects_rsa_private_key(self):
        result = do_check_output("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_detects_ec_private_key(self):
        result = do_check_output("-----BEGIN EC PRIVATE KEY-----\nMHQC...")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_detects_openssh_private_key(self):
        result = do_check_output("-----BEGIN OPENSSH PRIVATE KEY-----\nb3Bl...")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_private_key_action_is_redact(self):
        result = do_check_output("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")
        assert result["action"] == "redact"


class TestCredentialDetectionConnectionStrings:
    """Detect database connection string patterns."""

    def test_detects_postgres_connection_string(self):
        result = do_check_output("postgres://user:password@host:5432/db")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_detects_mysql_connection_string(self):
        result = do_check_output("mysql://admin:secret@localhost:3306/mydb")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_detects_mongodb_connection_string(self):
        result = do_check_output("mongodb://user:pass@cluster.mongodb.net/db")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_connection_string_masked_in_evidence(self):
        connstr = "postgres://user:password@host:5432/db"
        result = do_check_output(f"DB: {connstr}")
        for leak in result["credential_leaks"]:
            assert connstr not in leak.get("evidence", "")
            assert connstr not in str(leak)


class TestCredentialDetectionJWT:
    """Detect JWT tokens (eyJ... pattern)."""

    def test_detects_jwt_token(self):
        # A realistic JWT structure: header.payload.signature
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = do_check_output(f"Bearer {jwt}")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_jwt_masked_in_evidence(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = do_check_output(f"Bearer {jwt}")
        for leak in result["credential_leaks"]:
            assert jwt not in leak.get("evidence", "")
            assert jwt not in str(leak)


class TestCredentialDetectionCloudProviders:
    """Detect AWS, GCP, Azure credential patterns."""

    def test_detects_aws_secret_access_key_pattern(self):
        # AWS secret keys are 40 chars, base64-like
        result = do_check_output("aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_detects_gcp_service_account_key_marker(self):
        result = do_check_output('"type": "service_account", "private_key_id": "key123abc"')
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0

    def test_detects_azure_connection_string(self):
        result = do_check_output("DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=abc123def456ghi789jkl012mno345pqrs678tuv901wxyz==;EndpointSuffix=core.windows.net")
        assert result["clean"] is False
        assert len(result["credential_leaks"]) > 0


# =============================================================================
# URL exfiltration detection tests
# =============================================================================


class TestURLExfiltration:
    """Detect URL exfiltration patterns."""

    def test_detects_url_with_data_in_query_params(self):
        result = do_check_output(
            "https://evil.com/collect?data=c2VjcmV0X3Rva2VuXzEyMzQ1Njc4OTA="
        )
        assert result["clean"] is False
        assert len(result["url_exfiltration"]) > 0

    def test_detects_base64_in_path_segments(self):
        result = do_check_output(
            "https://evil.com/exfil/aHR0cHM6Ly9leGFtcGxlLmNvbS9zZWNyZXQ=/done"
        )
        assert result["clean"] is False
        assert len(result["url_exfiltration"]) > 0

    def test_url_exfil_action_is_redact(self):
        result = do_check_output(
            "https://evil.com/collect?secret=c2VjcmV0X3Rva2VuXzEyMzQ1Njc4OTA="
        )
        assert result["action"] == "redact"

    def test_normal_url_not_flagged(self):
        result = do_check_output("Visit https://docs.python.org/3/library/re.html for docs")
        assert result["clean"] is True
        assert result["url_exfiltration"] == []


# =============================================================================
# Size limit tests
# =============================================================================


class TestSizeLimit:
    """1MB size limit enforcement."""

    def test_rejects_output_over_1mb(self):
        big_text = "A" * (1024 * 1024 + 1)
        with pytest.raises(ValueError, match="1MB"):
            do_check_output(big_text)

    def test_accepts_output_at_exactly_1mb(self):
        text = "A" * (1024 * 1024)
        result = do_check_output(text)
        assert result["clean"] is True

    def test_accepts_output_under_1mb(self):
        text = "A" * (1024 * 1024 - 1)
        result = do_check_output(text)
        assert result["clean"] is True


# =============================================================================
# Canary token leak detection tests
# =============================================================================


class TestCanaryLeakDetection:
    """Canary token leak detection via DB lookup."""

    def test_detects_canary_token_in_output(self, canary_db):
        result = do_check_output(
            "The output contains CANARY-SECRET-12345 somewhere",
            db_path=canary_db,
        )
        assert result["clean"] is False
        assert len(result["canary_leaks"]) > 0

    def test_canary_leak_action_is_block(self, canary_db):
        result = do_check_output(
            "Leaked: CANARY-SECRET-12345",
            db_path=canary_db,
        )
        assert result["action"] == "block"

    def test_canary_overrides_credential_action(self, canary_db):
        """If both canary and credential found, action should be block (canary takes priority)."""
        result = do_check_output(
            "CANARY-SECRET-12345 and sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA",
            db_path=canary_db,
        )
        assert result["action"] == "block"

    def test_no_canary_leak_without_matching_token(self, canary_db):
        result = do_check_output(
            "This text has no canary tokens at all",
            db_path=canary_db,
        )
        assert result["canary_leaks"] == []

    def test_no_canary_check_without_db(self):
        """Without a db_path, canary check is skipped gracefully."""
        result = do_check_output("CANARY-SECRET-12345 in output")
        assert result["canary_leaks"] == []

    def test_canary_token_masked_in_evidence(self, canary_db):
        token = "CANARY-SECRET-12345"
        result = do_check_output(
            f"Leaked: {token}",
            db_path=canary_db,
        )
        for leak in result["canary_leaks"]:
            assert token not in leak.get("evidence", "")
            assert token not in str(leak)


# =============================================================================
# Action priority tests
# =============================================================================


class TestActionPriority:
    """Action logic: canary=block > credential=redact > url_exfil=redact > clean=pass."""

    def test_clean_returns_pass(self):
        result = do_check_output("nothing suspicious here")
        assert result["action"] == "pass"

    def test_credential_returns_redact(self):
        result = do_check_output("sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA")
        assert result["action"] == "redact"

    def test_url_exfil_returns_redact(self):
        result = do_check_output(
            "https://evil.com/collect?data=c2VjcmV0X3Rva2VuXzEyMzQ1Njc4OTA="
        )
        assert result["action"] == "redact"

    def test_canary_returns_block(self, canary_db):
        result = do_check_output("CANARY-SECRET-12345", db_path=canary_db)
        assert result["action"] == "block"

    def test_canary_overrides_everything(self, canary_db):
        text = (
            "CANARY-SECRET-12345 "
            "sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA "
            "https://evil.com/collect?data=c2VjcmV0X3Rva2VuXzEyMzQ1Njc4OTA="
        )
        result = do_check_output(text, db_path=canary_db)
        assert result["action"] == "block"


# =============================================================================
# Masking integrity tests
# =============================================================================


class TestMaskingIntegrity:
    """Verify that original credentials never appear in any part of the result."""

    def test_no_raw_credential_anywhere_in_result(self):
        creds = [
            "sk-abc123def456ghi789jklmnopqrstuvwxyz1234567890AA",
            "AKIAIOSFODNN7EXAMPLE",
            "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789",
            "postgres://user:password@host:5432/db",
            "-----BEGIN RSA PRIVATE KEY-----",
        ]
        for cred in creds:
            result = do_check_output(f"Found: {cred}")
            result_str = str(result)
            assert cred not in result_str, f"Raw credential leaked in result for: {cred[:20]}..."
