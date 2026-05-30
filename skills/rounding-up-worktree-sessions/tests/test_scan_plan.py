"""TASK 13 — scan + plan subcommands (read-only).

Builds a temp $CONFIG/projects tree from the committed fixtures and drives the
CLI subcommands as a subprocess (so argparse wiring + JSON envelopes are covered
end to end). Asserts: scan finds the right sessions, excludes agent-*, respects
lookback; plan groups the cross-dir query-opt fixtures into ONE group; and
appears_running flips True when a sibling .lock fixture is present.
"""
import json
import os
import shutil
import subprocess
import sys

import roundup

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUNDUP = os.path.join(SKILL, "roundup.py")
FIXTURES = os.path.join(SKILL, "tests", "fixtures")
FIXTURE_PROJECTS = os.path.join(FIXTURES, "projects")


def _run(*args):
    return subprocess.run([sys.executable, ROUNDUP, *args], capture_output=True, text=True)


def _make_config(tmp_path):
    """Copy the fixture projects/ tree into a tmp config dir and return its path."""
    cfg = tmp_path / ".claude"
    shutil.copytree(FIXTURE_PROJECTS, str(cfg / "projects"))
    return str(cfg)


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------
def test_scan_excludes_agent_files_and_emits_sessions(tmp_path):
    cfg = _make_config(tmp_path)
    res = _run("scan", "--config-dir", cfg, "--lookback-hours", "100000", "--json")
    assert res.returncode == 0, res.stderr
    doc = json.loads(res.stdout)
    assert doc["schema_version"] == 1
    uuids = [s["uuid"] for s in doc["sessions"]]
    # agent-*.jsonl must be excluded.
    assert all(not u.startswith("agent-") for u in uuids)
    assert "5c6d7e8f-5555-4aaa-8bbb-0123456789ab" not in uuids
    # GM-M1: exact sorted-uuid-set equality. The SIX real sessions:
    #   two under -ODY-styleseat (0f3c..=styleseat-a, 9ab1..=styleseat-b),
    #   qopt-a (1a2b..), qopt-c (2b3c..), mismatch/query-opt-b (4d5e..),
    #   and the HEAD-only session under -x (7b2c..).
    expected_uuids = {
        "0f3c1a2b-1111-4aaa-8bbb-0123456789ab",
        "9ab1c2d3-2222-4ccc-8ddd-0123456789ab",
        "1a2b3c4d-6666-4ddd-8eee-0123456789ab",
        "2b3c4d5e-7777-4fff-8aaa-0123456789ab",
        "4d5e6f70-4444-4bbb-8ccc-0123456789ab",
        "7b2c3d4e-3333-4eee-8fff-0123456789ab",
    }
    assert set(uuids) == expected_uuids
    # Each session carries its config_dir.
    assert all(s["config_dir"] == cfg for s in doc["sessions"])


def test_scan_respects_lookback(tmp_path):
    cfg = _make_config(tmp_path)
    # All fixtures are dated 2026-05-28; a --since AFTER that drops everything.
    res = _run("scan", "--config-dir", cfg, "--since", "2027-01-01T00:00:00Z", "--json")
    assert res.returncode == 0, res.stderr
    doc = json.loads(res.stdout)
    assert doc["sessions"] == []


def test_scan_lock_file_flips_appears_running(tmp_path):
    cfg = _make_config(tmp_path)
    # Drop a sibling <uuid>.lock next to one session jsonl.
    target_dir = os.path.join(cfg, "projects", "-Users-eek-Development-worktrees-ODY-styleseat")
    uuid = "0f3c1a2b-1111-4aaa-8bbb-0123456789ab"
    open(os.path.join(target_dir, uuid + ".lock"), "w").close()
    res = _run("scan", "--config-dir", cfg, "--lookback-hours", "100000", "--json")
    assert res.returncode == 0, res.stderr
    doc = json.loads(res.stdout)
    by_uuid = {s["uuid"]: s for s in doc["sessions"]}
    assert by_uuid[uuid]["appears_running"] is True
    # A session without a lock and an old mtime is not running.
    other = "1a2b3c4d-6666-4ddd-8eee-0123456789ab"
    assert by_uuid[other]["appears_running"] is False


