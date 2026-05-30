import pytest
import roundup

DEFAULT = "/Users/eek/.claude"


def _s(uuid, cd_target, config_dir=DEFAULT):
    # C2: panes cd to launch_cd_target (the resume cd-target), not open_dir.
    return {"uuid": uuid, "launch_cd_target": cd_target, "config_dir": config_dir}


# ---------------------------------------------------------------------------
# Expected-script builders (GM-I2): render_applescript is deterministic, so the
# layout/escaping tests assert FULL-script equality, not bare substrings.
# ---------------------------------------------------------------------------
def _pane_cmd(uuid, cd_target, config_dir=DEFAULT):
    # C1: prefix ALWAYS present (ambient CLAUDE_CONFIG_DIR is ~/.claude-work).
    return (
        "cd %s && CLAUDE_CONFIG_DIR=%s claude --dangerously-skip-permissions --resume %s"
        % (cd_target, config_dir, uuid)
    )


def _emit_pane(lines, pane_var, cmd):
    escaped = cmd.replace("\\", "\\\\").replace('"', '\\"')
    lines.append('\tinput text "%s" to %s' % (escaped, pane_var))
    lines.append("\tdelay 0.3")
    lines.append('\tsend key "enter" to %s' % pane_var)
    lines.append("\tdelay 0.3")


def _expected_one(uuid, cd_target, config_dir=DEFAULT):
    lines = ['tell application "Ghostty"']
    lines.append("\tactivate")
    lines.append("\tset baseWindow to (new window)")
    lines.append("\tset pane1 to (focused terminal of selected tab of baseWindow)")
    _emit_pane(lines, "pane1", _pane_cmd(uuid, cd_target, config_dir))
    lines.append("end tell")
    return "\n".join(lines)


def _expected_two(specs):
    # specs = [(uuid, cd_target), (uuid, cd_target)]
    lines = ['tell application "Ghostty"']
    lines.append("\tactivate")
    lines.append("\tset baseWindow to (new window)")
    lines.append("\tset pane1 to (focused terminal of selected tab of baseWindow)")
    lines.append("\tset pane2 to (split pane1 direction right)")
    _emit_pane(lines, "pane1", _pane_cmd(*specs[0]))
    _emit_pane(lines, "pane2", _pane_cmd(*specs[1]))
    lines.append("end tell")
    return "\n".join(lines)


def _expected_three(specs):
    # §9.2 layout: pane1 base; split pane1 right -> pane2; split pane1 down -> pane3.
    lines = ['tell application "Ghostty"']
    lines.append("\tactivate")
    lines.append("\tset baseWindow to (new window)")
    lines.append("\tset pane1 to (focused terminal of selected tab of baseWindow)")
    lines.append("\tset pane2 to (split pane1 direction right)")
    lines.append("\tset pane3 to (split pane1 direction down)")
    _emit_pane(lines, "pane1", _pane_cmd(*specs[0]))
    _emit_pane(lines, "pane2", _pane_cmd(*specs[1]))
    _emit_pane(lines, "pane3", _pane_cmd(*specs[2]))
    lines.append("end tell")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# escaper
# ---------------------------------------------------------------------------
def test_escape_backslash_then_quote():
    assert roundup._escape_applescript('a"b\\c') == 'a\\"b\\\\c'


def test_escape_rejects_newline():
    with pytest.raises(Exception):
        roundup._escape_applescript("a\nb")


# ---------------------------------------------------------------------------
# build_pane_command (C1: prefix ALWAYS present; C2: cd to launch_cd_target)
# ---------------------------------------------------------------------------
def test_pane_command_default_gets_prefix():
    """C1: even a default-config-dir session emits the explicit prefix.

    Renamed from test_pane_command_default_no_prefix; the spike decision is
    unconditional (ambient CLAUDE_CONFIG_DIR is ~/.claude-work), so every pane must
    set the prefix to its own config_dir.
    """
    cmd = roundup.build_pane_command(_s("u1", "/wt/styleseat"), DEFAULT, False)
    assert cmd == (
        "cd /wt/styleseat && CLAUDE_CONFIG_DIR=/Users/eek/.claude "
        "claude --dangerously-skip-permissions --resume u1"
    )
    assert "CLAUDE_CONFIG_DIR=/Users/eek/.claude" in cmd


def test_pane_command_nondefault_gets_prefix():
    cmd = roundup.build_pane_command(
        _s("u1", "/wt/x", config_dir="/Users/eek/.claude-work"), DEFAULT, False
    )
    assert "CLAUDE_CONFIG_DIR=/Users/eek/.claude-work" in cmd


def test_pane_command_explicit_env_still_prefix():
    cmd = roundup.build_pane_command(_s("u1", "/wt/x"), DEFAULT, True)
    assert "CLAUDE_CONFIG_DIR=/Users/eek/.claude" in cmd


def test_pane_command_none_cd_target_returns_none():
    """I-launch-1: no usable cd-target -> None (caller skips the pane)."""
    cmd = roundup.build_pane_command({"uuid": "u1", "config_dir": DEFAULT}, DEFAULT, False)
    assert cmd is None


# ---------------------------------------------------------------------------
# render_applescript — FULL-script equality (GM-I2)
# ---------------------------------------------------------------------------
def test_render_single_session_window():
    group = {"group_key": "g", "sessions": ["u1"]}
    by_uuid = {"u1": _s("u1", "/wt/u1")}
    script = roundup.render_applescript([group], by_uuid, default_config_dir=DEFAULT)
    assert script == _expected_one("u1", "/wt/u1")


def test_render_two_session_layout():
    group = {"group_key": "g", "sessions": ["u1", "u2"]}
    by_uuid = {u: _s(u, "/wt/" + u) for u in ("u1", "u2")}
    script = roundup.render_applescript([group], by_uuid, default_config_dir=DEFAULT)
    assert script == _expected_two([("u1", "/wt/u1"), ("u2", "/wt/u2")])


def test_render_three_session_layout():
    group = {"group_key": "g", "sessions": ["u1", "u2", "u3"]}
    by_uuid = {u: _s(u, "/wt/" + u) for u in ("u1", "u2", "u3")}
    script = roundup.render_applescript([group], by_uuid, default_config_dir=DEFAULT)
    assert script == _expected_three(
        [("u1", "/wt/u1"), ("u2", "/wt/u2"), ("u3", "/wt/u3")]
    )


def test_render_skips_pane_with_no_cd_target_and_warns():
    """I-launch-1: a session with no cd-target is dropped before layout + warned."""
    group = {"group_key": "g", "sessions": ["u1", "u2"]}
    by_uuid = {
        "u1": _s("u1", "/wt/u1"),
        "u2": {"uuid": "u2", "config_dir": DEFAULT},  # no launch_cd_target
    }
    warnings = []
    script = roundup.render_applescript(
        [group], by_uuid, default_config_dir=DEFAULT, warnings=warnings
    )
    # Only u1 remains -> single-pane window (no split).
    assert script == _expected_one("u1", "/wt/u1")
    assert "cd None" not in script
    assert any("u2" in w for w in warnings)
