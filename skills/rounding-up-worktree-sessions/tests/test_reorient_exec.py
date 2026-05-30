"""TASK 14 — reorient executor (the risky one). Real-fs tests in tmp dirs.

Covers: successful move of jsonl+sidecar; collision refusal; dry-run mutates
nothing; injected sidecar-move failure triggers rollback of the jsonl; running
re-check skip (TOCTOU); --update-history rewrites only matching project lines and
makes a backup; history failure leaves moves intact.
"""
import json
import os
import shutil
import subprocess
import sys

import tripwire

import roundup

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUNDUP = os.path.join(SKILL, "roundup.py")


class _IsInstance:
    """Argument matcher: equals any instance of ``cls``.

    Used in tripwire ``assert_call(raised=...)`` to match the exception
    instance recorded for a ``.raises()`` side effect without pinning the
    exact object identity.
    """

    def __init__(self, cls):
        self._cls = cls

    def __eq__(self, other):
        return isinstance(other, self._cls)

    def __repr__(self):
        return f"_IsInstance({self._cls.__name__})"

TARGET = "/Users/eek/Development/worktrees/ODY/styleseat"
TARGET2 = "/Users/eek/Development/worktrees/ODY/mobileweb"
WS_ROOT = "/Users/eek/Development/worktrees/ODY"


def _age(path, seconds=3600):
    """Backdate a path's mtime so the §8.8 recent-mtime TOCTOU signal does NOT fire.

    Simulates the real plan -> AskUserQuestion -> reorient gap: by move time the
    session file is no longer "recently" written, so only a lock would flag running.
    """
    old = os.path.getmtime(path) - seconds
    os.utime(path, (old, old))


def _setup(tmp_path, uuid="u1", sidecar=False, body='{"cwd":"/x"}\n'):
    cfg = tmp_path / ".claude"
    old = cfg / "projects" / "-old"
    old.mkdir(parents=True, exist_ok=True)
    jsonl = old / (uuid + ".jsonl")
    jsonl.write_text(body)
    _age(str(jsonl))
    if sidecar:
        sc = old / uuid
        sc.mkdir()
        (sc / "marker.txt").write_text("sidecar\n")
    return str(cfg), str(old)


def _session(cfg, old, uuid="u1", target=TARGET, sidecar=None, running=False):
    return {
        "uuid": uuid,
        "config_dir": cfg,
        "jsonl_path": os.path.join(old, uuid + ".jsonl"),
        "sidecar_dir": sidecar,
        "resolved_worktree_dir": target,
        "workspace_root_dir": WS_ROOT,
        "resolve_confidence": "high",
        "appears_running": running,
    }


def _decision(cfg, uuid="u1", target="repo_subdir"):
    return {"uuid": uuid, "config_dir": cfg, "target": target}


def test_dry_run_no_mutation(tmp_path):
    cfg, old = _setup(tmp_path)
    s = _session(cfg, old)
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], os.path.exists)
    before = set(os.listdir(old))
    result = roundup.execute_reorient(plans, dry_run=True, update_history=False)
    after = set(os.listdir(old))
    assert before == after
    assert result["moved"] == []  # nothing actually moved in dry-run


def test_live_move_jsonl_and_sidecar(tmp_path):
    cfg, old = _setup(tmp_path, sidecar=True)
    enc = roundup.encode_cwd_literal(TARGET)
    s = _session(cfg, old, sidecar=os.path.join(old, "u1"))
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], os.path.exists)
    result = roundup.execute_reorient(plans, dry_run=False, update_history=False)
    new_dir = os.path.join(cfg, "projects", enc)
    assert os.path.exists(os.path.join(new_dir, "u1.jsonl"))
    assert os.path.exists(os.path.join(new_dir, "u1", "marker.txt"))
    assert not os.path.exists(os.path.join(old, "u1.jsonl"))
    assert not os.path.exists(os.path.join(old, "u1"))
    assert len(result["moved"]) == 1


def test_collision_refusal(tmp_path):
    cfg, old = _setup(tmp_path)
    enc = roundup.encode_cwd_literal(TARGET)
    # Pre-create the destination jsonl so the dest collides.
    new_dir = os.path.join(cfg, "projects", enc)
    os.makedirs(new_dir)
    open(os.path.join(new_dir, "u1.jsonl"), "w").close()
    s = _session(cfg, old)
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], os.path.exists)
    result = roundup.execute_reorient(plans, dry_run=False, update_history=False)
    # Source still present; nothing moved.
    assert os.path.exists(os.path.join(old, "u1.jsonl"))
    assert result["moved"] == []
    assert any(c["uuid"] == "u1" for c in result["collisions"]) or any(
        s["uuid"] == "u1" and s["skip_reason"] == "collision" for s in result["skipped"]
    )


