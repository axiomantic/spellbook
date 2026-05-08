"""Smoke tests for ``commands/a2a.md`` slash dispatcher.

The slash command is a behavioral spec aimed at the orchestrator, not
executable Python. Per the implementation plan §Task 6 (Step 6.3) there
are no unit tests of runtime behavior — manual e2e in T7 covers that.
These smoke tests check structural invariants that can break silently:

    * the file exists,
    * its YAML frontmatter parses,
    * the frontmatter ``description`` enumerates trigger phrases that
      preserve user muscle memory ('listen for messages') AND advertises
      the new verbs ('open inbox', 'close inbox'),
    * every required Phase heading (A through F) appears,
    * the ``## /a2a close`` section and ``## Error path`` section appear,
    * each helper subcommand the dispatch table promises has its own
      ``## /a2a <subcommand>`` section,
    * the ``/a2a open`` body asks via AskUserQuestion when no name is
      given (Phase B),
    * the ``/a2a open`` body invokes the ``_open_state write`` helper
      with ``--output-file`` (Phase E),
    * the LOAD-BEARING Phase D bg-agent prompt is embedded VERBATIM
      from design §5.3.

The tests run in the default suite — no integration marker.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


COMMAND_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "commands"
    / "a2a.md"
)


# Verbatim Phase D prompt template per impl plan §Task 6 Step 6.2 Phase D
# (lines 1071-1077 of 2026-05-07-a2a-watch-chain-impl.md). The plan is
# authoritative for ship-time behavior; design §5.3 lacks the
# `Set the Bash timeout parameter...` line, but the impl plan (line 1081)
# elevates it to a MUST and inserts it between the bash command line and
# the "When it exits" sentence. Reproduce that ordering exactly so a
# drift in either side fails the test.
#
# The script path uses ``<SPELLBOOK_ABS>`` as a substitution placeholder
# (parallel to ``<NAME>``) rather than a hardcoded developer-machine
# absolute path so the slash command is portable across operators. The
# orchestrator substitutes both placeholders at dispatch time: ``<NAME>``
# from Phase B/C, and ``<SPELLBOOK_ABS>`` from the operator's
# ``SPELLBOOK_DIR`` value resolved per ``~/.claude/CLAUDE.md``. Earlier
# revisions used the literal token ``$SPELLBOOK_DIR`` here, but that
# relied on an LLM-side reading convention that does NOT carry through
# to dispatched subagent prompts: the bg Task agent's Bash invocation
# expanded ``$SPELLBOOK_DIR`` against the shell environment (where it is
# unset and empty), producing ``python3 /skills/agent2agent/...`` and
# failing on the first cycle. Using an obvious placeholder forces the
# orchestrator to substitute, matching the existing ``<NAME>`` pattern.
PHASE_D_PROMPT_VERBATIM = (
    "Run exactly this one Bash command and wait for it to exit:\n"
    "\n"
    "    python3 <SPELLBOOK_ABS>/skills/agent2agent/scripts/agent2agent.py watch <NAME>\n"
    "\n"
    "Set the Bash timeout parameter to 600000 milliseconds.\n"
    "\n"
    "When it exits, respond with ONLY the last non-empty line of its stdout. "
    "Do not interpret, summarize, or wrap it. Do not perform any other tool calls. "
    "Do not run any loops. Do not check anything periodically. "
    "Do not respond until the bash command exits."
)


# The "Set the Bash timeout parameter to 600000 milliseconds." line is
# REQUIRED by the impl plan (§Task 6, Step 6.2 Phase D, line 1081):
# the Phase D prompt must include this line unconditionally.
PHASE_D_BASH_TIMEOUT_LINE = (
    "Set the Bash timeout parameter to 600000 milliseconds."
)


def _read_command() -> str:
    return COMMAND_PATH.read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> dict:
    # Frontmatter is between two `---` lines at the top.
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip() != "":
        raise AssertionError(
            "commands/a2a.md must begin with a YAML frontmatter block "
            "delimited by `---` lines"
        )
    return yaml.safe_load(parts[1])


# ---------------------------------------------------------------------------
# Existence + frontmatter
# ---------------------------------------------------------------------------


def test_a2a_command_file_exists() -> None:
    assert COMMAND_PATH.is_file(), (
        f"expected commands/a2a.md at {COMMAND_PATH}; not found"
    )


def test_a2a_frontmatter_parses_as_yaml() -> None:
    fm = _parse_frontmatter(_read_command())
    assert isinstance(fm, dict), (
        f"frontmatter must parse to a mapping; got {type(fm).__name__}"
    )
    assert "description" in fm and isinstance(fm["description"], str), (
        f"frontmatter must contain a string `description` field; got {fm!r}"
    )


def test_a2a_frontmatter_description_lists_required_triggers() -> None:
    """description must enumerate every trigger phrase from impl plan §Task 6 Step 6.2.

    The plan (line 1051) lists these comma-joined trigger phrases. We
    assert each one is present somewhere in the description. Includes
    the LEGACY `'listen for messages'` muscle-memory trigger.
    """
    fm = _parse_frontmatter(_read_command())
    description = fm["description"]
    required_triggers = [
        "/a2a",
        "open inbox",
        "close inbox",
        "listen for messages",  # LEGACY trigger — preserve muscle memory
        "listen as",
        "send a message to session",
        "check inbox",
        "reply to that session",
        "inter-agent chat",
        "inter-agent messaging",
        "agent2agent",
        "a2a",
        "agent bus",
        "message another session",
        "tell session Y to",
        "ask session Y",
    ]
    missing = [t for t in required_triggers if t not in description]
    assert not missing, (
        f"frontmatter `description` must enumerate every trigger phrase from "
        f"impl plan §Task 6 Step 6.2; missing: {missing!r}; "
        f"actual description: {description!r}"
    )


def test_a2a_frontmatter_description_lists_subcommands() -> None:
    """description must enumerate every public subcommand."""
    fm = _parse_frontmatter(_read_command())
    description = fm["description"]
    required_subcommands = [
        "open",
        "close",
        "send",
        "check",
        "read",
        "peek",
        "names",
        "bound-name",
    ]
    missing = [s for s in required_subcommands if s not in description]
    assert not missing, (
        f"frontmatter `description` must enumerate every public subcommand; "
        f"missing: {missing!r}; actual description: {description!r}"
    )


# ---------------------------------------------------------------------------
# Structural invariants: phases + per-subcommand sections
# ---------------------------------------------------------------------------


def test_a2a_open_section_contains_all_six_phases() -> None:
    """Phases A–F must each appear with documented behavior.

    Per impl plan line 1102: "All 8 phase headings (A–H, plus the
    per-subcommand sections specified in Step 6.2) are present, each
    with documented behavior. Specifically: Phase A (pre-flight liveness
    probe), Phase B (slug generation), Phase C (helper open call),
    Phase D (bg Task dispatch), Phase E (state-file write), Phase F
    (per-completion behavioral protocol)."

    No phase may be omitted or collapsed.
    """
    body = _read_command()
    required_phases = [
        "Phase A",
        "Phase B",
        "Phase C",
        "Phase D",
        "Phase E",
        "Phase F",
    ]
    missing = [p for p in required_phases if p not in body]
    assert not missing, (
        f"commands/a2a.md must document Phases A through F per impl plan "
        f"§Task 6 Step 6.2; missing: {missing!r}"
    )


def test_a2a_close_section_present() -> None:
    body = _read_command()
    assert "## /a2a close" in body, (
        "commands/a2a.md must contain a `## /a2a close` section per "
        "impl plan §Task 6 Step 6.2 item 5"
    )


def test_a2a_error_path_section_present() -> None:
    """Error path section per impl plan §Task 6 Step 6.2 item 9."""
    body = _read_command()
    assert "## Error path" in body, (
        "commands/a2a.md must contain a `## Error path` section per "
        "impl plan §Task 6 Step 6.2 item 9 (silent retry once on missing "
        "marker; second failure surfaces `[a2a watch chain failed: <reason>]`)"
    )


def test_a2a_error_path_documents_failure_marker() -> None:
    """Error path must surface the exact marker per impl plan line 1095."""
    body = _read_command()
    assert "[a2a watch chain failed:" in body, (
        "Error path section must surface the exact marker "
        "`[a2a watch chain failed: <reason>]` per impl plan line 1095"
    )


@pytest.mark.parametrize(
    "subcommand",
    [
        "open",
        "close",
        "send",
        "check",
        "read",
        "peek",
        "names",
        "bound-name",
    ],
)
def test_a2a_per_subcommand_section_present(subcommand: str) -> None:
    """Each public subcommand from the dispatch table must have its own section."""
    body = _read_command()
    heading = f"## /a2a {subcommand}"
    assert heading in body, (
        f"commands/a2a.md must contain a `{heading}` section per impl plan "
        f"§Task 6 Step 6.2 dispatch table"
    )


# ---------------------------------------------------------------------------
# Phase B — AskUserQuestion when no name given
# ---------------------------------------------------------------------------


def test_a2a_open_no_arg_uses_askuserquestion() -> None:
    """When `<name>` omitted, Phase B prompts via AskUserQuestion."""
    body = _read_command()
    assert "AskUserQuestion" in body, (
        "Phase B (slug generation) must use AskUserQuestion when no name "
        "is given per impl plan §Task 6 Step 6.2 Phase B"
    )


# ---------------------------------------------------------------------------
# Phase E — _open_state write with --output-file
# ---------------------------------------------------------------------------


def test_a2a_phase_e_invokes_open_state_write_with_output_file() -> None:
    """Phase E must call `_open_state write` AND pass `--output-file`.

    Per impl plan line 1084: T4's `_open_state write` requires
    `--output-file` and rejects relative paths. Without `--output-file`
    the orphan-recovery hook degrades to fail-safe-dead.
    """
    body = _read_command()
    assert "_open_state write" in body, (
        "Phase E must invoke the `_open_state write` helper subcommand "
        "per impl plan §Task 6 Step 6.2 Phase E"
    )
    assert "--output-file" in body, (
        "Phase E must pass `--output-file` to `_open_state write` per "
        "impl plan line 1084 (rejects relative paths server-side)"
    )


def test_a2a_close_invokes_open_state_clear() -> None:
    """`/a2a close` must clear `.open/<sid>` via the helper."""
    body = _read_command()
    assert "_open_state clear" in body, (
        "/a2a close must invoke `_open_state clear` per design §5.4 step 7"
    )


# ---------------------------------------------------------------------------
# Phase D — load-bearing prompt verbatim
# ---------------------------------------------------------------------------


def test_a2a_phase_d_prompt_is_verbatim() -> None:
    """The Phase D bg-agent prompt is LOAD-BEARING and must be verbatim.

    Per impl plan line 1101: "The Phase D prompt block matches the
    design §5.3 Phase D text byte-for-byte." A drift here can
    reintroduce LLM-side polling and blow up silent-idle token cost.
    """
    body = _read_command()
    # Normalize line endings; the markdown file may have been edited
    # cross-platform, but the verbatim payload must appear once.
    normalized = body.replace("\r\n", "\n")
    assert PHASE_D_PROMPT_VERBATIM in normalized, (
        "Phase D bg-agent prompt MUST appear verbatim per design §5.3 "
        "Phase D / impl plan line 1101. Expected payload:\n"
        f"{PHASE_D_PROMPT_VERBATIM!r}"
    )


def test_a2a_phase_d_prompt_includes_bash_timeout_line() -> None:
    """Phase D must include the unconditional Bash timeout instruction.

    Per impl plan line 1081: "The Phase D prompt template MUST also
    include the line `Set the Bash timeout parameter to 600000
    milliseconds.` unconditionally (no probing, no conditionalization)."
    """
    body = _read_command()
    assert PHASE_D_BASH_TIMEOUT_LINE in body, (
        f"Phase D prompt must include verbatim line: "
        f"{PHASE_D_BASH_TIMEOUT_LINE!r} (impl plan line 1081)"
    )


# ---------------------------------------------------------------------------
# Phase F — per-completion behavioral protocol markers
# ---------------------------------------------------------------------------


def test_a2a_phase_f_documents_both_markers() -> None:
    """Phase F must reference both PENDING_BATCH and WATCH_RECYCLE markers.

    Per design §5.3 Phase F, the parent dispatches behavior on the
    bg agent's last stdout line, which is one of these two markers.
    """
    body = _read_command()
    for marker in ("PENDING_BATCH", "WATCH_RECYCLE"):
        assert marker in body, (
            f"Phase F must reference the {marker} marker per design §5.3 "
            f"Phase F (parent's per-completion dispatch logic)"
        )


def test_a2a_phase_f_invokes_drain_helper() -> None:
    """Phase F PENDING_BATCH path must call the helper's `drain` subcommand."""
    body = _read_command()
    # Match `agent2agent.py drain <name> <batch-id>` from design §5.3 Phase F step 5.
    assert re.search(r"\bdrain\b", body), (
        "Phase F PENDING_BATCH path must invoke `drain <name> <batch-id>` "
        "per design §5.3 Phase F step 5"
    )


