"""Rule module source loading and selection resolution.

Reads the hand-authored ``rules/*.md`` files that are the source of truth for
the shipped ruleset, parses their YAML frontmatter, and resolves which modules
an install should deliver.

The frontmatter parser here is deliberately hand-rolled rather than delegating
to PyYAML. PyYAML is a dev-only dependency, and the installer must import on a
bare interpreter. The parser covers exactly the schema the rule modules use:
plain scalars, ``>`` folded blocks, ``- `` item lists, ``[]``, and ``null``.

It also never coerces ``on``/``off`` to a bool, which is the failure PyYAML's
YAML 1.1 booleans produce (see the design's section 7.2.1). ``default`` is
always read as a string here regardless of whether the file quotes it; the
quoting requirement is enforced separately by ``validate_rule_module()``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

MODULE_FILENAME_RE = re.compile(r"^(?P<prefix>\d{2})-(?P<slug>[a-z][a-z0-9-]*)\.md$")

CLASS_MANDATORY = "mandatory"
CLASS_PREFERENCE = "preference"

CONFIG_KEY_PREFIX = "rules.module."

# Antigravity documents a 12,000-character cap per rule file. It is the only
# per-file cap any supported harness declares. Enforced by the validator; the
# loader records it so callers do not re-derive the number.
PER_FILE_CAP_BYTES = 12_000


class RuleModuleError(ValueError):
    """A rule module file is malformed and cannot be loaded."""


@dataclass(frozen=True)
class RuleModule:
    """One hand-authored rule module from ``rules/``."""

    path: Path
    prefix: str
    id: str
    name: str
    module_class: str
    default_state: str
    description: str
    benefit: str
    declining_means: str
    related: List[str] = field(default_factory=list)
    renamed_from: List[str] = field(default_factory=list)
    superseded_by: Optional[str] = None
    paths: List[str] = field(default_factory=list)
    body: str = ""

    @property
    def is_mandatory(self) -> bool:
        return self.module_class == CLASS_MANDATORY

    @property
    def is_preference(self) -> bool:
        return self.module_class == CLASS_PREFERENCE

    @property
    def default_on(self) -> bool:
        """Pre-check state used when this module's config key is absent."""
        return self.default_state == "on"

    @property
    def source_name(self) -> str:
        """Repo-side filename, ``XX-<id>.md``."""
        return self.path.name

    @property
    def installed_name(self) -> str:
        """Installed filename, ``XX-spellbook-<id>.md``.

        The ``spellbook-`` infix makes spellbook's files identifiable inside a
        rules directory the user also owns.
        """
        return f"{self.prefix}-spellbook-{self.id}.md"

    @property
    def config_key(self) -> str:
        """Config key for this module. Binds to the stable id, not the prefix."""
        return f"{CONFIG_KEY_PREFIX}{self.id}"

    @property
    def size_bytes(self) -> int:
        """Post-frontmatter-strip body size, which is what caps measure."""
        return len(self.body.encode("utf-8"))


