"""The installer's registered hook phases must agree with what ``dispatch()`` handles.

This repository has drifted three times in the same direction. ``UserPromptSubmit``
was handled, tested and documented as the always-on agent2agent notify floor, but
never registered, so it never fired for anyone. ``Stop`` was handled and tested
before it was registered. ``PreCompact`` was the inverse: registered, described in
the module docstring, and handled nowhere; it is now unregistered.

Every one of those is silent. A phase that is registered but unhandled produces no
output, which is exactly what a correctly-working phase with nothing to say also
produces. These tests turn that silence into a red test.

The two sets must agree EXACTLY. There is no allowlist, deliberately: an allowlist
is where the next drift would hide. A phase that needs an exemption to keep these
tests green is a phase that is drifting.

The handled set is derived from the SOURCE of ``dispatch()`` by AST, not from a
literal list typed out here. A hand-maintained second list would be the same defect
one level up: it would need updating by the same person who forgot to update the
registration. AST introspection was chosen over refactoring ``dispatch()`` into a
handler table because the branches do not share a return contract -- ``PreToolUse``
and ``PostToolUse`` return lists of strings, ``Stop`` and ``SessionStart`` return
serialized JSON decisions -- so a data-driven table would have to encode that
difference and would change behavior in a file whose failure mode is "takes out the
turn". Reading the branch conditions changes nothing at runtime.
"""

import ast
import json
from pathlib import Path

import pytest

from installer.components.hooks import (
    HOOK_DEFINITIONS,
    STOP_HOOK_BLOCK_CAP_KEY,
    STOP_HOOK_BLOCK_CAP_VALUE,
    _HOOK_PHASES,
    _RETIRED_HOOK_PHASES,
    install_hooks,
    uninstall_hooks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SOURCE = REPO_ROOT / "hooks" / "spellbook_hook.py"

_NEW_PHASES = ("Stop", "UserPromptSubmit")
_UNIFIED_COMMAND = (
    "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python "
    "$SPELLBOOK_DIR/hooks/spellbook_hook.py"
)


def _dispatched_event_names() -> frozenset[str]:
    """Event names ``dispatch()`` branches on, read from its own source."""
    tree = ast.parse(HOOK_SOURCE.read_text(encoding="utf-8"))
    dispatch = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch"
    )
    names: set[str] = set()
    for node in ast.walk(dispatch):
        if not isinstance(node, ast.Compare):
            continue
        if not (isinstance(node.left, ast.Name) and node.left.id == "event_name"):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, ast.Eq) and isinstance(comparator, ast.Constant):
                if isinstance(comparator.value, str):
                    names.add(comparator.value)
            elif isinstance(op, ast.In) and isinstance(
                comparator, (ast.Tuple, ast.List, ast.Set)
            ):
                for elt in comparator.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        names.add(elt.value)
    return frozenset(names)


def test_ast_extraction_finds_the_known_branches():
    """Guard the extractor itself: an empty result would make every check vacuous."""
    handled = _dispatched_event_names()
    assert {"PreToolUse", "PostToolUse", "SessionStart"} <= handled


def test_every_handled_phase_is_registered():
    missing = _dispatched_event_names() - set(HOOK_DEFINITIONS)
    assert not missing, (
        f"dispatch() handles {sorted(missing)} but installer/components/hooks.py "
        "never registers those phases, so the handlers can never fire. "
        "Add them to HOOK_DEFINITIONS."
    )


def test_every_registered_phase_is_handled():
    unhandled = set(HOOK_DEFINITIONS) - _dispatched_event_names()
    assert not unhandled, (
        f"installer/components/hooks.py registers {sorted(unhandled)} but "
        "dispatch() has no branch for them, so the events spawn a subprocess "
        "and are silently discarded. Either handle the phase or unregister it "
        "(see _RETIRED_HOOK_PHASES). Do not add an exemption here."
    )


def test_registered_and_handled_sets_are_identical():
    """The whole point, stated once as a single equality."""
    assert set(HOOK_DEFINITIONS) == set(_dispatched_event_names())


def test_precompact_is_not_registered():
    """PreCompact was registered for its whole life and handled never."""
    assert "PreCompact" not in HOOK_DEFINITIONS
    assert "PreCompact" not in _dispatched_event_names()
    assert "PreCompact" in _RETIRED_HOOK_PHASES