# ---------------------------------------------------------------------------
# T8: SKILL.md architecture sections — proves prose pass landed
# ---------------------------------------------------------------------------


SKILL_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "agent2agent"
    / "SKILL.md"
)


def test_skill_md_documents_watch_chain() -> None:
    """SKILL.md must document the watch-chain architecture per impl plan §Task 8.

    The pre-T8 SKILL.md only covered the hook-driven UserPromptSubmit
    notify path; T8 adds an architecture section that explains the new
    watch chain (T3a/T3b/T4/T5/T6 implementation), the open-state record
    at ``<bus>/.open/<sid>``, the ``WATCH_RECYCLE`` heartbeat, the
    fswatch + polling backstop, the silent-idle cost model, and the
    ``/a2a`` slash command surface.

    These markers are the load-bearing terms a reader needs to find when
    diagnosing a chain issue or onboarding to the architecture. Each
    must appear in SKILL.md; their absence is a regression of the prose
    pass.
    """
    body = SKILL_PATH.read_text(encoding="utf-8")
    required_markers = [
        # Watch-chain architecture (impl plan §Task 8 Step 8.3)
        "watch chain",
        "WATCH_RECYCLE",
        "PENDING_BATCH",
        "pending/",
        "open-state",
        "fswatch",
        # Compaction limitation (impl plan §Task 8 Step 8.3 para 3)
        "Compaction",
        # Silent-idle cost model (impl plan §Task 8 Step 8.4)
        "Silent-Idle",
        # Slash command surface (impl plan §Task 8 Step 8.5)
        "/a2a open",
        "/a2a close",
        # Protocol-internal subcommands (impl plan §Task 8 Step 8.5)
        "watch",
        "drain",
    ]
    missing = [m for m in required_markers if m not in body]
    assert not missing, (
        "SKILL.md must document the watch-chain architecture per impl plan "
        f"§Task 8; missing markers: {missing!r}"
    )


