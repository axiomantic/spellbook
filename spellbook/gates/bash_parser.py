"""bashlex AST parser for the PreToolUse Bash gate (WI-6a).

This module is the L4 (AST) layer of the security gate stack. It walks the
``bashlex`` AST and emits deny findings for the categories that a pure
``permissions.allow/deny`` regex cannot represent without false-positive risk:

- Compound commands (``;``, ``&&``, ``||``, ``|``)
- Command substitution (``$(...)``, backticks)
- Process substitution (``<(...)``, ``>(...)``)
- Dangerous redirects (``/dev/tcp/*``, writes to ``/etc/``, ``~/.ssh/*``, etc.)
- Env-prefix escapes (``GIT_PAGER=...``, ``GIT_EXTERNAL_DIFF=...``, ``PAGER=...``)
- Shell-out flags (``find -exec``, ``xargs sh -c``, ``git -c core.pager=``,
  ``git -c alias.X=!``)
- Direct shell invocation (``eval``, ``sh -c``, ``bash -c``, ``source``)
- Wrapper-stripping bypasses (``timeout``, ``nohup``, ``npx``, ...) that
  conceal a dangerous payload

Unknown bashlex node kinds are fail-closed: the parser emits a CRITICAL
``BASH-PARSER-UNKNOWN-NODE`` finding AND appends a JSONL entry to the audit
log so the operator can decide whether to opt the kind in via
``SPELLBOOK_BASH_PARSER_ALLOW``.

The public entry point is :func:`parse_and_check`, which returns a list of
finding dicts in the same shape produced by
:func:`spellbook.gates.rules.check_patterns`. Empty list means the parser
had no objection (later layers in ``check.py`` still run).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from spellbook.core.compat import CrossPlatformLock, LockHeldError

try:
    import bashlex
except ImportError:  # bashlex is a required dep; fail-closed if unavailable.
    bashlex = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


_AUDIT_LOG_PATH: Path = Path.home() / ".local" / "spellbook" / "logs" / "audit.jsonl"


def _audit_log_path() -> Path:
    """Return the on-disk path of the audit log.

    Internal callers use this indirection so tests can mock the path via
    ``tripwire.mock("spellbook.gates.bash_parser:_audit_log_path")`` instead
    of monkey-patching the module-level constant. Reads ``_AUDIT_LOG_PATH``
    dynamically so a runtime override (e.g., a future env-var hook) can mutate
    the constant in-place and have callers pick up the change without restart.
    """
    return _AUDIT_LOG_PATH


def _append_audit(record: dict) -> None:
    """Append one JSON line to the audit log without blocking the gate.

    The log lives at ``~/.local/spellbook/logs/audit.jsonl`` by default. Tests
    mock ``_audit_log_path`` (via tripwire) to redirect writes to a tmp path.

    The audit log runs on every Bash tool invocation. A blocking lock here
    would let any stalled lock-holder hang the security gate, which would
    delay the verdict — unacceptable. We acquire the lock non-blocking; on
    contention we retry once after a short sleep, and on second failure we
    drop the audit entry with a stderr warning. **The security verdict is
    independent of audit-log success**: rare audit-log loss is acceptable;
    delaying the gate is not.
    """
    path = _audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    line = json.dumps(record, separators=(",", ":")) + "\n"

    for attempt in (0, 1):
        try:
            with CrossPlatformLock(lock_path, shared=False, blocking=False):
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(line)
                    fh.flush()
                    os.fsync(fh.fileno())
            return
        except LockHeldError:
            if attempt == 0:
                # Brief backoff, then one retry. Total worst-case latency
                # added to the gate is well under 50ms.
                time.sleep(0.01)
                continue
            # Second failure: drop the audit entry but keep the gate moving.
            try:
                sys.stderr.write(
                    "spellbook.bash_parser: audit log busy; dropping one "
                    f"audit entry (verdict unaffected). path={path}\n"
                )
            except Exception as stderr_exc:  # noqa: BLE001
                # stderr write itself failed (closed/redirected fd). Observe
                # via logger so the failure is at least recorded somewhere,
                # but never propagate — gate verdict must not depend on
                # audit-log diagnostics.
                _log.warning(
                    "audit-log busy stderr-write failed: %s: %s",
                    type(stderr_exc).__name__,
                    stderr_exc,
                )
            return


# ---------------------------------------------------------------------------
# Finding helpers
# ---------------------------------------------------------------------------


def _finding(
    rule_id: str,
    severity: str,
    message: str,
    matched_text: str,
) -> dict:
    """Return a finding dict in the same shape as ``check_patterns``."""
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "matched_text": matched_text,
    }


# ---------------------------------------------------------------------------
# Reject-list tables (design §7 Phase 6a)
# ---------------------------------------------------------------------------


# Env-var names whose use as a command prefix can hijack a tool's helper hook
# (pagers, diff drivers, editors). Match against the ``NAME`` half of an
# AssignmentNode word like ``GIT_PAGER=evil``.
#
# Includes shell-startup-sourced env vars (``BASH_ENV`` for non-interactive
# bash, ``ENV`` for sh/dash/ksh) and language-library-path env vars
# (``PYTHONPATH``, ``PERL5LIB``, ``RUBYLIB``) that allow module-injection
# style hijacks where a script-language process loads attacker-controlled
# code from a directory the attacker prepends.
_ENV_PREFIX_DENY: frozenset[str] = frozenset(
    {
        "GIT_EXTERNAL_DIFF",
        "GIT_PAGER",
        "GIT_SEQUENCE_EDITOR",
        "GIT_EDITOR",
        "LESS",
        "MANPAGER",
        "PAGER",
        "EDITOR",
        "VISUAL",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        # Shell-startup-sourced env vars
        "BASH_ENV",
        "ENV",
        # Language-library-path env vars (module injection)
        "PYTHONPATH",
        "PERL5LIB",
        "RUBYLIB",
        # Cycle-7 F5: additional language-runtime env vars that load
        # attacker-controlled code at process start.
        # * ``NODE_PATH``: prepends a directory to Node's module resolution.
        # * ``PYTHONINSPECT=1``: drops Python into an interactive shell after
        #   the script body runs (post-execution hijack of any Python call).
        # * ``PYTHONBREAKPOINT=mod:fn``: redirects ``breakpoint()`` to call
        #   an attacker module's function.
        # * ``JAVA_TOOL_OPTIONS``: silently injects JVM flags
        #   (``-javaagent:/tmp/evil.jar``) into every java invocation.
        # * ``NODE_OPTIONS``: silently injects Node flags
        #   (``--require=/tmp/evil.js``) into every node invocation.
        "NODE_PATH",
        "PYTHONINSPECT",
        "PYTHONBREAKPOINT",
        "JAVA_TOOL_OPTIONS",
        "NODE_OPTIONS",
    }
)


# Path prefixes (or full paths) that must never appear as a redirect target.
# Compared as substring/prefix against the redirect's destination word.
#
# Includes ``/proc/`` (writes to ``/proc/sys/...`` reconfigure the running
# kernel) and ``/var/spool/cron/`` (writes here install cron jobs that run
# as the file's owner — root-equivalent escape for an unprivileged process
# with write perms via group misconfig).
_REDIRECT_DENY_PREFIXES: tuple[str, ...] = (
    "/dev/tcp/",
    "/dev/udp/",
    "/etc/",
    # Cycle-8 F1: previously a blanket ``/usr/`` deny here. That was overly
    # restrictive: it blocked legitimate writes under ``/usr/local/`` (e.g.
    # installing tools to ``/usr/local/bin``). Narrow the deny to the
    # specific system-managed subdirectories. ``/usr/local/`` is intentionally
    # absent so user-installed tools and Homebrew-style prefixes still work.
    "/usr/bin/",
    "/usr/sbin/",
    "/usr/lib/",
    "/usr/lib64/",
    "/usr/include/",
    "/usr/share/",
    "/usr/libexec/",
    "/boot/",
    "/sys/",
    "/proc/",
    "/var/spool/cron/",
)
_REDIRECT_DENY_SUBSTRINGS: tuple[str, ...] = (
    "/.ssh/",
    "/.aws/",
    "/.config/op/",
    "/.netrc",
    "/.gnupg/",
)


# Wrapper-strip commands. If we encounter one of these as the first word of
# a CommandNode, we treat it as a wrapper around the remaining argv and
# re-classify the wrapped argv. The wrapper itself is "free"; only the
# wrapped command matters.
_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {
        "timeout",
        "nice",
        "nohup",
        "setsid",
        "ionice",
        "stdbuf",
        "unbuffer",
        "env",
        "command",
        "exec",
    }
)


# Wrappers that ALWAYS warrant a finding because they fetch+run untrusted
# code: ``npx`` runs arbitrary npm packages, ``mise exec`` runs arbitrary
# tool versions, ``docker exec`` runs arbitrary containers. We do not have
# an allowlist for the wrapped target, so flag unconditionally.
_WRAPPER_ALWAYS_FLAG: frozenset[str] = frozenset(
    {
        "npx",
        "mise",
        "docker",
    }
)


# Commands that are dangerous when surfaced anywhere (including under a
# wrapper). The wrapper-strip logic re-checks the wrapped argv against this
# set so ``timeout 5 rm -rf /`` flips a WRAPPER finding even though the AST
# walker already would have flagged ``rm -rf`` via the existing regex layer.
_DANGEROUS_BARE_COMMANDS: frozenset[str] = frozenset(
    {
        "rm",
        "rmdir",
        "dd",
        "mkfs",
        "shred",
        "curl",
        "wget",
        "nc",
        "ncat",
        "socat",
        "telnet",
        "ssh",
        "scp",
        "rsync",
        "chmod",
        "chown",
        "chgrp",
        "setfacl",
    }
)


# Direct-shell-invocation commands. ``eval`` and ``sh -c`` / ``bash -c``
# obviously execute arbitrary code; ``source`` sources a file into the
# current shell, which equally lets the file run anything.
_DIRECT_SHELL_COMMANDS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",  # exec with a string arg is shell-flavored too
        "source",
        ".",
        "sh",
        "bash",
        "zsh",
        "ksh",
        "dash",
        "fish",
        "tcsh",
        "csh",
    }
)


# Subset that requires the ``-c`` flag to qualify as direct-shell. ``sh`` /
# ``bash`` alone (interactive) is fine; ``sh -c "rm -rf /"`` is not.
_SHELL_BINS_NEED_DASH_C: frozenset[str] = frozenset(
    {"sh", "bash", "zsh", "ksh", "dash", "fish", "tcsh", "csh"}
)


# Allowlist for ``source`` / ``.`` targets. Empty by default — the test
# suite expects ``source /tmp/evil.sh`` to deny. Operators can extend via
# the env-escape-hatch if a workflow legitimately needs it.
_SOURCE_ALLOW_PREFIXES: tuple[str, ...] = ()


# Bashlex node kinds we explicitly handle. Any other kind fails closed.
_KNOWN_NODE_KINDS: frozenset[str] = frozenset(
    {
        "list",
        "pipeline",
        "compound",
        "command",
        "commandsubstitution",
        "processsubstitution",
        "redirect",
        "assignment",
        "word",
        "operator",
        "pipe",
        "reservedword",
        "parameter",
        "tilde",
        "heredoc",
        "if",
        "for",
        "while",
        "until",
        "case",
        "function",
    }
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_and_check(command: str, security_mode: str = "paranoid") -> list[dict]:
    """Parse ``command`` with bashlex and emit deny findings.

    Args:
        command: The raw Bash tool invocation string.
        security_mode: ``"standard"`` or ``"paranoid"`` (matches
            :mod:`spellbook.gates.rules`). The bashlex parser treats both
            equally — every category is paranoid by design — but the
            argument is preserved for symmetry with ``check_patterns``.

    Returns:
        List of finding dicts. Empty list = no parser objection.
    """
    if not command or not command.strip():
        return []

    if bashlex is None:
        # bashlex import failed at module load. Fail closed so the gate denies
        # every Bash call until the operator restores the dep.
        return [
            _finding(
                "BASH-PARSER-UNAVAILABLE",
                "CRITICAL",
                "bashlex parser is not installed; failing closed.",
                command,
            )
        ]

    try:
        trees = bashlex.parse(command)
    except Exception as exc:  # noqa: BLE001 — bashlex raises a family of errors
        return [
            _finding(
                "BASH-PARSER-PARSE-ERROR",
                "CRITICAL",
                f"bashlex failed to parse command: {type(exc).__name__}: {exc}",
                command,
            )
        ]

    findings: list[dict] = []
    for tree in trees:
        findings.extend(_walk(tree, command))
    return findings


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------


def _walk(node: object, command: str) -> list[dict]:
    """Recursively classify ``node`` and its children.

    Top-level dispatch sits in :func:`_classify_node` so the test suite can
    drive the unknown-node fail-closed path with a synthetic node.
    """
    findings: list[dict] = []
    findings.extend(_classify_node(node))

    # Recurse into children in a kind-aware manner so we do not double-count
    # parent findings or miss nested substitutions.
    kind = getattr(node, "kind", None)

    if kind in {"list", "pipeline"}:
        for child in getattr(node, "parts", ()) or ():
            child_kind = getattr(child, "kind", None)
            # Operators and pipes are leaves; nothing to recurse into.
            if child_kind in {"operator", "pipe", "reservedword"}:
                continue
            findings.extend(_walk(child, command))
    elif kind == "compound":
        # CompoundNode wraps control-flow constructs (if/for/while/until/case
        # and function bodies). The wrapped construct(s) live under ``.list``,
        # NOT ``.parts`` — without recursing into ``.list`` the walker would
        # silently skip every nested command, providing a clean bypass for
        # ``while true; do rm -rf /; done`` and similar.
        for child in getattr(node, "list", ()) or ():
            findings.extend(_walk(child, command))
    elif kind == "command":
        # Command parts contain Words (with possibly nested commandsub /
        # processsub), Assignments, and Redirects. We classified the
        # command itself in _classify_node; recurse into substitutions and
        # redirects so nested command-sub / proc-sub / redirect-on-/etc
        # are caught even when the outer command alone looked fine.
        for part in getattr(node, "parts", ()) or ():
            part_kind = getattr(part, "kind", None)
            if part_kind == "word":
                # Words can hold nested commandsubstitution /
                # processsubstitution under .parts.
                for sub in getattr(part, "parts", ()) or ():
                    findings.extend(_walk(sub, command))
            elif part_kind == "redirect":
                # Classify the redirect itself (deny-list path check), THEN
                # recurse into its output target — a WordNode whose ``.parts``
                # may contain a CommandsubstitutionNode (``ls > $(whoami).txt``).
                findings.extend(_classify_node(part))
                output = getattr(part, "output", None)
                if output is not None:
                    for sub in getattr(output, "parts", ()) or ():
                        findings.extend(_walk(sub, command))
            elif part_kind == "assignment":
                # Classify the env-prefix itself, THEN recurse into the
                # assignment's parts so a CMDSUB inside the value
                # (``VAR=$(whoami) ls``) is detected.
                findings.extend(_classify_node(part))
                for sub in getattr(part, "parts", ()) or ():
                    findings.extend(_walk(sub, command))
            else:
                findings.extend(_walk(part, command))
    elif kind in {"commandsubstitution", "processsubstitution"}:
        inner = getattr(node, "command", None)
        if inner is not None:
            findings.extend(_walk(inner, command))
    elif kind in {"if", "for", "while", "until", "case", "function"}:
        for child in getattr(node, "parts", ()) or ():
            child_kind = getattr(child, "kind", None)
            if child_kind in {"operator", "pipe", "reservedword"}:
                continue
            findings.extend(_walk(child, command))
    elif kind == "word":
        # Top-level / orphaned WordNode: walk its parts so a command-sub
        # inside (``echo prefix$(whoami)suffix``) is still detected when
        # the parent walker forwarded the word directly.
        for sub in getattr(node, "parts", ()) or ():
            findings.extend(_walk(sub, command))

    return findings


# ---------------------------------------------------------------------------
# Single-node classification (used by the walker AND directly by tests)
# ---------------------------------------------------------------------------


def _classify_node(node: object) -> list[dict]:
    """Emit findings for a single AST node based on its ``kind``.

    Unknown kinds fail closed with an audit-log entry, unless the operator
    has explicitly opted them in via ``SPELLBOOK_BASH_PARSER_ALLOW``.
    """
    kind = getattr(node, "kind", None)

    if kind in {"list", "pipeline"}:
        return _classify_compound(node)
    if kind in {"if", "for", "while", "until", "case"}:
        # Control-flow constructs are inherently compound (a body, not a
        # single command). Emit BASH-PARSER-COMPOUND so the operator must
        # split into separate Bash invocations or opt in via the env
        # escape hatch. The walker still recurses into the construct's
        # body so any nested CMDSUB / dangerous redirect is also surfaced.
        return [
            _finding(
                "BASH-PARSER-COMPOUND",
                "CRITICAL",
                f"Compound control-flow construct (`{kind}`) is not allowed; "
                "split into separate Bash invocations.",
                _node_text(node),
            )
        ]
    if kind == "command":
        return _classify_command(node)
    if kind == "commandsubstitution":
        return [
            _finding(
                "BASH-PARSER-CMDSUB",
                "CRITICAL",
                "Command substitution ($(...) or backticks) is not allowed.",
                _node_text(node),
            )
        ]
    if kind == "processsubstitution":
        return [
            _finding(
                "BASH-PARSER-PROCSUB",
                "CRITICAL",
                "Process substitution (<(...) or >(...)) is not allowed.",
                _node_text(node),
            )
        ]
    if kind == "redirect":
        return _classify_redirect(node)
    if kind == "assignment":
        return _classify_assignment(node)
    if kind in _KNOWN_NODE_KINDS:
        # Other known kinds are structural (word, operator, pipe, etc.) and
        # produce no finding by themselves. Their interesting content is
        # surfaced by the walker.
        return []

    # Unknown kind — fail-closed (or honor the env escape hatch).
    return _handle_unknown_kind(node, kind)


# ---------------------------------------------------------------------------
# Compound (list / pipeline)
# ---------------------------------------------------------------------------


def _classify_compound(node: object) -> list[dict]:
    parts = getattr(node, "parts", ()) or ()
    # A ListNode that wraps a single command followed by a trailing ``&``
    # operator is "background this command" — semantically a single command,
    # not a chain. Don't emit COMPOUND for that; let the walker still recurse
    # into the command itself.
    #
    # SECURITY: ``ls & pwd`` parses as a ListNode with parts
    # [command, operator(&), command] — i.e., operators == ["&"] but TWO
    # command parts. Treating that as "single bg command" lets the second
    # command slip past the compound check. Require exactly one command part
    # before short-circuiting.
    operators = [
        getattr(p, "op", None)
        for p in parts
        if getattr(p, "kind", None) == "operator"
    ]
    command_parts = [p for p in parts if getattr(p, "kind", None) == "command"]
    if (
        getattr(node, "kind", None) == "list"
        and operators == ["&"]
        and len(command_parts) == 1
    ):
        # Single-command background — not actually a compound chain.
        return []

    op_text = ", ".join(op for op in operators if op) or "|"
    return [
        _finding(
            "BASH-PARSER-COMPOUND",
            "CRITICAL",
            f"Compound command ({op_text}) is not allowed; "
            "split into separate Bash invocations.",
            _node_text(node),
        )
    ]


# ---------------------------------------------------------------------------
# Command (the busiest case)
# ---------------------------------------------------------------------------


def _classify_command(node: object) -> list[dict]:
    """Classify a CommandNode: env prefix, direct-shell, shell-out, wrapper."""
    findings: list[dict] = []

    parts = list(getattr(node, "parts", ()) or ())
    words = [p for p in parts if getattr(p, "kind", None) == "word"]
    word_strs = [getattr(w, "word", "") for w in words]

    if not word_strs:
        # All-assignment command (e.g. ``FOO=bar``). Assignment classifier
        # handles this via the walker recursion.
        return findings

    head = word_strs[0]
    rest = word_strs[1:]
    # Normalize the command head via basename so absolute paths like
    # ``/bin/sh`` and ``/usr/bin/env`` are matched against our inventories
    # the same way as bare ``sh`` / ``env``. Without this, an attacker can
    # bypass DIRECT-SHELL / SHELLOUT / WRAPPER checks by spelling the
    # binary with a path prefix.
    head_base = os.path.basename(head)

    # --- Direct shell invocation ---------------------------------------
    if head_base in _DIRECT_SHELL_COMMANDS:
        if head_base in _SHELL_BINS_NEED_DASH_C:
            if "-c" in rest:
                findings.append(
                    _finding(
                        "BASH-PARSER-DIRECT-SHELL",
                        "CRITICAL",
                        f"Direct shell invocation ({head_base} -c ...) is not allowed.",
                        _node_text(node),
                    )
                )
                return findings
        elif head_base in {"source", "."}:
            target = rest[0] if rest else ""
            if not _source_target_allowed(target):
                findings.append(
                    _finding(
                        "BASH-PARSER-DIRECT-SHELL",
                        "CRITICAL",
                        f"`{head_base}` of non-allowlisted file is not allowed.",
                        _node_text(node),
                    )
                )
                return findings
        else:
            # eval, exec-as-string
            findings.append(
                _finding(
                    "BASH-PARSER-DIRECT-SHELL",
                    "CRITICAL",
                    f"Direct shell invocation ({head_base}) is not allowed.",
                    _node_text(node),
                )
            )
            return findings

    # --- Shell-out flags -----------------------------------------------
    shellout = _detect_shellout(head_base, rest)
    if shellout is not None:
        findings.append(shellout)
        # Don't return; a shellout may also be wrapped, but one finding is
        # enough to block the call.
        return findings

    # --- Wrapper-stripping bypass --------------------------------------
    if head_base in _WRAPPER_ALWAYS_FLAG:
        findings.append(
            _finding(
                "BASH-PARSER-WRAPPER",
                "CRITICAL",
                f"Wrapper `{head_base}` runs untrusted code; not allowed without "
                "explicit per-target allowlist.",
                _node_text(node),
            )
        )
        return findings

    if head_base in _WRAPPER_COMMANDS:
        wrapped = _strip_wrapper_args(head_base, rest)
        if wrapped:
            # Normalize wrapped head too so ``timeout 5 /bin/sh -c ...``
            # cannot bypass the wrapped-direct-shell check.
            wrapped_head_raw = wrapped[0]
            wrapped_head = os.path.basename(wrapped_head_raw)
            if wrapped_head in _DANGEROUS_BARE_COMMANDS:
                findings.append(
                    _finding(
                        "BASH-PARSER-WRAPPER",
                        "CRITICAL",
                        f"Wrapper `{head_base}` conceals dangerous command "
                        f"`{wrapped_head}`; not allowed.",
                        _node_text(node),
                    )
                )
                return findings
            if wrapped_head in _DIRECT_SHELL_COMMANDS:
                findings.append(
                    _finding(
                        "BASH-PARSER-WRAPPER",
                        "CRITICAL",
                        f"Wrapper `{head_base}` conceals shell invocation "
                        f"`{wrapped_head}`; not allowed.",
                        _node_text(node),
                    )
                )
                return findings
            if wrapped_head in _WRAPPER_ALWAYS_FLAG:
                findings.append(
                    _finding(
                        "BASH-PARSER-WRAPPER",
                        "CRITICAL",
                        f"Wrapper `{head_base}` conceals untrusted-runner "
                        f"`{wrapped_head}`; not allowed.",
                        _node_text(node),
                    )
                )
                return findings

    return findings


# Per-wrapper flag tables. Cycle-7 F1/F2: a flag-blind "skip everything that
# starts with ``-``" loop misses bypasses where a flag takes a SEPARATE arg —
# ``timeout -s KILL 5 rm -rf /`` would treat ``KILL`` as the wrapped head and
# miss ``rm -rf /``. The tables below explicitly enumerate which flags consume
# the next argv slot vs which are standalone, so we can advance argv correctly.
#
# Long-form ``--flag=VALUE`` always consumes only one slot (the equals form
# embeds the value), so they appear in the standalone set.

# ``timeout(1)`` flags. Source: GNU coreutils manpage.
_TIMEOUT_FLAGS_WITH_ARG: frozenset[str] = frozenset(
    {"-s", "--signal", "-k", "--kill-after"}
)
_TIMEOUT_FLAGS_NO_ARG: frozenset[str] = frozenset(
    {"-v", "--verbose", "--preserve-status", "--foreground"}
)

# ``env(1)`` flags. Source: GNU coreutils manpage.
_ENV_FLAGS_WITH_ARG: frozenset[str] = frozenset(
    {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
)
_ENV_FLAGS_NO_ARG: frozenset[str] = frozenset(
    {"-i", "--ignore-environment", "-0", "--null"}
)


def _strip_wrapper_args(wrapper: str, argv: list[str]) -> list[str]:
    """Skip wrapper-specific option args to reach the wrapped argv.

    Each wrapper has its own option grammar. A flag-blind loop (drop every
    leading ``-``-prefixed token) is unsafe: flags that take a SEPARATE
    argument let the attacker push the dangerous head past our scan. For
    ``timeout`` and ``env`` we use explicit per-flag tables (see
    ``_TIMEOUT_FLAGS_WITH_ARG`` and ``_ENV_FLAGS_WITH_ARG``). For every other
    wrapper we keep the conservative best-effort dash/numeric skip.
    """
    out: deque[str] = deque(argv)

    if wrapper == "timeout":
        _strip_timeout_args(out)
    elif wrapper == "env":
        _strip_env_args(out)
    else:
        # Conservative legacy path for the other wrappers (``nice``, ``nohup``,
        # ``setsid``, ``ionice``, ``stdbuf``, ``unbuffer``, ``command``, ``exec``).
        # Drop leading dash-flags and a leading numeric/duration, then stop.
        while out:
            head = out[0]
            if head.startswith("-"):
                out.popleft()
                continue
            if head.rstrip("smhd").replace(".", "", 1).isdigit():
                out.popleft()
                continue
            break

    return list(out)


def _strip_timeout_args(out: deque[str]) -> None:
    """Consume ``timeout``'s flag/positional grammar in place.

    Grammar: ``timeout [OPTION]... DURATION COMMAND [ARG]...``

    Options handled:
      * ``-s SIGNAL`` / ``--signal SIGNAL`` (separate-arg)
      * ``-k DURATION`` / ``--kill-after DURATION`` (separate-arg)
      * ``-v`` / ``--verbose`` / ``--preserve-status`` / ``--foreground`` (no-arg)
      * ``--signal=SIG`` / ``--kill-after=10`` (equals form, single slot)

    After flags, exactly one DURATION positional is consumed (numeric with
    optional ``s``/``m``/``h``/``d`` suffix).
    """
    while out:
        head = out[0]
        if head in _TIMEOUT_FLAGS_WITH_ARG:
            # Two-slot consume: flag + arg. If the arg is missing (malformed
            # input) just stop — we cannot guess where the wrapped argv begins.
            out.popleft()
            if out:
                out.popleft()
            continue
        if head in _TIMEOUT_FLAGS_NO_ARG:
            out.popleft()
            continue
        if head.startswith("--") and "=" in head:
            # ``--signal=KILL`` etc. — single-slot, value embedded.
            out.popleft()
            continue
        if head.startswith("-") and len(head) > 1 and not head[1:].isdigit():
            # Unknown short/long flag — best-effort drop. Avoids treating a
            # bare numeric like ``-5`` as a flag.
            out.popleft()
            continue
        break

    # DURATION positional (e.g. ``5``, ``1h``, ``2d``, ``1.5m``).
    if out:
        head = out[0]
        if head.rstrip("smhd").replace(".", "", 1).isdigit():
            out.popleft()


def _strip_env_args(out: deque[str]) -> None:
    """Consume ``env``'s flag and KEY=VALUE prefix grammar in place.

    Grammar: ``env [OPTION]... [-] [NAME=VALUE]... [COMMAND [ARG]...]``

    Options handled:
      * ``-u VAR`` / ``--unset VAR`` (separate-arg)
      * ``-C DIR`` / ``--chdir DIR`` (separate-arg)
      * ``-S STR`` / ``--split-string STR`` (separate-arg)
      * ``-i`` / ``--ignore-environment`` / ``-0`` / ``--null`` (no-arg)
      * ``--unset=VAR`` / ``--chdir=DIR`` / ``--split-string=STR`` (equals form)

    After flags, ``KEY=VALUE`` env-prefix pairs are consumed (env's purpose
    is setting vars). The remaining argv is the wrapped command.
    """
    while out:
        head = out[0]
        if head in _ENV_FLAGS_WITH_ARG:
            out.popleft()
            if out:
                out.popleft()
            continue
        if head in _ENV_FLAGS_NO_ARG:
            out.popleft()
            continue
        if head.startswith("--") and "=" in head:
            # ``--unset=VAR``, ``--chdir=DIR``, ``--split-string=...``.
            out.popleft()
            continue
        if head == "-":
            # POSIX ``env -`` separator: same effect as ``-i``.
            out.popleft()
            continue
        if head.startswith("-") and len(head) > 1 and not head[1:].isdigit():
            # Unknown flag — best-effort drop.
            out.popleft()
            continue
        break

    # KEY=VALUE env-prefix pairs. ``env FOO=bar BAZ=qux cmd``.
    while out and "=" in out[0] and not out[0].startswith("/"):
        out.popleft()


def _detect_shellout(head: str, rest: list[str]) -> dict | None:
    """Return a SHELLOUT finding if ``head rest...`` matches a known pattern."""
    if head == "find" and "-exec" in rest:
        return _finding(
            "BASH-PARSER-SHELLOUT",
            "CRITICAL",
            "`find -exec` runs an arbitrary command per match; not allowed.",
            f"{head} {' '.join(rest)}",
        )
    if head == "find" and "-execdir" in rest:
        return _finding(
            "BASH-PARSER-SHELLOUT",
            "CRITICAL",
            "`find -execdir` runs an arbitrary command per match; not allowed.",
            f"{head} {' '.join(rest)}",
        )
    if head == "find" and "-ok" in rest:
        # ``-ok`` is the interactive variant of ``-exec`` — it prompts y/n
        # before each invocation. Autonomous agents auto-confirm, so this
        # is exactly as dangerous as ``-exec`` in our threat model.
        return _finding(
            "BASH-PARSER-SHELLOUT",
            "CRITICAL",
            "`find -ok` runs an arbitrary command per match (auto-confirmed); not allowed.",
            f"{head} {' '.join(rest)}",
        )
    if head == "find" and "-okdir" in rest:
        return _finding(
            "BASH-PARSER-SHELLOUT",
            "CRITICAL",
            "`find -okdir` runs an arbitrary command per match (auto-confirmed); not allowed.",
            f"{head} {' '.join(rest)}",
        )
    if head == "xargs":
        # xargs with sh/bash-c is the classic shell-out. Normalize each
        # token via basename so ``xargs /bin/sh -c ...`` is caught the
        # same as ``xargs sh -c ...``.
        for i, tok in enumerate(rest):
            if os.path.basename(tok) in _SHELL_BINS_NEED_DASH_C:
                return _finding(
                    "BASH-PARSER-SHELLOUT",
                    "CRITICAL",
                    "`xargs` driving a shell is not allowed.",
                    f"{head} {' '.join(rest)}",
                )
            if tok == "-I" and i + 2 < len(rest):
                # ``xargs -I {} sh -c ...`` already covered by the sh-bin
                # check above. Keep this explicit branch for clarity.
                continue
    if head == "awk":
        # ``awk 'system(...)'`` — match the system( token in any arg.
        for tok in rest:
            if "system(" in tok:
                return _finding(
                    "BASH-PARSER-SHELLOUT",
                    "CRITICAL",
                    "`awk system(...)` is not allowed.",
                    f"{head} {' '.join(rest)}",
                )
    if head == "git":
        # ``git -c core.pager=...`` and ``git -c alias.X=!...`` hijack hooks.
        # Git config keys are CASE-INSENSITIVE (``Core.Pager`` and ``CoRe.PaGeR``
        # both reach the same setting), so attackers can bypass a case-sensitive
        # check with mixed-case spellings. Lowercase only the KEY half — the
        # VALUE may legitimately be case-sensitive (paths, commands).
        for i, tok in enumerate(rest):
            if tok == "-c" and i + 1 < len(rest):
                cfg = rest[i + 1]
                if "=" in cfg:
                    key, value = cfg.split("=", 1)
                else:
                    key, value = cfg, ""
                key_lower = key.lower()
                cfg_normalized = (
                    f"{key_lower}={value}" if "=" in cfg else key_lower
                )
                if cfg_normalized.startswith("core.pager=") or cfg_normalized.startswith("pager."):
                    return _finding(
                        "BASH-PARSER-SHELLOUT",
                        "CRITICAL",
                        "`git -c core.pager=...` is not allowed (hook hijack).",
                        f"{head} {' '.join(rest)}",
                    )
                if cfg_normalized.startswith("alias.") and "=!" in cfg_normalized:
                    return _finding(
                        "BASH-PARSER-SHELLOUT",
                        "CRITICAL",
                        "`git -c alias.X=!...` is not allowed (alias bang hijack).",
                        f"{head} {' '.join(rest)}",
                    )
                if cfg_normalized.startswith("core.editor=") or cfg_normalized.startswith(
                    "core.sshcommand="
                ):
                    return _finding(
                        "BASH-PARSER-SHELLOUT",
                        "CRITICAL",
                        f"`git -c {key_lower}=...` is not allowed.",
                        f"{head} {' '.join(rest)}",
                    )
    if head in {"less", "more"}:
        for tok in rest:
            if tok.startswith("+") and "!" in tok:
                return _finding(
                    "BASH-PARSER-SHELLOUT",
                    "CRITICAL",
                    f"`{head} +'!...'` is not allowed.",
                    f"{head} {' '.join(rest)}",
                )
    if head == "vim" or head == "vi":
        for i, tok in enumerate(rest):
            # ``vim -c '!cmd'`` — startup ex-command shell-out.
            if tok == "-c" and i + 1 < len(rest) and "!" in rest[i + 1]:
                return _finding(
                    "BASH-PARSER-SHELLOUT",
                    "CRITICAL",
                    f"`{head} -c '!...'` is not allowed.",
                    f"{head} {' '.join(rest)}",
                )
            # ``vim --cmd '!cmd'`` — pre-init ex-command shell-out, runs
            # before vimrc loads.
            if tok == "--cmd" and i + 1 < len(rest) and "!" in rest[i + 1]:
                return _finding(
                    "BASH-PARSER-SHELLOUT",
                    "CRITICAL",
                    f"`{head} --cmd '!...'` is not allowed.",
                    f"{head} {' '.join(rest)}",
                )
            # ``vim '+!cmd'`` / ``vim +!sh`` — the ``+`` startup-command
            # form is functionally equivalent to ``-c``; a leading ``+``
            # followed by a body containing ``!`` runs a shell command at
            # startup.
            if tok.startswith("+") and "!" in tok:
                return _finding(
                    "BASH-PARSER-SHELLOUT",
                    "CRITICAL",
                    f"`{head} '+!...'` is not allowed.",
                    f"{head} {' '.join(rest)}",
                )
    if head == "parallel":
        return _finding(
            "BASH-PARSER-SHELLOUT",
            "CRITICAL",
            "`parallel` runs arbitrary commands; not allowed.",
            f"{head} {' '.join(rest)}",
        )
    return None


# ---------------------------------------------------------------------------
# Redirect
# ---------------------------------------------------------------------------


def _classify_redirect(node: object) -> list[dict]:
    output = getattr(node, "output", None)
    target = getattr(output, "word", "") if output is not None else ""
    if not target:
        return []

    # SECURITY: an attacker can defeat a naïve ``startswith`` check with
    # path traversal (``> /tmp/../etc/passwd``) or tilde-traversal
    # (``> ~/../../etc/shadow``). Build a set of candidate strings so the
    # deny list matches all of:
    #
    #   - the raw target verbatim — matters for logical paths like
    #     ``/dev/tcp/...`` and ``/proc/...`` that don't survive ``resolve()``,
    #   - the lexically-normalized target (``os.path.normpath`` after
    #     ``expanduser``) — collapses ``..`` segments WITHOUT following
    #     symlinks, so the deny list still matches the canonical form on
    #     systems where the prefix itself is a symlink (e.g. macOS
    #     ``/etc`` → ``/private/etc``, where ``Path.resolve()`` would
    #     rewrite the prefix and bypass our string match),
    #   - the fully resolved target (``Path.resolve(strict=False)``) — a
    #     belt-and-suspenders catch for cases where the lexical form
    #     differs from the resolved form in the attacker's favor.
    candidates: list[str] = [target]

    expanded = os.path.expanduser(target)
    candidates.append(os.path.normpath(expanded))

    try:
        resolved = str(Path(target).expanduser().resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        # Pathological input (e.g., NUL byte). The raw + normpath candidates
        # are still in play.
        resolved = ""
    if resolved:
        candidates.append(resolved)

    # On Windows, ``os.path.normpath`` and ``Path.resolve`` emit backslashes
    # while the deny prefixes are POSIX-style (``/etc/``, ``/proc/``). Fold
    # each candidate to forward slashes so the prefix match works on both
    # platforms — the gate's threat model is shell redirection, which is a
    # POSIX construct regardless of host OS. Also strip any drive letter
    # (``C:``) so a tilde-traversal target like ``~/../../etc/shadow``
    # which expanduser turns into ``C:\Users\...\..\..\etc\shadow`` and
    # normpath collapses to ``C:\etc\shadow`` still matches ``/etc/``.
    expanded_candidates: list[str] = []
    for c in tuple(candidates):
        slashed = c.replace("\\", "/")
        expanded_candidates.append(slashed)
        _, no_drive = os.path.splitdrive(slashed)
        if no_drive != slashed:
            expanded_candidates.append(no_drive)
    candidates.extend(expanded_candidates)

    for candidate in candidates:
        # Cycle-7 F3: each entry in ``_REDIRECT_DENY_PREFIXES`` ends with a
        # trailing ``/`` so a child path (``/etc/passwd``) matches. But that
        # leaves the bare directory itself (``/etc``) — i.e., redirecting
        # *onto* the directory — uncovered. Match either the prefix verbatim
        # OR the prefix with its trailing slash stripped, so both ``> /etc``
        # and ``> /etc/foo`` deny.
        if any(
            candidate.startswith(p) or candidate == p.rstrip("/")
            for p in _REDIRECT_DENY_PREFIXES
        ):
            return [
                _finding(
                    "BASH-PARSER-REDIRECT",
                    "CRITICAL",
                    f"Redirect to forbidden path `{target}` is not allowed.",
                    target,
                )
            ]
        if any(s in candidate for s in _REDIRECT_DENY_SUBSTRINGS):
            return [
                _finding(
                    "BASH-PARSER-REDIRECT",
                    "CRITICAL",
                    f"Redirect to forbidden path `{target}` is not allowed.",
                    target,
                )
            ]
    return []


# ---------------------------------------------------------------------------
# Assignment (env prefix)
# ---------------------------------------------------------------------------


def _classify_assignment(node: object) -> list[dict]:
    word = getattr(node, "word", "")
    if not word or "=" not in word:
        return []
    name = word.split("=", 1)[0]
    if name in _ENV_PREFIX_DENY:
        return [
            _finding(
                "BASH-PARSER-ENVPREFIX",
                "CRITICAL",
                f"Env prefix `{name}=...` can hijack tool helpers; not allowed.",
                word,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Unknown-kind handling
# ---------------------------------------------------------------------------


def _handle_unknown_kind(node: object, kind: object) -> list[dict]:
    """Either fail-closed with audit-log entry, or honor the env escape hatch."""
    allowlist = _env_allowlist()
    record_base = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": "Bash",
        "layer": "L4-bashlex",
        "node_type": str(kind),
        "node_repr": _node_repr(node),
    }
    if str(kind) in allowlist:
        record = {
            **record_base,
            "verdict": "allow",
            "reason": "unknown_ast_node_allowed_via_env",
        }
        try:
            _append_audit(record)
        except Exception as exc:  # noqa: BLE001
            # Audit-log failure must NOT crash the gate; we still return [].
            # Observe via logger so an operator chasing missing audit lines
            # has a breadcrumb; verdict (allow) is unchanged.
            _log.warning(
                "audit-log append failed for allow-via-env unknown-kind %r: %s: %s",
                kind,
                type(exc).__name__,
                exc,
            )
        return []

    record = {
        **record_base,
        "verdict": "deny",
        "reason": "unknown_ast_node_type",
    }
    try:
        _append_audit(record)
    except Exception as exc:  # noqa: BLE001
        # Audit-log failure must NOT crash the gate; the deny finding is
        # still returned below. Observe so the silent loss is traceable.
        _log.warning(
            "audit-log append failed for deny unknown-kind %r: %s: %s",
            kind,
            type(exc).__name__,
            exc,
        )
    return [
        _finding(
            "BASH-PARSER-UNKNOWN-NODE",
            "CRITICAL",
            f"Unknown bashlex AST node kind `{kind}`; failing closed.",
            _node_repr(node),
        )
    ]


def _env_allowlist() -> frozenset[str]:
    raw = os.environ.get("SPELLBOOK_BASH_PARSER_ALLOW", "")
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source_target_allowed(target: str) -> bool:
    if not target:
        return False
    return any(target.startswith(p) for p in _SOURCE_ALLOW_PREFIXES)


def _node_text(node: object) -> str:
    """Best-effort textual representation for evidence in findings."""
    word = getattr(node, "word", None)
    if isinstance(word, str) and word:
        return word
    parts = getattr(node, "parts", None)
    if parts:
        out = []
        for p in parts:
            t = _node_text(p)
            if t:
                out.append(t)
        if out:
            return " ".join(out)
    kind = getattr(node, "kind", None)
    return f"<{kind}>" if kind else repr(node)


def _node_repr(node: object) -> str:
    kind = getattr(node, "kind", None)
    pos = getattr(node, "pos", None)
    return f"kind={kind!r} pos={pos!r}"
