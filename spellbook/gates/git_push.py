"""Programmatic ``git push`` pre-pass for the tier classifier.

Replaces the catch-all ``git push`` T2 row in ``tiers.toml`` with a
config-driven classifier that asks only when the push targets a
protected branch on a recognized remote. See the design doc
(``docs/.../2026-05-16-narrow-git-push-protected-branches-design.md``)
for the full architecture rationale.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]


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
    """Clear all module-level caches. Test-fixture hook.

    Currently clears only ``load_protected_config``'s ``lru_cache``.
    Task 3 extends this to clear ``_HEAD_CACHE``.
    """
    load_protected_config.cache_clear()
