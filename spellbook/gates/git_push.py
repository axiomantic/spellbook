"""Programmatic ``git push`` pre-pass for the tier classifier.

Replaces the catch-all ``git push`` T2 row in ``tiers.toml`` with a
config-driven classifier that asks only when the push targets a
protected branch on a recognized remote. See the design doc
(``docs/.../2026-05-16-narrow-git-push-protected-branches-design.md``)
for the full architecture rationale.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


#: Sentinel token. When env var equals exactly ``__disable__`` after
#: comma-split + strip, protection on that axis is disabled entirely.
_DISABLE_SENTINEL: str = "__disable__"

_DEFAULT_BRANCHES: tuple[str, ...] = ("master", "main")
_DEFAULT_REMOTES: frozenset[str] = frozenset({"origin", "upstream"})

_PROTECTED_KEYS: frozenset[str] = frozenset({"branches", "remotes"})

_ENV_BRANCHES = "SPELLBOOK_PROTECTED_BRANCHES"
_ENV_REMOTES = "SPELLBOOK_PROTECTED_REMOTES"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProtectedConfig:
    """Resolved (TOML + env overlay) protected-branch / remote config.

    Attributes:
        branches: Tuple of ``fnmatchcase`` patterns. Empty tuple means
            "no branches are protected" (sentinel-disabled axis).
        remotes: Frozenset of exact remote names. Empty frozenset means
            "no remotes are recognised" (sentinel-disabled axis).
    """

    branches: tuple[str, ...]
    remotes: frozenset[str]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _parse_env_list(env_name: str) -> tuple[str, ...] | None:
    """Parse a comma-separated env-var override.

    Returns:
        - ``None`` when env var is unset OR empty after strip (caller
          falls back to TOML/default).
        - ``()`` (empty tuple) when env var is exactly ``__disable__``
          (caller disables that axis).
        - A non-empty tuple of stripped, non-empty elements otherwise.

    Raises:
        ValueError when ``__disable__`` is mixed with other tokens.
    """
    raw = os.environ.get(env_name, "")
    if not raw.strip():
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if _DISABLE_SENTINEL in parts:
        if len(parts) != 1:
            raise ValueError(
                f"{env_name}: {_DISABLE_SENTINEL} must be alone; got {parts!r}"
            )
        return ()
    return tuple(parts)


@lru_cache(maxsize=1)
def load_protected_config(toml_path: Path) -> ProtectedConfig:
    """Load the ``[protected]`` table from ``tiers.toml`` and overlay env vars.

    Precedence (lowest → highest):
      hardcoded fallback (``_DEFAULT_*``)  ←  TOML ``[protected]``  ←  env var

    Args:
        toml_path: Path to ``tiers.toml`` (or a test fixture).

    Returns:
        Resolved :class:`ProtectedConfig`.

    Raises:
        ValueError on unknown nested keys, wrong value types, or
        malformed env-var content.

    Caching:
        ``lru_cache(maxsize=1)`` — tests must call
        :func:`_reset_caches` between cases that mutate env vars or
        on-disk TOML content. In long-lived processes (e.g. the
        spellbook hook daemon), config changes to ``tiers.toml`` or
        the ``SPELLBOOK_PROTECTED_*`` env vars require a process
        restart or an explicit ``_reset_caches()`` call to take effect.
    """
    branches: tuple[str, ...] = _DEFAULT_BRANCHES
    remotes: frozenset[str] = _DEFAULT_REMOTES

    # --- TOML layer ---------------------------------------------------------
    try:
        text = toml_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Common case: no tiers.toml on disk; rely on defaults + env overlay.
        text = ""
    except OSError as exc:
        # PermissionError and other OSError subclasses must not crash
        # the gate mid-classification — treat any read failure as "no
        # TOML layer present" and fall through to defaults + env overlay.
        # Unlike FileNotFoundError, these are unexpected and worth
        # surfacing so operators can diagnose.
        logger.warning(
            "Failed to read %s for [protected] config: %s; falling back to defaults",
            toml_path, exc,
        )
        text = ""
    if text:
        data = tomllib.loads(text)
        protected_raw = data.get("protected")
        if protected_raw is not None:
            if not isinstance(protected_raw, dict):
                raise ValueError(
                    f"{toml_path}: [protected] must be a table, got "
                    f"{type(protected_raw).__name__}"
                )
            unknown = set(protected_raw.keys()) - _PROTECTED_KEYS
            if unknown:
                raise ValueError(
                    f"{toml_path}: [protected] unknown keys {sorted(unknown)}; "
                    f"allowed: {sorted(_PROTECTED_KEYS)}"
                )
            if "branches" in protected_raw:
                b = protected_raw["branches"]
                if not isinstance(b, list) or not all(isinstance(x, str) for x in b):
                    raise ValueError(
                        f"{toml_path}: [protected].branches must be a list of "
                        f"strings, got {b!r}"
                    )
                branches = tuple(b)
            if "remotes" in protected_raw:
                r = protected_raw["remotes"]
                if not isinstance(r, list) or not all(isinstance(x, str) for x in r):
                    raise ValueError(
                        f"{toml_path}: [protected].remotes must be a list of "
                        f"strings, got {r!r}"
                    )
                remotes = frozenset(r)

    # --- env overlay --------------------------------------------------------
    env_branches = _parse_env_list(_ENV_BRANCHES)
    if env_branches is not None:
        branches = env_branches  # may be () for sentinel disable
    env_remotes = _parse_env_list(_ENV_REMOTES)
    if env_remotes is not None:
        remotes = frozenset(env_remotes)  # may be empty for sentinel disable

    return ProtectedConfig(branches=branches, remotes=remotes)


# ---------------------------------------------------------------------------
# Test hook (cleared by an autouse fixture in tests/test_security/conftest.py)
# ---------------------------------------------------------------------------


def _reset_caches() -> None:
    """Clear all module-level caches. Test-fixture hook."""
    load_protected_config.cache_clear()
    _HEAD_CACHE.clear()


# ---------------------------------------------------------------------------
# Current-branch resolver (with HEAD-mtime cache)
# ---------------------------------------------------------------------------


#: Per-process cache: cwd -> (head_mtime, branch_or_None).
#: Sentinel mtime ``-1.0`` caches "not a git repo" so subsequent calls
#: in the same cwd don't restat. Any real mtime > -1.0 invalidates it.
#:
#: Bounded via ``_HEAD_CACHE_MAX`` with FIFO eviction (see ``_cache_set``)
#: so long-lived processes (e.g. the spellbook hook daemon) cannot grow
#: this cache without bound across many transient cwds (tmp dirs,
#: ephemeral worktrees). Reads via ``_cache_get`` bump LRU order.
_HEAD_CACHE_MAX: int = 128
_HEAD_CACHE: OrderedDict[str, tuple[float, str | None]] = OrderedDict()


def _cache_set(key: str, value: tuple[float, str | None]) -> None:
    """Insert into _HEAD_CACHE with FIFO eviction past _HEAD_CACHE_MAX."""
    _HEAD_CACHE[key] = value
    _HEAD_CACHE.move_to_end(key)
    while len(_HEAD_CACHE) > _HEAD_CACHE_MAX:
        _HEAD_CACHE.popitem(last=False)


def _cache_get(key: str) -> tuple[float, str | None] | None:
    """Get + bump-to-end (LRU). Returns None on miss."""
    val = _HEAD_CACHE.get(key)
    if val is not None:
        _HEAD_CACHE.move_to_end(key)
    return val


def _find_git_dir(cwd: str) -> Path | None:
    """Walk up from cwd looking for a .git dir or file (worktree pointer).

    Mirrors git's own repo-discovery: ``git -C <subdir>`` walks parents
    until it finds .git or hits the filesystem root. Returns the .git
    path on hit (the existing branching distinguishes dir vs file in
    the caller); returns None if no .git is found up to root.
    """
    p = Path(cwd)
    for ancestor in (p, *p.parents):
        candidate = ancestor / ".git"
        if candidate.exists():
            return candidate
    return None


def _run_symbolic_ref(cwd: str, timeout: float = 1.0) -> tuple[str | None, bool]:
    """Invoke ``git -C cwd symbolic-ref --short HEAD``.

    Returns:
        (branch, transient_failure):
          - (branch_name, False) on success.
          - (None, True) on transient failure (TimeoutExpired,
            FileNotFoundError, generic OSError) — caller should NOT
            cache this; retry next call.
          - (None, False) on stable non-zero exit (CalledProcessError,
            e.g. detached HEAD) — caller MAY cache.
    """
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            timeout=timeout,
            check=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return (None, True)
    except FileNotFoundError:
        return (None, True)
    except subprocess.CalledProcessError:
        return (None, False)  # detached HEAD or similar; stable
    except OSError:
        return (None, True)
    branch = result.stdout.strip()
    return (branch or None, False)


def _resolve_current_branch(cwd: str | None) -> str | None:
    """Return the current symbolic branch name for ``cwd``, or ``None``.

    Strategy:
      1. If ``cwd`` is empty/None → return None.
      2. Locate the canonical HEAD file:
         a. ``<cwd>/.git`` is a directory → ``<cwd>/.git/HEAD``.
         b. ``<cwd>/.git`` is a file → parse ``gitdir: <path>`` and use
            ``<path>/HEAD`` (worktree case).
         c. otherwise → not a git repo; cache ``(-1.0, None)`` and return None.
      3. Stat HEAD; on success compare mtime with cache; return cached
         branch when mtime matches.
      4. On miss, call ``git symbolic-ref``. Transient failures are not
         cached; stable failures are cached as ``(mtime, None)``.
    """
    if not cwd:
        return None
    # Reject relative cwd defensively. In a long-lived daemon (the
    # spellbook hook daemon, the MCP server), the process CWD is
    # unrelated to the operator's project root, so passing a relative
    # path to os.path.realpath would silently resolve against the wrong
    # root and produce wrong-branch results. All valid callers (the
    # Claude Code hook, the MCP wrapper, the CLI) pass absolute paths;
    # treat a relative cwd as a programming error and fail shut. The
    # None return triggers _failsafe -> T2-ask in classify_git_push,
    # which is the safer default than a silently wrong allow.
    if not os.path.isabs(cwd):
        return None
    # Normalize for consistent cache keying. Resolve symlinks and
    # collapse redundant separators / "." / ".." components so
    # semantically-equivalent paths (e.g. /tmp/foo, /tmp/foo/,
    # /tmp/foo/.) share a single cache entry.
    #
    # os.path.realpath is the C-level normalization; faster than
    # Path.resolve() and resolves symlinks (required for correct cache
    # keying — /tmp/foo and /tmp/symlink-to-foo must share an entry).
    try:
        cwd = os.path.realpath(cwd)
    except OSError:
        return None

    # Fast cache check: "not a git repo" sentinel. Real mtime entries
    # still need revalidation below (re-stat to detect HEAD changes),
    # so don't short-circuit those. Use _cache_get so the sentinel
    # entry bumps LRU order consistently with other cache reads.
    cached_pre = _cache_get(cwd)
    if cached_pre is not None and cached_pre[0] == -1.0:
        return None

    # Walk up parents looking for .git, mirroring git's own discovery.
    # The prior implementation only checked ``Path(cwd) / ".git"`` and
    # short-circuited to "not a git repo" if not found AT cwd, which
    # broke every push invoked from a subdirectory of a repo.
    git_path = _find_git_dir(cwd)

    head_path: Path | None
    if git_path is None:
        _cache_set(cwd, (-1.0, None))
        return None
    if git_path.is_dir():
        head_path = git_path / "HEAD"
    elif git_path.is_file():
        try:
            pointer = git_path.read_text(encoding="utf-8").strip()
        except OSError:
            # Pointer unreadable — skip cache, always probe.
            branch, _ = _run_symbolic_ref(cwd)
            return branch
        if not pointer.startswith("gitdir:"):
            branch, _ = _run_symbolic_ref(cwd)
            return branch
        gitdir = pointer[len("gitdir:"):].strip()
        # Resolve relative gitdir against the directory containing the
        # .git file (the worktree root), NOT the process CWD or the
        # original cwd argument. With the walk-up logic added for
        # subdir support, ``cwd`` may be a subdirectory of the worktree
        # while ``git_path`` is in an ancestor, so we anchor on
        # ``git_path.parent`` for correctness. Real worktrees commonly
        # have relative gitdir pointers such as
        # ``gitdir: ../.git/worktrees/<name>``. Absolute gitdir paths
        # are unaffected because ``os.path.join(base, abs) == abs``.
        # Uses ``os.path.realpath`` for consistency with the cwd
        # normalization above (C-level, faster than Path.resolve()).
        gitdir_base = str(git_path.parent)
        head_path = Path(os.path.realpath(os.path.join(gitdir_base, gitdir))) / "HEAD"
    else:
        _cache_set(cwd, (-1.0, None))
        return None

    try:
        mtime = head_path.stat().st_mtime
    except OSError:
        _cache_set(cwd, (-1.0, None))
        return None

    cached = _cache_get(cwd)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    # Fast path: parse the HEAD file directly when it is a plain
    # symbolic ref (the overwhelmingly common case). Avoids spawning
    # ``git`` and works for minimal fake repos used in tests. Falls
    # back to subprocess for detached HEAD or unusual HEAD contents.
    try:
        head_text = head_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        # Transient race between mtime stat and read, or permissions
        # change mid-resolve. Common enough to not warrant a warning,
        # but surface at DEBUG so operators tracing fallback behavior
        # can see why the subprocess path was taken.
        logger.debug(
            "Could not read HEAD at %s: %s; falling back to subprocess",
            head_path, exc,
        )
        head_text = ""
    branch: str | None = None
    if head_text.startswith("ref: refs/heads/"):
        branch = head_text[len("ref: refs/heads/"):].strip() or None
        _cache_set(cwd, (mtime, branch))
        return branch

    branch, transient = _run_symbolic_ref(cwd)
    if transient:
        return None  # do NOT cache
    _cache_set(cwd, (mtime, branch))
    return branch


# ---------------------------------------------------------------------------
# classify_git_push -- main entry point
# ---------------------------------------------------------------------------


from spellbook.gates.tiers import T_UNCLASSIFIED  # noqa: E402 — circular: tiers.py lazy-imports git_push.py inside classify_tool_call


# Predicate for URL-form remotes. ``scheme://...`` OR ``user@host:...``.
_URL_REMOTE_RE = re.compile(r"^[\w.+-]+@[\w.+-]+:")


def _is_url_form(remote: str) -> bool:
    """Return True if ``remote`` looks like a URL (not a remote name)."""
    if "://" in remote:
        return True
    if _URL_REMOTE_RE.search(remote):
        return True
    return False


# Known git push flags that consume the next positional argument.
# Hardcoded; if a future git release adds a value-taking flag not in
# this set, the parser will treat that flag's VALUE as a positional
# argument (remote or refspec), potentially producing a false-positive
# T_UNCLASSIFIED for an actual protected-branch push. The trade-off
# preserves a small, auditable parser over a full git argv grammar.
# Verified against git 2.45 documentation as of this branch's merge.
#
# Additional limitation: flag values that legitimately start with ``-``
# (e.g. ``git push --exec="-foo"`` or ``--exec -foo`` where the value is
# ``-foo``) are NOT consumed by the value-skip logic below — the leading
# hyphen makes the parser conservatively treat the value as a separate
# flag (see ``_parse_push_args``'s defensive ``not rest[i + 1].startswith("-")``
# check). This biases toward T_UNCLASSIFIED for malformed-looking pushes;
# in practice such hyphen-prefixed values are virtually never used with
# git push and the safer-failure trade-off is preserved.
_FLAGS_TAKING_VALUE: frozenset[str] = frozenset({
    "-o", "--push-option",
    "--repo",
    "--receive-pack",
    "--exec",
})


def _parse_push_args(command: str) -> tuple[str | None, list[str], bool, bool]:
    """Parse a ``git push`` invocation.

    Returns:
        (remote, refspecs, all_or_mirror, set_upstream):
          remote        -- first positional after flag-stripping, or None.
          refspecs      -- remaining positionals (already ``+`` and ``HEAD:``
                          stripped to dest branch name).
          all_or_mirror -- True if ``--all`` or ``--mirror`` present.
          set_upstream  -- True if ``-u`` / ``--set-upstream`` present
                          (used informationally; does not change targets).
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return (None, [], False, False)

    # Drop ``git`` and ``push``.
    if len(tokens) < 2 or tokens[0] != "git" or tokens[1] != "push":
        return (None, [], False, False)
    rest = tokens[2:]

    positionals: list[str] = []
    all_or_mirror = False
    set_upstream = False
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok in ("--all", "--mirror"):
            all_or_mirror = True
            i += 1
            continue
        if tok in ("-u", "--set-upstream"):
            set_upstream = True
            i += 1
            continue
        if tok in _FLAGS_TAKING_VALUE:
            # Defensive: if the supposed value is itself a flag, only
            # skip the flag; git would reject this input anyway.
            if i + 1 < len(rest) and not rest[i + 1].startswith("-"):
                i += 2
            else:
                i += 1
            continue
        if tok.startswith("--") and "=" in tok:
            # ``--push-option=...`` etc. -- single token.
            i += 1
            continue
        if tok.startswith("-"):
            # Other unknown short/long flag; assume valueless to stay safe.
            i += 1
            continue
        positionals.append(tok)
        i += 1

    # SH1: If the first positional looks like a refspec (contains ``:``
    # or starts with ``+``) AND is NOT a URL-form remote, the remote is
    # IMPLICIT — git defaults to the configured
    # ``branch.<name>.pushRemote`` / ``remote.pushDefault`` / ``origin``.
    # Pre-fix, the parser treated ``:main`` / ``+main`` as the remote
    # NAME, so they were rejected as "unknown remote" and the destructive
    # refspec slipped through as T_UNCLASSIFIED. The ``_is_url_form``
    # guard prevents URL-form remotes (which legitimately contain ``:``
    # for the scheme separator, e.g. ``https://...`` or
    # ``git@host:path``) from being mis-parsed as refspecs.
    if (
        positionals
        and (":" in positionals[0] or positionals[0].startswith("+"))
        and not _is_url_form(positionals[0])
    ):
        remote = None
        raw_refspecs = positionals
    else:
        remote = positionals[0] if positionals else None
        raw_refspecs = positionals[1:]

    refspec_dests: list[str] = []
    for spec in raw_refspecs:
        # Strip leading ``+`` (refspec-level force prefix).
        if spec.startswith("+"):
            spec = spec[1:]
        # Take destination (after the colon) if present, else source.
        if ":" in spec:
            _, dest = spec.split(":", 1)
        else:
            dest = spec
        # SH2: Defensive — strip leading ``+`` from the dest too. Per
        # git's refspec ABNF, ``+`` is only valid as a refspec-level
        # prefix, but an input like ``HEAD:+main`` is ambiguous: git
        # MAY create a ref literally named ``+main``, but the operator
        # almost certainly meant ``+HEAD:main`` (force HEAD to main).
        # Treat a post-``:`` ``+`` as a force-prefix on the dest to
        # fail-safe toward asking instead of silently allowing.
        if dest.startswith("+"):
            dest = dest[1:]
        # Normalize ``refs/heads/foo`` -> ``foo`` for fnmatch. Done AFTER
        # the ``+`` strip so ``+refs/heads/main`` is normalized correctly.
        if dest.startswith("refs/heads/"):
            dest = dest[len("refs/heads/"):]
        # ``HEAD`` as dest is rare; leave for resolver.
        refspec_dests.append(dest)

    return (remote, refspec_dests, all_or_mirror, set_upstream)


