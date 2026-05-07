"""Tests for the Read tool secret-path denylist.

Phase 6d adds a denylist of secret paths that the Read tool MUST NOT touch.
The hook (spellbook/gates/check.py) routes Read tool invocations through
``_check_read_path`` which compares the resolved file path against patterns
in ``spellbook/gates/secret_paths.py``.

Tests cover:
- POSIX-style enumerated secrets (~/.ssh, ~/.aws/*, ~/.netrc, ~/.config/op,
  browser credential stores).
- Glob-style project-relative patterns (.env*, *.pem, *.key, id_rsa*,
  id_ed25519*).
- Windows additions (resolved via Path.home()).
- Negative controls (non-secret paths must remain safe).
- Symlink resolution (a symlink in a benign location pointing into the
  deny zone must still deny).
- Tilde-vs-absolute equivalence (both shapes resolve to the same
  denied path).
"""

import os

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Parametrized denylist coverage
# ---------------------------------------------------------------------------

# (label, relative-to-home path or glob filename) - all should DENY.
# Tilde-relative entries are expanded against the user's $HOME (which the
# fixture monkeypatches to a tmp dir) so the test stays hermetic.
DENY_HOME_RELATIVE = [
    ("ssh_id_rsa", ".ssh/id_rsa"),
    ("ssh_id_ed25519", ".ssh/id_ed25519"),
    ("ssh_authorized_keys", ".ssh/authorized_keys"),
    ("ssh_config", ".ssh/config"),
    ("aws_credentials", ".aws/credentials"),
    ("aws_config", ".aws/config"),
    ("op_config", ".config/op/config"),
    ("netrc_dotted", ".netrc"),
    ("netrc_underscored", "_netrc"),  # Windows variant
]

# Glob-style project-relative filenames - resolved under a tmp project dir.
DENY_PROJECT_GLOB = [
    ("dotenv_plain", ".env"),
    ("dotenv_local", ".env.local"),
    ("dotenv_production", ".env.production"),
    ("pem_file", "private.pem"),
    ("key_file", "service.key"),
    ("id_rsa_loose", "id_rsa"),
    ("id_rsa_pub_loose", "id_rsa.pub"),
    ("id_ed25519_loose", "id_ed25519"),
]

# Negative controls - must remain SAFE.
ALLOW_NEGATIVE = [
    ("plain_text", "notes.txt"),
    ("python_source", "main.py"),
    ("readme", "README.md"),
    ("dotfile_unrelated", ".gitignore"),
    ("env_substring_not_match", "environment.md"),
]


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Provide a hermetic $HOME so tilde-paths in the denylist resolve here."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".ssh").mkdir()
    (home / ".aws").mkdir()
    (home / ".config" / "op").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    # Path.home() consults HOME on POSIX. On Windows it consults USERPROFILE.
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.mark.parametrize(
    "label,rel_path",
    DENY_HOME_RELATIVE,
    ids=[row[0] for row in DENY_HOME_RELATIVE],
)
def test_read_secret_denied_home_relative(fake_home, label, rel_path):
    from spellbook.gates.check import check_tool_input

    target = fake_home / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("dummy-secret")

    result = check_tool_input("Read", {"file_path": str(target)})
    assert result["safe"] is False, f"expected DENY for {label}: {target}"
    assert result["tool_name"] == "Read"
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    ), f"missing READ-SECRET finding for {label}"


@pytest.mark.parametrize(
    "label,rel_path",
    DENY_HOME_RELATIVE,
    ids=[f"tilde_{row[0]}" for row in DENY_HOME_RELATIVE],
)
def test_read_secret_denied_via_tilde(fake_home, label, rel_path):
    """User-supplied tilde paths must expand and deny just like absolutes."""
    from spellbook.gates.check import check_tool_input

    target = fake_home / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("dummy-secret")

    result = check_tool_input("Read", {"file_path": f"~/{rel_path}"})
    assert result["safe"] is False, f"expected DENY for tilde-{label}"
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    )


@pytest.mark.parametrize(
    "label,filename",
    DENY_PROJECT_GLOB,
    ids=[row[0] for row in DENY_PROJECT_GLOB],
)
def test_read_secret_denied_project_glob(tmp_path, label, filename):
    from spellbook.gates.check import check_tool_input

    project = tmp_path / "project"
    project.mkdir()
    target = project / filename
    target.write_text("payload")

    result = check_tool_input("Read", {"file_path": str(target)})
    assert result["safe"] is False, f"expected DENY for project glob {label}"
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    )