def test_scan_running_threshold_recent_mtime(tmp_path):
    cfg = _make_config(tmp_path)
    target_dir = os.path.join(cfg, "projects", "-Users-eek-Development-worktrees-QOPT-query-opt-a")
    uuid = "1a2b3c4d-6666-4ddd-8eee-0123456789ab"
    # Touch to now so the recent-mtime signal fires (default threshold 120s).
    os.utime(os.path.join(target_dir, uuid + ".jsonl"), None)
    res = _run("scan", "--config-dir", cfg, "--lookback-hours", "100000", "--json")
    assert res.returncode == 0, res.stderr
    doc = json.loads(res.stdout)
    by_uuid = {s["uuid"]: s for s in doc["sessions"]}
    assert by_uuid[uuid]["appears_running"] is True


# ---------------------------------------------------------------------------
# Finding 5 — scan tolerates unreadable config/project dirs (os.listdir OSError)
# ---------------------------------------------------------------------------
def test_scan_tolerates_unreadable_projects_root(tmp_path):
    # os.path.isdir(projects_root) passes but os.listdir raises PermissionError.
    # scan_config_dirs must warn and continue, not crash.
    import stat

    cfg = tmp_path / ".claude"
    projects = cfg / "projects"
    projects.mkdir(parents=True)
    os.chmod(str(projects), 0)
    try:
        sessions, warnings = roundup.scan_config_dirs(
            [str(cfg)], lookback_hours=100000, since_iso=None, running_threshold_sec=120
        )
    finally:
        os.chmod(str(projects), stat.S_IRWXU)
    assert sessions == []
    assert any("failed to list" in w for w in warnings)


def test_scan_tolerates_unreadable_project_dir(tmp_path):
    # A single unreadable <project_dir> must be skipped with a warning; other
    # readable project dirs still scan.
    import stat

    cfg = _make_config(tmp_path)
    bad = os.path.join(cfg, "projects", "-Users-eek-Development-worktrees-ODY-styleseat")
    os.chmod(bad, 0)
    try:
        sessions, warnings = roundup.scan_config_dirs(
            [cfg], lookback_hours=100000, since_iso=None, running_threshold_sec=120
        )
    finally:
        os.chmod(bad, stat.S_IRWXU)
    assert any("failed to list" in w for w in warnings)
    # Sessions from OTHER readable project dirs are still returned.
    uuids = {s["uuid"] for s in sessions}
    assert "1a2b3c4d-6666-4ddd-8eee-0123456789ab" in uuids


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------
def test_plan_emits_envelope(tmp_path):
    cfg = _make_config(tmp_path)
    res = _run("plan", "--config-dir", cfg, "--lookback-hours", "100000", "--json")
    assert res.returncode == 0, res.stderr
    doc = json.loads(res.stdout)
    assert doc["schema_version"] == 1
    assert "groups" in doc
    assert "reorient_candidates" in doc
    assert "sessions" in doc
    assert "warnings" in doc


def test_plan_groups_query_opt_cross_dir_into_one_group(tmp_path):
    cfg = _make_config(tmp_path)
    res = _run("plan", "--config-dir", cfg, "--lookback-hours", "100000", "--json")
    assert res.returncode == 0, res.stderr
    doc = json.loads(res.stdout)
    groups = {g["group_key"]: g for g in doc["groups"]}
    assert "query-opt" in groups
    qopt = groups["query-opt"]
    # qopt-a, qopt-c, and query-opt-b (in the mismatch dir) all share the prefix.
    assert qopt["session_count"] == 3
    assert qopt["group_key_source"] == "title_prefix"


# ---------------------------------------------------------------------------
# reorient_candidates over-inclusion guard (build_plan, §4.4 / I2)
#
# A session is a reorient_candidate ONLY when reorienting it would actually CHANGE
# its storage project dir for at least one OFFERED target. If the session's current
# storage dir already equals encode_cwd_literal(target) for the only available target,
# it MUST NOT be a candidate. These tests pin both the main-repo case (only a
# project-subdir target; workspace_root_dir None) and the worktree case (a workspace
# root is also available), proving an already-at-target session is excluded even when
# the path encodes non-trivially (e.g. a DOT in the dir name -> dash).
# ---------------------------------------------------------------------------
def _plan_session(uuid, encoded_cwd_current, last_cwd, launch_cwd, branch=None):
    """A minimal SessionRecord shaped like scan output, ready for build_plan."""
    return {
        "uuid": uuid,
        "config_dir": "/Users/eek/.claude",
        "jsonl_path": "/Users/eek/.claude/projects/%s/%s.jsonl" % (encoded_cwd_current, uuid),
        "sidecar_dir": None,
        "encoded_cwd_current": encoded_cwd_current,
        "last_cwd": last_cwd,
        "launch_cwd": launch_cwd,
        "git_branch_dominant": branch,
        "title": None,
        "recency_ts": "2026-05-28T00:00:00Z",
        "appears_running": False,
    }