def test_rollback_on_injected_sidecar_failure(tmp_path):
    # GM-C1: assert CONTENT (exact bytes), not just path existence, after rollback.
    JSONL_BODY = '{"cwd":"/x"}\n{"type":"message"}\n'
    SIDECAR_MARKER = "sidecar-marker-content\n"
    cfg, old = _setup(tmp_path, sidecar=True, body=JSONL_BODY)
    # Overwrite the default sidecar marker with a known body.
    marker_path = os.path.join(old, "u1", "marker.txt")
    with open(marker_path, "w") as fh:
        fh.write(SIDECAR_MARKER)
    enc = roundup.encode_cwd_literal(TARGET)
    new_dir = os.path.join(cfg, "projects", enc)

    s = _session(cfg, old, sidecar=os.path.join(old, "u1"))
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], os.path.exists)

    # tripwire: mock the module-level shutil.move at its import site in roundup.
    # execute_reorient calls shutil.move in FIFO order:
    #   1) jsonl move  (succeeds -> real move)
    #   2) sidecar move (FAILS -> raises, triggers journal rollback)
    #   3) rollback reversal of the jsonl journal entry (succeeds -> real move)
    # Each registered side effect fires exactly once and is asserted after the
    # sandbox, satisfying tripwire's use + assert guarantees.
    real_move = shutil.move

    def real(src, dst):
        return real_move(src, dst)

    move_mock = tripwire.mock("roundup:shutil.move")
    move_mock.calls(real)  # 1) jsonl move
    move_mock.raises(OSError("injected sidecar move failure"))  # 2) sidecar move
    move_mock.calls(real)  # 3) rollback: jsonl moved back

    with tripwire:
        result = roundup.execute_reorient(plans, dry_run=False, update_history=False)

    # Assert the exact move sequence (FIFO order).
    move_mock.assert_call(args=(plans[0]["old_jsonl"], plans[0]["new_jsonl"]), kwargs={})
    move_mock.assert_call(
        args=(plans[0]["old_sidecar"], plans[0]["new_sidecar"]),
        kwargs={},
        raised=_IsInstance(OSError),
    )
    move_mock.assert_call(args=(plans[0]["new_jsonl"], plans[0]["old_jsonl"]), kwargs={})

    # jsonl restored to the old dir with EXACT original bytes.
    restored_jsonl = os.path.join(old, "u1.jsonl")
    assert os.path.exists(restored_jsonl)
    with open(restored_jsonl) as fh:
        assert fh.read() == JSONL_BODY

    # sidecar dir + marker restored with exact content.
    restored_marker = os.path.join(old, "u1", "marker.txt")
    assert os.path.isdir(os.path.join(old, "u1"))
    with open(restored_marker) as fh:
        assert fh.read() == SIDECAR_MARKER

    # Destination has NO u1.jsonl and NO u1/ dir.
    assert not os.path.exists(os.path.join(new_dir, "u1.jsonl"))
    assert not os.path.exists(os.path.join(new_dir, "u1"))

    # No partial success recorded; rolled_back carries the expected uuid+error shape.
    assert result["moved"] == []
    assert result["rolled_back"] == [
        {"uuid": "u1", "error": "injected sidecar move failure"}
    ]


def test_toctou_running_recheck_skip(tmp_path):
    cfg, old = _setup(tmp_path)
    s = _session(cfg, old)  # plan-time: not running
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], os.path.exists)
    # Now drop a lock so the live re-check flags it running.
    open(os.path.join(old, "u1.lock"), "w").close()
    result = roundup.execute_reorient(plans, dry_run=False, update_history=False)
    assert os.path.exists(os.path.join(old, "u1.jsonl"))  # not moved
    assert result["moved"] == []
    assert any(s["uuid"] == "u1" and s["skip_reason"] == "running" for s in result["skipped"])


