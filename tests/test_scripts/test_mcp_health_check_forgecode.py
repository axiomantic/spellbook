"""Regression tests for check_forgecode_mcp in scripts/mcp-health-check.py.

This function had no test coverage, which is why it kept hard-failing on an
Authorization header that installers stopped writing when bearer-token auth was
removed: every correctly-installed ForgeCode user was reported ``unhealthy`` with
``missing_auth``, pointing at a credential that no longer exists.

The script is loaded by path because its filename is not a valid module name.
No installer internals are mocked; each test writes a real ``.mcp.json``.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "mcp-health-check.py"


def _load_module():
    # The script imports `installer.components.mcp` at function level, so the
    # repo root must be importable before the check runs.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("mcp_health_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def health():
    return _load_module()


@pytest.fixture
def daemon_url(health):
    from installer.components.mcp import DEFAULT_HOST, DEFAULT_PORT

    return f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"


def _write_config(config_dir: Path, entry: dict, mode: int = 0o600) -> Path:
    path = config_dir / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {"spellbook": entry}}))
    path.chmod(mode)
    return path


def test_config_without_authorization_header_is_healthy(health, tmp_path, daemon_url):
    """The credential-free config an installer writes today must pass.

    This is the HIGH-2 regression: step 5 used to reject exactly this file.
    """
    _write_config(tmp_path, {"url": daemon_url, "oauth": False})

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert result.healthy is True, result.error
    assert result.error is None


def test_contract_reports_no_auth_fields(health, tmp_path, daemon_url):
    """has_auth / auth_format_ok are gone from the contract entirely.

    A consumer reading them would otherwise get a permanently False value that
    reads as a finding rather than as a removed concept.
    """
    _write_config(tmp_path, {"url": daemon_url, "oauth": False})

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    contract = next(
        d.details for d in result.diagnostics if d.check == "forgecode_contract"
    )
    assert "has_auth" not in contract
    assert "auth_format_ok" not in contract


def test_no_auth_diagnostic_is_emitted(health, tmp_path, daemon_url):
    _write_config(tmp_path, {"url": daemon_url, "oauth": False})

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert not any(d.check == "mcp_auth_header" for d in result.diagnostics)


def test_stale_authorization_header_is_ignored_not_required(
    health, tmp_path, daemon_url
):
    """A leftover header from an older install must not change the verdict."""
    _write_config(
        tmp_path,
        {
            "url": daemon_url,
            "oauth": False,
            "headers": {"Authorization": "Bearer stale-token"},
        },
    )

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert result.healthy is True, result.error


# The checks that must STILL fail. Without these, the tests above would pass
# just as well against a function that returns healthy unconditionally.


def test_missing_file_is_unhealthy(health, tmp_path):
    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert result.healthy is False
    assert "not found" in (result.error or "")


def test_malformed_json_is_unhealthy(health, tmp_path):
    (tmp_path / ".mcp.json").write_text("{not json")

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert result.healthy is False


def test_wrong_url_is_unhealthy(health, tmp_path):
    _write_config(tmp_path, {"url": "http://127.0.0.1:9999/mcp", "oauth": False})

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert result.healthy is False
    contract = next(
        d.details for d in result.diagnostics if d.check == "forgecode_contract"
    )
    assert contract["status"] == "wrong_url"


def test_oauth_enabled_is_unhealthy(health, tmp_path, daemon_url):
    """Step 5 (formerly 6) still runs after the deletion above it."""
    _write_config(tmp_path, {"url": daemon_url, "oauth": True})

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert result.healthy is False
    contract = next(
        d.details for d in result.diagnostics if d.check == "forgecode_contract"
    )
    assert contract["status"] == "oauth_enabled"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_loose_mode_is_a_soft_warning(health, tmp_path, daemon_url):
    """Step 6 (formerly 7) still runs and stays a soft warning."""
    _write_config(tmp_path, {"url": daemon_url, "oauth": False}, mode=0o644)

    result = health.check_forgecode_mcp(config_dir=tmp_path)

    assert result.healthy is True, result.error
    contract = next(
        d.details for d in result.diagnostics if d.check == "forgecode_contract"
    )
    assert contract["status"] == "insecure_mode"


def test_docstring_advertises_six_validations(health):
    doc = health.check_forgecode_mcp.__doc__ or ""
    assert "six ordered" in doc
    assert "seven ordered" not in doc
    assert "7." not in doc