def _split_frontmatter(text: str, path: Path) -> tuple[List[str], str]:
    """Split a module file into its frontmatter lines and its body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RuleModuleError(f"{path}: missing opening frontmatter delimiter")

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx], "\n".join(lines[idx + 1 :]).strip()

    raise RuleModuleError(f"{path}: missing closing frontmatter delimiter")


def _strip_scalar(raw: str) -> str:
    """Unquote a scalar value, preserving its text exactly otherwise."""
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_frontmatter(text: str, path: Path) -> tuple[Dict[str, Any], str]:
    """Parse a rule module's frontmatter into a dict, plus its body.

    Supported value forms, which is the whole schema the modules use:

    - ``key: value`` plain or quoted scalar
    - ``key: >`` followed by an indented folded block
    - ``key:`` followed by ``  - item`` list entries
    - ``key: []`` empty list
    - ``key: null`` explicit null
    """
    fm_lines, body = _split_frontmatter(text, path)
    data: Dict[str, Any] = {}

    idx = 0
    while idx < len(fm_lines):
        line = fm_lines[idx]
        idx += 1

        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise RuleModuleError(f"{path}: unparseable frontmatter line: {line!r}")

        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()

        if raw == ">" or raw == "|":
            block: List[str] = []
            while idx < len(fm_lines):
                nxt = fm_lines[idx]
                if nxt.strip() and not nxt.startswith((" ", "\t")):
                    break
                block.append(nxt.strip())
                idx += 1
            joiner = " " if raw == ">" else "\n"
            data[key] = joiner.join(part for part in block if part).strip()
            continue

        if raw == "":
            items: List[str] = []
            while idx < len(fm_lines):
                nxt = fm_lines[idx]
                if not nxt.startswith((" ", "\t")) or not nxt.strip().startswith("- "):
                    break
                items.append(_strip_scalar(nxt.strip()[2:]))
                idx += 1
            data[key] = items
            continue

        if raw == "[]":
            data[key] = []
            continue
        if raw == "null" or raw == "~":
            data[key] = None
            continue

        data[key] = _strip_scalar(raw)

    return data, body


def _require(data: Mapping[str, Any], key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuleModuleError(f"{path}: frontmatter field {key!r} is required")
    return value.strip()


def _string_list(data: Mapping[str, Any], key: str, path: Path) -> List[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuleModuleError(f"{path}: frontmatter field {key!r} must be a list")
    return [str(item) for item in value]


def parse_rule_module(path: Path) -> RuleModule:
    """Parse one ``rules/<XX>-<id>.md`` file into a RuleModule."""
    match = MODULE_FILENAME_RE.match(path.name)
    if not match:
        raise RuleModuleError(
            f"{path}: filename must match <two-digit-prefix>-<slug>.md"
        )

    data, body = parse_frontmatter(path.read_text(encoding="utf-8"), path)

    module_class = _require(data, "class", path)
    if module_class not in (CLASS_MANDATORY, CLASS_PREFERENCE):
        raise RuleModuleError(
            f"{path}: class must be {CLASS_MANDATORY!r} or {CLASS_PREFERENCE!r}"
        )

    if module_class == CLASS_PREFERENCE:
        default_state = _require(data, "default", path)
        if default_state not in ("on", "off"):
            raise RuleModuleError(f"{path}: default must be 'on' or 'off'")
        benefit = _require(data, "benefit", path)
        declining_means = _require(data, "declining_means", path)
    else:
        if "default" in data:
            raise RuleModuleError(f"{path}: mandatory modules must not set default")
        default_state = "on"
        benefit = ""
        declining_means = ""

    superseded_by = data.get("superseded_by")
    if superseded_by is not None and not isinstance(superseded_by, str):
        raise RuleModuleError(f"{path}: superseded_by must be null or an id")

    return RuleModule(
        path=path,
        prefix=match.group("prefix"),
        id=_require(data, "id", path),
        name=_require(data, "name", path),
        module_class=module_class,
        default_state=default_state,
        description=_require(data, "description", path),
        benefit=benefit,
        declining_means=declining_means,
        related=_string_list(data, "related", path),
        renamed_from=_string_list(data, "renamed_from", path),
        superseded_by=superseded_by,
        paths=_string_list(data, "paths", path),
        body=body,
    )


def get_rules_dir(spellbook_dir: Path) -> Path:
    """Return the rule module source directory for a spellbook checkout."""
    return spellbook_dir / "rules"


def load_rule_modules(rules_dir: Path) -> List[RuleModule]:
    """Load every rule module from ``rules_dir``, in delivery order.

    Order is ascending filename prefix with ties broken by id, so the order is
    total and a regenerated bundle is byte-stable. Returns an empty list when
    the directory is absent, which keeps a partial checkout from crashing the
    installer.
    """
    if not rules_dir.is_dir():
        return []

    # ``Path.glob`` swallows OSError and yields nothing, so an unreadable
    # rules/ was indistinguishable from an empty one and the installer told
    # the user "no rule modules found" -- pointing at the wrong problem
    # entirely. Probe the directory directly so a permission error says so.
    #
    # The previous implementation opened the directory with ``os.open(dir,
    # O_RDONLY)`` and immediately closed the handle, which works on POSIX
    # but raises OSError on Windows -- Windows does not allow opening a
    # directory handle at all. Use ``os.scandir`` instead: it is the
    # cross-platform directory iterator and raises OSError on a real
    # permissions problem on every OS.
    try:
        with os.scandir(rules_dir) as it:
            for _entry in it:
                break  # one probe is enough -- any OSError will surface above
    except OSError as exc:
        raise RuleModuleError(f"cannot read rule modules in {rules_dir}: {exc}") from exc

    modules = [parse_rule_module(path) for path in sorted(rules_dir.glob("*.md"))]

    seen: Dict[str, Path] = {}
    for module in modules:
        if module.id in seen:
            raise RuleModuleError(
                f"duplicate rule module id {module.id!r}: "
                f"{seen[module.id]} and {module.path}"
            )
        seen[module.id] = module.path

    modules.sort(key=lambda m: (m.prefix, m.id))
    return modules


def mandatory_modules(modules: Sequence[RuleModule]) -> List[RuleModule]:
    return [m for m in modules if m.is_mandatory]


def preference_modules(modules: Sequence[RuleModule]) -> List[RuleModule]:
    return [m for m in modules if m.is_preference]


def recorded_value(
    values: Mapping[str, Any], module: RuleModule
) -> Optional[Any]:
    """The user's recorded answer for a module, honoring ``renamed_from``.

    A rename must not read as "never offered". Looking up only the current key
    would make a module the user explicitly declined take its default again,
    silently reinstalling a rule they turned off.
    """
    if module.config_key in values:
        return values[module.config_key]
    for old_id in module.renamed_from:
        key = f"{CONFIG_KEY_PREFIX}{old_id}"
        if key in values:
            return values[key]
    return None


@dataclass
class ModuleSelection:
    """Which modules an install delivers, and why each preference is checked."""

    modules: List[RuleModule]
    selected_ids: List[str]
    prechecked_ids: List[str]
    declined_ids: List[str]
    unanswered_ids: List[str]

    @property
    def selected(self) -> List[RuleModule]:
        chosen = set(self.selected_ids)
        return [m for m in self.modules if m.is_mandatory or m.id in chosen]

    @property
    def deselected(self) -> List[RuleModule]:
        chosen = set(self.selected_ids)
        return [m for m in self.modules if m.is_preference and m.id not in chosen]


def resolve_selection(
    modules: Sequence[RuleModule],
    config_values: Optional[Mapping[str, Any]] = None,
) -> ModuleSelection:
    """Resolve the effective selection from config plus per-module defaults.

    The config value is tri-state (design section 12.1):

    - ``True``  -- the user kept the module; it stays checked.
    - ``False`` -- the user declined it; it is never re-checked automatically.
    - absent    -- the module was never offered; it takes its ``default``.

    A recorded answer is authoritative on every path, including legacy
    migration. Migration detection is per-platform and fires on states a
    previously-answering user can reach (adding a second harness whose legacy
    sidecar was never cleaned), so overriding a recorded ``False`` there would
    silently reinstall rules the user turned off.
    """
    values = config_values or {}
    selected: List[str] = []
    prechecked: List[str] = []
    declined: List[str] = []
    unanswered: List[str] = []

    for module in preference_modules(modules):
        recorded = recorded_value(values, module)

        if recorded is None:
            unanswered.append(module.id)
            keep = module.default_on
        else:
            keep = bool(recorded)
            if not keep:
                declined.append(module.id)

        if keep:
            selected.append(module.id)
            prechecked.append(module.id)

    return ModuleSelection(
        modules=list(modules),
        selected_ids=selected,
        prechecked_ids=prechecked,
        declined_ids=declined,
        unanswered_ids=unanswered,
    )


def config_schema_entries(modules: Sequence[RuleModule]) -> List[Dict[str, Any]]:
    """Generate one boolean config-schema entry per preference module.

    The entry format supports only boolean, number, and string, so a per-module
    map is not expressible; one boolean key per preference module is.
    """
    return [
        {
            "key": module.config_key,
            "type": "boolean",
            "description": module.benefit,
            "default": module.default_on,
        }
        for module in preference_modules(modules)
    ]
