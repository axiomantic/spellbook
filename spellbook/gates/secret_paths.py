"""Secret-path denylist for the Read tool gate (Phase 6d).

The Read tool MUST NOT be allowed to fetch the contents of well-known
secret files (SSH keys, cloud credentials, password manager databases,
browser credential stores, project-relative `.env` files, etc.).

This module exposes:

- ``SECRET_PATH_RULES``: structured patterns. Two flavors are supported:
    * ``HomeSubpath(rel)`` — anything under ``Path.home() / rel``.
    * ``EnvSubpath(env, rel)`` — anything under ``$env / rel`` (for
      Windows ``APPDATA``/``LOCALAPPDATA``); silently no-op when the
      env var is unset.
    * ``BasenameGlob(pattern)`` — ``PurePath.match()``-style glob over
      the **basename** of the resolved path. Used for project-relative
      patterns like ``.env*``, ``*.pem``, ``*.key``, ``id_rsa*``,
      ``id_ed25519*``.
- ``check_secret_path(file_path)``: resolves the input path (expanding
  ``~`` and following symlinks where the target exists) and returns the
  matched rule id, or ``None`` when nothing matches.

Path resolution rules (per design §7 Phase 6d, Surfaced Assumption #2):

1. ``Path(file_path).expanduser()`` — handles user-supplied ``~``.
2. Resolve symlinks. ``Path.resolve(strict=False)`` follows links where
   it can and falls back to a normalized absolute path when the tail
   does not exist. This catches the symlink-bypass case where a
   benign-looking path links into the deny zone, while still allowing
   the gate to evaluate paths that do not exist yet.
3. Compare the resolved path against each rule.

Comparison is case-sensitive on POSIX and naturally case-insensitive on
Windows (because ``Path.resolve()`` returns case-canonicalized paths
there). No additional case folding is needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePath


@dataclass(frozen=True)
class HomeSubpath:
    """Match anything under ``Path.home() / rel`` (inclusive of rel itself)."""

    rel: str
    rule_id: str


@dataclass(frozen=True)
class EnvSubpath:
    """Match anything under ``$env_var / rel`` when ``env_var`` is set."""

    env_var: str
    rel: str
    rule_id: str


@dataclass(frozen=True)
class BasenameGlob:
    """Match when ``PurePath(resolved).match("**/" + pattern)`` is true.

    Used for project-relative secrets where the absolute parent directory
    is not predictable (e.g. ``.env`` in any repo).
    """

    pattern: str
    rule_id: str


SECRET_PATH_RULES: tuple[object, ...] = (
    # POSIX home-relative secrets
    HomeSubpath(rel=".ssh", rule_id="READ-SECRET-001"),
    HomeSubpath(rel=".aws", rule_id="READ-SECRET-002"),
    HomeSubpath(rel=".config/op", rule_id="READ-SECRET-003"),
    HomeSubpath(rel=".netrc", rule_id="READ-SECRET-004"),
    HomeSubpath(rel="_netrc", rule_id="READ-SECRET-004"),  # Windows variant
    # macOS browser credential stores: ~/Library/Application Support/<browser>/Login Data
    HomeSubpath(
        rel="Library/Application Support",
        rule_id="READ-SECRET-005",
    ),
    # Windows env-var-rooted secrets
    EnvSubpath(env_var="APPDATA", rel="1Password", rule_id="READ-SECRET-006"),
    EnvSubpath(
        env_var="LOCALAPPDATA",
        rel="Google/Chrome/User Data",
        rule_id="READ-SECRET-007",
    ),
    # Project-relative globs (matched against any resolved path)
    BasenameGlob(pattern=".env", rule_id="READ-SECRET-010"),
    BasenameGlob(pattern=".env.*", rule_id="READ-SECRET-010"),
    BasenameGlob(pattern="*.pem", rule_id="READ-SECRET-011"),
    BasenameGlob(pattern="*.key", rule_id="READ-SECRET-012"),
    BasenameGlob(pattern="id_rsa", rule_id="READ-SECRET-013"),
    BasenameGlob(pattern="id_rsa.*", rule_id="READ-SECRET-013"),
    BasenameGlob(pattern="id_ed25519", rule_id="READ-SECRET-014"),
    BasenameGlob(pattern="id_ed25519.*", rule_id="READ-SECRET-014"),
)


def _resolve(file_path: str) -> Path:
    """Expand ``~`` and resolve symlinks; tolerate non-existent tails."""
    return Path(file_path).expanduser().resolve(strict=False)


def _is_under(child: Path, parent: Path) -> bool:
    """True if ``child`` is ``parent`` or a descendant of it."""
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def check_secret_path(file_path: str) -> str | None:
    """Return the matched rule id, or None if the path is not a secret.

    Args:
        file_path: The user-supplied path. May contain ``~`` and may
            point at a non-existent file.

    Returns:
        The ``rule_id`` of the first matching denylist entry, or
        ``None`` when no rule matches.
    """
    if not file_path:
        return None

    try:
        resolved = _resolve(file_path)
    except (OSError, RuntimeError):
        # Path resolution can fail on weird inputs; fail-open is fine
        # because the bash/exfil rules would still catch a real attack
        # via the Bash tool.
        return None

    home = Path.home().resolve()

    for rule in SECRET_PATH_RULES:
        if isinstance(rule, HomeSubpath):
            target = (home / rule.rel).resolve(strict=False)
            if _is_under(resolved, target):
                return rule.rule_id
        elif isinstance(rule, EnvSubpath):
            base = os.environ.get(rule.env_var)
            if not base:
                continue
            target = (Path(base) / rule.rel).resolve(strict=False)
            if _is_under(resolved, target):
                return rule.rule_id
        elif isinstance(rule, BasenameGlob):
            if PurePath(resolved.name).match(rule.pattern):
                return rule.rule_id
    return None
