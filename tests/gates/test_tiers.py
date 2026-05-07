"""Tests for spellbook.gates.tiers (WI-6b).

Covers four sub-deliverables:

1. ``TierRecord`` dataclass + TOML loader (schema validation, unknown-key
   rejection, tier enum check).
2. ``classify_tool_call`` — maps a (tool, tool_input) pair to a Tier value
   (or T_UNCLASSIFIED) plus a hook verdict (allow/ask/deny).
3. ``tier_record_to_deny_pattern`` — projects a TierRecord to the 0-or-more
   ``settings.json`` deny strings per design §6.4.
4. ``derive_l2_deny_list`` — end-to-end: read tiers.toml, project T3 records,
   return the flat list installer feeds into ``install_permissions(deny=...)``.

The shipped ``spellbook/gates/tiers.toml`` is loaded by some tests as the
real seed file; targeted tests with synthetic TOML cover edge cases without
mutating the seed.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _shipped_tiers_toml() -> Path:
    """Return the path to the seeded tiers.toml shipped with spellbook."""
    return (
        Path(__file__).resolve().parents[2]
        / "spellbook"
        / "gates"
        / "tiers.toml"
    )


def _write_tiers(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "tiers.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Sub-phase (a): schema + loader + classifier
# ---------------------------------------------------------------------------


def test_shipped_tiers_toml_loads_and_validates():
    """The shipped tiers.toml must parse and contain at least one record per tier."""
    from spellbook.gates.tiers import load_tiers

    records = load_tiers(_shipped_tiers_toml())
    assert len(records) >= 1, "shipped tiers.toml must seed at least one record"
    tiers_seen = {r.tier for r in records}
    # Plan §6 requires T0/T2/T3 minimum. T1 is recommended but not required.
    assert {"T0", "T2", "T3"}.issubset(tiers_seen)


def test_load_tiers_rejects_unknown_keys(tmp_path):
    from spellbook.gates.tiers import load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git status"
        tier = "T0"
        description = "git status"
        bogus_key = "uh oh"
        """,
    )
    with pytest.raises(ValueError, match="unknown keys"):
        load_tiers(p)


def test_load_tiers_rejects_invalid_tier_value(tmp_path):
    from spellbook.gates.tiers import load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git status"
        tier = "T9"
        description = "??"
        """,
    )
    with pytest.raises(ValueError, match="tier must be one of"):
        load_tiers(p)


def test_load_tiers_rejects_missing_required_field(tmp_path):
    from spellbook.gates.tiers import load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        tier = "T0"
        description = "missing pattern"
        """,
    )
    with pytest.raises(ValueError, match="missing required"):
        load_tiers(p)


@pytest.mark.parametrize(
    "tier,expected_verdict",
    [
        ("T0", "allow"),
        ("T1", "allow"),
        ("T2", "ask"),
        ("T3", "deny"),
    ],
)
def test_tier_to_verdict_mapping(tier, expected_verdict):
    from spellbook.gates.tiers import tier_to_verdict

    assert tier_to_verdict(tier) == expected_verdict


def test_unclassified_tier_to_verdict_is_ask():
    from spellbook.gates.tiers import tier_to_verdict, T_UNCLASSIFIED

    assert tier_to_verdict(T_UNCLASSIFIED) == "ask"


def test_classify_tool_call_bash_literal_match(tmp_path):
    from spellbook.gates.tiers import classify_tool_call, load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"
        """,
    )
    records = load_tiers(p)
    tier = classify_tool_call("Bash", {"command": "git push --force origin main"}, records)
    assert tier == "T3"


def test_classify_tool_call_bash_no_match_returns_unclassified(tmp_path):
    from spellbook.gates.tiers import classify_tool_call, load_tiers, T_UNCLASSIFIED

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"
        """,
    )
    records = load_tiers(p)
    tier = classify_tool_call("Bash", {"command": "ls -la"}, records)
    assert tier == T_UNCLASSIFIED


