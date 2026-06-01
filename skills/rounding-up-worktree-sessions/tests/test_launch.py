"""TASK 15 — launch executor.

--dry-run / --print-script emits the expected applescript for 1/2/3-pane groups
and mutates nothing (osascript runner is NOT invoked — asserted via injection).
A per-session WARNING is emitted for a session whose config_dir != the ambient
default.
"""
import json
import os
import subprocess
import sys

import roundup

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUNDUP = os.path.join(SKILL, "roundup.py")
DEFAULT = "/Users/eek/.claude"


def _plan(sessions, groups):
    return {"schema_version": 1, "sessions": sessions, "groups": groups}


def _sess(uuid, cd_target="/wt/x", config_dir=DEFAULT):
    # C2: launch panes cd to launch_cd_target (the resume cd-target).
    return {"uuid": uuid, "launch_cd_target": cd_target, "config_dir": config_dir}


# ---------------------------------------------------------------------------
# execute_launch (in-process, injectable runner)
# ---------------------------------------------------------------------------
def test_dry_run_does_not_invoke_runner_single_pane():
    plan = _plan([_sess("u1")], [{"group_key": "g", "sessions": ["u1"]}])
    calls = []
    result = roundup.execute_launch(
        plan, dry_run=True, default_config_dir=DEFAULT, run_osascript=lambda s: calls.append(s)
    )
    assert calls == []  # runner never invoked under dry-run
    assert 'tell application "Ghostty"' in result["script"]
    assert "--resume u1" in result["script"]
    assert "split" not in result["script"]


def test_dry_run_two_pane_layout():
    plan = _plan(
        [_sess("u1"), _sess("u2")],
        [{"group_key": "g", "sessions": ["u1", "u2"]}],
    )
    calls = []
    result = roundup.execute_launch(
        plan, dry_run=True, default_config_dir=DEFAULT, run_osascript=lambda s: calls.append(s)
    )
    assert calls == []
    assert "direction right" in result["script"]
    assert "--resume u1" in result["script"]
    assert "--resume u2" in result["script"]


def test_dry_run_three_pane_layout():
    plan = _plan(
        [_sess(u) for u in ("u1", "u2", "u3")],
        [{"group_key": "g", "sessions": ["u1", "u2", "u3"]}],
    )
    calls = []
    result = roundup.execute_launch(
        plan, dry_run=True, default_config_dir=DEFAULT, run_osascript=lambda s: calls.append(s)
    )
    assert calls == []
    assert "direction right" in result["script"]
    assert "direction down" in result["script"]
    for u in ("u1", "u2", "u3"):
        assert f"--resume {u}" in result["script"]


def test_live_invokes_runner_once():
    plan = _plan([_sess("u1")], [{"group_key": "g", "sessions": ["u1"]}])
    calls = []
    roundup.execute_launch(
        plan, dry_run=False, default_config_dir=DEFAULT, run_osascript=lambda s: calls.append(s)
    )
    assert len(calls) == 1
    assert 'tell application "Ghostty"' in calls[0]


def test_live_osascript_missing_warns_and_does_not_propagate():
    """On non-macOS, `osascript` is absent and the runner raises FileNotFoundError.

    execute_launch must degrade gracefully: emit the not-found warning, report
    ran=False, and NOT propagate the exception.
    """
    plan = _plan([_sess("u1")], [{"group_key": "g", "sessions": ["u1"]}])

    def missing_osascript(_script):
        raise FileNotFoundError(2, "No such file or directory", "osascript")

    result = roundup.execute_launch(
        plan,
        dry_run=False,
        default_config_dir=DEFAULT,
        run_osascript=missing_osascript,
    )

    assert result["ran"] is False
    assert (
        "osascript command not found. Relaunching sessions is only supported on macOS."
        in result["warnings"]
    )