def test_skill_md_silent_idle_cost_model_cites_token_numbers() -> None:
    """SKILL.md Silent-Idle section must cite the design §0.5 cost numbers.

    Per impl plan §Task 8 Step 8.4: the Silent-Idle Cost Model
    subsection embeds the per-cycle, per-hour, and per-day idle token
    estimates from design §0.5. These numbers gate the operator's
    decision to ``/a2a close`` for overnight idle. Drifting away from
    them silently is a regression.
    """
    body = SKILL_PATH.read_text(encoding="utf-8")
    # Per-hour idle range (~10–15k tokens) is the most decision-relevant
    # number; per-day (~240–400k) is the headline that drives the
    # `/a2a close` recommendation. Both must be present.
    required_phrases = [
        "Per-hour",  # table row label per design §0.5 phrasing
        "Per-day",   # table row label per design §0.5 phrasing
        "/a2a close",
    ]
    missing = [p for p in required_phrases if p not in body]
    assert not missing, (
        "SKILL.md Silent-Idle Cost Model subsection must cite per-hour/"
        "per-day idle estimates and recommend `/a2a close` for true "
        f"silence per impl plan §Task 8 Step 8.4; missing: {missing!r}"
    )


def test_skill_md_protocol_internal_subcommands_marked() -> None:
    """`watch` and `drain` rows in the Quick Reference must be marked protocol-internal.

    Per impl plan §Task 8 Step 8.5: the Quick Reference table gains
    `watch` and `drain` rows annotated as ``Protocol-internal — invoked
    by `/a2a open` watch chain. Users should not run these directly``.
    Without this annotation, operators may invoke ``watch`` directly
    and break the lockfile invariant.
    """
    body = SKILL_PATH.read_text(encoding="utf-8")
    assert "Protocol-internal" in body, (
        "SKILL.md Quick Reference must annotate `watch` and `drain` "
        "rows as `Protocol-internal` per impl plan §Task 8 Step 8.5"
    )
