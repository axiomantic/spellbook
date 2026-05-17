"""End-to-end cwd plumbing tests for check_tool_input → classify_tool_call
→ classify_git_push.

Uses real on-disk .git fixtures because the resolver is filesystem-backed.

The autouse `_reset_git_push_caches` fixture is supplied by
tests/test_security/conftest.py (see Task 2 Step 0a). Do NOT
re-declare it here (per design §9.5 / M-1)."""

from pathlib import Path

import pytest


def _make_git_repo(path: Path, branch: str = "main") -> None:
    git = path / ".git"
    git.mkdir(exist_ok=True)
    (git / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    refs_heads = git / "refs" / "heads"
    refs_heads.mkdir(parents=True, exist_ok=True)
    ref_file = refs_heads / branch
    ref_file.parent.mkdir(parents=True, exist_ok=True)
    ref_file.write_text("0" * 40 + "\n", encoding="utf-8")


def test_feature_branch_push_with_cwd_does_not_ask(tmp_path):
    """Bare `git push` from a feature-branch cwd → no TIER-ASK (verdict allow)."""
    from spellbook.gates.check import check_tool_input

    _make_git_repo(tmp_path, branch="feature/x")
    result = check_tool_input(
        "Bash", {"command": "git push"}, cwd=str(tmp_path)
    )
    assert result["verdict"] == "allow", result
    assert all(
        not f.get("rule_id", "").startswith("TIER-") for f in result["findings"]
    ), result


def test_protected_branch_push_with_cwd_asks(tmp_path):
    from spellbook.gates.check import check_tool_input

    _make_git_repo(tmp_path, branch="main")
    result = check_tool_input(
        "Bash", {"command": "git push"}, cwd=str(tmp_path)
    )
    assert result["verdict"] == "ask", result


def test_no_cwd_failsafe_to_ask(tmp_path):
    """No cwd → resolver can't probe → failsafe T2 (ask)."""
    from spellbook.gates.check import check_tool_input

    result = check_tool_input("Bash", {"command": "git push"})
    assert result["verdict"] == "ask", result


def test_autonomous_env_var_silences_failsafe(tmp_path, monkeypatch):
    from spellbook.gates.check import check_tool_input

    monkeypatch.setenv("SPELLBOOK_GIT_PUSH_AUTONOMOUS", "1")
    # No cwd → resolver returns None → autonomous failsafe = T_UNCLASSIFIED.
    result = check_tool_input("Bash", {"command": "git push"})
    assert result["verdict"] == "allow", result


def test_non_push_command_unaffected(tmp_path):
    from spellbook.gates.check import check_tool_input

    result = check_tool_input(
        "Bash", {"command": "git status"}, cwd=str(tmp_path)
    )
    assert result["verdict"] == "allow"