def test_classify_tool_call_mcp_exact_match(tmp_path):
    from spellbook.gates.tiers import classify_tool_call, load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "mcp__atlassian__transition_issue"
        pattern = "*"
        tier = "T2"
        description = "JIRA transition"
        """,
    )
    records = load_tiers(p)
    tier = classify_tool_call(
        "mcp__atlassian__transition_issue",
        {"issueIdOrKey": "FOO-1", "transition": "Done"},
        records,
    )
    assert tier == "T2"


def test_classify_tool_call_mcp_wildcard_match(tmp_path):
    from spellbook.gates.tiers import classify_tool_call, load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "mcp__atlassian__delete_*"
        pattern = "*"
        tier = "T3"
        description = "atlassian delete"
        """,
    )
    records = load_tiers(p)
    tier = classify_tool_call(
        "mcp__atlassian__delete_issue", {"issueKey": "FOO-1"}, records
    )
    assert tier == "T3"


def test_classify_tool_call_capability_tool_match(tmp_path):
    from spellbook.gates.tiers import classify_tool_call, load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Edit"
        pattern = "*"
        tier = "T0"
        description = "Edit anywhere"
        """,
    )
    records = load_tiers(p)
    tier = classify_tool_call(
        "Edit",
        {"file_path": "/tmp/foo.py", "old_string": "a", "new_string": "b"},
        records,
    )
    assert tier == "T0"


def test_classify_tool_call_t3_outranks_t0_when_both_match(tmp_path):
    """Highest-tier match wins so a deny rule cannot be diluted by a later allow."""
    from spellbook.gates.tiers import classify_tool_call, load_tiers

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git"
        tier = "T0"
        description = "any git"

        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"
        """,
    )
    records = load_tiers(p)
    tier = classify_tool_call(
        "Bash", {"command": "git push --force origin master"}, records
    )
    assert tier == "T3"


# ---------------------------------------------------------------------------
# Sub-phase (b): projection function (design §6.4 cases 1-7)
# ---------------------------------------------------------------------------


def _record(**kwargs):
    """Build a TierRecord with sane defaults."""
    from spellbook.gates.tiers import TierRecord

    base = {
        "tool": "Bash",
        "pattern": "x",
        "tier": "T3",
        "description": "test record",
        "mcp_qualifier": None,
    }
    base.update(kwargs)
    return TierRecord(**base)


def test_projection_case_1_bash_literal_pattern():
    """Case 1: Bash + literal pattern → ``["Bash(<pattern>:*)"]``."""
    from spellbook.gates.tiers import tier_record_to_deny_pattern

    rec = _record(tool="Bash", pattern="git push --force", tier="T3")
    assert tier_record_to_deny_pattern(rec) == ["Bash(git push --force:*)"]


def test_projection_case_2_bash_alternation_expands(monkeypatch):
    """Case 2: Bash + ``(a|b)`` → expand to multiple literal prefixes."""
    from spellbook.gates.tiers import tier_record_to_deny_pattern

    rec = _record(
        tool="Bash", pattern="git push --force origin (master|main)", tier="T3"
    )
    out = tier_record_to_deny_pattern(rec)
    assert "Bash(git push --force origin master:*)" in out
    assert "Bash(git push --force origin main:*)" in out
    assert len(out) == 2


def test_projection_case_3_bash_regex_class_warns_and_skips(caplog):
    """Case 3: Bash + regex-class ``[^a-z]+`` → empty list with warning."""
    import logging

    from spellbook.gates.tiers import tier_record_to_deny_pattern

    rec = _record(tool="Bash", pattern="rm [^a-z]+", tier="T3")
    with caplog.at_level(logging.WARNING):
        out = tier_record_to_deny_pattern(rec)
    assert out == []
    assert any("not projectable" in m.lower() or "skip" in m.lower() for m in caplog.messages)


def test_projection_case_4_mcp_exact_tool():
    """Case 4: MCP tool name (``mcp__server__tool``) → ``[<tool name>]``."""
    from spellbook.gates.tiers import tier_record_to_deny_pattern

    rec = _record(
        tool="mcp__atlassian__delete_issue",
        pattern="*",
        tier="T3",
    )
    assert tier_record_to_deny_pattern(rec) == ["mcp__atlassian__delete_issue"]


def test_projection_case_5_mcp_wildcard():
    """Case 5: MCP wildcard (``mcp__server__delete_*``) → ``[<wildcard>]``."""
    from spellbook.gates.tiers import tier_record_to_deny_pattern

    rec = _record(
        tool="mcp__atlassian__delete_*",
        pattern="*",
        tier="T3",
    )
    assert tier_record_to_deny_pattern(rec) == ["mcp__atlassian__delete_*"]


