import os
import roundup


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
