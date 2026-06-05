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


# Verbatim Phase D dispatch block for the IMMORTAL bg-watcher architecture
# (commands/a2a.md Phase D, "Dispatch via:" block). The slash command no
# longer dispatches a Task subagent with a natural-language prompt; it
# dispatches a single immortal `Bash(run_in_background: true)` watcher that
# exits only on a terminal marker. The load-bearing content is the
# `Bash(run_in_background: true, command: ...)` block — its drift can
# reintroduce LLM-side polling or silently break delivery.
#
# The script path uses ``<SPELLBOOK_ABS>`` as a substitution placeholder
# (parallel to ``<NAME>``) rather than a hardcoded developer-machine
# absolute path so the slash command is portable across operators. The
# orchestrator substitutes both placeholders at dispatch time: ``<NAME>``
# from Phase B/C, and ``<SPELLBOOK_ABS>`` from the operator's
# ``SPELLBOOK_DIR`` value resolved per ``~/.claude/CLAUDE.md``. Earlier
# revisions used the literal token ``$SPELLBOOK_DIR`` here, but that
# relied on an LLM-side reading convention that does NOT carry through
# to dispatched background commands: the bg shell expands
# ``$SPELLBOOK_DIR`` against the (empty) environment, producing
# ``python3 /skills/agent2agent/...`` and failing on the first cycle.
# Using an obvious placeholder forces the orchestrator to substitute,
# matching the existing ``<NAME>`` pattern.
#
# CRITICAL: the dispatch carries NO `--max-elapsed` flag (infinite mode)
# and the watcher must NOT be given a 600000ms Bash timeout — see
# PHASE_D_FORBIDDEN_TIMEOUT_LINE / PHASE_D_OLD_TIMEOUT_LINE below.
PHASE_D_PROMPT_VERBATIM = (
    "Bash(\n"
    "    run_in_background: true,\n"
    "    command: python3 <SPELLBOOK_ABS>/skills/agent2agent/scripts/agent2agent.py watch <NAME>\n"
    ")"
)


# The immortal watcher dispatch must FORBID the per-call Bash timeout: a
# `run_in_background` task detaches and ignores the per-call ceiling, so a
# timeout is both unnecessary and a footgun. commands/a2a.md Phase D pins
# this invariant verbatim ("Do NOT set a 600000ms timeout: ...").
PHASE_D_FORBIDDEN_TIMEOUT_LINE = (
    "Do NOT set a 600000ms timeout"
)


