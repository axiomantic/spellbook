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


# ---------------------------------------------------------------------------
# classify_git_push — Task 4
# ---------------------------------------------------------------------------


def _cfg(branches=("master", "main"), remotes=("origin", "upstream")):
    from spellbook.gates.git_push import ProtectedConfig
    return ProtectedConfig(branches=tuple(branches), remotes=frozenset(remotes))


def test_command_not_starting_git_push_returns_none(tmp_path):
    from spellbook.gates.git_push import classify_git_push

    assert classify_git_push("git status", str(tmp_path), _cfg()) is None
    assert classify_git_push("ls", str(tmp_path), _cfg()) is None


def test_push_to_protected_branch_returns_t2(tmp_path):
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="main")
    assert classify_git_push("git push origin main", str(tmp_path), _cfg()) == "T2"


def test_push_to_feature_branch_returns_unclassified(tmp_path):
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin feature/x", str(tmp_path), _cfg()
    ) == T_UNCLASSIFIED


def test_bare_push_resolves_via_head(tmp_path):
    """`git push` with no refspec resolves via current branch."""
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    _make_git_repo(tmp_path, branch="main")
    assert classify_git_push("git push", str(tmp_path), _cfg()) == "T2"

    (tmp_path / "fx").mkdir()
    _make_git_repo(tmp_path / "fx", branch="feature/y")
    assert classify_git_push(
        "git push", str(tmp_path / "fx"), _cfg()
    ) == T_UNCLASSIFIED


def test_explicit_refspec_main_returns_t2(tmp_path):
    """`git push origin feature/x:main` targets main regardless of HEAD."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin feature/x:main", str(tmp_path), _cfg()
    ) == "T2"


def test_force_refspec_plus_main_returns_t2(tmp_path):
    """`git push origin +main` -> pre-pass T2 (T3 from the new tiers.toml
    row will additionally fire via the record loop -- verified in Task 9
    L2 regression)."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin +main", str(tmp_path), _cfg()
    ) == "T2"


def test_all_flag_returns_t2(tmp_path):
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push --all origin", str(tmp_path), _cfg()
    ) == "T2"


def test_mirror_flag_returns_t2(tmp_path):
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push --mirror origin", str(tmp_path), _cfg()
    ) == "T2"


def test_set_upstream_flags_stripped(tmp_path):
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="main")
    assert classify_git_push(
        "git push -u origin main", str(tmp_path), _cfg()
    ) == "T2"
    assert classify_git_push(
        "git push --set-upstream origin main", str(tmp_path), _cfg()
    ) == "T2"


def test_unknown_remote_returns_unclassified(tmp_path):
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    _make_git_repo(tmp_path, branch="main")
    assert classify_git_push(
        "git push some-fork main", str(tmp_path), _cfg()
    ) == T_UNCLASSIFIED


@pytest.mark.parametrize("remote", [
    "git@github.com:foo/bar.git",
    "git@github.com:foo/bar",
    "ssh://git@github.com/foo/bar.git",
    "https://github.com/foo/bar.git",
    "file:///tmp/repo",
])
def test_url_form_remote_returns_unclassified(tmp_path, remote):
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    _make_git_repo(tmp_path, branch="main")
    assert classify_git_push(
        f"git push {remote} main", str(tmp_path), _cfg()
    ) == T_UNCLASSIFIED


def test_fnmatch_release_glob_matches(tmp_path):
    """fnmatch.fnmatchcase('*') is multi-segment greedy -- both
    `release/v1.0` AND `release/v1.0/rc1` match `release/*`."""
    from spellbook.gates.git_push import classify_git_push

    cfg = _cfg(branches=("release/*",))
    _make_git_repo(tmp_path, branch="release/v1.0")
    assert classify_git_push("git push origin release/v1.0", str(tmp_path), cfg) == "T2"

    (tmp_path / "rc").mkdir()
    _make_git_repo(tmp_path / "rc", branch="release/v1.0/rc1")
    assert classify_git_push(
        "git push origin release/v1.0/rc1", str(tmp_path / "rc"), cfg
    ) == "T2"


def test_fnmatch_non_match_substring(tmp_path):
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    cfg = _cfg(branches=("main",))
    _make_git_repo(tmp_path, branch="mains")
    assert classify_git_push("git push origin mains", str(tmp_path), cfg) == T_UNCLASSIFIED

    cfg2 = _cfg(branches=("release/*",))
    (tmp_path / "rf").mkdir()
    _make_git_repo(tmp_path / "rf", branch="release-fix")
    assert classify_git_push(
        "git push origin release-fix", str(tmp_path / "rf"), cfg2
    ) == T_UNCLASSIFIED