@pytest.mark.parametrize("phase", _NEW_PHASES)
def test_new_phase_is_in_definitions_and_phase_list(phase):
    assert phase in HOOK_DEFINITIONS
    assert phase in _HOOK_PHASES


@pytest.mark.parametrize("phase", _NEW_PHASES)
def test_new_phase_blocks_and_omits_matcher(phase):
    entries = HOOK_DEFINITIONS[phase]
    assert len(entries) == 1
    entry = entries[0]
    assert "matcher" not in entry, "catch-all hooks omit matcher entirely"
    assert len(entry["hooks"]) == 1
    hook = entry["hooks"][0]
    assert hook["type"] == "command"
    assert hook["command"] == _UNIFIED_COMMAND
    assert "async" not in hook, f"{phase} returns a decision and must block"
    assert 0 < hook["timeout"] <= 10


def test_install_renders_new_phases_into_settings(tmp_path):
    """Verify the produced artifact, not install_hooks' return value."""
    settings_path = tmp_path / "settings.json"
    result = install_hooks(settings_path)
    assert result.success

    rendered = json.loads(settings_path.read_text(encoding="utf-8"))
    for phase in _NEW_PHASES:
        entries = rendered["hooks"][phase]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        assert _UNIFIED_COMMAND in commands, f"{phase} missing from rendered settings"


def test_install_preserves_a_foreign_hook_in_a_new_phase(tmp_path):
    settings_path = tmp_path / "settings.json"
    foreign = {"type": "command", "command": "/usr/local/bin/my-own-stop-hook"}
    settings_path.write_text(
        json.dumps({"hooks": {"Stop": [{"hooks": [foreign]}]}}), encoding="utf-8"
    )

    assert install_hooks(settings_path).success

    rendered = json.loads(settings_path.read_text(encoding="utf-8"))
    commands = [h["command"] for e in rendered["hooks"]["Stop"] for h in e["hooks"]]
    assert foreign["command"] in commands
    assert _UNIFIED_COMMAND in commands


def test_uninstall_removes_new_phases(tmp_path):
    settings_path = tmp_path / "settings.json"
    assert install_hooks(settings_path).success

    result = uninstall_hooks(settings_path)
    assert result.success

    rendered = json.loads(settings_path.read_text(encoding="utf-8"))
    for phase in _NEW_PHASES:
        entries = rendered["hooks"].get(phase, [])
        commands = [h["command"] for e in entries for h in e["hooks"]]
        assert _UNIFIED_COMMAND not in commands, f"{phase} survived uninstall"


# --- Retired phases: existing installs must be migrated, not stranded. -------

def _precompact_settings(extra_hooks=()):
    """A settings file as an already-installed operator's would look."""
    entry = {"hooks": [{"type": "command", "command": _UNIFIED_COMMAND, "timeout": 5}]}
    entry["hooks"].extend(extra_hooks)
    return {
        "existingUserKey": "preserved",
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"type": "command", "command": _UNIFIED_COMMAND}]}
            ],
            "PreCompact": [entry],
        },
    }


def test_install_removes_a_real_precompact_entry(tmp_path):
    """The load-bearing migration check: a fixture that ACTUALLY has the entry."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(_precompact_settings()), encoding="utf-8")

    before = json.loads(settings_path.read_text(encoding="utf-8"))
    assert before["hooks"]["PreCompact"][0]["hooks"][0]["command"] == _UNIFIED_COMMAND

    assert install_hooks(settings_path).success

    after = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "PreCompact" not in after["hooks"]
    assert after["existingUserKey"] == "preserved"
    assert "PreToolUse" in after["hooks"]


def test_install_preserves_a_foreign_precompact_hook(tmp_path):
    """An operator's own PreCompact hook is not spellbook's to remove."""
    foreign = {"type": "command", "command": "/usr/local/bin/my-own-precompact"}
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(_precompact_settings(extra_hooks=[foreign])), encoding="utf-8"
    )

    assert install_hooks(settings_path).success

    after = json.loads(settings_path.read_text(encoding="utf-8"))
    commands = [h["command"] for e in after["hooks"]["PreCompact"] for h in e["hooks"]]
    assert commands == [foreign["command"]]


def test_install_is_idempotent_on_a_machine_that_never_had_precompact(tmp_path):
    settings_path = tmp_path / "settings.json"
    assert install_hooks(settings_path).success
    first = settings_path.read_text(encoding="utf-8")
    assert "PreCompact" not in json.loads(first)["hooks"]

    assert install_hooks(settings_path).success
    assert settings_path.read_text(encoding="utf-8") == first


def test_uninstall_removes_a_retired_phase_entry(tmp_path):
    """uninstall iterates _HOOK_PHASES, which no longer lists PreCompact."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(_precompact_settings()), encoding="utf-8")

    result = uninstall_hooks(settings_path)
    assert result.success

    after = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "PreCompact" not in after["hooks"]