# The OLD architecture (Task-subagent recycle chain) instructed the agent to
# "Set the Bash timeout parameter to 600000 milliseconds." That line is now
# an ANTIPATTERN and must be ABSENT from the immortal-watcher command file.
PHASE_D_OLD_TIMEOUT_LINE = (
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
    """The Phase D bg-watcher dispatch is LOAD-BEARING and must be verbatim.

    Under the immortal-watcher architecture, Phase D dispatches a single
    `Bash(run_in_background: true)` watcher whose command line carries the
    `<SPELLBOOK_ABS>` and `<NAME>` substitution tokens and `watch <NAME>`
    with NO `--max-elapsed`. A drift here can reintroduce LLM-side polling
    and blow up silent-idle token cost, or silently break delivery.
    """
    body = _read_command()
    # Normalize line endings; the markdown file may have been edited
    # cross-platform, but the verbatim payload must appear once.
    normalized = body.replace("\r\n", "\n")
    assert PHASE_D_PROMPT_VERBATIM in normalized, (
        "Phase D bg-watcher dispatch block MUST appear verbatim. "
        "Expected payload:\n"
        f"{PHASE_D_PROMPT_VERBATIM!r}"
    )
    # Infinite mode: the dispatched watcher command line carries NO
    # --max-elapsed flag. (The flag name may still appear in prose — e.g.
    # Invariant Principle "no `--max-elapsed`" — so assert specifically that
    # the `watch <NAME>` command line is not immediately followed by the
    # flag, rather than that the literal never appears anywhere.)
    assert "agent2agent.py watch <NAME> --max-elapsed" not in normalized, (
        "Phase D dispatch command line must NOT pass --max-elapsed "
        "(infinite mode); the immortal watcher exits only on a terminal marker"
    )


def test_a2a_phase_d_forbids_bash_timeout_line() -> None:
    """Phase D must FORBID the 600000ms Bash timeout, not require it.

    The immortal watcher is dispatched via `Bash(run_in_background: true)`,
    which detaches and ignores the per-call timeout ceiling. The OLD
    Task-recycle architecture instructed "Set the Bash timeout parameter to
    600000 milliseconds." — that line is now an antipattern. The command
    file must (a) pin the forbid-timeout invariant verbatim and (b) NOT
    contain the old set-timeout instruction.
    """
    body = _read_command()
    assert PHASE_D_FORBIDDEN_TIMEOUT_LINE in body, (
        f"Phase D must pin the forbid-timeout invariant verbatim: "
        f"{PHASE_D_FORBIDDEN_TIMEOUT_LINE!r}"
    )
    assert PHASE_D_OLD_TIMEOUT_LINE not in body, (
        f"Phase D must NOT contain the OLD set-timeout instruction "
        f"{PHASE_D_OLD_TIMEOUT_LINE!r}; a `run_in_background` task ignores "
        f"the per-call timeout ceiling, so setting it is a footgun"
    )


# ---------------------------------------------------------------------------
# Phase F — per-completion behavioral protocol markers
# ---------------------------------------------------------------------------


def test_a2a_phase_f_documents_terminal_markers() -> None:
    """Phase F must reference the immortal watcher's terminal markers.

    Under the immortal-watcher architecture the parent dispatches behavior
    on the bg watcher's last stdout line. The production terminal markers
    are PENDING_BATCH (messages arrived → drain + re-arm), WATCH_INBOX_GONE
    (inbox closed elsewhere → clear, no re-arm), and WATCH_LOCKED (another
    watcher owns it → no re-arm). WATCH_RECYCLE is the finite-mode/debug
    stray (never emitted in production) and Phase F documents its benign
    silent-re-arm handling.
    """
    body = _read_command()
    for marker in (
        "PENDING_BATCH",
        "WATCH_INBOX_GONE",
        "WATCH_LOCKED",
        "WATCH_RECYCLE",
    ):
        assert marker in body, (
            f"Phase F must reference the {marker} marker (parent's "
            f"per-completion dispatch logic for the immortal watcher)"
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
    """SKILL.md must document the immortal watch-chain architecture.

    SKILL.md's architecture section explains the immortal bg-Bash watch
    chain, the open-state record at ``<bus>/.open/<sid>``, the heartbeat
    liveness contract, the fswatch + polling backstop, the silent-idle
    cost model, and the ``/a2a`` slash command surface.

    These markers are the load-bearing terms a reader needs to find when
    diagnosing a chain issue or onboarding to the architecture. Each must
    appear in SKILL.md; their absence is a regression of the prose pass.

    Note: under the immortal-watcher architecture SKILL.md documents the
    terminal markers PENDING_BATCH / WATCH_INBOX_GONE / WATCH_LOCKED (the
    per-cycle WATCH_RECYCLE is finite-mode/debug-only and is documented in
    commands/a2a.md, not here).
    """
    body = SKILL_PATH.read_text(encoding="utf-8")
    required_markers = [
        # Watch-chain architecture
        "watch chain",
        # Immortal-watcher terminal markers
        "PENDING_BATCH",
        "WATCH_INBOX_GONE",
        "WATCH_LOCKED",
        "pending/",
        "open-state",
        "fswatch",
        # Compaction limitation
        "Compaction",
        # Silent-idle cost model
        "Silent-Idle",
        # Slash command surface
        "/a2a open",
        "/a2a close",
        # Protocol-internal subcommands
        "watch",
        "drain",
    ]
    missing = [m for m in required_markers if m not in body]
    assert not missing, (
        "SKILL.md must document the watch-chain architecture per impl plan "
        f"§Task 8; missing markers: {missing!r}"
    )


def test_skill_md_silent_idle_cost_model_cites_token_numbers() -> None:
    """SKILL.md Silent-Idle Cost Model table must carry its idle-window rows.

    Under the immortal-watcher architecture the cost model headline is that
    an idle session incurs ~0 watcher-induced tokens (no recycle). The
    Silent-Idle Cost Model table enumerates the per-batch and idle-window
    rows; the prose explains that there is no longer an overnight-idle token
    reason to ``/a2a close`` (close only retires a name). Drifting away from
    these row labels silently is a regression of the cost-model pass.
    """
    body = SKILL_PATH.read_text(encoding="utf-8")
    # Table row labels from the immortal-watcher cost model, plus the
    # `/a2a close` reference the prose anchors the retire-vs-silence
    # distinction on.
    required_phrases = [
        "Per real message batch",  # table row label
        "Idle hour",               # table row label
        "Idle day",                # table row label
        "/a2a close",
    ]
    missing = [p for p in required_phrases if p not in body]
    assert not missing, (
        "SKILL.md Silent-Idle Cost Model subsection must carry the "
        "per-batch / idle-hour / idle-day rows and reference `/a2a close`; "
        f"missing: {missing!r}"
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