def _mkrepo(path):
    """Create an on-disk git-marked dir so enumerate_worktree_dirs finds it."""
    os.makedirs(os.path.join(path, ".git"), exist_ok=True)
    return path


def test_plan_excludes_already_at_target_main_repo(tmp_path):
    """Main repo (workspace_root_dir None): the only target is the project-subdir
    (resolved_worktree_dir). When the session already lives at encode(that dir) it is
    NOT a reorient_candidate. Uses a DOT-bearing dir so the encoder is exercised
    (mirrors the live styleseat.github case: dot -> dash storage dir already correct)."""
    repos_root = tmp_path / "repos"
    empty_worktrees = tmp_path / "worktrees"  # no worktrees -> workspace_root None
    empty_worktrees.mkdir()
    repo = _mkrepo(str(repos_root / "styleseat.github"))  # DOT in the basename
    enc = roundup.encode_cwd_literal(repo)  # dot -> dash
    # The session's storage dir already encodes the resolved repo dir.
    s = _plan_session("53994eb1-3617-4d27-bd0a-e7f9b41f74c2", enc, repo, repo, branch="mw")

    def branch_of(d):
        return "mw" if d == repo else None

    body = roundup.build_plan(
        [s], worktrees_root=str(empty_worktrees), repos_root=str(repos_root),
        branch_of=branch_of,
    )
    # Sanity: it resolved to the main repo with NO workspace root (only one target).
    enriched = {x["uuid"]: x for x in body["sessions"]}[s["uuid"]]
    assert enriched["resolved_worktree_dir"] == repo
    assert enriched["workspace_root_dir"] is None
    # Already-at-target: must be excluded from reorient_candidates.
    assert body["reorient_candidates"] == []


def test_plan_excludes_already_at_target_worktree(tmp_path):
    """Worktree case (workspace_root_dir non-null): the session already lives at
    encode(resolved_worktree_dir) (the repo-subdir target). Even though a second
    (workspace-root) target exists, the session is at a valid target, so it is NOT a
    candidate (current matches at least one available target encoding)."""
    worktrees_root = tmp_path / "worktrees"
    repos_root = tmp_path / "repos"
    repos_root.mkdir()
    wt_root = str(worktrees_root / "ODY")
    repo = _mkrepo(str(worktrees_root / "ODY" / "styleseat"))
    enc_repo = roundup.encode_cwd_literal(repo)
    s = _plan_session("0f3c1a2b-1111-4aaa-8bbb-0123456789ab", enc_repo, repo, repo, branch="ODY")

    def branch_of(d):
        return "ODY" if d == repo else None

    body = roundup.build_plan(
        [s], worktrees_root=str(worktrees_root), repos_root=str(repos_root),
        branch_of=branch_of,
    )
    enriched = {x["uuid"]: x for x in body["sessions"]}[s["uuid"]]
    assert enriched["resolved_worktree_dir"] == repo
    assert enriched["workspace_root_dir"] == wt_root  # second target is available
    assert body["reorient_candidates"] == []


def test_plan_includes_genuinely_misfiled_session(tmp_path):
    """Control: a session whose storage dir matches NEITHER available target IS a
    candidate. Guards against the exclusion tests passing vacuously."""
    worktrees_root = tmp_path / "worktrees"
    repos_root = tmp_path / "repos"
    repos_root.mkdir()
    repo = _mkrepo(str(worktrees_root / "ODY" / "styleseat"))
    # Storage dir encodes some unrelated old cwd, not the repo nor the workspace root.
    misfiled = roundup.encode_cwd_literal("/Users/eek/Development/somewhere-else")
    s = _plan_session("9ab1c2d3-2222-4ccc-8ddd-0123456789ab", misfiled, repo, repo, branch="ODY")

    def branch_of(d):
        return "ODY" if d == repo else None

    body = roundup.build_plan(
        [s], worktrees_root=str(worktrees_root), repos_root=str(repos_root),
        branch_of=branch_of,
    )
    enriched = {x["uuid"]: x for x in body["sessions"]}[s["uuid"]]
    assert enriched["resolved_worktree_dir"] == repo  # resolved, just misfiled
    assert body["reorient_candidates"] == [s["uuid"]]
