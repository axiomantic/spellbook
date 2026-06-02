import os
import roundup


def _idx(branch_to_dirs, dir_to_branch, workspace_root_of):
    return {
        "branch_to_dirs": branch_to_dirs,
        "dir_to_branch": dir_to_branch,
        "workspace_root_of": workspace_root_of,
    }


def _sess(branch=None, last_cwd=None, launch_cwd=None, encoded_cwd_current=None):
    return {
        "git_branch_dominant": branch,
        "last_cwd": last_cwd,
        "launch_cwd": launch_cwd,
        "encoded_cwd_current": encoded_cwd_current,
    }


def test_git_branch_single_hit_high():
    repo = "/wt/ODY/styleseat"
    idx = _idx({"feat": [repo]}, {repo: "feat"}, {repo: "/wt/ODY"})
    out = roundup.derive_worktree(_sess(branch="feat"), idx)
    assert out["resolved_worktree_dir"] == repo
    assert out["resolve_confidence"] == "high"
    assert out["resolve_signal"] == "git_branch"
    assert out["workspace_root_dir"] == "/wt/ODY"


def test_cwd_fallback_medium():
    repo = "/wt/ODY/styleseat"
    idx = _idx({}, {repo: "feat"}, {repo: "/wt/ODY"})
    out = roundup.derive_worktree(_sess(branch=None, last_cwd=repo), idx)
    assert out["resolved_worktree_dir"] == repo
    assert out["resolve_confidence"] == "medium"
    assert out["resolve_signal"] == "cwd"


def test_head_only_unresolved():
    idx = _idx({}, {}, {})
    out = roundup.derive_worktree(_sess(branch=None, launch_cwd="/somewhere"), idx)
    assert out["resolve_confidence"] == "unresolved"
    assert out["resolved_worktree_dir"] is None
    assert out["open_dir"] == "/somewhere"


def test_main_repo_workspace_root_none():
    main = "/Development/lockfreequeues"
    idx = _idx({"master": [main]}, {main: "master"}, {main: None})
    out = roundup.derive_worktree(_sess(branch="master"), idx)
    assert out["resolved_worktree_dir"] == main
    assert out["workspace_root_dir"] is None
    assert out["resolved_workspace"] == "lockfreequeues"


def test_multi_dir_slug_match_branch():
    """GM-M3 + Bug B: Step-1 multi-dir branch with NO usable cwd -> prefer the dir
    whose workspace slug == branch, at LOW confidence (the resolution is genuinely
    ambiguous) with a warning set."""
    d1 = "/wt/feat/styleseat"   # workspace_root /wt/feat -> slug 'feat' == branch
    d2 = "/wt/other/styleseat"  # workspace_root /wt/other -> slug 'other'
    # d2 listed first to prove selection is by slug, not list order.
    idx = _idx({"feat": [d2, d1]},
               {d1: "feat", d2: "feat"},
               {d1: "/wt/feat", d2: "/wt/other"})
    out = roundup.derive_worktree(_sess(branch="feat"), idx)  # no last_cwd/launch_cwd
    assert out["resolved_worktree_dir"] == d1   # slug-matched dir, not d2
    assert out["resolve_confidence"] == "low"
    assert out["resolve_signal"] == "git_branch"
    assert out["warning"]


def test_multi_dir_tiebreak_downgrades_to_low(tmp_path):
    """Bug B: multi-dir branch tiebreak with no usable cwd is now LOW confidence."""
    d1 = tmp_path / "a"
    d1.mkdir()
    d2 = tmp_path / "b"
    d2.mkdir()
    # make d2 newer
    os.utime(str(d2), (10_000_000, 20_000_000))
    os.utime(str(d1), (10_000_000, 10_000_000))
    idx = _idx({"feat": [str(d1), str(d2)]},
               {str(d1): "feat", str(d2): "feat"},
               {str(d1): str(tmp_path), str(d2): str(tmp_path)})
    out = roundup.derive_worktree(_sess(branch="feat"), idx)  # no cwd match
    assert out["resolve_confidence"] == "low"
    assert out["resolved_worktree_dir"] == str(d2)   # most recently modified
    assert out["warning"]


# ---------------------------------------------------------------------------
# Fix 1 — launch_cd_target derives from the CURRENT storage project dir, not
# the internal first-cwd, so previously-reoriented sessions resume correctly.
# ---------------------------------------------------------------------------
def test_launch_cd_target_matches_storage_dir_for_previously_reoriented():
    """A session whose storage project-dir basename encodes a KNOWN worktree dir
    (different from its internal launch_cwd) must set launch_cd_target to that
    storage-matching worktree dir, NOT the stale internal cwd. This is the
    previously-reoriented case: the jsonl lives under encode(new_dir) but its
    internal first-cwd is still the OLD path."""
    repo = "/wt/ODY/styleseat"
    idx = _idx({"feat": [repo]}, {repo: "feat"}, {repo: "/wt/ODY"})
    # storage dir basename == encode_cwd_literal(repo); launch_cwd is the OLD path.
    sess = _sess(
        branch="feat",
        launch_cwd="/old/internal/cwd",
        encoded_cwd_current=roundup.encode_cwd_literal(repo),
    )
    out = roundup.derive_worktree(sess, idx)
    # display/reorient target is still the resolved worktree...
    assert out["resolved_worktree_dir"] == repo
    # ...but the LAUNCH cd-target follows the storage dir, not the internal cwd.
    assert out["launch_cd_target"] == repo