def test_toctou_live_collision_recheck_skip(tmp_path):
    """GM-I1: dest appears AFTER plan time -> live _live_collision fires.

    Plan time uses path_exists=NEVER so the plan does NOT mark a collision; the dest
    u1.jsonl is then created before execute, and the executor's live re-check must
    refuse the move with the source intact.
    """
    SRC_BODY = '{"cwd":"/x"}\n{"keep":"me"}\n'
    cfg, old = _setup(tmp_path, body=SRC_BODY)
    enc = roundup.encode_cwd_literal(TARGET)
    new_dir = os.path.join(cfg, "projects", enc)
    s = _session(cfg, old)
    # NEVER at plan time -> plan has collision=False.
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], lambda p: False)
    assert plans[0]["collision"] is False

    # Now create the dest jsonl so the LIVE collision check fires at move time.
    os.makedirs(new_dir, exist_ok=True)
    with open(os.path.join(new_dir, "u1.jsonl"), "w") as fh:
        fh.write("pre-existing destination\n")

    result = roundup.execute_reorient(plans, dry_run=False, update_history=False)

    assert result["moved"] == []
    assert any(c["uuid"] == "u1" for c in result["collisions"])
    assert any(
        sk["uuid"] == "u1" and sk["skip_reason"] == "collision" for sk in result["skipped"]
    )
    # Source jsonl content survives intact.
    with open(os.path.join(old, "u1.jsonl")) as fh:
        assert fh.read() == SRC_BODY


def test_update_history_rewrites_and_backs_up(tmp_path):
    cfg, old = _setup(tmp_path)
    # history with one matching project line (literal cwd == old launch cwd) and one not.
    history = os.path.join(cfg, "history.jsonl")
    with open(history, "w") as fh:
        fh.write(json.dumps({"project": "/Users/eek/old-cwd", "sessionId": "u1"}) + "\n")
        fh.write(json.dumps({"project": "/Users/eek/unrelated", "sessionId": "zz"}) + "\n")
    s = _session(cfg, old)
    s["launch_cwd"] = "/Users/eek/old-cwd"
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], os.path.exists)
    result = roundup.execute_reorient(
        plans, dry_run=False, update_history=True, now_stamp="2026-05-29T00:00:00Z",
        sessions_by_uuid={"u1": s},
    )
    # Backup created with the injected timestamp.
    backup = history + ".backup.2026-05-29T00:00:00Z"
    assert os.path.exists(backup)
    # Matching line rewritten to the new literal cwd (TARGET); unrelated untouched.
    lines = [json.loads(line) for line in open(history) if line.strip()]
    by_sid = {r["sessionId"]: r for r in lines}
    assert by_sid["u1"]["project"] == TARGET
    assert by_sid["zz"]["project"] == "/Users/eek/unrelated"
    assert result["history_updated"] is True


def test_history_failure_leaves_moves_intact(tmp_path):
    cfg, old = _setup(tmp_path)
    enc = roundup.encode_cwd_literal(TARGET)
    history = os.path.join(cfg, "history.jsonl")
    with open(history, "w") as fh:
        fh.write(json.dumps({"project": "/Users/eek/old-cwd", "sessionId": "u1"}) + "\n")
    s = _session(cfg, old)
    s["launch_cwd"] = "/Users/eek/old-cwd"
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(cfg)], os.path.exists)

    # tripwire: force the history rewrite to blow up AFTER the file move has
    # happened. _rewrite_history fires exactly once (one config_dir with a
    # matching launch_cwd) and is asserted after the sandbox.
    rewrite_mock = tripwire.mock("roundup:_rewrite_history")
    rewrite_mock.raises(OSError("injected history failure"))

    with tripwire:
        result = roundup.execute_reorient(
            plans, dry_run=False, update_history=True, now_stamp="2026-05-29T00:00:00Z",
            sessions_by_uuid={"u1": s},
        )

    rewrite_mock.assert_call(
        args=(history, {"/Users/eek/old-cwd": TARGET}),
        kwargs={},
        raised=_IsInstance(OSError),
    )
    # File move still stands.
    assert os.path.exists(os.path.join(cfg, "projects", enc, "u1.jsonl"))
    assert len(result["moved"]) == 1
    assert result["history_updated"] is False
    # GM-I3: assert the EXACT warning string, not a substring membership test.
    expected = "history update failed (moves intact): injected history failure"
    assert result["warnings"] == [expected]


