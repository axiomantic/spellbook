"""Regression tests for scripts/branch-context.sh and scripts/branch-context.py.

These two scripts are the canonical merge-base resolver for every review skill,
so a silent regression in either one poisons every review that consumes them.

Testing approach:

* Real git repositories, built with ``git init`` under ``tmp_path``. No git
  command is mocked. Remotes are local bare repos, so fetch works offline.
* ``gh`` is replaced by a real executable stub placed first on ``PATH``. That is
  not a mocking framework -- it is a fixture binary -- and it guarantees no test
  reaches the network. tripwire's subprocess plugin cannot help implement this:
  both scripts run in a *separate* process, so an in-process interception layer
  would never observe their calls.
* ``monkeypatch`` is used only for ``setenv``/``delenv``, which is permitted.

Every scenario is asserted for SHELL/PYTHON PARITY: the ``resolution``
subcommand of both implementations must produce byte-identical stdout for the
same repository state. A ``.sh`` change that skips the matching ``.py`` update
fails these tests.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# These are REBOUND by the session-scoped `_snapshot_scripts` fixture below to
# point at immutable copies. They are declared here only so the module-level
# helpers can name them.
SH_SCRIPT = REPO_ROOT / "scripts" / "branch-context.sh"
PY_SCRIPT = REPO_ROOT / "scripts" / "branch-context.py"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("jq") is None,
    reason="branch-context requires git and jq on PATH",
)


# --------------------------------------------------------------------------
# git helpers -- real repositories, no mocking
# --------------------------------------------------------------------------

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_NOSYSTEM": "1",
    # Hermeticity: without this, a developer's global config (commit.gpgsign,
    # url.*.insteadOf, init.templateDir) leaks in and breaks the helpers.
    "GIT_CONFIG_GLOBAL": os.devnull,
}


def git(cwd: Path, *args: str) -> str:
    """Run a git command in ``cwd`` and return stripped stdout."""
    env = {**os.environ, **GIT_ENV}
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit_file(repo: Path, name: str, content: str) -> str:
    """Write ``name``, commit it, and return the new commit sha."""
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-m", f"add {name}")
    return git(repo, "rev-parse", "HEAD")


def init_repo(path: Path, default_branch: str = "main") -> Path:
    """Create a non-bare repo with one commit on ``default_branch``."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", default_branch)
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    commit_file(path, "README.md", "base\n")
    return path