def test_fnmatchcase_distinguishes_Main_from_main(tmp_path):
    """fnmatchcase MUST be case-sensitive on every platform.
    Locks the fnmatchcase-vs-fnmatch choice against silent case-folding
    on macOS / Windows."""
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    cfg = _cfg(branches=("main",))
    _make_git_repo(tmp_path, branch="Main")
    assert classify_git_push("git push origin Main", str(tmp_path), cfg) == T_UNCLASSIFIED


def test_disable_sentinel_branches_short_circuits(tmp_path):
    """Sentinel-disabled branches axis MUST short-circuit BEFORE the resolver.

    Asserts the perf-property of the short-circuit at git_push.py:439-442,
    not just its T_UNCLASSIFIED outcome. Uses a BARE ``git push`` (which
    would otherwise invoke ``_resolve_current_branch`` via the
    ``remote is None`` branch) so the tripwire fires if the short-circuit
    is removed. With the short-circuit in place the resolver is never
    called; with it removed, the lambda below fails the test.
    """
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    # required(False): if the resolver IS called, the lambda fails the test.
    # If it is NOT called (the property under test), the unconsumed
    # configuration is benign rather than raising UnusedMocksError.
    tripwire.mock("spellbook.gates.git_push:_resolve_current_branch").__call__.required(False).calls(
        lambda *a, **k: pytest.fail("resolver must not be called when branches axis is sentinel-disabled")
    )

    cfg = _cfg(branches=())  # sentinel-disabled axis
    _make_git_repo(tmp_path, branch="main")
    with tripwire:
        # Bare push: without the short-circuit, this would hit the
        # ``remote is None`` branch and call _resolve_current_branch.
        assert classify_git_push("git push", str(tmp_path), cfg) == T_UNCLASSIFIED


def test_disable_sentinel_remotes_short_circuits(tmp_path):
    """Sentinel-disabled remotes axis MUST short-circuit BEFORE the resolver.

    Same rationale as the branches counterpart: uses a bare ``git push`` so
    that, if the short-circuit at git_push.py:439-442 were removed, the
    ``remote is None`` branch would invoke ``_resolve_current_branch`` and
    trip the tripwire lambda below.
    """
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    # required(False): if the resolver IS called, the lambda fails the test.
    # If it is NOT called (the property under test), the unconsumed
    # configuration is benign rather than raising UnusedMocksError.
    tripwire.mock("spellbook.gates.git_push:_resolve_current_branch").__call__.required(False).calls(
        lambda *a, **k: pytest.fail("resolver must not be called when remotes axis is sentinel-disabled")
    )

    cfg = _cfg(remotes=())  # sentinel-disabled axis
    _make_git_repo(tmp_path, branch="main")
    with tripwire:
        # Bare push: without the short-circuit, this would hit the
        # ``remote is None`` branch and call _resolve_current_branch.
        assert classify_git_push("git push", str(tmp_path), cfg) == T_UNCLASSIFIED


def test_resolver_returns_none_failsafe_t2(tmp_path):
    """When ``_resolve_current_branch`` returns None for a bare ``git push``,
    non-autonomous mode failsafes to T2 (operator confirmation).

    Note: this test exercises the resolver-returned-None branch in
    ``classify_git_push``, NOT the subprocess machinery. Genuine
    subprocess-fallback coverage lives in the ``test_resolve_branch_*``
    tests above (detached-HEAD fixture + tripwire subprocess mocks).
    """
    from spellbook.gates.git_push import classify_git_push

    mock_resolve = tripwire.mock("spellbook.gates.git_push:_resolve_current_branch")
    mock_resolve.returns(None)
    with tripwire:
        result = classify_git_push("git push", str(tmp_path), _cfg())
    assert result == "T2"
    mock_resolve.assert_call(args=(str(tmp_path),), kwargs={})


def test_resolver_returns_none_autonomous_silent(tmp_path):
    """When ``_resolve_current_branch`` returns None for a bare ``git push``,
    autonomous mode degrades silently to T_UNCLASSIFIED.

    Note: this test exercises the resolver-returned-None branch in
    ``classify_git_push``, NOT the subprocess machinery. Genuine
    subprocess-fallback coverage lives in the ``test_resolve_branch_*``
    tests above (detached-HEAD fixture + tripwire subprocess mocks).
    """
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    mock_resolve = tripwire.mock("spellbook.gates.git_push:_resolve_current_branch")
    mock_resolve.returns(None)
    with tripwire:
        result = classify_git_push("git push", str(tmp_path), _cfg(), autonomous=True)
    assert result == T_UNCLASSIFIED
    mock_resolve.assert_call(args=(str(tmp_path),), kwargs={})


def test_non_git_cwd_failsafe_t2(tmp_path):
    from spellbook.gates.git_push import classify_git_push

    # tmp_path has no .git -- bare push falls into failsafe.
    assert classify_git_push("git push", str(tmp_path), _cfg()) == "T2"