def test_launch_cd_target_matches_storage_dir_stripped_dash_form():
    """Dash-form normalization: the storage basename may be in stripped form while
    encode_cwd_literal(dir) keeps the leading dash (or vice versa). A match must
    still be found regardless of dash form on either side."""
    repo = "/wt/ODY/styleseat"
    idx = _idx({"feat": [repo]}, {repo: "feat"}, {repo: "/wt/ODY"})
    # stored under the STRIPPED form (no leading dash).
    sess = _sess(
        branch="feat",
        launch_cwd="/old/internal/cwd",
        encoded_cwd_current=roundup.encode_cwd_literal(repo).lstrip("-"),
    )
    out = roundup.derive_worktree(sess, idx)
    assert out["launch_cd_target"] == repo


def test_launch_cd_target_falls_back_to_launch_cwd_for_normal_session():
    """A normal (never-reoriented) session: the storage dir was created by its own
    launch_cwd, so encode(launch_cwd) == storage basename and launch_cd_target ==
    launch_cwd (also the safe fallback when nothing else matches)."""
    repo = "/wt/ODY/styleseat"
    launch = "/Users/eek/normal/cwd"
    idx = _idx({"feat": [repo]}, {repo: "feat"}, {repo: "/wt/ODY"})
    sess = _sess(
        branch="feat",
        launch_cwd=launch,
        encoded_cwd_current=roundup.encode_cwd_literal(launch),
    )
    out = roundup.derive_worktree(sess, idx)
    assert out["launch_cd_target"] == launch


def test_launch_cd_target_fallback_when_no_candidate_matches():
    """If the storage basename matches no known dir AND no launch_cwd encoding match,
    fall back to launch_cwd (current behavior preserved)."""
    repo = "/wt/ODY/styleseat"
    idx = _idx({"feat": [repo]}, {repo: "feat"}, {repo: "/wt/ODY"})
    sess = _sess(
        branch="feat",
        launch_cwd="/some/launch/cwd",
        encoded_cwd_current="-totally-unknown-storage-dir",
    )
    out = roundup.derive_worktree(sess, idx)
    assert out["launch_cd_target"] == "/some/launch/cwd"


def test_launch_cd_target_matches_dotted_storage_dir():
    """Bug A read-side: a session stored under a dot-encoded project dir (the dot
    became a dash) must still match its real dir via launch_cd_target. The dir
    `/Users/eek/Development/styleseat.github` stores under
    `-Users-eek-Development-styleseat-github`; resume must cd into the real dir."""
    repo = "/Users/eek/Development/styleseat.github"
    idx = _idx({"master": [repo]}, {repo: "master"}, {repo: None})
    sess = _sess(
        branch="master",
        launch_cwd="/old/internal/cwd",
        encoded_cwd_current=roundup.encode_cwd_literal(repo),
    )
    out = roundup.derive_worktree(sess, idx)
    assert out["launch_cd_target"] == repo


# ---------------------------------------------------------------------------
# Bug B — common-branch ambiguity must not override a usable cwd. A session on
# an ambiguous branch (branch maps to >1 dir) whose launch_cwd / last_cwd is
# itself a known repo dir resolves to that cwd (signal='cwd'), NOT the branch
# mtime/slug tiebreak. Only when cwd is not a usable repo dir does the branch
# tiebreak apply, and then at confidence='low' with a warning.
# ---------------------------------------------------------------------------
def test_ambiguous_branch_prefers_known_cwd_over_tiebreak(tmp_path):
    """nim-skills regression: branch 'master' maps to >1 dir; the session's cwd
    (/Development/nim-skills) is a known repo NOT among the branch candidates.
    Must resolve to the cwd dir (signal='cwd'), not the styleseat tiebreak."""
    styleseat = str(tmp_path / "styleseat")
    other = str(tmp_path / "other")
    nim = str(tmp_path / "nim-skills")
    for d in (styleseat, other, nim):
        os.makedirs(os.path.join(d, ".git"))
    # 'master' maps to two dirs; nim-skills is NOT one of them.
    idx = _idx(
        {"master": [styleseat, other]},
        {styleseat: "master", other: "master", nim: "master"},
        {styleseat: None, other: None, nim: None},
    )
    sess = _sess(branch="master", last_cwd=nim, launch_cwd=nim)
    out = roundup.derive_worktree(sess, idx)
    assert out["resolved_worktree_dir"] == nim
    assert out["resolve_signal"] == "cwd"
    assert out["resolve_confidence"] == "medium"


def test_ambiguous_branch_falls_back_to_tiebreak_low_when_cwd_not_repo(tmp_path):
    """If the cwd is NOT a usable repo dir, fall back to the branch tiebreak but
    at confidence='low' (not medium) with a warning."""
    d1 = str(tmp_path / "a")
    d2 = str(tmp_path / "b")
    for d in (d1, d2):
        os.makedirs(os.path.join(d, ".git"))
    os.utime(os.path.join(d2, ".git"), (10_000_000, 20_000_000))
    os.utime(os.path.join(d1, ".git"), (10_000_000, 10_000_000))
    idx = _idx(
        {"master": [d1, d2]},
        {d1: "master", d2: "master"},
        {d1: None, d2: None},
    )
    # cwd points at a dir that is NOT in the index at all.
    sess = _sess(branch="master", last_cwd="/not/a/repo", launch_cwd="/not/a/repo")
    out = roundup.derive_worktree(sess, idx)
    assert out["resolved_worktree_dir"] == d2  # mtime tiebreak
    assert out["resolve_signal"] == "git_branch"
    assert out["resolve_confidence"] == "low"
    assert out["warning"]