@pytest.mark.parametrize(
    "label,filename",
    ALLOW_NEGATIVE,
    ids=[row[0] for row in ALLOW_NEGATIVE],
)
def test_read_non_secret_allowed(tmp_path, fake_home, label, filename):
    from spellbook.gates.check import check_tool_input

    project = tmp_path / "project"
    project.mkdir()
    target = project / filename
    target.write_text("ordinary content")

    result = check_tool_input("Read", {"file_path": str(target)})
    assert result["safe"] is True, (
        f"expected ALLOW for {label}: got findings={result['findings']!r}"
    )
    assert result["findings"] == []
    assert result["tool_name"] == "Read"


# ---------------------------------------------------------------------------
# Symlink resolution regression test (per plan Step 3)
# ---------------------------------------------------------------------------


def test_secret_denylist_resolves_symlink(tmp_path, monkeypatch):
    """A symlink in a benign location pointing into the deny zone must deny."""
    from spellbook.gates.check import check_tool_input

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    aws_dir = fake_home / ".aws"
    aws_dir.mkdir()
    (aws_dir / "credentials").write_text("real-creds")
    docs = fake_home / "Documents" / "innocent"
    docs.mkdir(parents=True)
    (docs / "decoy.txt").symlink_to(aws_dir / "credentials")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    result = check_tool_input("Read", {"file_path": str(docs / "decoy.txt")})
    assert result["safe"] is False
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_read_with_no_file_path_is_safe():
    """Read calls without a file_path should not crash; treat as no-op safe."""
    from spellbook.gates.check import check_tool_input

    result = check_tool_input("Read", {})
    assert result["safe"] is True
    assert result["findings"] == []
    assert result["tool_name"] == "Read"


def test_read_with_nonexistent_path_still_evaluates(fake_home):
    """The denylist must still match even if the path does not yet exist."""
    from spellbook.gates.check import check_tool_input

    target = fake_home / ".ssh" / "id_rsa_unborn"
    # Do NOT create the file; resolve() must handle missing tail components.
    result = check_tool_input("Read", {"file_path": str(target)})
    assert result["safe"] is False
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    )


def test_read_finding_severity_is_critical(fake_home):
    """READ-SECRET findings must be CRITICAL so safe collapses to False."""
    from spellbook.gates.check import check_tool_input

    target = fake_home / ".aws" / "credentials"
    target.write_text("creds")

    result = check_tool_input("Read", {"file_path": str(target)})
    secret_findings = [
        f for f in result["findings"] if f["rule_id"].startswith("READ-SECRET")
    ]
    assert secret_findings
    assert all(f["severity"] == "CRITICAL" for f in secret_findings)


def test_read_browser_login_data_macos_denied(fake_home, tmp_path):
    """macOS browser credential store paths must be denied."""
    from spellbook.gates.check import check_tool_input

    # ~/Library/Application Support/<browser>/Login Data
    target = (
        fake_home
        / "Library"
        / "Application Support"
        / "Google"
        / "Chrome"
        / "Default"
        / "Login Data"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("sqlite-fake")

    result = check_tool_input("Read", {"file_path": str(target)})
    assert result["safe"] is False
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    )


def test_read_appdata_1password_windows_denied(tmp_path, monkeypatch):
    """%APPDATA%/1Password/* on Windows must be denied."""
    from spellbook.gates.check import check_tool_input

    appdata = tmp_path / "AppData" / "Roaming"
    appdata.mkdir(parents=True)
    op_dir = appdata / "1Password"
    op_dir.mkdir()
    target = op_dir / "config.sqlite"
    target.write_text("opaque")

    monkeypatch.setenv("APPDATA", str(appdata))
    # Keep HOME outside this dir so we exercise the APPDATA code path.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    result = check_tool_input("Read", {"file_path": str(target)})
    assert result["safe"] is False
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    )


def test_read_localappdata_chrome_login_data_denied(tmp_path, monkeypatch):
    """%LOCALAPPDATA%/Google/Chrome/User Data/*/Login Data must be denied."""
    from spellbook.gates.check import check_tool_input

    localappdata = tmp_path / "AppData" / "Local"
    localappdata.mkdir(parents=True)
    target = (
        localappdata
        / "Google"
        / "Chrome"
        / "User Data"
        / "Default"
        / "Login Data"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("sqlite")

    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    result = check_tool_input("Read", {"file_path": str(target)})
    assert result["safe"] is False
    assert any(
        f["rule_id"].startswith("READ-SECRET") for f in result["findings"]
    )