def _failsafe(autonomous: bool) -> str:
    """Return T2 in non-autonomous mode, T_UNCLASSIFIED in autonomous."""
    return T_UNCLASSIFIED if autonomous else "T2"


def _match_protected(target: str, patterns: tuple[str, ...]) -> bool:
    """fnmatchcase target against each pattern. Empty patterns -> no match."""
    return any(fnmatchcase(target, p) for p in patterns)


def classify_git_push(
    command: str,
    cwd: str | None,
    config: ProtectedConfig,
    *,
    autonomous: bool = False,
) -> str | None:
    """Pre-pass classifier for ``git push``.

    Returns:
        ``None`` when ``command`` is not a ``git push`` invocation.
        ``"T2"`` when the push targets a protected branch on a
        recognized remote (or for fail-safe in non-autonomous mode).
        :data:`T_UNCLASSIFIED` for feature-branch / unknown-remote /
        URL-form-remote / sentinel-disabled / autonomous-failsafe pushes.

    See design doc Section 4 and Section 5 for the full state table.
    """
    # Word-boundary check: must be exactly the "git push" subcommand
    # (not "git pushed-fail" or "git push-fancy"). Using split(None, 2)
    # so a single-token "gitpush" or "git" alone also fails fast.
    _tokens_head = command.lstrip().split(None, 2)
    if len(_tokens_head) < 2 or _tokens_head[0] != "git" or _tokens_head[1] != "push":
        return None

    # Sentinel-disabled axes short-circuit before any subprocess work.
    if not config.branches:
        return T_UNCLASSIFIED
    if not config.remotes:
        return T_UNCLASSIFIED

    remote, refspec_dests, all_or_mirror, _set_upstream = _parse_push_args(command)

    # --all / --mirror -> broad scope; always ask.
    if all_or_mirror:
        return "T2"

    # SH3: Bare ``git push`` with no remote AND no refspecs: rely on the
    # resolver alone. The SH1 fix lets ``git push :main`` (delete) reach
    # this point with remote=None but refspec_dests=["main"], so the
    # early-return guard must require BOTH conditions; otherwise the
    # refspec is silently ignored and the resolver checks the WRONG
    # target (the current branch, not the refspec dest).
    if remote is None and not refspec_dests:
        branch = _resolve_current_branch(cwd)
        if branch is None:
            return _failsafe(autonomous)
        return "T2" if _match_protected(branch, config.branches) else T_UNCLASSIFIED

    # URL-form remote -> out of scope for name-based matching. None-guard:
    # ``remote`` may legitimately be None now (implicit-remote refspec
    # path from SH1), so skip URL-form check in that case.
    if remote is not None and _is_url_form(remote):
        return T_UNCLASSIFIED

    # Unknown remote name -> out of scope. None-guard: same rationale as
    # above. Implicit-remote refspecs (remote is None) fall through to
    # the dest-matching loop below (the SH3 fix-point).
    if remote is not None and remote not in config.remotes:
        return T_UNCLASSIFIED

    # Refspecs given: classify against each target. Any protected hit -> T2.
    if refspec_dests:
        # Replace ``HEAD`` dests with resolved current branch.
        resolved_targets: list[str] = []
        head_resolved: str | None | bool = False  # tri-state: not-yet-resolved
        for dest in refspec_dests:
            if dest == "HEAD":
                if head_resolved is False:
                    head_resolved = _resolve_current_branch(cwd)
                if head_resolved is None:
                    return _failsafe(autonomous)
                resolved_targets.append(head_resolved)  # type: ignore[arg-type]
            else:
                resolved_targets.append(dest)
        for t in resolved_targets:
            if _match_protected(t, config.branches):
                return "T2"
        return T_UNCLASSIFIED

    # Remote provided, no refspec: target is current branch.
    branch = _resolve_current_branch(cwd)
    if branch is None:
        return _failsafe(autonomous)
    return "T2" if _match_protected(branch, config.branches) else T_UNCLASSIFIED


# ---------------------------------------------------------------------------
# validate_tiers_toml -- install-time umbrella validator (Task 5)
# ---------------------------------------------------------------------------


def validate_tiers_toml(toml_path: Path) -> None:
    """Umbrella validator: eagerly parse [[tiers]] AND [protected].

    Install-time hook so schema errors in either section surface at
    install / `spellbook validate`, not split between L2 derivation
    (tiers) and first-push (protected).

    Raises:
        ValueError: schema error in either section.
        FileNotFoundError: ``toml_path`` does not exist.
    """
    from spellbook.gates.tiers import load_tiers  # local import to avoid cycle
    load_tiers(toml_path)
    # Clear cache so we re-parse the file we were just handed
    # (lru_cache key would otherwise be stale if same path reused in tests).
    load_protected_config.cache_clear()
    load_protected_config(toml_path)
