"""Tests for spellbook.gates.git_push — config loader (Task 2).

The autouse `_reset_git_push_caches` fixture is supplied by
tests/test_security/conftest.py (see Task 2 Step 0a). Do NOT
re-declare it here.
"""

import subprocess
from pathlib import Path

import pytest
import tripwire


# ---------------------------------------------------------------------------
# load_protected_config — defaults
# ---------------------------------------------------------------------------


def test_defaults_when_no_protected_section(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[[tiers]]\n'
        'tool = "Bash"\n'
        'pattern = "ls"\n'
        'tier = "T0"\n'
        'description = "x"\n',
        encoding="utf-8",
    )
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("master", "main")
    assert cfg.remotes == frozenset({"origin", "upstream"})


def test_toml_protected_section_overrides_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\n'
        'branches = ["staging", "production"]\n'
        'remotes = ["origin"]\n',
        encoding="utf-8",
    )
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("staging", "production")
    assert cfg.remotes == frozenset({"origin"})


# ---------------------------------------------------------------------------
# env-var overlay
# ---------------------------------------------------------------------------


def test_env_var_overrides_branches(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "staging,production")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("staging", "production")


def test_env_var_overrides_remotes_independently(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.setenv("SPELLBOOK_PROTECTED_REMOTES", "fork")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("master", "main")  # TOML default unchanged
    assert cfg.remotes == frozenset({"fork"})


def test_env_var_empty_string_falls_back_to_toml(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nbranches = ["x"]\n',
        encoding="utf-8",
    )
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("x",)


def test_env_var_whitespace_elements_dropped(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", " main , , master ")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("main", "master")


# ---------------------------------------------------------------------------
# __disable__ sentinel
# ---------------------------------------------------------------------------


def test_disable_sentinel_branches(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "__disable__")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ()  # empty tuple means "no protection"


def test_disable_sentinel_remotes(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_REMOTES", "__disable__")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.remotes == frozenset()


def test_disable_sentinel_mixed_is_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "main,__disable__")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="__disable__ must be alone"):
        load_protected_config(toml_path)


# ---------------------------------------------------------------------------
# schema hardening
# ---------------------------------------------------------------------------


def test_protected_nested_unknown_key_fails_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nbranches = ["main"]\ntypo_key = "oops"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"unknown keys.*typo_key"):
        load_protected_config(toml_path)


def test_protected_branches_wrong_type_fails_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nbranches = "main"\n',  # string, not list
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"branches.*list"):
        load_protected_config(toml_path)


def test_protected_remotes_wrong_type_fails_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nremotes = "origin"\n',  # string, not list
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"remotes.*list"):
        load_protected_config(toml_path)


