"""Reversibility-tier classifier and L2 permission projector (WI-6b).

This module implements the tier-based policy layer specified in
``docs/security-architecture-design.md`` §7 (Phase 6b) and §6.4. It does
three jobs:

1. **Load + validate** the seed file ``spellbook/gates/tiers.toml`` into
   immutable :class:`TierRecord` instances. The validator is hand-rolled
   on top of :mod:`tomllib` because TOML itself does not reject unknown
   keys; the schema must be enforced at the application layer (see
   plan §WI-6b Step 5 rationale).
2. **Classify** a (tool_name, tool_input) pair against the loaded records
   and return one of ``"T0"``, ``"T1"``, ``"T2"``, ``"T3"``, or
   :data:`T_UNCLASSIFIED`. The hook surface maps that to a verdict via
   :func:`tier_to_verdict` (silent-allow / loud-allow / ask / deny / ask).
3. **Project T3 records into ``settings.json`` deny strings** so the
   installer can derive the managed L2 deny list at install time. This
   is the bridge between the in-process hook policy and Claude Code's
   ``permissions.deny`` array, ensuring T3 forbidden patterns are blocked
   even when the hook is not running (defense in depth).

Public surface:

- :class:`TierRecord` (frozen dataclass)
- :data:`T_UNCLASSIFIED`
- :func:`load_tiers`
- :func:`classify_tool_call`
- :func:`tier_to_verdict`
- :func:`tier_record_to_deny_pattern`
- :func:`derive_l2_deny_list`

The module deliberately depends only on the standard library so the
installer can import it cheaply without dragging gate-runtime deps
(notably ``bashlex``) into install time.
"""

from __future__ import annotations

import itertools
import logging
import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ImportError:  # Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------


#: Tier value used when no record matches a (tool, args) pair. Maps to ``ask``
#: at the hook surface per design §7.
T_UNCLASSIFIED = "T_UNCLASSIFIED"


_VALID_TIERS: frozenset[str] = frozenset({"T0", "T1", "T2", "T3"})


#: Tier → hook verdict (design §7 Phase 6b).
_TIER_VERDICT: dict[str, str] = {
    "T0": "allow",  # silent
    "T1": "allow",  # loud — caller emits audit log
    "T2": "ask",
    "T3": "deny",
    T_UNCLASSIFIED: "ask",
}


#: Capability tools whose name alone is the deny pattern (case 6).
_CAPABILITY_TOOLS: frozenset[str] = frozenset(
    {
        "Edit",
        "Write",
        "Read",
        "WebFetch",
        "WebSearch",
        "MultiEdit",
        "NotebookEdit",
        "Task",
    }
)


# ---------------------------------------------------------------------------
# Dataclass + schema validator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierRecord:
    """One row from ``tiers.toml``.

    Attributes:
        tool: Tool name to match. May be a literal Claude Code tool name
            (``"Bash"``, ``"Edit"``), an MCP tool name
            (``"mcp__server__tool"``), or an MCP wildcard
            (``"mcp__server__delete_*"``).
        pattern: For Bash records, the literal command prefix (or a regex
            with simple alternation). For MCP / capability records,
            ``"*"`` (the tool name itself is the discriminator).
        tier: One of ``"T0"``, ``"T1"``, ``"T2"``, ``"T3"``.
        description: Human-readable explanation; written into audit logs.
        mcp_qualifier: Optional MCP server hint (e.g. ``"atlassian"``);
            reserved for future use, currently informational.
    """

    tool: str
    pattern: str
    tier: str
    description: str
    mcp_qualifier: str | None = None


_ALLOWED_KEYS: frozenset[str] = frozenset(f.name for f in fields(TierRecord))
# Required keys are spelled out instead of derived from ``fields()`` because
# the dataclass default-vs-required heuristic (``f.default is f.default_factory``)
# is brittle across Python versions.
_REQUIRED_KEYS: frozenset[str] = frozenset({"tool", "pattern", "tier", "description"})


