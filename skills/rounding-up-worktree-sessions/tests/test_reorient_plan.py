import os
import roundup


def _sess(uuid, jsonl_path, wt, ws_root, sidecar=None, running=False, conf="high"):
    return {
        "uuid": uuid,
        "config_dir": "/Users/eek/.claude",
        "jsonl_path": jsonl_path,
        "sidecar_dir": sidecar,
        "resolved_worktree_dir": wt,
        "workspace_root_dir": ws_root,
        "resolve_confidence": conf,
        "appears_running": running,
    }


def _by_uuid(*sessions):
    return {s["uuid"]: s for s in sessions}


def NEVER(p):
    return False


def test_repo_subdir_move_plan():
    s = _sess("u1", "/Users/eek/.claude/projects/-old/u1.jsonl",
              "/Users/eek/Development/worktrees/ODY/styleseat",
              "/Users/eek/Development/worktrees/ODY")
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"}], NEVER)
    p = plans[0]
    assert not p["skipped"]
    assert p["target_kind"] == "repo_subdir"
    assert p["new_project_dir"].endswith("-Users-eek-Development-worktrees-ODY-styleseat")
    assert p["new_jsonl"].endswith("/u1.jsonl")


def test_workspace_root_move_plan():
    s = _sess("u1", "/Users/eek/.claude/projects/-old/u1.jsonl",
              "/Users/eek/Development/worktrees/ODY/styleseat",
              "/Users/eek/Development/worktrees/ODY")
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "workspace_root"}], NEVER)
    assert plans[0]["new_project_dir"].endswith("-Users-eek-Development-worktrees-ODY")


def test_skip_decision():
    s = _sess("u1", "/p/u1.jsonl", "/wt", "/wt-root")
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "skip"}], NEVER)
    assert plans[0]["skipped"] and plans[0]["skip_reason"] == "user_skip"


def test_running_session_skipped():
    s = _sess("u1", "/Users/eek/.claude/projects/-old/u1.jsonl", "/wt", "/wt-root", running=True)
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"}], NEVER)
    assert plans[0]["skipped"] and plans[0]["skip_reason"] == "running"


def test_already_correct_skipped():
    # old project dir already equals the target encoding
    enc = roundup.encode_cwd_literal("/Users/eek/Development/worktrees/ODY/styleseat")
    old = os.path.join("/Users/eek/.claude/projects", enc, "u1.jsonl")
    s = _sess("u1", old, "/Users/eek/Development/worktrees/ODY/styleseat",
              "/Users/eek/Development/worktrees/ODY")
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"}], NEVER)
    assert plans[0]["skipped"] and plans[0]["skip_reason"] == "already_correct"


def test_already_correct_skipped_stripped_old_dir():
    # MEDIUM Fix 2: the session's CURRENT storage dir is the STRIPPED encoding of the
    # target (older Claude sessions), while new_project_dir is the leading-dash form
    # from encode_cwd_literal. The already-correct skip must normalize basenames
    # (lstrip('-')) so the SAME path under either encoding is recognized as correct
    # and skipped (no move). Without normalization this session is wrongly moved.
    target = "/Users/eek/Development/worktrees/ODY/styleseat"
    enc_stripped = roundup.encode_cwd_literal(target).lstrip("-")  # STRIPPED on disk
    old = os.path.join("/Users/eek/.claude/projects", enc_stripped, "u1.jsonl")
    s = _sess("u1", old, target, "/Users/eek/Development/worktrees/ODY")
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"}], NEVER)
    assert plans[0]["skipped"] and plans[0]["skip_reason"] == "already_correct"


def test_collision_flagged():
    s = _sess("u1", "/Users/eek/.claude/projects/-old/u1.jsonl", "/wt", "/wt-root")
    s["resolved_worktree_dir"] = "/Users/eek/Development/worktrees/ODY/styleseat"
    s["workspace_root_dir"] = "/Users/eek/Development/worktrees/ODY"
    def always(p):
        return True
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"}], always)
    assert plans[0]["collision"] and plans[0]["skipped"] and plans[0]["skip_reason"] == "collision"


def test_unresolved_skipped():
    s = _sess("u1", "/p/u1.jsonl", None, None, conf="unresolved")
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"}], NEVER)
    assert plans[0]["skipped"] and plans[0]["skip_reason"] == "unresolved"


def test_repo_subdir_none_target_dir_skipped_not_crash():
    # Finding 2: a repo_subdir decision for a session whose resolved_worktree_dir is
    # None (possible under Phase-B group-plurality resolution) must yield a skipped
    # MovePlan (reason no_repo_subdir), NOT a TypeError from encode_cwd_literal(None).
    # The session must be resolved (conf != unresolved) so it reaches the target
    # resolution branch.
    s = _sess("u1", "/Users/eek/.claude/projects/-old/u1.jsonl", None, "/wt-root", conf="high")
    plans = roundup.build_reorient_plan(_by_uuid(s),
        [{"uuid": "u1", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"}], NEVER)
    assert plans[0]["target_kind"] == "repo_subdir"
    assert plans[0]["skipped"] and plans[0]["skip_reason"] == "no_repo_subdir"
