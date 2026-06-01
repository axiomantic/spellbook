import os
import subprocess

import tripwire

import roundup
from _matchers import _IsInstance


def _mk_git(d):
    os.makedirs(os.path.join(d, ".git"), exist_ok=True)


def test_enumerate_finds_workspace_roots_and_subdirs(tmp_path):
    wt = tmp_path / "worktrees"
    repo = wt / "ODY-2957" / "styleseat"
    repo.mkdir(parents=True)
    _mk_git(str(repo))
    dirs = roundup.enumerate_worktree_dirs(str(wt), str(tmp_path / "Development"))
    assert str(wt / "ODY-2957") in dirs           # workspace root
    assert str(repo) in dirs                        # repo subdir with .git


def test_build_index_maps_and_workspace_root(tmp_path):
    wt = str(tmp_path / "worktrees")
    ws = os.path.join(wt, "ODY-2957")
    repo = os.path.join(ws, "styleseat")
    main = str(tmp_path / "Development" / "lockfreequeues")

    def branch_of(d):
        return {repo: "ODY-2957-stripe", main: "master", ws: "ODY-2957-stripe"}.get(d)

    idx = roundup.build_worktree_index([ws, repo, main], branch_of, wt)
    assert repo in idx["branch_to_dirs"]["ODY-2957-stripe"]
    assert idx["dir_to_branch"][main] == "master"
    assert idx["workspace_root_of"][repo] == ws       # subdir -> workspace root
    assert idx["workspace_root_of"][ws] == ws         # root -> itself
    assert idx["workspace_root_of"][main] is None      # main repo -> None


def test_enumerate_nonexistent_roots_return_empty(tmp_path):
    # Finding 4 (baseline): nonexistent roots must yield [] without raising.
    dirs = roundup.enumerate_worktree_dirs(
        str(tmp_path / "no-worktrees"), str(tmp_path / "no-repos")
    )
    assert dirs == []


def test_enumerate_unreadable_worktrees_root_tolerated(tmp_path):
    # Finding 4: an unreadable worktrees_root passes os.path.isdir but os.listdir
    # raises PermissionError. The scan must not crash; it returns what it can (here,
    # the repos_root contents).
    import stat

    wt = tmp_path / "worktrees"
    wt.mkdir()
    repos = tmp_path / "repos"
    main = repos / "lockfreequeues"
    main.mkdir(parents=True)
    _mk_git(str(main))
    # Strip read permission from worktrees_root so os.listdir(worktrees_root) raises.
    os.chmod(str(wt), 0)
    try:
        dirs = roundup.enumerate_worktree_dirs(str(wt), str(repos))
    finally:
        os.chmod(str(wt), stat.S_IRWXU)
    # No crash; the readable repos_root entry is still enumerated.
    assert str(main) in dirs


def test_enumerate_unreadable_repos_root_tolerated(tmp_path):
    # Finding 4: an unreadable repos_root must be treated as empty, not crash.
    import stat

    wt = tmp_path / "worktrees"
    repo = wt / "ODY" / "styleseat"
    repo.mkdir(parents=True)
    _mk_git(str(repo))
    repos = tmp_path / "repos"
    repos.mkdir()
    os.chmod(str(repos), 0)
    try:
        dirs = roundup.enumerate_worktree_dirs(str(wt), str(repos))
    finally:
        os.chmod(str(repos), stat.S_IRWXU)
    assert str(repo) in dirs


def test_git_branch_returns_none_on_timeout(tmp_path):
    # MEDIUM Fix 4: a hung git (TimeoutExpired) must be folded into the graceful
    # "branch unknown" path (return None), not propagate and crash enumeration.
    # The repo style guide forbids monkeypatch.setattr; use the tripwire framework.
    run_mock = tripwire.mock("subprocess:run")
    run_mock.raises(subprocess.TimeoutExpired(cmd=["git"], timeout=5.0))

    with tripwire:
        assert roundup._git_branch(str(tmp_path)) is None

    # The fix must call git with a bounded timeout; assert the call interaction,
    # including that a timeout kwarg was passed and the TimeoutExpired was raised.
    run_mock.assert_call(
        args=(["git", "-C", str(tmp_path), "rev-parse", "--abbrev-ref", "HEAD"],),
        kwargs={"capture_output": True, "text": True, "check": False, "timeout": 5.0},
        raised=_IsInstance(subprocess.TimeoutExpired),
    )


def test_find_project_dir_all_dash_cwd_does_not_return_root(tmp_path):
    # Finding 3: cwd="/" encodes to "-", whose lstrip("-") is "". os.path.join(root, "")
    # == root, which isdir -> the old code wrongly returned projects_root itself. The
    # loop must skip empty candidate names so an all-dashes cwd resolves to None.
    projects = tmp_path / "projects"
    projects.mkdir()
    assert roundup._find_project_dir(str(projects), "/") is None