def _parse_record(raw: dict, source_idx: int, source: Path | None) -> TierRecord:
    """Validate a raw dict and construct a :class:`TierRecord`."""
    where = (
        f"{source}:[[tiers]]#{source_idx}" if source else f"tiers[[{source_idx}]]"
    )

    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected table, got {type(raw).__name__}")

    keys = set(raw.keys())
    unknown = keys - _ALLOWED_KEYS
    if unknown:
        raise ValueError(
            f"{where}: unknown keys {sorted(unknown)}; "
            f"allowed keys are {sorted(_ALLOWED_KEYS)}"
        )

    missing = _REQUIRED_KEYS - keys
    if missing:
        raise ValueError(
            f"{where}: missing required key(s) {sorted(missing)}"
        )

    tier = raw.get("tier")
    if tier not in _VALID_TIERS:
        raise ValueError(
            f"{where}: tier must be one of {sorted(_VALID_TIERS)}, got {tier!r}"
        )

    for k in ("tool", "pattern", "description"):
        v = raw.get(k)
        if not isinstance(v, str) or not v:
            raise ValueError(
                f"{where}: field {k!r} must be a non-empty string, got {v!r}"
            )

    mcp_qualifier = raw.get("mcp_qualifier")
    if mcp_qualifier is not None and not isinstance(mcp_qualifier, str):
        raise ValueError(
            f"{where}: mcp_qualifier must be a string or omitted, got {mcp_qualifier!r}"
        )

    return TierRecord(
        tool=raw["tool"],
        pattern=raw["pattern"],
        tier=raw["tier"],
        description=raw["description"],
        mcp_qualifier=mcp_qualifier,
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_tiers(path: Path) -> list[TierRecord]:
    """Load and validate ``tiers.toml``.

    Args:
        path: Path to a TOML file containing one or more ``[[tiers]]``
            arrays of tables.

    Returns:
        List of validated :class:`TierRecord` instances, in source order.

    Raises:
        ValueError: schema validation failed (unknown key, bad tier,
            missing required field, wrong type).
        FileNotFoundError: ``path`` does not exist.
        tomllib.TOMLDecodeError: ``path`` is not valid TOML.

    Warning policy:
        Records whose Bash ``pattern`` contains regex constructs that
        :func:`_expand_alternations` cannot project to a literal prefix
        (character classes, quantifiers, escapes) are dropped at load
        time with a warning. A regex-only pattern would silently fail
        to match at hook-time AND at L2 derivation, so we surface the
        misconfiguration loudly and skip the record entirely. This
        mirrors the existing "not projectable" warning path used by
        :func:`tier_record_to_deny_pattern`.
    """
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    rows = data.get("tiers", []) or []
    if not isinstance(rows, list):
        raise ValueError(
            f"{path}: top-level [[tiers]] must be an array of tables, got "
            f"{type(rows).__name__}"
        )

    out: list[TierRecord] = []
    for i, row in enumerate(rows):
        rec = _parse_record(row, i, path)
        if rec.tool == "Bash" and not _is_projectable_bash_pattern(rec.pattern):
            logger.warning(
                "tiers: %s:[[tiers]]#%d: Bash pattern %r is not projectable "
                "(contains regex constructs not supported by the literal-"
                "prefix matcher: character classes, quantifiers, or escapes). "
                "The record would silently fail to match at hook-time AND "
                "fail to project to an L2 deny string; skipping it. Rewrite "
                "the pattern as a literal prefix or simple ``(a|b|c)`` "
                "alternation, or split it into multiple records.",
                path,
                i,
                rec.pattern,
            )
            continue
        out.append(rec)
    return out


def _is_projectable_bash_pattern(pattern: str) -> bool:
    """Return True if ``pattern`` can be safely projected to literal prefixes.

    Mirrors the gate used inside :func:`_expand_alternations`. Kept as a
    standalone helper so the loader can fail-loud on unprojectable Bash
    patterns BEFORE they reach classification or L2 derivation.
    """
    return _expand_alternations(pattern) != []


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def tier_to_verdict(tier: str) -> str:
    """Map a tier string (or :data:`T_UNCLASSIFIED`) to a hook verdict.

    Returns one of ``"allow"``, ``"ask"``, ``"deny"``. Unknown values fall
    through to ``"ask"`` (fail-safe default).
    """
    return _TIER_VERDICT.get(tier, "ask")


# Tier ordering for "highest tier wins" semantics. T3 (deny) > T2 (ask) >
# T1 (loud allow) > T0 (silent allow) > T_UNCLASSIFIED.
_TIER_RANK: dict[str, int] = {
    T_UNCLASSIFIED: -1,
    "T0": 0,
    "T1": 1,
    "T2": 2,
    "T3": 3,
}


def classify_tool_call(
    tool_name: str,
    tool_input: dict,
    records: Iterable[TierRecord],
) -> str:
    """Classify a single tool call against tier records.

    Args:
        tool_name: e.g. ``"Bash"``, ``"Edit"``, ``"mcp__atlassian__edit_issue"``.
        tool_input: Tool input dict. For Bash, the ``"command"`` key is
            inspected; for other tools, only ``tool_name`` is matched.
        records: Iterable of :class:`TierRecord`.

    Returns:
        The tier of the highest-tier matching record, or
        :data:`T_UNCLASSIFIED` when no record matches. Highest-tier wins
        so a deny rule cannot be diluted by an overlapping allow rule.
    """
    best_rank = _TIER_RANK[T_UNCLASSIFIED]
    best_tier = T_UNCLASSIFIED

    for rec in records:
        if not _record_matches(rec, tool_name, tool_input):
            continue
        rank = _TIER_RANK.get(rec.tier, -1)
        if rank > best_rank:
            best_rank = rank
            best_tier = rec.tier

    return best_tier


def _record_matches(rec: TierRecord, tool_name: str, tool_input: dict) -> bool:
    """Return True iff ``rec`` matches a (tool_name, tool_input) pair."""
    # MCP wildcard tool match (``mcp__server__delete_*``).
    if rec.tool.startswith("mcp__") and rec.tool.endswith("*"):
        prefix = rec.tool.rstrip("*")
        return tool_name.startswith(prefix)

    # MCP / capability tool exact match.
    if rec.tool != tool_name:
        return False

    # Bash records additionally match against the command prefix.
    if tool_name == "Bash":
        command = (tool_input or {}).get("command", "")
        return _bash_pattern_matches(rec.pattern, command)

    # Non-Bash exact tool match: pattern is conventionally "*" but we accept
    # any value — the tool name itself is the discriminator.
    return True


def _bash_pattern_matches(pattern: str, command: str) -> bool:
    """Match ``pattern`` (literal or alternation) against ``command``.

    Uses the same projection logic as :func:`_expand_alternations`: each
    expanded literal is tested as a prefix of ``command`` (after stripping
    leading whitespace).
    """
    cmd = command.lstrip()
    for prefix in _expand_alternations(pattern):
        if cmd.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Projection (design §6.4)
# ---------------------------------------------------------------------------


# Match a single, non-nested ``(a|b|c)`` alternation group.
#
# LIMITATION: this regex deliberately does NOT support nested alternation
# groups such as ``(a|(b|c))`` or ``((x|y)|z)`` — the inner ``[^()|]+``
# class rejects ``(`` and ``)`` inside a choice, so any pattern containing
# nesting is left unexpanded by ``_expand_alternations`` and falls through
# to the regex-class / quantifier short-circuit (returning an empty list,
# which the Bash projection logs and skips). The current ``tiers.toml``
# seed only uses simple flat alternations like ``(master|main)``; if a
# future rule legitimately needs nesting, replace this regex with a
# recursive expander (or reject the seed at load time with a clear error).
_ALTERNATION_RE = re.compile(r"\(([^()|]+(?:\|[^()|]+)+)\)")
_REGEX_CLASS_RE = re.compile(r"\[[^\]]+\]")
_REGEX_QUANTIFIER_RE = re.compile(r"[+*?]\s*$|\.\*|\\[a-zA-Z]")


def _expand_alternations(pattern: str) -> list[str]:
    """Expand simple ``(a|b|c)`` groups into a list of literal strings.

    Returns an empty list if the pattern contains regex constructs we
    cannot safely expand (character classes, quantifiers, escapes).
    """
    if _REGEX_CLASS_RE.search(pattern):
        return []
    if _REGEX_QUANTIFIER_RE.search(pattern):
        return []

    # Find all alternation groups left-to-right.
    groups: list[list[str]] = []
    cursor = 0
    fragments: list[list[str]] = []
    for m in _ALTERNATION_RE.finditer(pattern):
        # Literal lead-in.
        lead = pattern[cursor : m.start()]
        if lead:
            fragments.append([lead])
        # Alternation choices.
        choices = m.group(1).split("|")
        fragments.append(choices)
        cursor = m.end()
    tail = pattern[cursor:]
    if tail:
        fragments.append([tail])

    if not fragments:
        return [pattern]

    # Any non-alternation fragments are single-element lists; itertools.product
    # walks the cartesian product to produce all literal expansions.
    return ["".join(parts) for parts in itertools.product(*fragments)]


def tier_record_to_deny_pattern(record: TierRecord) -> list[str]:
    """Project a :class:`TierRecord` to ``settings.json`` deny patterns.

    Implements the seven cases from design §6.4. Returns an empty list
    (with a warning log) for records that cannot be safely projected
    (regex classes, unknown tools).

    Args:
        record: A tier record. The function does NOT check ``record.tier``
            — callers should pre-filter to T3 records before projecting.

    Returns:
        Zero or more deny patterns suitable for ``permissions.deny``.
    """
    tool = record.tool
    pattern = record.pattern

    # --- Cases 4 & 5: MCP tools (exact and wildcard) -----------------------
    if tool.startswith("mcp__"):
        # Wildcard or exact, the deny pattern IS the tool name verbatim.
        return [tool]

    # --- Case 6: capability tools -----------------------------------------
    if tool in _CAPABILITY_TOOLS:
        return [tool]

    # --- Cases 1, 2, 3: Bash ----------------------------------------------
    if tool == "Bash":
        expansions = _expand_alternations(pattern)
        if not expansions:
            logger.warning(
                "tiers: pattern %r for tool Bash is not projectable to a "
                "literal deny string (regex constructs); skipping deny "
                "derivation. Hook-time enforcement still applies.",
                pattern,
            )
            return []
        return [f"Bash({prefix}:*)" for prefix in expansions]

    # --- Case 7: unknown tool ---------------------------------------------
    logger.warning(
        "tiers: unknown tool %r in tier record %r; cannot project to a deny "
        "pattern. Skipping (hook-time classifier still runs).",
        tool,
        record.description,
    )
    return []


def derive_l2_deny_list(tiers_path: Path) -> list[str]:
    """Read ``tiers.toml`` and return the flat list of T3 deny patterns.

    Used by the installer (``installer/components/permissions.py``) to
    populate ``permissions.deny`` at install time.

    Missing files are tolerated (returns ``[]``); malformed TOML or schema
    errors propagate so the installer fails loudly rather than silently
    skipping the L2 layer.

    Returns:
        Deduplicated list of deny strings, in source order.
    """
    if not tiers_path.exists():
        # Debug, not warning: in normal operation tiers.toml ships in-tree, so a
        # missing file is either a test fixture or a partial install and the
        # caller usually does not care. Operators looking for this case can
        # raise the log level.
        logger.debug(
            "tiers: %s does not exist; L2 deny derivation produced 0 patterns.",
            tiers_path,
        )
        return []

    records = load_tiers(tiers_path)

    out: list[str] = []
    seen: set[str] = set()
    for rec in records:
        if rec.tier != "T3":
            continue
        for pat in tier_record_to_deny_pattern(rec):
            if pat not in seen:
                seen.add(pat)
                out.append(pat)
    return out