# ---------------------------------------------------------------------------
# C3 — `reorient --dry-run --json` emits PURE parseable JSON (no human prints).
# ---------------------------------------------------------------------------
def test_reorient_dry_run_json_is_pure_and_no_mutation(tmp_path):
    cfg, old = _setup(tmp_path)
    s = _session(cfg, old)
    # Build a plan-shaped doc the CLI can read (provides sessions_by_uuid).
    plan_doc = {"schema_version": 1, "sessions": [s]}
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_doc))
    decisions_file = tmp_path / "decisions.json"
    decisions_file.write_text(json.dumps([_decision(cfg)]))

    before = set(os.listdir(old))
    res = subprocess.run(
        [
            sys.executable,
            ROUNDUP,
            "reorient",
            "--decisions",
            str(decisions_file),
            "--plan",
            str(plan_file),
            "--dry-run",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    # stdout MUST parse as JSON (no human "DRY-RUN move:" lines leaking in).
    doc = json.loads(res.stdout)
    assert "DRY-RUN move" not in res.stdout
    assert isinstance(doc["dry_run_moves"], list)
    assert len(doc["dry_run_moves"]) == 1
    entry = doc["dry_run_moves"][0]
    assert entry["uuid"] == "u1"
    assert entry["target"] == "repo_subdir"
    assert entry["old"] == old
    enc = roundup.encode_cwd_literal(TARGET)
    assert entry["new"] == os.path.join(cfg, "projects", enc)
    assert entry["collision"] is False
    # Filesystem unchanged.
    assert set(os.listdir(old)) == before
    assert doc["moved"] == []


# ---------------------------------------------------------------------------
# GM-M3 extras
# ---------------------------------------------------------------------------
def test_rewrite_history_preserves_malformed_lines_verbatim(tmp_path):
    """GM-M3: non-JSON / malformed / blank lines are preserved byte-for-byte; only
    matching `project` lines are rewritten."""
    history = tmp_path / "history.jsonl"
    malformed = "this is not json at all {oops\n"
    blank = "\n"
    nonmatch = json.dumps({"project": "/Users/eek/keep", "sessionId": "zz"}) + "\n"
    match = json.dumps({"project": "/Users/eek/old", "sessionId": "u1"}) + "\n"
    history.write_text(malformed + blank + nonmatch + match)

    rewritten = roundup._rewrite_history(str(history), {"/Users/eek/old": "/Users/eek/new"})
    assert rewritten == 1

    out = history.read_text()
    out_lines = out.splitlines(keepends=True)
    # Malformed and blank lines preserved EXACTLY and in order.
    assert out_lines[0] == malformed
    assert out_lines[1] == blank
    # Non-matching JSON line preserved verbatim (re-serialization not applied).
    assert out_lines[2] == nonmatch
    # Matching line rewritten to the new project value.
    rewritten_rec = json.loads(out_lines[3])
    assert rewritten_rec["project"] == "/Users/eek/new"
    assert rewritten_rec["sessionId"] == "u1"


def test_rewrite_history_preserves_non_ascii(tmp_path):
    """MEDIUM Fix 2: rewritten records keep non-ASCII chars unescaped (ensure_ascii=False)."""
    history = tmp_path / "history.jsonl"
    match = json.dumps({"project": "/Users/eek/old", "summary": "café déjà"}) + "\n"
    history.write_text(match)

    rewritten = roundup._rewrite_history(str(history), {"/Users/eek/old": "/Users/eek/new"})
    assert rewritten == 1

    out = history.read_text(encoding="utf-8")
    # Non-ASCII chars are written literally, not as \uXXXX escapes.
    assert "café déjà" in out
    assert "\\u" not in out
    rec = json.loads(out)
    assert rec["project"] == "/Users/eek/new"
    assert rec["summary"] == "café déjà"


def test_already_correct_noop_skipped_no_move(tmp_path):
    """Second line of defense: a decision whose old==new is skipped with
    'already_correct' and performs NO filesystem move (a no-op move must never be
    physically executed). The session's jsonl already lives in the dir that encodes
    its reorient target, so build_reorient_plan marks it already_correct and the
    LIVE executor must leave it untouched."""
    cfg = tmp_path / ".claude"
    enc = roundup.encode_cwd_literal(TARGET)
    # Session ALREADY stored under the encoded target dir (old == new).
    correct_dir = cfg / "projects" / enc
    correct_dir.mkdir(parents=True)
    jsonl = correct_dir / "u1.jsonl"
    JSONL_BODY = '{"cwd":"/x"}\n{"keep":"me"}\n'
    jsonl.write_text(JSONL_BODY)
    _age(str(jsonl))

    s = _session(str(cfg), str(correct_dir))  # resolved_worktree_dir == TARGET
    plans = roundup.build_reorient_plan({"u1": s}, [_decision(str(cfg))], os.path.exists)
    # Plan stage already detects the no-op.
    assert plans[0]["skipped"] is True
    assert plans[0]["skip_reason"] == "already_correct"
    assert plans[0]["new_jsonl"] is None  # no destination computed for a no-op

    before = set(os.listdir(str(correct_dir)))
    result = roundup.execute_reorient(plans, dry_run=False, update_history=False)

    # LIVE executor performed no move: nothing in moved, skip carried through, the
    # file is byte-for-byte intact in place.
    assert result["moved"] == []
    assert any(
        sk["uuid"] == "u1" and sk["skip_reason"] == "already_correct"
        for sk in result["skipped"]
    )
    assert set(os.listdir(str(correct_dir))) == before
    assert jsonl.read_text() == JSONL_BODY


def test_history_skipped_when_rolled_back_nonempty(tmp_path):
    """GM-M3: history rewrite is SKIPPED when rolled_back is non-empty, even though
    a prior item moved successfully."""
    cfg, old = _setup(tmp_path, uuid="u1")
    # Second item has a sidecar whose move we force to fail -> rollback + break.
    old2 = os.path.join(cfg, "projects", "-old2")
    os.makedirs(old2, exist_ok=True)
    jsonl2 = os.path.join(old2, "u2.jsonl")
    with open(jsonl2, "w") as fh:
        fh.write('{"cwd":"/y"}\n')
    _age(jsonl2)
    sc2 = os.path.join(old2, "u2")
    os.mkdir(sc2)
    with open(os.path.join(sc2, "m.txt"), "w") as fh:
        fh.write("sc2\n")

    s1 = _session(cfg, old, uuid="u1", target=TARGET)
    s1["launch_cwd"] = "/Users/eek/old-cwd"
    s2 = _session(cfg, old2, uuid="u2", target=TARGET2, sidecar=sc2)
    s2["launch_cwd"] = "/Users/eek/old-cwd2"

    history = os.path.join(cfg, "history.jsonl")
    with open(history, "w") as fh:
        fh.write(json.dumps({"project": "/Users/eek/old-cwd", "sessionId": "u1"}) + "\n")
    original_history = open(history).read()

    sbu = {"u1": s1, "u2": s2}
    plans = roundup.build_reorient_plan(
        sbu,
        [_decision(cfg, "u1", "repo_subdir"), _decision(cfg, "u2", "repo_subdir")],
        os.path.exists,
    )

    # tripwire: mock module-level shutil.move at its import site in roundup.
    # FIFO move sequence inside execute_reorient:
    #   1) u1.jsonl move  (ok)
    #   2) u2.jsonl move  (ok)
    #   3) u2 sidecar move (FAILS -> raises, triggers u2 rollback + batch break)
    #   4) u2 rollback: u2.jsonl moved back (ok)
    # History is then SKIPPED (rolled_back non-empty), so no shutil.move /
    # copy2 / _rewrite_history fires afterward.
    real_move = shutil.move

    def real(src, dst):
        return real_move(src, dst)

    move_mock = tripwire.mock("roundup:shutil.move")
    move_mock.calls(real)  # 1) u1.jsonl
    move_mock.calls(real)  # 2) u2.jsonl
    move_mock.raises(OSError("injected u2 sidecar failure"))  # 3) u2 sidecar
    move_mock.calls(real)  # 4) rollback: u2.jsonl back

    p1 = plans[0]
    p2 = plans[1]

    with tripwire:
        result = roundup.execute_reorient(
            plans,
            dry_run=False,
            update_history=True,
            now_stamp="2026-05-29T00:00:00Z",
            sessions_by_uuid=sbu,
        )

    move_mock.assert_call(args=(p1["old_jsonl"], p1["new_jsonl"]), kwargs={})
    move_mock.assert_call(args=(p2["old_jsonl"], p2["new_jsonl"]), kwargs={})
    move_mock.assert_call(
        args=(p2["old_sidecar"], p2["new_sidecar"]),
        kwargs={},
        raised=_IsInstance(OSError),
    )
    move_mock.assert_call(args=(p2["new_jsonl"], p2["old_jsonl"]), kwargs={})

    # u1 moved; u2 rolled back; batch stopped.
    assert [m["uuid"] for m in result["moved"]] == ["u1"]
    assert [r["uuid"] for r in result["rolled_back"]] == ["u2"]
    # History NOT touched: no backup, file unchanged, history_updated False.
    assert result["history_updated"] is False
    assert open(history).read() == original_history
    assert not os.path.exists(history + ".backup.2026-05-29T00:00:00Z")