def test_warning_for_non_default_config_session():
    plan = _plan(
        [_sess("u1", config_dir="/Users/eek/.claude-work")],
        [{"group_key": "g", "sessions": ["u1"]}],
    )
    result = roundup.execute_launch(
        plan, dry_run=True, default_config_dir=DEFAULT, run_osascript=lambda s: None
    )
    # GM-I2: exact warning string (the cd target /wt/x is missing so two warnings fire;
    # assert the non-default-config one verbatim).
    expected = (
        "session u1 lives under non-default config dir /Users/eek/.claude-work; "
        "it may not auto-resume if CLAUDE_CONFIG_DIR is not honored (design Decision B)"
    )
    assert expected in result["warnings"]


def test_warning_for_missing_origin_cwd(tmp_path):
    # C2: the warning keys on launch_cd_target (the resume cd-target), not open_dir.
    missing = str(tmp_path / "does-not-exist")
    plan = _plan(
        [_sess("u1", cd_target=missing)],
        [{"group_key": "g", "sessions": ["u1"]}],
    )
    result = roundup.execute_launch(
        plan, dry_run=True, default_config_dir=DEFAULT, run_osascript=lambda s: None
    )
    # GM-I2: exact warning string.
    expected = (
        "session u1 origin cwd missing on disk (%s); resume will fail until restored"
        % missing
    )
    assert expected in result["warnings"]


