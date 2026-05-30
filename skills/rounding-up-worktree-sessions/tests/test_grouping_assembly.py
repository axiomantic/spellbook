import roundup


def _s(uuid, title, ws=None, wt=None, conf="high", recency="2026-05-28T00:00:00Z"):
    return {
        "uuid": uuid,
        "title": title,
        "resolved_workspace": ws,
        "resolved_worktree_dir": wt,
        "workspace_root_dir": ("/wt/" + ws) if ws else None,
        "resolve_confidence": conf,
        "resolve_signal": "git_branch" if conf == "high" else "unresolved",
        "encoded_cwd_current": "-X-" + uuid,
        "launch_cwd": "/launch/" + uuid,
        "open_dir": wt or ("/launch/" + uuid),
        "recency_ts": recency,
    }


def test_groups_by_title_prefix():
    sessions = [_s("u1", "lfq-lychee"), _s("u2", "lfq-guava")]
    groups, _ = roundup.group_sessions(sessions)
    assert len(groups) == 1
    g = groups[0]
    assert g["group_key"] == "lfq"
    assert g["session_count"] == 2


def test_sessions_ordered_by_recency_desc():
    sessions = [
        _s("old", "lfq-a", recency="2026-05-20T00:00:00Z"),
        _s("new", "lfq-b", recency="2026-05-28T00:00:00Z"),
    ]
    groups, _ = roundup.group_sessions(sessions)
    assert groups[0]["sessions"] == ["new", "old"]


def test_phase_b_group_plurality_resolves_unresolved():
    resolved = _s("r1", "lfq-a", ws="LFQ", wt="/wt/LFQ/lfq", conf="high")
    pending = _s("p1", "lfq-b", conf="unresolved")
    groups, updated = roundup.group_sessions([resolved, pending])
    p = [s for s in updated if s["uuid"] == "p1"][0]
    assert p["resolve_confidence"] == "low"
    assert p["resolve_signal"] == "group_plurality"
    assert p["resolved_workspace"] == "LFQ"


def test_unresolvable_stays_unresolved():
    pending = _s("p1", "lonely", conf="unresolved")
    groups, updated = roundup.group_sessions([pending])
    p = updated[0]
    assert p["resolve_confidence"] == "unresolved"