def test_protected_non_dict_fails_loud(tmp_path, monkeypatch):
    """A top-level scalar `protected` value (instead of a table) must fail loud."""
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    # `protected = "x"` makes the top-level value a string, not a table.
    toml_path.write_text('protected = "x"\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"\[protected\] must be a table"):
        load_protected_config(toml_path)


# ---------------------------------------------------------------------------
# _resolve_current_branch (Task 3)
# ---------------------------------------------------------------------------


def _make_git_repo(path: Path, branch: str = "main") -> None:
    """Build a minimal .git directory pointing HEAD at refs/heads/<branch>."""
    git = path / ".git"
    git.mkdir()
    (git / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    refs_heads = git / "refs" / "heads"
    refs_heads.mkdir(parents=True)
    ref_path = refs_heads / branch
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_text(
        "0000000000000000000000000000000000000000\n", encoding="utf-8"
    )


def test_resolve_branch_in_repo(tmp_path):
    from spellbook.gates.git_push import _resolve_current_branch

    _make_git_repo(tmp_path, branch="feature/x")
    assert _resolve_current_branch(str(tmp_path)) == "feature/x"


def test_resolve_branch_empty_cwd_returns_none():
    from spellbook.gates.git_push import _resolve_current_branch

    assert _resolve_current_branch("") is None
    assert _resolve_current_branch(None) is None  # type: ignore[arg-type]


def test_resolve_branch_non_git_cwd_returns_none(tmp_path):
    from spellbook.gates.git_push import _resolve_current_branch

    # No .git directory anywhere.
    assert _resolve_current_branch(str(tmp_path)) is None


def test_head_cache_invalidated_on_head_mtime_change(tmp_path):
    import os
    import time

    from spellbook.gates.git_push import _HEAD_CACHE, _resolve_current_branch

    _make_git_repo(tmp_path, branch="main")
    assert _resolve_current_branch(str(tmp_path)) == "main"
    assert str(tmp_path) in _HEAD_CACHE

    # Rewrite HEAD to point at a different branch.
    (tmp_path / ".git" / "refs" / "heads" / "other").write_text("0" * 40 + "\n")
    (tmp_path / ".git" / "HEAD").write_text(
        "ref: refs/heads/other\n", encoding="utf-8"
    )
    # Bump mtime explicitly to defeat 1-second filesystem mtime granularity.
    future = time.time() + 5
    os.utime(tmp_path / ".git" / "HEAD", (future, future))

    assert _resolve_current_branch(str(tmp_path)) == "other"


def test_worktree_pointer_file_resolves_via_gitdir(tmp_path):
    """A worktree's .git is a FILE containing 'gitdir: <path>'.
    The resolver must read that pointer and stat the pointed-to HEAD."""
    from spellbook.gates.git_push import _resolve_current_branch

    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    _make_git_repo(main_repo, branch="main")

    # Build the worktree metadata directory under .git/worktrees/<name>/.
    wt_meta = main_repo / ".git" / "worktrees" / "feature_x"
    wt_meta.mkdir(parents=True)
    (wt_meta / "HEAD").write_text("ref: refs/heads/feature_x\n", encoding="utf-8")

    # Build the worktree itself: .git is a FILE pointing at the metadata dir.
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_meta}\n", encoding="utf-8")

    assert _resolve_current_branch(str(wt)) == "feature_x"


def test_reset_caches_clears_head_cache(tmp_path):
    from spellbook.gates.git_push import _HEAD_CACHE, _reset_caches, _resolve_current_branch

    _make_git_repo(tmp_path)
    _resolve_current_branch(str(tmp_path))
    assert _HEAD_CACHE  # populated
    _reset_caches()
    assert _HEAD_CACHE == {}


# ---------------------------------------------------------------------------
# _run_symbolic_ref subprocess-fallback coverage (tripwire-mocked)
#
# These tests exercise the path where HEAD does NOT begin with
# ``ref: refs/heads/<branch>``, forcing _resolve_current_branch to fall
# through to ``_run_symbolic_ref`` -> ``subprocess.run``. All subprocess
# interactions are tripwire-mocked per the project's "always use tripwire!"
# rule for subprocess/network/DB touches.
# ---------------------------------------------------------------------------


def _make_detached_head_repo(path: Path) -> None:
    """Build a minimal .git dir whose HEAD is a raw SHA (detached)."""
    git = path / ".git"
    git.mkdir()
    # 40-char SHA, no ``ref:`` prefix — defeats the in-process fast-path.
    (git / "HEAD").write_text(
        "0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8"
    )


def test_resolve_branch_detached_head_calls_subprocess_and_caches_none(tmp_path):
    """Detached HEAD: fast-path misses, subprocess raises CalledProcessError
    (stable), resolver returns None AND caches (mtime, None) so a second
    call does NOT re-invoke subprocess."""
    from spellbook.gates.git_push import _HEAD_CACHE, _resolve_current_branch

    _make_detached_head_repo(tmp_path)
    cwd = str(tmp_path)
    expected_cmd = ["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"]

    tripwire.subprocess.mock_run(
        command=expected_cmd,
        raises=subprocess.CalledProcessError(returncode=128, cmd=expected_cmd),
    )

    with tripwire:
        result = _resolve_current_branch(cwd)
        # Second call must hit the cache; do NOT register a second mock.
        result_cached = _resolve_current_branch(cwd)

    assert result is None
    assert result_cached is None
    # Cache populated with (mtime, None) — mtime is real (>= 0), not the
    # -1.0 "not a git repo" sentinel.
    assert cwd in _HEAD_CACHE
    cached_mtime, cached_branch = _HEAD_CACHE[cwd]
    assert cached_branch is None
    assert cached_mtime >= 0.0
    tripwire.subprocess.assert_run(
        command=expected_cmd, returncode=0, stdout="", stderr="",
    )


def test_resolve_branch_subprocess_transient_failure_does_not_cache(tmp_path):
    """Transient failure (TimeoutExpired): resolver returns None and does
    NOT cache, so the next call retries."""
    from spellbook.gates.git_push import _HEAD_CACHE, _resolve_current_branch

    _make_detached_head_repo(tmp_path)
    cwd = str(tmp_path)
    expected_cmd = ["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"]

    tripwire.subprocess.mock_run(
        command=expected_cmd,
        raises=subprocess.TimeoutExpired(cmd=expected_cmd, timeout=1.0),
    )

    with tripwire:
        result = _resolve_current_branch(cwd)

    assert result is None
    # Transient failures must NOT be cached.
    assert cwd not in _HEAD_CACHE
    tripwire.subprocess.assert_run(
        command=expected_cmd, returncode=0, stdout="", stderr="",
    )


def test_resolve_branch_subprocess_success_returns_branch(tmp_path):
    """Unusual HEAD content (e.g. packed-refs scenario) where the
    in-process fast-path misses but git resolves it: subprocess returns
    a branch name, resolver returns it and caches (mtime, branch)."""
    from spellbook.gates.git_push import _HEAD_CACHE, _resolve_current_branch

    _make_detached_head_repo(tmp_path)
    cwd = str(tmp_path)
    expected_cmd = ["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"]

    tripwire.subprocess.mock_run(
        command=expected_cmd,
        returncode=0,
        stdout="packed-branch\n",
    )

    with tripwire:
        result = _resolve_current_branch(cwd)

    assert result == "packed-branch"
    # Successful resolution is cached.
    assert cwd in _HEAD_CACHE
    cached_mtime, cached_branch = _HEAD_CACHE[cwd]
    assert cached_branch == "packed-branch"
    assert cached_mtime >= 0.0
    tripwire.subprocess.assert_run(
        command=expected_cmd,
        returncode=0,
        stdout="packed-branch\n",
        stderr="",
    )