def init_bare_origin(path: Path, source: Path, default_branch: str) -> Path:
    """Clone ``source`` into a bare repo whose HEAD points at ``default_branch``."""
    subprocess.run(
        ["git", "clone", "--bare", str(source), str(path)],
        env={**os.environ, **GIT_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    git(path, "symbolic-ref", "HEAD", f"refs/heads/{default_branch}")
    return path


def add_remote(repo: Path, name: str, url: Path) -> None:
    """Add a remote, fetch it, and resolve its HEAD symref."""
    git(repo, "remote", "add", name, str(url))
    git(repo, "fetch", "--quiet", name)
    git(repo, "remote", "set-head", name, "-a")


def clone(origin: Path, dest: Path, remote_name: str = "origin") -> Path:
    """Clone a bare origin into ``dest``. Clone resolves the remote HEAD for us."""
    subprocess.run(
        ["git", "clone", "--quiet", "--origin", remote_name, str(origin), str(dest)],
        env={**os.environ, **GIT_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    git(dest, "config", "user.name", "Test")
    git(dest, "config", "user.email", "test@example.com")
    return dest


# --------------------------------------------------------------------------
# gh stub -- a real executable, first on PATH
# --------------------------------------------------------------------------


def make_gh_stub(bin_dir: Path, payload: str | None) -> Path:
    """Install a ``gh`` stub.

    ``payload`` None means "no PR found": the stub exits 1 with no output,
    exactly as real ``gh pr view`` does for a branch with no pull request.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh = bin_dir / "gh"
    if payload is None:
        gh.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    else:
        payload_file = bin_dir / "pr.json"
        payload_file.write_text(payload, encoding="utf-8")
        gh.write_text(
            f'#!/bin/sh\ncat "{payload_file}"\n',
            encoding="utf-8",
        )
    gh.chmod(0o755)
    return gh


# --------------------------------------------------------------------------
# script invocation + parity
# --------------------------------------------------------------------------


def run_script(script: Path, repo: Path, bin_dir: Path, *args: str, fetch: bool = False):
    """Invoke one implementation and return the CompletedProcess."""
    env = {**os.environ, **GIT_ENV}
    env["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
    if not fetch:
        env["SPELLBOOK_BRANCH_CONTEXT_NO_FETCH"] = "1"
    else:
        env.pop("SPELLBOOK_BRANCH_CONTEXT_NO_FETCH", None)
    argv = [str(script), *args] if script.suffix == ".sh" else ["python3", str(script), *args]
    return subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True, check=False)


def parse_resolution(stdout: str) -> dict[str, str]:
    out = {}
    for line in stdout.strip().splitlines():
        key, _, value = line.partition("=")
        out[key] = value
    return out


def resolution_of_both(
    repo: Path,
    bin_dir: Path,
    *,
    fetch: bool = False,
    extra_args: tuple[str, ...] = (),
) -> dict[str, str]:
    """Run ``resolution`` under BOTH implementations, assert parity, return the fields.

    Parity is asserted on every scenario rather than in one dedicated test. The
    repo's MUST is that any ``.sh`` change carries a matching ``.py`` change, and
    the cheapest enforcement is to compare on every state the suite constructs.
    """
    sh = run_script(SH_SCRIPT, repo, bin_dir, "resolution", *extra_args, fetch=fetch)
    py = run_script(PY_SCRIPT, repo, bin_dir, "resolution", *extra_args, fetch=fetch)
    assert sh.returncode == py.returncode, (
        f"exit-code parity broken: sh={sh.returncode} py={py.returncode}\n"
        f"sh stderr: {sh.stderr}\npy stderr: {py.stderr}"
    )
    assert sh.returncode == 0, f"resolution failed: {sh.stderr}"
    assert sh.stdout == py.stdout, (
        "SHELL/PYTHON PARITY BROKEN for `resolution`.\n"
        f"--- branch-context.sh ---\n{sh.stdout}\n"
        f"--- branch-context.py ---\n{py.stdout}"
    )
    return parse_resolution(sh.stdout)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _snapshot_scripts(tmp_path_factory: pytest.TempPathFactory):
    """Run every test against an immutable SNAPSHOT of both implementations.

    This suite asserts byte-parity between ``branch-context.sh`` and
    ``branch-context.py``. Pointing it at the LIVE working-tree files makes it a
    data race with whatever is editing them: a partially applied change (one
    script edited, the other not yet) is a genuinely skewed pair, and the suite
    dutifully reports a real parity failure on a state that never existed as a
    commit. That surfaced as order-dependent, partially-failing runs -- a proper
    SUBSET failing, which is the signature of skew rather than a bug.

    Copying both files ONCE per session means every test in the run compares a
    single consistent pair, whatever happens to the working tree meanwhile.
    """
    global SH_SCRIPT, PY_SCRIPT
    snapshot_dir = tmp_path_factory.mktemp("branch-context-snapshot")
    sh_snapshot = snapshot_dir / "branch-context.sh"
    py_snapshot = snapshot_dir / "branch-context.py"
    shutil.copy2(SH_SCRIPT, sh_snapshot)
    shutil.copy2(PY_SCRIPT, py_snapshot)
    sh_snapshot.chmod(0o755)
    SH_SCRIPT, PY_SCRIPT = sh_snapshot, py_snapshot
    yield


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    """A PATH-prefix directory holding the gh stub (no PR by default)."""
    d = tmp_path / "fakebin"
    make_gh_stub(d, None)
    return d


@pytest.fixture
def solo_repo(tmp_path: Path) -> Path:
    """A repo with an ``origin`` whose HEAD is ``main``, on branch ``feature``."""
    origin_src = init_repo(tmp_path / "origin-src", "main")
    origin = init_bare_origin(tmp_path / "origin.git", origin_src, "main")
    repo = clone(origin, tmp_path / "work")
    git(repo, "checkout", "-b", "feature")
    commit_file(repo, "feature.txt", "work\n")
    return repo


# --------------------------------------------------------------------------
# Row 1 -- PR exists with a base ref
# --------------------------------------------------------------------------


def test_pr_base_ref_wins_when_pr_exists(solo_repo: Path, bin_dir: Path):
    """A PR whose headRefName matches the current branch supplies the base."""
    git(solo_repo, "branch", "develop", "origin/main")
    make_gh_stub(
        bin_dir,
        json.dumps(
            {
                "baseRefName": "develop",
                "url": "https://example.invalid/pr/1",
                "headRefName": "feature",
            }
        ),
    )
    fields = resolution_of_both(solo_repo, bin_dir)
    assert fields["resolved_via"] == "pr-base-ref"
    assert fields["merge_target"] == "develop"


def test_pr_with_mismatched_head_ref_is_rejected(solo_repo: Path, bin_dir: Path):
    """gh matches on branch NAME; a PR for a different head ref must be ignored."""
    make_gh_stub(
        bin_dir,
        json.dumps(
            {
                "baseRefName": "some-other-base",
                "url": "https://example.invalid/pr/9",
                "headRefName": "not-our-branch",
            }
        ),
    )
    fields = resolution_of_both(solo_repo, bin_dir)
    assert fields["resolved_via"] != "pr-base-ref"
    assert fields["merge_target"] != "some-other-base"


# --------------------------------------------------------------------------
# Row 2 -- no PR, upstream tracking branch set
# --------------------------------------------------------------------------


def test_upstream_tracking_used_when_no_pr(solo_repo: Path, bin_dir: Path):
    git(solo_repo, "branch", "--set-upstream-to", "origin/main", "feature")
    fields = resolution_of_both(solo_repo, bin_dir)
    assert fields["resolved_via"] == "upstream-tracking"
    assert fields["merge_target"] == "main"


def test_upstream_tracking_beats_remote_head(tmp_path: Path, bin_dir: Path):
    """Rung 2 outranks rung 3: a tracked release branch is not overridden by HEAD."""
    origin_src = init_repo(tmp_path / "src", "main")
    git(origin_src, "checkout", "-b", "release")
    commit_file(origin_src, "rel.txt", "rel\n")
    git(origin_src, "checkout", "main")
    origin = init_bare_origin(tmp_path / "o.git", origin_src, "main")
    repo = clone(origin, tmp_path / "w")
    git(repo, "checkout", "-b", "feature")
    commit_file(repo, "f.txt", "x\n")
    git(repo, "branch", "--set-upstream-to", "origin/release", "feature")

    fields = resolution_of_both(repo, bin_dir)
    assert fields["resolved_via"] == "upstream-tracking"
    assert fields["merge_target"] == "release"


# --------------------------------------------------------------------------
# Row 3 -- no PR, no upstream, remote HEAD available
# --------------------------------------------------------------------------


def test_remote_head_used_when_no_pr_and_no_upstream(solo_repo: Path, bin_dir: Path):
    probe = subprocess.run(
        ["git", "config", "--get", "branch.feature.merge"],
        cwd=solo_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode != 0, "precondition: feature must have no upstream"
    fields = resolution_of_both(solo_repo, bin_dir)
    assert fields["resolved_via"] == "remote-head"
    assert fields["merge_target"] == "main"
    assert fields["remote"] == "origin"


# --------------------------------------------------------------------------
# Row 4 -- fork / multi-remote: upstream wins over origin
# --------------------------------------------------------------------------


def test_upstream_remote_preferred_over_origin(tmp_path: Path, bin_dir: Path):
    """In a fork setup the parent repo is ``upstream``; it must supply the base."""
    parent_src = init_repo(tmp_path / "parent-src", "trunk")
    parent = init_bare_origin(tmp_path / "parent.git", parent_src, "trunk")

    fork_src = init_repo(tmp_path / "fork-src", "main")
    fork = init_bare_origin(tmp_path / "fork.git", fork_src, "main")

    repo = clone(parent, tmp_path / "work", remote_name="upstream")
    add_remote(repo, "origin", fork)
    git(repo, "checkout", "-b", "feature")
    commit_file(repo, "f.txt", "x\n")

    fields = resolution_of_both(repo, bin_dir)
    assert fields["remote"] == "upstream", "origin must not shadow upstream"
    assert fields["merge_target"] == "trunk"
    assert fields["base_ref"] == "upstream/trunk"


# --------------------------------------------------------------------------
# Row 5 -- detached HEAD
# --------------------------------------------------------------------------


def test_detached_head_is_reported_and_skips_pr_and_upstream(solo_repo: Path, bin_dir: Path):
    """Detached HEAD has no branch identity: rungs 1 and 2 must be skipped."""
    git(solo_repo, "branch", "--set-upstream-to", "origin/main", "feature")
    make_gh_stub(
        bin_dir,
        json.dumps(
            {
                "baseRefName": "should-not-be-used",
                "url": "https://example.invalid/pr/2",
                "headRefName": "feature",
            }
        ),
    )
    git(solo_repo, "checkout", "--detach", "HEAD")

    fields = resolution_of_both(solo_repo, bin_dir)
    assert fields["detached_head"] == "true"
    assert fields["resolved_via"] not in ("pr-base-ref", "upstream-tracking")
    assert fields["merge_target"] != "should-not-be-used"


def test_detached_head_warning_in_summary(solo_repo: Path, bin_dir: Path):
    git(solo_repo, "checkout", "--detach", "HEAD")
    sh = run_script(SH_SCRIPT, solo_repo, bin_dir, "summary")
    py = run_script(PY_SCRIPT, solo_repo, bin_dir, "summary")
    assert "detached HEAD" in sh.stdout
    assert "detached HEAD" in py.stdout


# --------------------------------------------------------------------------
# Row 6 -- master-default repo: no hardcoded "main"
# --------------------------------------------------------------------------


def test_master_default_repo_does_not_hardcode_main(tmp_path: Path, bin_dir: Path):
    origin_src = init_repo(tmp_path / "src", "master")
    origin = init_bare_origin(tmp_path / "o.git", origin_src, "master")
    repo = clone(origin, tmp_path / "w")
    git(repo, "checkout", "-b", "feature")
    commit_file(repo, "f.txt", "x\n")

    fields = resolution_of_both(repo, bin_dir)
    assert fields["merge_target"] == "master"
    assert fields["resolved_via"] == "remote-head"
    assert "main" not in fields["base_ref"]


def test_fallback_literal_is_labelled_as_a_guess(tmp_path: Path, bin_dir: Path):
    """With no PR, no upstream, and no remote, the literal must be flagged GUESSED."""
    repo = init_repo(tmp_path / "solo", "main")
    git(repo, "checkout", "-b", "feature")
    commit_file(repo, "f.txt", "x\n")

    fields = resolution_of_both(repo, bin_dir)
    assert fields["resolved_via"] == "fallback-literal"
    assert fields["remote"] == "none"

    sh = run_script(SH_SCRIPT, repo, bin_dir, "target")
    py = run_script(PY_SCRIPT, repo, bin_dir, "target")
    assert "GUESSED" in sh.stderr
    assert "GUESSED" in py.stderr
    assert sh.stdout == py.stdout


# --------------------------------------------------------------------------
# Row 7 -- inside a git worktree
# --------------------------------------------------------------------------


def test_worktree_is_detected(tmp_path: Path, solo_repo: Path, bin_dir: Path):
    wt = tmp_path / "wt"
    git(solo_repo, "worktree", "add", "-b", "wt-branch", str(wt), "HEAD")
    commit_file(wt, "wt.txt", "x\n")

    resolution_of_both(wt, bin_dir)

    sh = run_script(SH_SCRIPT, wt, bin_dir, "json")
    py = run_script(PY_SCRIPT, wt, bin_dir, "json")
    sh_data, py_data = json.loads(sh.stdout), json.loads(py.stdout)
    assert sh_data["is_worktree"] is True
    assert py_data["is_worktree"] is True
    assert sh_data["branch"] == py_data["branch"] == "wt-branch"
    assert sh_data == py_data, "SHELL/PYTHON PARITY BROKEN for `json` inside a worktree"


# --------------------------------------------------------------------------
# Fetch behaviour
# --------------------------------------------------------------------------


def test_fetch_runs_by_default_and_is_reported(solo_repo: Path, bin_dir: Path):
    fields = resolution_of_both(solo_repo, bin_dir, fetch=True)
    assert fields["fetch"] == "ok"


def test_fetch_can_be_skipped_by_env(solo_repo: Path, bin_dir: Path):
    fields = resolution_of_both(solo_repo, bin_dir, fetch=False)
    assert fields["fetch"] == "skipped (SPELLBOOK_BRANCH_CONTEXT_NO_FETCH=1)"


def test_fetch_failure_is_reported_not_silent(tmp_path: Path, bin_dir: Path):
    """An unreachable remote must degrade loudly, never silently."""
    origin_src = init_repo(tmp_path / "src", "main")
    origin = init_bare_origin(tmp_path / "o.git", origin_src, "main")
    repo = clone(origin, tmp_path / "w")
    git(repo, "checkout", "-b", "feature")
    commit_file(repo, "f.txt", "x\n")
    shutil.rmtree(origin)

    fields = resolution_of_both(repo, bin_dir, fetch=True)
    assert fields["fetch"].startswith("FAILED")
    assert "STALE" in fields["fetch"]


# --------------------------------------------------------------------------
# Parity across the remaining subcommands
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sub",
    [
        "base",
        "target",
        "files",
        "files-committed",
        "log",
        "stat",
        "stat-committed",
        "diff-committed",
    ],
)
def test_subcommand_stdout_parity(solo_repo: Path, bin_dir: Path, sub: str):
    (solo_repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    sh = run_script(SH_SCRIPT, solo_repo, bin_dir, sub)
    py = run_script(PY_SCRIPT, solo_repo, bin_dir, sub)
    assert sh.returncode == py.returncode
    # EXACT, not stripped. `.strip()` hid a real divergence: the Python `files`
    # endpoint used `print(run_git(...))`, which emits a bare newline where the
    # shell emits zero bytes. A consumer doing `.split("\n")` on that sees one
    # phantom filename -- a coverage manifest entry for a file that is not in
    # the diff. Stripping both sides made the two byte streams look identical.
    assert sh.stdout == py.stdout, (
        f"SHELL/PYTHON PARITY BROKEN for `{sub}`.\n"
        f"--- sh ---\n{sh.stdout!r}\n--- py ---\n{py.stdout!r}"
    )


def test_empty_file_list_emits_zero_bytes_in_both_implementations(
    tmp_path: Path, bin_dir: Path
):
    """An empty file list must be ZERO BYTES, not a bare newline.

    On a branch with nothing committed ahead of the base, `files-committed` has
    no output. `print("")` writes ``"\\n"``; the shell writes nothing. A caller
    doing ``out.split("\\n")`` then builds a one-entry manifest for a file named
    ``""`` -- or, worse, reports a non-zero file count for an empty diff.
    """
    repo = init_repo(tmp_path / "repo", default_branch="main")
    # A branch with no commits ahead of its base: the committed diff is empty.
    git(repo, "checkout", "-b", "feature")
    git(repo, "branch", "--set-upstream-to", "main", "feature")

    for sub in ("files-committed", "files"):
        sh = run_script(SH_SCRIPT, repo, bin_dir, sub)
        py = run_script(PY_SCRIPT, repo, bin_dir, sub)
        assert sh.returncode == 0 and py.returncode == 0, f"{sub}: {sh.stderr}{py.stderr}"
        assert sh.stdout == "", f"`{sub}` (sh) emitted {sh.stdout!r} for an empty list"
        assert py.stdout == "", f"`{sub}` (py) emitted {py.stdout!r} for an empty list"


# --------------------------------------------------------------------------
# Endpoint pairing -- the coverage-manifest invariant
# --------------------------------------------------------------------------


def test_files_committed_agrees_with_diff_committed(solo_repo: Path, bin_dir: Path):
    """``files-committed`` must manifest exactly the files ``diff-committed`` contains.

    Pairing ``files`` (working tree) with ``diff-committed`` lets a review build a
    coverage manifest of files the diff does not contain, then certify N-of-N
    against zero hunks. The endpoints must agree.
    """
    # An uncommitted-only file: in `files`, absent from `diff-committed`.
    (solo_repo / "uncommitted.txt").write_text("not committed\n", encoding="utf-8")
    git(solo_repo, "add", "uncommitted.txt")

    for script in (SH_SCRIPT, PY_SCRIPT):
        listed = set(run_script(script, solo_repo, bin_dir, "files-committed").stdout.split())
        diff_text = run_script(script, solo_repo, bin_dir, "diff-committed").stdout
        in_diff = {
            line.split(" b/", 1)[1]
            for line in diff_text.splitlines()
            if line.startswith("diff --git ")
        }
        assert listed == in_diff, f"{script.name}: files-committed disagrees with diff-committed"
        assert "uncommitted.txt" not in listed

        working = set(run_script(script, solo_repo, bin_dir, "files").stdout.split())
        assert "uncommitted.txt" in working, "`files` must still include the working tree"


def test_json_reports_both_endpoints_and_they_differ(solo_repo: Path, bin_dir: Path):
    """The MACHINE-READABLE endpoint must expose the committed count too.

    The human-facing endpoints were split into `files`/`files-committed`, but
    `json` -- the one the review automation actually branches on for E_NO_DIFF --
    kept reporting only the WORKING-TREE number. So a branch with zero commits
    and a dirty tree still looked reviewable, the review proceeded, and it built
    an empty coverage manifest that certified itself.
    """
    (solo_repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    git(solo_repo, "add", "dirty.txt")

    sh = run_script(SH_SCRIPT, solo_repo, bin_dir, "json")
    py = run_script(PY_SCRIPT, solo_repo, bin_dir, "json")
    sh_data, py_data = json.loads(sh.stdout), json.loads(py.stdout)

    assert sh_data == py_data, "SHELL/PYTHON PARITY BROKEN for `json`"
    for data in (sh_data, py_data):
        assert "files_changed_committed" in data, (
            "`json` must expose the committed file count; automation keying "
            "E_NO_DIFF on `files_changed` reads the working tree instead"
        )
        # The staged-but-uncommitted file is in `files_changed` and not in
        # `files_changed_committed`, so the two are genuinely distinct.
        assert data["files_changed"] == data["files_changed_committed"] + 1


def test_json_committed_count_is_zero_when_nothing_is_committed(
    tmp_path: Path, bin_dir: Path
):
    """The exact live condition: 0 commits ahead, dirty tree, review proceeds."""
    repo = init_repo(tmp_path / "repo", default_branch="main")
    git(repo, "checkout", "-b", "feature")
    git(repo, "branch", "--set-upstream-to", "main", "feature")
    (repo / "unreviewed.txt").write_text("work in progress\n", encoding="utf-8")
    git(repo, "add", "unreviewed.txt")

    for script in (SH_SCRIPT, PY_SCRIPT):
        data = json.loads(run_script(script, repo, bin_dir, "json").stdout)
        assert data["commits"] == 0
        assert data["files_changed_committed"] == 0, (
            f"{script.name}: nothing is committed ahead of the base"
        )
        assert data["files_changed"] == 1, (
            f"{script.name}: the working-tree count is NOT a proxy for reviewability"
        )


def test_files_committed_excludes_uncommitted_work(solo_repo: Path, bin_dir: Path):
    """The two file-list endpoints must be distinguishable, not aliases."""
    # Staged, not committed: `git diff <base>` sees it, `git diff <base>..HEAD` does not.
    # (An UNtracked file is invisible to both, so staging is what makes the
    # endpoints distinguishable.)
    (solo_repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    git(solo_repo, "add", "dirty.txt")
    for script in (SH_SCRIPT, PY_SCRIPT):
        committed = set(run_script(script, solo_repo, bin_dir, "files-committed").stdout.split())
        working = set(run_script(script, solo_repo, bin_dir, "files").stdout.split())
        assert working - committed == {"dirty.txt"}


# --------------------------------------------------------------------------
# --base override
# --------------------------------------------------------------------------


def test_base_override_reports_explicit_override(solo_repo: Path, bin_dir: Path):
    """An explicit --base skips detection and SAYS it did."""
    git(solo_repo, "branch", "sidebase", "origin/main")
    make_gh_stub(
        bin_dir,
        json.dumps(
            {
                "baseRefName": "should-not-be-used",
                "url": "https://example.invalid/pr/3",
                "headRefName": "feature",
            }
        ),
    )
    fields = resolution_of_both(solo_repo, bin_dir, extra_args=("--base", "sidebase"))
    assert fields["resolved_via"] == "explicit-override"
    assert fields["merge_target"] == "sidebase"
    assert fields["base_ref"] == "sidebase"
    assert fields["merge_base"] == git(solo_repo, "merge-base", "HEAD", "sidebase")


def test_base_override_equals_form_matches_space_form(solo_repo: Path, bin_dir: Path):
    git(solo_repo, "branch", "sidebase", "origin/main")
    spaced = resolution_of_both(solo_repo, bin_dir, extra_args=("--base", "sidebase"))
    equals = resolution_of_both(solo_repo, bin_dir, extra_args=("--base=sidebase",))
    assert spaced == equals


def test_base_override_applies_to_diff_endpoints(solo_repo: Path, bin_dir: Path):
    """The override must reach the diff subcommands, not just `resolution`."""
    commit_file(solo_repo, "second.txt", "second\n")
    base = git(solo_repo, "rev-parse", "HEAD~1")
    for script in (SH_SCRIPT, PY_SCRIPT):
        listed = run_script(
            script, solo_repo, bin_dir, "files-committed", "--base", base
        ).stdout.split()
        assert listed == ["second.txt"]


def test_base_without_argument_is_an_error(solo_repo: Path, bin_dir: Path):
    for script in (SH_SCRIPT, PY_SCRIPT):
        result = run_script(script, solo_repo, bin_dir, "resolution", "--base")
        assert result.returncode == 2, f"{script.name} accepted a bare --base"
        assert "--base requires a ref" in result.stderr


def test_unexpected_extra_argument_is_an_error(solo_repo: Path, bin_dir: Path):
    for script in (SH_SCRIPT, PY_SCRIPT):
        result = run_script(script, solo_repo, bin_dir, "resolution", "files")
        assert result.returncode == 2, f"{script.name} accepted two subcommands"
        assert "unexpected argument" in result.stderr


def test_resolution_banner_goes_to_stderr_not_stdout(solo_repo: Path, bin_dir: Path):
    """A consumer capturing stdout must get only the payload, never the banner."""
    for script in (SH_SCRIPT, PY_SCRIPT):
        result = run_script(script, solo_repo, bin_dir, "base")
        assert "resolved-via:" in result.stderr
        assert "resolved-via:" not in result.stdout
        assert result.stdout.strip() == git(solo_repo, "merge-base", "HEAD", "origin/main")