def test_no_pane_emitted_for_session_without_cd_target():
    """I-launch-1: a session with no launch_cd_target is skipped, never `cd None`."""
    plan = _plan(
        [{"uuid": "u1", "config_dir": DEFAULT}],  # no launch_cd_target
        [{"group_key": "g", "sessions": ["u1"]}],
    )
    result = roundup.execute_launch(
        plan, dry_run=True, default_config_dir=DEFAULT, run_osascript=lambda s: None
    )
    assert "cd None" not in result["script"]
    assert "--resume u1" not in result["script"]  # pane was dropped
    assert any("u1" in w and "cd-target" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# C2 end-to-end: cd-target derived via the REAL pipeline (not a hand-set field).
# Closes green-mirage M3 ("open_dir semantics untested").
# ---------------------------------------------------------------------------
REPO = "/wt/ODY/styleseat"
WS_ROOT = "/wt/ODY"
WT_ROOT = "/wt"


def _pipeline_session():
    """A single resolved session, driven through derive_worktree + group_sessions."""
    s = {
        "uuid": "u1",
        "config_dir": "/c",
        "jsonl_path": "/c/projects/-old/u1.jsonl",
        "sidecar_dir": None,
        "encoded_cwd_current": "-old",
        "launch_cwd": "/launch/u1",
        "last_cwd": REPO,
        "git_branch_dominant": "feat",
        "appears_running": False,
        "recency_ts": "2026-05-28T00:00:00Z",
        "title": "ody-styleseat-a",
    }
    index = roundup.build_worktree_index([REPO], lambda d: "feat", WT_ROOT)
    s.update(roundup.derive_worktree(s, index))
    _groups, sessions = roundup.group_sessions([s])
    return sessions[0]


def test_resolved_not_reoriented_session_cds_to_launch_cwd():
    """A resolved-but-not-reoriented session must cd to launch_cwd, NOT the worktree."""
    s = _pipeline_session()
    # Sanity: it DID resolve to the worktree (display/reorient target)...
    assert s["resolved_worktree_dir"] == REPO
    # ...but the launch cd-target is the literal launch_cwd (C2 invariant).
    assert s["launch_cd_target"] == "/launch/u1"
    cmd = roundup.build_pane_command(s, "/Users/eek/.claude", False)
    assert cmd.startswith("cd /launch/u1 && ")
    assert "cd %s" % REPO not in cmd


def test_pane_command_falls_back_to_default_config_dir():
    """MEDIUM Fix 3: a session with no `config_dir` (None/missing) must fall back to
    `default_config_dir` for the CLAUDE_CONFIG_DIR prefix rather than crashing in
    shlex.quote(None)."""
    s = {"uuid": "u1", "launch_cd_target": "/wt/x"}  # no config_dir key at all
    cmd = roundup.build_pane_command(s, "/Users/eek/.claude-work", False)
    assert cmd is not None
    assert "CLAUDE_CONFIG_DIR=/Users/eek/.claude-work " in cmd
    # An explicit None value must also fall back.
    s2 = {"uuid": "u2", "launch_cd_target": "/wt/y", "config_dir": None}
    cmd2 = roundup.build_pane_command(s2, "/Users/eek/.claude-work", False)
    assert "CLAUDE_CONFIG_DIR=/Users/eek/.claude-work " in cmd2


def test_session_reoriented_to_workspace_root_cds_to_workspace_root():
    """After a workspace_root reorient THIS RUN, the pane must cd to workspace_root."""
    s = _pipeline_session()
    plan = {"sessions": [s]}
    # Simulate a reorient summary that moved u1 into the workspace root.
    summary = {"moved": [{"uuid": "u1", "target_dir": WS_ROOT}]}
    roundup.apply_reorient_launch_overrides(plan, summary)
    assert plan["sessions"][0]["launch_cd_target"] == WS_ROOT
    cmd = roundup.build_pane_command(plan["sessions"][0], "/Users/eek/.claude", False)
    assert cmd.startswith("cd %s && " % WS_ROOT)


# ---------------------------------------------------------------------------
# Fix 2 — same-run wiring: launch consumes a reorient summary so a session
# reoriented THIS RUN cd's to its post-move target dir without a re-scan.
# ---------------------------------------------------------------------------
def test_execute_launch_applies_reorient_summary_override():
    """A session reoriented this run (present in the reorient summary's `moved`)
    must have its pane cd to the POST-MOVE target dir, not its original
    launch_cd_target."""
    # The session's plan-time cd-target is the OLD launch_cwd.
    s = _sess("u1", cd_target="/old/launch/cwd")
    plan = _plan([s], [{"group_key": "g", "sessions": ["u1"]}])
    summary = {"moved": [{"uuid": "u1", "target_dir": "/wt/ODY/styleseat"}]}
    result = roundup.execute_launch(
        plan,
        dry_run=True,
        default_config_dir=DEFAULT,
        reorient_summary=summary,
        run_osascript=lambda s: None,
    )
    assert "cd /wt/ODY/styleseat && " in result["script"]
    assert "cd /old/launch/cwd" not in result["script"]


def test_launch_reorient_summary_cli_applies_override(tmp_path):
    """CLI seam: `launch --plan ... --reorient-summary ... --print-script` loads the
    summary and applies the override before rendering panes."""
    s = _sess("u1", cd_target="/old/launch/cwd")
    plan = _plan([s], [{"group_key": "g", "sessions": ["u1"]}])
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan))
    summary = {"moved": [{"uuid": "u1", "target_dir": "/wt/ODY/styleseat"}]}
    sf = tmp_path / "summary.json"
    sf.write_text(json.dumps(summary))
    res = subprocess.run(
        [
            sys.executable,
            ROUNDUP,
            "launch",
            "--plan",
            str(pf),
            "--reorient-summary",
            str(sf),
            "--print-script",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    assert "cd /wt/ODY/styleseat && " in res.stdout
    assert "cd /old/launch/cwd" not in res.stdout


def test_reorient_summary_out_writes_canonical_summary(tmp_path):
    """`reorient --summary-out <path>` writes the same summary JSON the launch step
    consumes, so the orchestrator can capture it deterministically."""
    cfg = tmp_path / ".claude"
    old = cfg / "projects" / "-old"
    old.mkdir(parents=True)
    jsonl = old / "u1.jsonl"
    jsonl.write_text('{"cwd":"/x"}\n')
    # Backdate so the recent-mtime running signal does not fire.
    past = os.path.getmtime(str(jsonl)) - 3600
    os.utime(str(jsonl), (past, past))
    target = "/Users/eek/Development/worktrees/ODY/styleseat"
    s = {
        "uuid": "u1",
        "config_dir": str(cfg),
        "jsonl_path": str(jsonl),
        "sidecar_dir": None,
        "resolved_worktree_dir": target,
        "workspace_root_dir": "/Users/eek/Development/worktrees/ODY",
        "resolve_confidence": "high",
        "appears_running": False,
        "launch_cwd": "/Users/eek/old-cwd",
    }
    plan_doc = {"schema_version": 1, "sessions": [s]}
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_doc))
    decisions_file = tmp_path / "decisions.json"
    decisions_file.write_text(
        json.dumps([{"uuid": "u1", "config_dir": str(cfg), "target": "repo_subdir"}])
    )
    summary_out = tmp_path / "summary.json"
    res = subprocess.run(
        [
            sys.executable,
            ROUNDUP,
            "reorient",
            "--decisions",
            str(decisions_file),
            "--plan",
            str(plan_file),
            "--summary-out",
            str(summary_out),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    assert summary_out.exists()
    summary = json.loads(summary_out.read_text())
    assert [m["uuid"] for m in summary["moved"]] == ["u1"]
    assert summary["moved"][0]["target_dir"] == target


# ---------------------------------------------------------------------------
# CLI seam
# ---------------------------------------------------------------------------
def test_launch_print_script_no_osascript(tmp_path):
    plan = _plan([_sess("u1")], [{"group_key": "g", "sessions": ["u1"]}])
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan))
    res = subprocess.run(
        [sys.executable, ROUNDUP, "launch", "--plan", str(pf), "--print-script"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    assert 'tell application "Ghostty"' in res.stdout
    assert "--resume u1" in res.stdout


def test_native_applescript_verbs_no_keystroke_injection():
    """The rendered script uses the CONFIRMED native Ghostty verbs (1.2.0+ sdef) and
    contains NO System Events keystroke injection nor the bogus `current session`
    accessor that predated reading the real scripting dictionary."""
    plan = _plan(
        [_sess(u) for u in ("u1", "u2")],
        [{"group_key": "g", "sessions": ["u1", "u2"]}],
    )
    result = roundup.execute_launch(
        plan, dry_run=True, default_config_dir=DEFAULT, run_osascript=lambda s: None
    )
    script = result["script"]
    # Native verbs/accessors (from /Applications/Ghostty.app .../Ghostty.sdef).
    assert "focused terminal of selected tab of baseWindow" in script
    assert "set baseWindow to (new window)" in script
    assert "make new window" not in script
    assert "split pane1 direction right" in script
    assert 'input text "' in script
    assert 'send key "enter" to' in script
    # Keystroke-injection / pre-sdef forms must be fully gone.
    assert "System Events" not in script
    assert "keystroke" not in script
    assert "key code" not in script
    assert "current session" not in script
    assert 'send key "Return"' not in script


def test_launch_help_exits_zero():
    """`launch --help` (and `-h`) print the subcommand help and exit 0."""
    for flag in ("--help", "-h"):
        res = subprocess.run(
            [sys.executable, ROUNDUP, "launch", flag],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr
        assert "--plan" in res.stdout


def test_launch_gui_fallback_is_stub(tmp_path):
    plan = _plan([_sess("u1")], [{"group_key": "g", "sessions": ["u1"]}])
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan))
    res = subprocess.run(
        [sys.executable, ROUNDUP, "launch", "--plan", str(pf), "--launch-mode", "gui"],
        capture_output=True,
        text=True,
    )
    # gui fallback is deferred; must exit non-zero with a clear not-implemented message.
    assert res.returncode != 0
    combined = (res.stdout + res.stderr).lower()
    assert "not implemented" in combined
