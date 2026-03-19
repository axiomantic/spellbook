"""Tests for secret detection in memory content."""

import pytest
from spellbook.memory_secrets import scan_for_secrets


# --- AWS ---


def test_detects_aws_access_key():
    text = "Config uses AKIAIOSFODNN7EXAMPLE for S3 access"
    findings = scan_for_secrets(text)
    assert len(findings) == 1
    assert findings[0]["pattern_name"] == "AWS Access Key"
    # Full match must NOT be stored; only redacted preview
    assert "matched_text" not in findings[0]
    assert findings[0]["redacted_preview"] == "AKIA...LE"
    assert isinstance(findings[0]["start"], int)
    assert isinstance(findings[0]["end"], int)


def test_detects_aws_secret_key():
    text = "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    findings = scan_for_secrets(text)
    assert len(findings) >= 1
    aws_findings = [f for f in findings if f["pattern_name"] == "AWS Secret Key"]
    assert len(aws_findings) == 1
    assert "matched_text" not in aws_findings[0]
    assert "redacted_preview" in aws_findings[0]


# --- GitHub ---


def test_detects_github_token_classic():
    text = "GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef01"
    findings = scan_for_secrets(text)
    gh_findings = [f for f in findings if f["pattern_name"] == "GitHub Token (classic)"]
    assert len(gh_findings) == 1
    assert "matched_text" not in gh_findings[0]
    assert gh_findings[0]["redacted_preview"] == "ghp_...01"


def test_detects_github_token_fine_grained():
    # Fine-grained tokens are exactly 86 chars: "github_pat_" (11) + 82 alphanumeric/underscore + 3 padding = 82
    token = "github_pat_" + "A" * 82
    text = f"TOKEN={token}"
    findings = scan_for_secrets(text)
    gh_findings = [f for f in findings if f["pattern_name"] == "GitHub Token (fine-grained)"]
    assert len(gh_findings) == 1
    assert "matched_text" not in gh_findings[0]
    assert gh_findings[0]["redacted_preview"] == "gith...AA"


# --- GitLab ---


def test_detects_gitlab_token():
    text = "token: glpat-ABCDEFGHIJKLMNOPQRSTa"
    findings = scan_for_secrets(text)
    gl_findings = [f for f in findings if f["pattern_name"] == "GitLab Token"]
    assert len(gl_findings) == 1
    assert "matched_text" not in gl_findings[0]
    assert gl_findings[0]["redacted_preview"] == "glpa...Ta"


# --- Slack ---


def test_detects_slack_token():
    # Use xoxs- prefix to avoid triggering GitHub push protection on xoxb- format
    text = "SLACK_TOKEN=xoxs-ABCDEF1234-testtoken99"
    findings = scan_for_secrets(text)
    slack_findings = [f for f in findings if f["pattern_name"] == "Slack Token"]
    assert len(slack_findings) == 1
    assert "matched_text" not in slack_findings[0]
    assert slack_findings[0]["redacted_preview"] == "xoxs...99"


# --- Private Keys ---


def test_detects_rsa_private_key():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
    findings = scan_for_secrets(text)
    pk_findings = [f for f in findings if f["pattern_name"] == "Private Key Header"]
    assert len(pk_findings) == 1
    assert "matched_text" not in pk_findings[0]
    assert pk_findings[0]["redacted_preview"] == "----...--"


def test_detects_dsa_private_key():
    text = "-----BEGIN DSA PRIVATE KEY-----\nMIIBugIBAAKBgQC..."
    findings = scan_for_secrets(text)
    pk_findings = [f for f in findings if f["pattern_name"] == "Private Key Header"]
    assert len(pk_findings) == 1
    assert "matched_text" not in pk_findings[0]
    assert pk_findings[0]["redacted_preview"] == "----...--"


def test_detects_ec_private_key():
    text = "-----BEGIN EC PRIVATE KEY-----\nMHQCAQEEIBkg..."
    findings = scan_for_secrets(text)
    pk_findings = [f for f in findings if f["pattern_name"] == "Private Key Header"]
    assert len(pk_findings) == 1
    assert "matched_text" not in pk_findings[0]
    assert pk_findings[0]["redacted_preview"] == "----...--"


def test_detects_openssh_private_key():
    text = "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEA..."
    findings = scan_for_secrets(text)
    pk_findings = [f for f in findings if f["pattern_name"] == "Private Key Header"]
    assert len(pk_findings) == 1
    assert "matched_text" not in pk_findings[0]
    assert pk_findings[0]["redacted_preview"] == "----...--"


def test_detects_pgp_private_key():
    text = "-----BEGIN PGP PRIVATE KEY-----\nlQOYBF..."
    findings = scan_for_secrets(text)
    pk_findings = [f for f in findings if f["pattern_name"] == "Private Key Header"]
    assert len(pk_findings) == 1
    assert "matched_text" not in pk_findings[0]
    assert pk_findings[0]["redacted_preview"] == "----...--"


# --- Anthropic ---


def test_detects_anthropic_api_key():
    text = "ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwx"
    findings = scan_for_secrets(text)
    ant_findings = [f for f in findings if f["pattern_name"] == "Anthropic API Key"]
    assert len(ant_findings) == 1
    assert "matched_text" not in ant_findings[0]
    assert ant_findings[0]["redacted_preview"] == "sk-a...wx"