@pytest.mark.parametrize("tool", ["Edit", "Write", "WebFetch", "Read"])
def test_projection_case_6_capability_tool(tool):
    """Case 6: Capability tool → ``[<tool name>]``."""
    from spellbook.gates.tiers import tier_record_to_deny_pattern

    rec = _record(tool=tool, pattern="*", tier="T3")
    assert tier_record_to_deny_pattern(rec) == [tool]


def test_projection_case_7_unknown_tool_warns_and_skips(caplog):
    """Case 7: Unknown tool → empty list + warn."""
    import logging

    from spellbook.gates.tiers import tier_record_to_deny_pattern

    rec = _record(tool="WeirdTool", pattern="*", tier="T3")
    with caplog.at_level(logging.WARNING):
        out = tier_record_to_deny_pattern(rec)
    assert out == []
    assert any("unknown tool" in m.lower() or "weirdtool" in m.lower() for m in caplog.messages)


# ---------------------------------------------------------------------------
# derive_l2_deny_list — end-to-end projection over the full toml
# ---------------------------------------------------------------------------


def test_derive_l2_deny_list_only_t3_records(tmp_path):
    from spellbook.gates.tiers import derive_l2_deny_list

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git status"
        tier = "T0"
        description = "ok"

        [[tiers]]
        tool = "Bash"
        pattern = "git push"
        tier = "T2"
        description = "ask"

        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"

        [[tiers]]
        tool = "mcp__github__delete_*"
        pattern = "*"
        tier = "T3"
        description = "github delete"
        """,
    )
    deny = derive_l2_deny_list(p)
    assert "Bash(git push --force:*)" in deny
    assert "mcp__github__delete_*" in deny
    # T0 / T2 must NOT contribute to the deny list
    assert not any("git status" in d for d in deny)
    assert "Bash(git push:*)" not in deny


def test_derive_l2_deny_list_handles_missing_file(tmp_path):
    from spellbook.gates.tiers import derive_l2_deny_list

    out = derive_l2_deny_list(tmp_path / "nope.toml")
    # Missing file should not crash the installer; return [].
    assert out == []


# ---------------------------------------------------------------------------
# Cycle-6 hardening (F5): unprojectable Bash regex patterns are dropped at
# load time with a warning. A regex-only pattern would silently fail BOTH
# at hook-time classification AND at L2 deny derivation; the loader must
# surface the misconfiguration loudly and skip the record entirely.
# ---------------------------------------------------------------------------


def test_load_tiers_drops_unprojectable_bash_regex_pattern_with_warning(
    tmp_path, caplog
):
    """A T3 record with an unsupported regex (e.g. ``rm [^a-z]+``) must be
    dropped at parse time with a warning. The classifier must NOT match
    commands using that pattern, so a deny-by-classifier path silently
    powered by a half-broken regex pattern can't sneak through."""
    import logging

    from spellbook.gates.tiers import classify_tool_call, load_tiers, T_UNCLASSIFIED

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "rm [^a-z]+"
        tier = "T3"
        description = "regex-only deny — must be dropped"

        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"
        """,
    )

    with caplog.at_level(logging.WARNING):
        records = load_tiers(p)

    # The unprojectable record must be dropped — only the literal record
    # survives.
    patterns = [r.pattern for r in records]
    assert patterns == ["git push --force"]

    # Loader must have warned about the dropped record.
    assert any(
        "rm [^a-z]+" in m and ("regex" in m.lower() or "not projectable" in m.lower() or "drop" in m.lower())
        for m in caplog.messages
    ), f"expected drop-with-warning message, got {caplog.messages!r}"

    # Crucially, the classifier must NOT match a command using the dropped
    # pattern — silent matching would defeat the whole point of dropping it.
    tier = classify_tool_call("Bash", {"command": "rm FOO"}, records)
    assert tier == T_UNCLASSIFIED


def test_derive_l2_deny_list_skips_unprojectable_records(tmp_path, caplog):
    """``derive_l2_deny_list`` must not surface deny strings derived from a
    record that was already dropped at load time."""
    import logging

    from spellbook.gates.tiers import derive_l2_deny_list

    p = _write_tiers(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "rm [^a-z]+"
        tier = "T3"
        description = "regex-only deny"

        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"
        """,
    )

    with caplog.at_level(logging.WARNING):
        deny = derive_l2_deny_list(p)

    assert deny == ["Bash(git push --force:*)"]
