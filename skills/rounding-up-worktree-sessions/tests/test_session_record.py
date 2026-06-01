import roundup

BASE = dict(
    uuid="u1",
    config_dir="/Users/eek/.claude",
    jsonl_path="/p/u1.jsonl",
    sidecar_dir=None,
    encoded_cwd_current="-Users-eek-x",
)


def _rec(cwd=None, branch=None, ts=None, title=None, title_field="customTitle"):
    r = {}
    if cwd is not None:
        r["cwd"] = cwd
    if branch is not None:
        r["gitBranch"] = branch
    if ts is not None:
        r["timestamp"] = ts
    if title is not None:
        r[title_field] = title
    return r


def test_first_and_last_cwd():
    recs = [_rec(cwd="/a"), _rec(cwd="/b"), _rec(cwd="/c")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["launch_cwd"] == "/a"
    assert out["last_cwd"] == "/c"


def test_dominant_branch_ignores_head():
    recs = [_rec(branch="feat"), _rec(branch="HEAD"), _rec(branch="feat")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["git_branch_dominant"] == "feat"


def test_dominant_branch_head_only_is_none():
    recs = [_rec(branch="HEAD"), _rec(branch="HEAD")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["git_branch_dominant"] is None


def test_dominant_branch_tie_breaks_last_seen():
    # alpha and beta both appear once; beta is last-seen -> beta wins.
    recs = [_rec(branch="alpha"), _rec(branch="beta")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["git_branch_dominant"] == "beta"


def test_title_prefers_custom_then_agent():
    recs = [_rec(title="my-title", title_field="customTitle")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["title"] == "my-title"
    assert out["title_source"] == "customTitle"


def test_title_precedence_spans_records():
    # An EARLY record carries a low-precedence aiTitle; a LATER record carries a
    # high-precedence customTitle. Precedence is across the whole session, so the
    # customTitle must win even though the aiTitle appears first.
    recs = [
        _rec(title="ai-generated", title_field="aiTitle"),
        _rec(title="user-custom", title_field="customTitle"),
    ]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["title"] == "user-custom"
    assert out["title_source"] == "customTitle"


def test_title_latest_value_within_field():
    # Multiple records carry the same (highest-precedence) field; the latest value wins.
    recs = [
        _rec(title="old-custom", title_field="customTitle"),
        _rec(title="new-custom", title_field="customTitle"),
    ]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["title"] == "new-custom"
    assert out["title_source"] == "customTitle"


def test_recency_takes_max():
    recs = [_rec(ts="2026-05-28T10:00:00Z")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T12:00:00Z", **BASE)
    assert out["recency_ts"] == "2026-05-28T12:00:00Z"

    recs2 = [_rec(ts="2026-05-28T14:00:00Z")]
    out2 = roundup.build_session_record(records=recs2, file_mtime_iso="2026-05-28T12:00:00Z", **BASE)
    assert out2["recency_ts"] == "2026-05-28T14:00:00Z"


def test_message_count():
    recs = [_rec(cwd="/a"), _rec(cwd="/b")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T00:00:00Z", **BASE)
    assert out["message_count"] == 2


def test_numeric_timestamp_epoch_seconds():
    # A NUMERIC epoch-seconds timestamp must be converted to an ISO string so the
    # downstream max()/recency computation does not raise TypeError (str vs number).
    # 1748433600 s -> 2025-05-28T12:00:00Z.
    recs = [_rec(ts=1748433600)]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2025-05-28T10:00:00Z", **BASE)
    assert out["last_internal_ts"] == "2025-05-28T12:00:00Z"
    # recency takes max of file_mtime and the converted internal ts (ISO lexicographic).
    assert out["recency_ts"] == "2025-05-28T12:00:00Z"


def test_numeric_timestamp_epoch_milliseconds():
    # A NUMERIC milliseconds timestamp (> 1e11) must be divided by 1000 before conversion.
    # 1748433600000 ms -> 1748433600 s -> 2025-05-28T12:00:00Z.
    recs = [_rec(ts=1748433600000)]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2025-05-28T10:00:00Z", **BASE)
    assert out["last_internal_ts"] == "2025-05-28T12:00:00Z"
    assert out["recency_ts"] == "2025-05-28T12:00:00Z"


def test_bool_timestamp_is_ignored():
    # Fix 1: bool is a subclass of int, so `isinstance(True, (int, float))` is True. A
    # boolean timestamp must NOT be treated as numeric epoch (1.0s -> 1970-01-01T00:00:01Z);
    # it falls through to "skip" and leaves last_internal_ts unset for that record.
    recs = [_rec(ts=True)]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2025-05-28T10:00:00Z", **BASE)
    assert out["last_internal_ts"] is None
    assert not str(out["last_internal_ts"] or "").startswith("1970")
    # recency falls back to file_mtime since no internal ts was accepted.
    assert out["recency_ts"] == "2025-05-28T10:00:00Z"


def test_bool_timestamp_ignored_real_numeric_still_wins():
    # A later real numeric timestamp must still convert even after a bool is skipped.
    recs = [_rec(ts=True), _rec(ts=1748433600)]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2025-05-28T10:00:00Z", **BASE)
    assert out["last_internal_ts"] == "2025-05-28T12:00:00Z"
    assert out["recency_ts"] == "2025-05-28T12:00:00Z"


def test_iso_string_timestamp_still_works():
    # Regression: a normal ISO-string timestamp is used as-is.
    recs = [_rec(ts="2026-05-28T14:00:00Z")]
    out = roundup.build_session_record(records=recs, file_mtime_iso="2026-05-28T12:00:00Z", **BASE)
    assert out["last_internal_ts"] == "2026-05-28T14:00:00Z"
    assert out["recency_ts"] == "2026-05-28T14:00:00Z"