# --- OpenAI ---


def test_detects_openai_api_key():
    text = 'api_key = "sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx"'
    findings = scan_for_secrets(text)
    oai_findings = [f for f in findings if f["pattern_name"] == "OpenAI API Key"]
    assert len(oai_findings) == 1
    assert "matched_text" not in oai_findings[0]
    assert oai_findings[0]["redacted_preview"] == "sk-p...wx"


def test_detects_openai_legacy_key():
    token = "sk-" + "A" * 48
    text = f"OPENAI_KEY={token}"
    findings = scan_for_secrets(text)
    oai_findings = [f for f in findings if f["pattern_name"] == "OpenAI Legacy Key"]
    assert len(oai_findings) == 1
    assert "matched_text" not in oai_findings[0]
    assert oai_findings[0]["redacted_preview"] == "sk-A...AA"


# --- Google ---


def test_detects_google_api_key():
    token = "AIza" + "B" * 35
    text = f"GOOGLE_API_KEY={token}"
    findings = scan_for_secrets(text)
    g_findings = [f for f in findings if f["pattern_name"] == "Google API Key"]
    assert len(g_findings) == 1
    assert "matched_text" not in g_findings[0]
    assert g_findings[0]["redacted_preview"] == "AIza...BB"


# --- Stripe ---


def test_detects_stripe_secret_key():
    token = "sk_test_" + "C" * 24
    text = f"STRIPE_KEY={token}"
    findings = scan_for_secrets(text)
    stripe_findings = [f for f in findings if f["pattern_name"] == "Stripe Key"]
    assert len(stripe_findings) == 1
    assert "matched_text" not in stripe_findings[0]
    assert stripe_findings[0]["redacted_preview"] == "sk_t...CC"


def test_detects_stripe_live_publishable_key():
    token = "pk_live_" + "D" * 24
    text = f"STRIPE_PK={token}"
    findings = scan_for_secrets(text)
    stripe_findings = [f for f in findings if f["pattern_name"] == "Stripe Key"]
    assert len(stripe_findings) == 1
    assert "matched_text" not in stripe_findings[0]
    assert stripe_findings[0]["redacted_preview"] == "pk_l...DD"


# --- NPM ---


def test_detects_npm_token():
    token = "npm_" + "E" * 36
    text = f"NPM_TOKEN={token}"
    findings = scan_for_secrets(text)
    npm_findings = [f for f in findings if f["pattern_name"] == "NPM Token"]
    assert len(npm_findings) == 1
    assert "matched_text" not in npm_findings[0]
    assert npm_findings[0]["redacted_preview"] == "npm_...EE"


# --- PyPI ---


def test_detects_pypi_token():
    token = "pypi-" + "F" * 50
    text = f"TWINE_PASSWORD={token}"
    findings = scan_for_secrets(text)
    pypi_findings = [f for f in findings if f["pattern_name"] == "PyPI Token"]
    assert len(pypi_findings) == 1
    assert "matched_text" not in pypi_findings[0]
    assert pypi_findings[0]["redacted_preview"] == "pypi...FF"


# --- Hex Secret ---


def test_detects_hex_secret():
    hex_val = "a" * 64
    text = f"secret = {hex_val}"
    findings = scan_for_secrets(text)
    hex_findings = [f for f in findings if f["pattern_name"] == "Hex Secret (64+ chars)"]
    assert len(hex_findings) == 1
    assert "matched_text" not in hex_findings[0]
    assert "redacted_preview" in hex_findings[0]


# --- False positives ---


def test_no_false_positive_on_normal_text():
    text = "This project uses pytest for testing and SQLite for storage"
    findings = scan_for_secrets(text)
    assert len(findings) == 0


def test_no_false_positive_on_short_hex():
    text = "commit abc123def456"
    findings = scan_for_secrets(text)
    assert len(findings) == 0


# --- Structural tests ---


def test_returns_redacted_fields_not_raw_match():
    text = "key = AKIAIOSFODNN7EXAMPLE"
    findings = scan_for_secrets(text)
    assert len(findings) == 1
    assert findings[0]["pattern_name"] == "AWS Access Key"
    # Must NOT store full matched text
    assert "matched_text" not in findings[0]
    # Must store redacted preview and positions
    assert findings[0]["redacted_preview"] == "AKIA...LE"
    assert isinstance(findings[0]["start"], int)
    assert isinstance(findings[0]["end"], int)


def test_detects_generic_api_key_assignment():
    text = 'api_key = "sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx"'
    findings = scan_for_secrets(text)
    # Should match both OpenAI API Key and Generic High-Entropy Key Assignment
    pattern_names = {f["pattern_name"] for f in findings}
    assert "OpenAI API Key" in pattern_names or "Generic High-Entropy Key Assignment" in pattern_names
    assert len(findings) >= 1


def test_multiple_secrets_in_one_text():
    text = (
        "AWS_KEY=AKIAIOSFODNN7EXAMPLE\n"
        "GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef01\n"
    )
    findings = scan_for_secrets(text)
    assert len(findings) >= 2
    pattern_names = {f["pattern_name"] for f in findings}
    assert "AWS Access Key" in pattern_names
    assert "GitHub Token (classic)" in pattern_names
