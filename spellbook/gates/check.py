"""Security check module for the surviving bash/spawn/state gates.

Provides a single runtime gate function used by:

- ``hooks/spellbook_hook.py`` (PreToolUse gates for Bash and
  ``spawn_claude_session``)
- ``spellbook/sessions/resume.py`` (workflow state validation)
- ``spellbook/mcp/tools/security.py`` (MCP fallback when hooks
  cannot reach the embedded patterns)

Layer order for the Bash branch (defense in depth, cheapest first):

  1. L4 bashlex AST parser — catches compound commands, command sub,
     dangerous redirects, env-prefix escapes, shell-out flags, direct
     shell invocation, and wrapper-stripping bypasses.
  2. L3 tier classifier (WI-6b) — maps the call to a reversibility tier
     and emits a TIER-DENY/TIER-ASK finding. The same tier projection
     also produces the L2 deny list installed into ``settings.json``;
     the in-process layer is the runtime mirror of that policy.
  3. L2 DANGEROUS_BASH_PATTERNS regex — legacy regex set kept for
     defence in depth.
  4. EXFILTRATION_RULES — separate rule set for data-exfil patterns.

Other tools (Edit/Write/MCP/...) run the tier classifier first; the
catch-all INJECTION_RULES check still applies to non-Bash inputs.

Everything else that used to live here (audit logging, security
modes, canary output scanning) was removed in the nuclear
security cleanup.
"""

import json
import logging
import sys
from functools import lru_cache
from pathlib import Path