def test_uninstall_finds_hooks_when_only_a_retired_phase_remains(tmp_path):
    """Without the retired phases in the discovery scan this would report
    'no spellbook hooks found' and leave the entry behind."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreCompact": [
                        {"hooks": [{"type": "command", "command": _UNIFIED_COMMAND}]}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    result = uninstall_hooks(settings_path)
    assert result.success
    assert result.action == "removed"

    after = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "PreCompact" not in after["hooks"]


# --- The harness block cap: the other half of the Stop hook. -----------------
#
# The Stop hook blocks repeatedly and bounds itself with a rolling-window
# valve. Claude Code's own CLAUDE_CODE_STOP_HOOK_BLOCK_CAP would otherwise cut
# that short after eight consecutive blocks. Every assertion below reads the
# RENDERED settings file back from a temp path; none reads an exit code, and
# none touches the operator's real ~/.claude/settings.json.


def _rendered(settings_path):
    return json.loads(settings_path.read_text(encoding="utf-8"))


def test_install_writes_the_disabled_block_cap_into_env(tmp_path):
    settings_path = tmp_path / "settings.json"
    assert install_hooks(settings_path).success

    env = _rendered(settings_path)["env"]
    assert env[STOP_HOOK_BLOCK_CAP_KEY] == STOP_HOOK_BLOCK_CAP_VALUE
    assert STOP_HOOK_BLOCK_CAP_VALUE == "0", "the documented disable value"


def test_install_preserves_foreign_env_entries(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"env": {"MY_OWN_VAR": "keep me"}}), encoding="utf-8"
    )
    assert install_hooks(settings_path).success

    env = _rendered(settings_path)["env"]
    assert env["MY_OWN_VAR"] == "keep me"
    assert env[STOP_HOOK_BLOCK_CAP_KEY] == STOP_HOOK_BLOCK_CAP_VALUE


def test_uninstall_removes_the_block_cap_entry(tmp_path):
    settings_path = tmp_path / "settings.json"
    assert install_hooks(settings_path).success
    assert STOP_HOOK_BLOCK_CAP_KEY in _rendered(settings_path)["env"]

    assert uninstall_hooks(settings_path).success

    rendered = _rendered(settings_path)
    assert STOP_HOOK_BLOCK_CAP_KEY not in rendered.get("env", {})
    assert "env" not in rendered, "an emptied env object leaves no residue"


def test_uninstall_leaves_foreign_env_entries_alone(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"env": {"MY_OWN_VAR": "keep me"}}), encoding="utf-8"
    )
    assert install_hooks(settings_path).success
    assert uninstall_hooks(settings_path).success

    env = _rendered(settings_path)["env"]
    assert env == {"MY_OWN_VAR": "keep me"}


def test_uninstall_does_not_revert_an_operator_chosen_cap(tmp_path):
    """A value spellbook did not write belongs to the operator."""
    settings_path = tmp_path / "settings.json"
    assert install_hooks(settings_path).success
    rendered = _rendered(settings_path)
    rendered["env"][STOP_HOOK_BLOCK_CAP_KEY] = "5"
    settings_path.write_text(json.dumps(rendered), encoding="utf-8")

    assert uninstall_hooks(settings_path).success

    assert _rendered(settings_path)["env"][STOP_HOOK_BLOCK_CAP_KEY] == "5"


def test_uninstall_clears_the_env_entry_when_no_hooks_remain(tmp_path):
    """A settings file holding only the env entry must not be reported unchanged."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"env": {STOP_HOOK_BLOCK_CAP_KEY: STOP_HOOK_BLOCK_CAP_VALUE}}),
        encoding="utf-8",
    )

    assert uninstall_hooks(settings_path).success

    assert STOP_HOOK_BLOCK_CAP_KEY not in _rendered(settings_path).get("env", {})


def test_install_is_idempotent_for_env(tmp_path):
    settings_path = tmp_path / "settings.json"
    assert install_hooks(settings_path).success
    first = _rendered(settings_path)["env"]
    assert install_hooks(settings_path).success
    assert _rendered(settings_path)["env"] == first
