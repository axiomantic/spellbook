"""Tests for path_utils: detect_git_context and repo-root resolution."""

import os
import subprocess

import tripwire
import pytest

from spellbook.core.path_utils import (
    _git_free_repo_root,
    detect_git_context,
    encode_cwd,
    resolve_repo_root,
)


class TestDetectGitContext:
    @pytest.mark.allow("subprocess")
    def test_in_git_repo_on_branch(self, tmp_path):
        """Real git repo, detect branch name."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=repo, capture_output=True, check=True,
            env={**dict(__import__("os").environ), "GIT_AUTHOR_NAME": "Test",
                 "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "Test",
                 "GIT_COMMITTER_EMAIL": "t@t"},
        )

        ctx = detect_git_context(str(repo))
        # Default branch varies by git config; just check it's a non-empty string
        assert ctx.branch is not None
        assert len(ctx.branch) > 0
        assert ctx.is_worktree is False
        assert ctx.worktree_name is None

    def test_git_not_available(self):
        """FileNotFoundError from subprocess -> graceful fallback."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            raises=FileNotFoundError("git not found"),
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="", stderr="",
        )

    def test_git_timeout(self):
        """TimeoutExpired from subprocess -> graceful fallback."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            raises=subprocess.TimeoutExpired(cmd="git", timeout=5),
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="", stderr="",
        )

    def test_not_a_git_repo(self):
        """Non-zero returncode -> graceful fallback."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        tripwire.subprocess.mock_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=128,
            stderr="fatal: not a git repository",
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )
        tripwire.subprocess.assert_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )

    def test_detached_head_returns_short_hash(self):
        """Detached HEAD -> branch is short commit hash, not literal 'HEAD'."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout="HEAD\n",
        )
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--short", "HEAD"],
            stdout="abc1234\n",
        )
        tripwire.subprocess.mock_run(
            command=["git", "worktree", "list", "--porcelain"],
            stdout="worktree /tmp/nope\nHEAD abc1234567890\nbranch refs/heads/main\n\n",
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch == "abc1234"
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="HEAD\n", stderr="",
        )
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--short", "HEAD"],
            returncode=0, stdout="abc1234\n", stderr="",
        )
        tripwire.subprocess.assert_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=0,
            stdout="worktree /tmp/nope\nHEAD abc1234567890\nbranch refs/heads/main\n\n",
            stderr="",
        )


def _volume_is_case_insensitive(directory) -> bool:
    """Whether ``directory``'s volume resolves one file under two spellings.

    Probed, never assumed from ``sys.platform``: a macOS box can be either
    (APFS is formatted case-insensitive by default but case-sensitive is a
    supported choice), and a Linux box can mount either. The probe writes a
    file and asks for it back under a different case, which is the property
    the caller actually depends on.
    """
    probe = directory / "CaseProbe"
    probe.write_text("")
    try:
        return (directory / "caseprobe").exists()
    finally:
        probe.unlink()


def _git(*args, cwd):
    """Run git with a hermetic environment (no operator config, no global hooks)."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(cwd),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    return subprocess.run(
        ["git", *args], cwd=str(cwd), env=env,
        capture_output=True, text=True, check=True, timeout=60,
    )