def test_non_git_cwd_autonomous_unclassified(tmp_path):
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    assert classify_git_push(
        "git push", str(tmp_path), _cfg(), autonomous=True
    ) == T_UNCLASSIFIED


def test_head_colon_refspec_resolved(tmp_path):
    """`git push origin HEAD:main` -> target = main (after the colon)."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin HEAD:main", str(tmp_path), _cfg()
    ) == "T2"


# ---------------------------------------------------------------------------
# classify_git_push — additional coverage (review findings M-1/L-1/L-2/L-3/S-5/S-6)
# ---------------------------------------------------------------------------


def test_multi_refspec_mixed_protected_returns_t2(tmp_path):
    """Multi-refspec: any protected hit → T2 (short-circuit on first match)."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin main feature/x", str(tmp_path), _cfg()
    ) == "T2"


def test_multi_refspec_all_non_protected_returns_unclassified(tmp_path):
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    _make_git_repo(tmp_path, branch="feature/a")
    assert classify_git_push(
        "git push origin feature/a feature/b", str(tmp_path), _cfg()
    ) == T_UNCLASSIFIED


def test_multi_refspec_head_plus_branch(tmp_path):
    """HEAD substitutes the current branch; main pattern still T2s via the literal."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin HEAD main", str(tmp_path), _cfg()
    ) == "T2"


def test_combined_plus_and_refs_heads_strip(tmp_path):
    """`+refs/heads/main` → strip both `+` and `refs/heads/` → match `main`."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin +refs/heads/main", str(tmp_path), _cfg()
    ) == "T2"


def test_end_of_options_separator(tmp_path):
    """`git push -- origin main` should still classify correctly."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push -- origin main", str(tmp_path), _cfg()
    ) == "T2"


def test_delete_refspec_targets_destination(tmp_path):
    """`git push origin :main` (delete remote main) → T2 — the dangerous case."""
    from spellbook.gates.git_push import classify_git_push

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin :main", str(tmp_path), _cfg()
    ) == "T2"


def test_tag_refspec_does_not_match_branch_pattern(tmp_path):
    """`refs/tags/v1.0` is not stripped (only `refs/heads/` is); branch globs
    must not falsely match tag refs."""
    from spellbook.gates.git_push import classify_git_push
    from spellbook.gates.tiers import T_UNCLASSIFIED

    _make_git_repo(tmp_path, branch="feature/x")
    assert classify_git_push(
        "git push origin refs/tags/v1.0", str(tmp_path), _cfg()
    ) == T_UNCLASSIFIED


import pytest as _pytest


@_pytest.mark.parametrize("cmd", ["", "   ", "GIT PUSH origin main", "gitpush origin main"])
def test_non_git_push_inputs_return_none(tmp_path, cmd):
    """Empty/whitespace/case-mismatch/glued inputs must short-circuit to None."""
    from spellbook.gates.git_push import classify_git_push

    assert classify_git_push(cmd, str(tmp_path), _cfg()) is None


def test_git_pushed_fail_does_not_match(tmp_path):
    """The word-boundary check (S-5 fix) rejects `git pushed-fail`."""
    from spellbook.gates.git_push import classify_git_push

    assert classify_git_push("git pushed-fail origin main", str(tmp_path), _cfg()) is None


def test_git_push_fancy_subcommand_does_not_match(tmp_path):
    """`git push-fancy` (hypothetical) is NOT `git push`."""
    from spellbook.gates.git_push import classify_git_push

    assert classify_git_push("git push-fancy origin main", str(tmp_path), _cfg()) is None


# ---------------------------------------------------------------------------
# validate_tiers_toml umbrella validator — Task 5
# ---------------------------------------------------------------------------


def test_validate_tiers_toml_passes_on_clean_file(tmp_path):
    from spellbook.gates.git_push import validate_tiers_toml

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[[tiers]]\n'
        'tool = "Bash"\n'
        'pattern = "ls"\n'
        'tier = "T0"\n'
        'description = "x"\n'
        '\n'
        '[protected]\n'
        'branches = ["main"]\n'
        'remotes = ["origin"]\n',
        encoding="utf-8",
    )
    # Must not raise.
    validate_tiers_toml(toml_path)


def test_validate_tiers_toml_raises_on_bad_protected(tmp_path):
    from spellbook.gates.git_push import validate_tiers_toml

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nbranches = "main"\n',  # wrong type
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"branches.*list"):
        validate_tiers_toml(toml_path)


def test_validate_tiers_toml_raises_on_bad_tiers(tmp_path):
    from spellbook.gates.git_push import validate_tiers_toml

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[[tiers]]\n'
        'tool = "Bash"\n'
        'pattern = "x"\n'
        'tier = "T99"\n'  # invalid tier
        'description = "x"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"tier must be one of"):
        validate_tiers_toml(toml_path)