from spellbook.gates.bash_parser import parse_and_check as _bashlex_parse_and_check
from spellbook.gates.rules import (
    DANGEROUS_BASH_PATTERNS,
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    check_patterns,
)
from spellbook.gates.secret_paths import check_secret_path
from spellbook.gates.tiers import (
    classify_tool_call,
    load_tiers,
    tier_to_verdict,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier classifier integration
# ---------------------------------------------------------------------------


def _tiers_toml_path() -> Path:
    """Return the bundled tiers.toml path. Override in tests via this function."""
    return Path(__file__).resolve().parent / "tiers.toml"


@lru_cache(maxsize=1)
def _cached_tiers() -> tuple:
    """Load and memoize the seed tier records.

    Returned as a tuple so the lru_cache decorator can hash it. The cache
    is process-local; the hook runs in a long-lived daemon, so re-reading
    tiers.toml on every Bash call is wasteful. Tests that need a fresh
    load should call ``_cached_tiers.cache_clear()``.
    """
    path = _tiers_toml_path()
    try:
        return tuple(load_tiers(path))
    except FileNotFoundError:
        logger.debug("tiers: %s missing; classifier will return ask for all calls", path)
        return ()
    except Exception as exc:  # noqa: BLE001 — never crash the gate on malformed seed
        logger.error("tiers: failed to load %s: %s", path, exc)
        return ()


def _tier_findings(
    tool_name: str, tool_input: dict, cwd: str | None = None
) -> list[dict]:
    """Run the tier classifier and translate the result to gate findings.

    A T3 match produces a CRITICAL TIER-DENY finding (the gate blocks).
    A T2 / unclassified match produces a HIGH TIER-ASK finding (caller
    surfaces an `ask` verdict). T0 / T1 produce no findings (silent /
    loud allow; loud-allow auditing is the caller's responsibility).

    Args:
        tool_name: e.g. ``"Bash"``, ``"Edit"``, ``"mcp__..."``.
        tool_input: Tool input dict.
        cwd: Optional working directory; forwarded to
            :func:`spellbook.gates.tiers.classify_tool_call` so the
            git_push pre-pass can resolve the current branch.
    """
    records = _cached_tiers()
    if not records:
        return []

    tier = classify_tool_call(tool_name, tool_input or {}, records, cwd=cwd)
    verdict = tier_to_verdict(tier)

    if verdict == "deny":
        return [
            {
                "rule_id": "TIER-DENY",
                "severity": "CRITICAL",
                "message": (
                    f"Tier classifier denied {tool_name} call (tier={tier}). "
                    "This combination is forbidden; see spellbook/gates/tiers.toml."
                ),
                "matched_text": _summarize_input(tool_name, tool_input),
            }
        ]
    if verdict == "ask":
        # Only emit TIER-ASK when there's an actual matching record. A pure
        # T_UNCLASSIFIED fall-through is the default policy ("ask"), but
        # leaving it here would clamour every routine call. Keep TIER-ASK
        # narrow: only when a record positively assigns T2.
        if tier == "T2":
            return [
                {
                    "rule_id": "TIER-ASK",
                    "severity": "HIGH",
                    "message": (
                        f"Tier classifier marked {tool_name} call as T2 (ask). "
                        "Operator confirmation required."
                    ),
                    "matched_text": _summarize_input(tool_name, tool_input),
                }
            ]
        # T_UNCLASSIFIED — silent. The hook surface decides whether to fall
        # through to the regex layers (Bash) or to a default-ask policy.
        return []
    # "allow" — silent for T0; T1 callers may choose to log via a separate
    # auditor, but this layer does not emit a finding.
    return []


def _summarize_input(tool_name: str, tool_input: dict) -> str:
    """Return a short, log-safe summary of the tool call for findings."""
    if not isinstance(tool_input, dict):
        return f"{tool_name}(<non-dict input>)"
    if tool_name == "Bash":
        return (tool_input.get("command", "") or "")[:200]
    # Fall back to keys list — values may contain secrets / large blobs.
    return f"{tool_name}(keys={sorted(tool_input.keys())})"


def check_tool_input(
    tool_name: str,
    tool_input: dict,
    security_mode: str = "standard",
    cwd: str | None = None,
) -> dict:
    """Check tool input against relevant security pattern sets.

    Routes checks based on tool name:
    - Bash: DANGEROUS_BASH_PATTERNS + EXFILTRATION_RULES
    - spawn_claude_session: INJECTION_RULES + ESCALATION_RULES
    - workflow_state_save: INJECTION_RULES (on all string values in state)
    - Other tools: INJECTION_RULES (on all string values)

    Args:
        tool_name: The name of the tool being invoked.
        tool_input: The input dict for the tool.
        security_mode: One of "standard" or "paranoid".

    Returns:
        Dict with keys:
            safe: bool - True if no findings above LOW severity
            verdict: str - "allow" | "ask" | "deny". "ask" iff every
                non-LOW finding is a TIER-ASK; "deny" if any non-LOW
                finding is not a TIER-ASK; "allow" if no non-LOW
                findings. Callers that want the harness ``ask`` UX
                (Claude Code's permission prompt) should branch on
                this field; legacy callers can keep using ``safe``.
            findings: list[dict] - matched patterns
            tool_name: str - the tool name checked
    """
    findings: list[dict] = []

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # L4 bashlex AST parser runs first — it is the strongest layer and
        # short-circuits the gate on compound commands, command substitution,
        # dangerous redirects, env-prefix escapes, shell-out flags, direct
        # shell invocation, and wrapper-stripping bypasses.
        findings.extend(_bashlex_parse_and_check(command, security_mode))
        # L3 tier classifier (WI-6b): map the call to a reversibility tier
        # and emit TIER-DENY (T3) / TIER-ASK (T2) findings. T0 / T1 produce
        # no findings; T_UNCLASSIFIED falls through to the regex layers.
        findings.extend(_tier_findings(tool_name, tool_input, cwd=cwd))
        # L2 DANGEROUS_BASH_PATTERNS — legacy regex set kept for defense in
        # depth even when the tier classifier already accepted the call.
        findings.extend(
            check_patterns(command, DANGEROUS_BASH_PATTERNS, security_mode)
        )
        findings.extend(
            check_patterns(command, EXFILTRATION_RULES, security_mode)
        )
    elif tool_name == "spawn_claude_session":
        prompt = tool_input.get("prompt", "")
        findings.extend(
            check_patterns(prompt, INJECTION_RULES, security_mode)
        )
        findings.extend(
            check_patterns(prompt, ESCALATION_RULES, security_mode)
        )
    elif tool_name == "Read":
        findings.extend(_check_read_path(tool_input))
    elif tool_name == "workflow_state_save":
        for text in _extract_strings(tool_input):
            findings.extend(
                check_patterns(text, INJECTION_RULES, security_mode)
            )
    else:
        # L3 tier classifier for capability tools (Edit/Write/...) and MCP
        # tools (mcp__server__tool). The classifier emits TIER-DENY for T3
        # records (e.g. mcp__github__delete_*) and TIER-ASK for T2 records
        # (e.g. mcp__atlassian__transition_issue).
        findings.extend(_tier_findings(tool_name, tool_input, cwd=cwd))
        for text in _extract_strings(tool_input):
            findings.extend(
                check_patterns(text, INJECTION_RULES, security_mode)
            )

    safe = all(f.get("severity") == "LOW" for f in findings)
    return {
        "safe": safe,
        "verdict": _compute_verdict(findings, safe=safe),
        "findings": findings,
        "tool_name": tool_name,
    }


def _compute_verdict(findings: list[dict], *, safe: bool) -> str:
    """Project ``findings`` to one of ``allow`` / ``ask`` / ``deny``.

    - ``allow``: no non-LOW findings (the ``safe`` codepath).
    - ``ask``: at least one non-LOW finding, AND every non-LOW finding
      is a TIER-ASK (``rule_id`` starts with ``"TIER-ASK"``). This is
      the harness ``permissionDecision: "ask"`` codepath — operator
      can approve in-session.
    - ``deny``: at least one non-LOW finding that is not a TIER-ASK
      (TIER-DENY, CRITICAL bashlex/exfil/injection/secret-path, etc.).
      Mixed TIER-ASK + non-ask findings resolve to ``deny`` — deny wins.
    """
    if safe:
        return "allow"
    non_low = [f for f in findings if f.get("severity") != "LOW"]
    if all(f.get("rule_id", "").startswith("TIER-ASK") for f in non_low):
        return "ask"
    return "deny"


def _check_read_path(tool_input: dict) -> list[dict]:
    """Check a Read-tool invocation against the secret-path denylist.

    Resolves the ``file_path`` argument (expanding ``~`` and following
    symlinks) and returns a list with a single CRITICAL finding when the
    resolved path matches any rule in
    ``spellbook.gates.secret_paths.SECRET_PATH_RULES``.

    Args:
        tool_input: The Read tool's input dict. Expected key: ``file_path``.

    Returns:
        A list with one finding dict on a denylist match, else empty.
    """
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return []

    rule_id = check_secret_path(file_path)
    if rule_id is None:
        return []

    try:
        resolved = str(Path(file_path).expanduser().resolve(strict=False))
    except (OSError, RuntimeError) as e:
        # Path resolution can fail on weird inputs (cyclic symlinks,
        # unreadable parents, recursion limits). Log and proceed with
        # the un-resolved path — the rule already matched, so we still
        # surface the finding; we just lose the canonicalized display.
        logger.warning(
            "secret-path resolve failed for %r (%s): %s",
            file_path,
            type(e).__name__,
            e,
        )
        resolved = file_path

    return [
        {
            "rule_id": rule_id,
            "severity": "CRITICAL",
            "message": f"Read of secret-path denylist match: {resolved}",
            "matched_text": resolved,
        }
    ]


def _extract_strings(obj: object) -> list[str]:
    """Recursively extract all string values from a nested dict/list structure.

    Args:
        obj: The object to extract strings from.

    Returns:
        List of string values found.
    """
    strings: list[str] = []
    if isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            strings.extend(_extract_strings(value))
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(_extract_strings(item))
    return strings


def main() -> None:
    """CLI entry point for security gate checks.

    Reads JSON from stdin in the Claude Code hook protocol format:
        {"tool_name": str, "tool_input": dict}

    Exits 0 if safe, 2 if blocked. On block, prints a JSON error
    object to stderr (per Claude Code's hook protocol — exit 2 with
    reason on stderr so the harness surfaces it to the user):
        {"error": "Security check failed: <reason>"}

    This keeps the opencode plugin and gemini policy toml entry
    points working without pulling in the larger CLI surface that
    used to live in ``spellbook.security.check``.
    """
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(
            json.dumps({"error": "Security check failed: invalid JSON input"}),
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    # Empty string -> None preserves fail-safe semantics in classify_git_push,
    # which treats ``cwd is None`` as the "cannot resolve branch" trigger and
    # falls back to T2. Passing ``cwd=""`` would resolve relative to an
    # undefined directory and silently skip the protected-branch pre-pass.
    cwd = data.get("cwd") or None

    result = check_tool_input(tool_name, tool_input, cwd=cwd)
    if not result["safe"]:
        reasons = "; ".join(f["message"] for f in result["findings"])
        print(
            json.dumps({"error": f"Security check failed: {reasons}"}),
            file=sys.stderr,
            flush=True,
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