class TestResolveRepoRootMapping:
    """The repo-root mapping is a STORAGE KEY, so it is pinned, not described.

    ``encode_cwd`` turns this string into the develop-gate-ledger filename and
    the session-storage directory name. A root that differs from the previous
    release by one character does not raise: it addresses a file that is not
    there, and every caller reads that as "no state for this project" -- a
    resumed develop run silently starts over, wearing the appearance of a
    normal first run. These assertions therefore name the expected root
    literally rather than recomputing it, so an implementation change cannot
    move the expectation along with the behaviour.
    """

    @pytest.mark.allow("subprocess")
    def test_pins_the_root_for_every_repository_shape(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        _git("init", "-q", ".", cwd=plain)
        _git("commit", "-q", "--allow-empty", "-m", "x", cwd=plain)
        (plain / "a" / "b").mkdir(parents=True)

        worktree = tmp_path / "wt"
        _git("worktree", "add", "-q", "-b", "side", str(worktree), cwd=plain)
        (worktree / "s").mkdir()

        not_a_repo = tmp_path / "norepo"
        not_a_repo.mkdir()

        # Git reports a resolved path (it chdirs, and getcwd resolves symlinks),
        # so on macOS /var/... becomes /private/var/... . The mapping includes
        # that resolution; a walk that skipped it would key a different file.
        plain_root = os.path.realpath(str(plain))

        expected = {
            str(plain): plain_root,
            str(plain / "a"): plain_root,
            str(plain / "a" / "b"): plain_root,
            str(worktree): plain_root,
            str(worktree / "s"): plain_root,
            # No repository: the input passes through UNRESOLVED. Callers rely
            # on this -- resolving it here would rekey every non-repo project.
            str(not_a_repo): str(not_a_repo),
            "": "",
        }
        actual = {p: resolve_repo_root(p) for p in expected}
        assert actual == expected

    @pytest.mark.allow("subprocess")
    def test_pins_the_root_for_shapes_the_walk_declines(self, tmp_path):
        """Submodule and bare layouts keep git's answer, odd as it is.

        Git reports a submodule's GIT DIR rather than its working tree. That
        is the mapping in force, so it is pinned here; the filesystem walk
        must recognize these shapes and hand them back to git rather than
        substitute the answer a reader would expect.
        """
        sup = tmp_path / "sup"
        sup.mkdir()
        _git("init", "-q", ".", cwd=sup)
        _git("commit", "-q", "--allow-empty", "-m", "x", cwd=sup)
        src = tmp_path / "src"
        src.mkdir()
        _git("init", "-q", ".", cwd=src)
        _git("commit", "-q", "--allow-empty", "-m", "y", cwd=src)
        _git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
             str(src), "subm", cwd=sup)

        bare = tmp_path / "bare.git"
        _git("init", "-q", "--bare", str(bare), cwd=tmp_path)

        assert resolve_repo_root(str(sup / "subm")) == os.path.realpath(
            str(sup / ".git" / "modules" / "subm")
        )
        assert resolve_repo_root(str(bare)) == os.path.realpath(str(bare))
        assert _git_free_repo_root(str(sup / "subm")) is None
        assert _git_free_repo_root(str(bare)) is None

    @pytest.mark.allow("subprocess")
    def test_walk_answers_the_real_git_shapes_rather_than_declining(self, tmp_path):
        """Without this, the no-subprocess test below proves nothing.

        That test builds its layouts by hand. If real git wrote a shape the
        walk did not recognize, the walk would decline, the spawn would come
        back, and a suite of hand-built layouts would still be green. This
        asserts the walk RESOLVES the shapes git itself produces.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-q", ".", cwd=repo)
        _git("commit", "-q", "--allow-empty", "-m", "x", cwd=repo)
        worktree = tmp_path / "wt"
        _git("worktree", "add", "-q", "-b", "side", str(worktree), cwd=repo)
        (worktree / "s").mkdir()

        repo_root = os.path.realpath(str(repo))
        for probe in (repo, worktree, worktree / "s"):
            assert _git_free_repo_root(str(probe)) == repo_root, probe

    @pytest.mark.allow("subprocess")
    def test_declines_a_path_spelled_in_a_case_the_disk_does_not_use(self, tmp_path):
        """A case-variant input must not answer where it would answer WRONGLY.

        ``realpath`` resolves symlinks but leaves case alone, so on a
        case-insensitive volume ``/x/MYREPO`` reaches the end of the walk
        spelled the way the caller wrote it, while git -- whose answer comes
        from ``getcwd`` after a ``chdir`` -- reports ``/x/myrepo``. Both are
        non-None and they disagree, which is the one outcome the walk is built
        to avoid: ``encode_cwd`` turns the string into a storage key, so the
        two spellings address two different ledger files and a resumed develop
        run silently starts over.

        The walk therefore declines rather than reconstructs the on-disk
        spelling. Case folding is the filesystem's rule and not Python's, and
        HFS+ also normalizes Unicode, so a reconstruction would be a guess;
        deferring costs one process spawn and cannot be wrong.
        """
        if not _volume_is_case_insensitive(tmp_path):
            pytest.skip("case-sensitive volume: no case-variant path resolves here")

        repo = tmp_path / "myrepo"
        (repo / "a").mkdir(parents=True)
        _git("init", "-q", ".", cwd=repo)
        _git("commit", "-q", "--allow-empty", "-m", "x", cwd=repo)

        variant = str(tmp_path / "MYREPO")
        expected = os.path.realpath(str(repo))

        # The walk defers ...
        assert _git_free_repo_root(variant) is None
        assert _git_free_repo_root(os.path.join(variant, "A")) is None
        # ... and the canonical spelling still takes the fast path.
        assert _git_free_repo_root(str(repo)) == expected
        # ... so the answer the CALLER sees is git's, under either spelling.
        assert resolve_repo_root(variant) == expected
        assert resolve_repo_root(os.path.join(variant, "A")) == expected


class TestResolveRepoRootSpawnsNothing:
    """The mechanism, not the timing: no ``git`` process on the hook path.

    ``spellbook_hook._develop_ledger_path`` reaches this function on every
    ``Task`` PostToolUse, in a FRESH PROCESS per hook event, so the spawn is
    paid in full every time and no in-process memo can amortize it. What is
    asserted here is therefore the mechanism, not a duration: inside a
    ``tripwire`` sandbox with no mock registered, ``subprocess.run`` raises
    ``UnmockedInteractionError``. Outside a sandbox tripwire lets subprocess
    through (``[tool.tripwire.firewall] allow`` lists ``subprocess:*``), so
    entering the sandbox explicitly -- not merely omitting a mark -- is what
    makes this a detector rather than a description.

    Two placement decisions carry the test:

    - The call under test is ``resolve_repo_root``, NOT
      ``_develop_ledger_path``. That caller wraps everything in
      ``except Exception``, which swallows ``UnmockedInteractionError`` and
      would report a restored spawn as a pass. ``resolve_repo_root`` catches
      only ``TimeoutExpired``/``FileNotFoundError``/``OSError``, and
      ``UnmockedInteractionError`` inherits from ``Exception`` alone, so it
      propagates.
    - The results are compared AFTER the sandbox closes. An assertion inside
      would raise ``AssertionInsideSandboxError`` and confuse a mapping
      failure with a spawn.

    The layouts are written directly to disk rather than created by git,
    since invoking git would itself need the sandbox this test withholds.
    ``TestResolveRepoRootMapping.test_walk_answers_the_real_git_shapes_rather_than_declining``
    is what ties these hand-built layouts back to what git actually writes;
    without it, a walk that declined every real shape would still be green
    here.
    """

    @staticmethod
    def _write_repo(root):
        (root / ".git" / "objects").mkdir(parents=True)
        (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    def test_plain_repo_and_subdirectory_resolve_without_git(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "a" / "b").mkdir(parents=True)
        self._write_repo(repo)

        with tripwire:
            got = [resolve_repo_root(str(repo)), resolve_repo_root(str(repo / "a" / "b"))]

        expected = os.path.realpath(str(repo))
        assert got == [expected, expected]

    def test_linked_worktree_maps_to_the_main_worktree_without_git(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_repo(repo)
        git_dir = repo / ".git" / "worktrees" / "wt"
        git_dir.mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/side\n")
        (git_dir / "commondir").write_text("../..\n")

        worktree = tmp_path / "wt"
        (worktree / "s").mkdir(parents=True)
        (worktree / ".git").write_text(f"gitdir: {git_dir}\n")

        with tripwire:
            got = [resolve_repo_root(str(worktree)), resolve_repo_root(str(worktree / "s"))]

        # The whole point of the mapping: a worktree is NOT an ancestor of
        # the root it keys to, so no prefix rule could produce this.
        expected = os.path.realpath(str(repo))
        assert got == [expected, expected]

    def test_non_repository_passes_through_without_git(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()

        with tripwire:
            got = resolve_repo_root(str(plain))

        assert got == str(plain)

    def test_encode_cwd_reaches_the_same_key_without_git(self, tmp_path):
        """The caller's contract, not just the helper's."""
        repo = tmp_path / "repo"
        (repo / "sub").mkdir(parents=True)
        self._write_repo(repo)

        with tripwire:
            got = [encode_cwd(str(repo / "sub")), encode_cwd(str(repo))]

        assert got[0] == got[1]
