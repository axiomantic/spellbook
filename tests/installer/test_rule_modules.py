"""Tests for rule module loading, selection, bundling, and detection.

These exercise the real filesystem via ``tmp_path`` rather than mocking the
layer under test. The delivery bugs this branch fixes were all invisible to
tests that asserted on a signal (a call happened, a symlink exists) instead of
the artifact, so these assert on written bytes and parsed markers.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import tripwire

from installer.components.rule_bundle import (
    BundleTooLargeError,
    delivery_marker,
    generate_bundle,
    parse_bundle_module_ids,
)
from installer.components.rule_delivery import (
    MERGE_END,
    MERGE_START,
    install_module_symlinks,
    remove_legacy_artifacts,
    write_bundle,
)
from installer.components.rule_migration import (
    InstallState,
    detect_platform_state,
)
from installer.components.rule_modules import (
    RuleModuleError,
    get_rules_dir,
    load_rule_modules,
    parse_rule_module,
    preference_modules,
    resolve_selection,
)

MANDATORY_TEMPLATE = """---
id: {id}
name: {name}
class: mandatory
description: >
  A mandatory module used in tests.
related: []
renamed_from: []
superseded_by: null
paths: []
---

{body}
"""

PREFERENCE_TEMPLATE = """---
id: {id}
name: {name}
class: preference
default: "{default}"
description: >
  A preference module used in tests.
benefit: >
  Benefit text for {id}.
declining_means: >
  Declining text for {id}.
related: []
renamed_from: []
superseded_by: null
paths: []
---

{body}
"""


def _write_module(rules_dir: Path, prefix: str, module_id: str, **kwargs) -> Path:
    rules_dir.mkdir(parents=True, exist_ok=True)
    path = rules_dir / f"{prefix}-{module_id}.md"
    template = (
        PREFERENCE_TEMPLATE if kwargs.get("preference") else MANDATORY_TEMPLATE
    )
    path.write_text(
        template.format(
            id=module_id,
            name=kwargs.get("name", module_id.title()),
            default=kwargs.get("default", "on"),
            body=kwargs.get("body", f"Body of {module_id}."),
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def rules_dir(tmp_path: Path) -> Path:
    d = tmp_path / "rules"
    _write_module(d, "00", "core", body="Core body.")
    _write_module(d, "10", "session", preference=True, default="on")
    _write_module(d, "60", "autonomy", preference=True, default="on",
                  body="Autonomy body. " * 50)
    _write_module(d, "86", "review-posture", preference=True, default="off")
    return d


class TestLoading:
    def test_loads_in_prefix_order(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        assert [m.id for m in modules] == [
            "core", "session", "autonomy", "review-posture"
        ]

    def test_installed_name_carries_the_spellbook_infix(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        assert modules[0].installed_name == "00-spellbook-core.md"
        assert modules[0].source_name == "00-core.md"

    def test_config_key_binds_to_id_not_prefix(self, rules_dir: Path):
        """A file rename must not orphan a recorded selection."""
        modules = load_rule_modules(rules_dir)
        before = {m.id: m.config_key for m in modules}

        (rules_dir / "10-session.md").rename(rules_dir / "15-session.md")
        after = {m.id: m.config_key for m in load_rule_modules(rules_dir)}

        assert before["session"] == after["session"] == "rules.module.session"

    def test_default_is_read_as_a_string_never_a_bool(self, rules_dir: Path):
        """YAML 1.1 parses bare ``on`` as True; a bool here inverts every
        default and would silently deliver nothing on a non-tty install."""
        modules = load_rule_modules(rules_dir)
        for module in preference_modules(modules):
            assert module.default_state in ("on", "off")
            assert not isinstance(module.default_state, bool)

    def test_mandatory_module_with_a_default_is_rejected(self, tmp_path: Path):
        d = tmp_path / "rules"
        d.mkdir()
        (d / "00-core.md").write_text(
            MANDATORY_TEMPLATE.format(id="core", name="Core", body="x").replace(
                "class: mandatory", "class: mandatory\ndefault: \"on\""
            ),
            encoding="utf-8",
        )
        with pytest.raises(RuleModuleError):
            parse_rule_module(d / "00-core.md")

    def test_missing_rules_dir_is_empty_not_an_error(self, tmp_path: Path):
        assert load_rule_modules(tmp_path / "nope") == []


class TestSelection:
    def test_fresh_install_prechecks_default_on_only(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        selection = resolve_selection(modules, {})

        assert "session" in selection.selected_ids
        assert "autonomy" in selection.selected_ids
        assert "review-posture" not in selection.selected_ids

    def test_mandatory_modules_are_never_offered(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        selection = resolve_selection(modules, {})

        assert "core" not in selection.selected_ids
        assert "core" not in selection.declined_ids
        assert any(m.id == "core" for m in selection.selected)

    def test_a_declined_module_is_never_rechecked(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        config = {"rules.module.session": False}

        for _ in range(3):
            selection = resolve_selection(modules, config)
            assert "session" not in selection.selected_ids
            assert "session" in selection.declined_ids

    def test_a_new_module_is_prechecked_on_first_appearance(self, rules_dir: Path):
        """An absent key means "never offered", so the module takes its default."""
        modules = load_rule_modules(rules_dir)
        config = {"rules.module.session": True}  # autonomy key absent

        selection = resolve_selection(modules, config)

        assert "autonomy" in selection.selected_ids
        assert "autonomy" in selection.unanswered_ids

    def test_migration_takes_defaults_for_unanswered_modules_only(
        self, rules_dir: Path
    ):
        """Migration installs everything the user had, and nothing they did not.

        A migrating user has no recorded answers, so migration is expressed by
        config-key absence alone -- no flag. review-posture defaults off, so
        migrating never adds it: that would be a new rule, not a preserved one.
        """
        modules = load_rule_modules(rules_dir)

        selection = resolve_selection(modules, {})

        assert "session" in selection.selected_ids
        assert "autonomy" in selection.selected_ids
        assert "review-posture" not in selection.selected_ids

    def test_migration_never_reinstalls_a_module_the_user_declined(
        self, rules_dir: Path
    ):
        """A recorded False survives migration.

        Migration detection is per-platform and fires on states a user who has
        already answered can reach -- adding a second harness whose legacy
        sidecar was never cleaned. Discarding declines here silently reinstalls
        rules the user explicitly turned off, on every platform.

        There is no migration flag to pass: the recorded answer is
        authoritative on every path, and that is what makes it survive.
        """
        modules = load_rule_modules(rules_dir)
        config = {"rules.module.session": False}

        selection = resolve_selection(modules, config)

        assert "session" not in selection.selected_ids
        assert "session" in selection.declined_ids
        assert "session" not in selection.unanswered_ids

    def test_a_renamed_module_keeps_the_answer_recorded_under_its_old_id(
        self, rules_dir: Path
    ):
        """A rename must not read as "never offered".

        Reading only the current key would make a declined module take its
        default again, silently reinstalling a rule the user turned off.
        """
        from installer.components.rule_modules import RuleModule, resolve_selection

        modules = load_rule_modules(rules_dir)
        session = next(m for m in modules if m.id == "session")
        renamed = RuleModule(
            **{
                **session.__dict__,
                "id": "session-modes",
                "renamed_from": ["session"],
            }
        )
        others = [m for m in modules if m.id != "session"]

        selection = resolve_selection(
            [renamed, *others], {"rules.module.session": False}
        )

        assert "session-modes" not in selection.selected_ids
        assert "session-modes" in selection.declined_ids
        assert "session-modes" not in selection.unanswered_ids


class TestBundle:
    def test_contains_exactly_the_selected_modules_in_order(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        selected = [m for m in modules if m.id != "review-posture"]

        bundle = generate_bundle(selected, "1.2.3", "codex")

        # Parsed from the per-module markers, not substring-searched: a
        # substring search passes on a superset.
        assert parse_bundle_module_ids(bundle.content) == [
            "core", "session", "autonomy"
        ]

    def test_carries_one_delivery_marker_with_the_version(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        bundle = generate_bundle(modules, "1.2.3", "codex")

        assert bundle.content.count(delivery_marker("1.2.3")) == 1

    def test_regeneration_is_byte_stable(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        first = generate_bundle(modules, "1.2.3", "codex").content
        second = generate_bundle(modules, "1.2.3", "codex").content
        assert first == second

    def test_deselection_regenerates_without_the_module(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        kept = [m for m in modules if m.id != "autonomy"]

        bundle = generate_bundle(kept, "1.2.3", "codex")

        assert "autonomy" not in parse_bundle_module_ids(bundle.content)
        assert "Autonomy body." not in bundle.content

    def test_no_modules_are_dropped_when_no_cap_applies(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        bundle = generate_bundle(modules, "1.2.3", "codex")
        assert bundle.dropped == []

    def test_over_cap_drops_preference_modules_largest_first(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        mandatory_size = generate_bundle(
            [m for m in modules if m.is_mandatory], "1.2.3", "codex"
        ).size_bytes

        bundle = generate_bundle(modules, "1.2.3", "codex", cap=mandatory_size + 200)

        # autonomy is the largest preference module, so it goes first.
        assert bundle.dropped[0][0] == "autonomy"
        assert bundle.size_bytes <= mandatory_size + 200
        assert "core" in parse_bundle_module_ids(bundle.content)

    def test_drop_report_names_every_dropped_module_and_the_cap(self, rules_dir: Path):
        modules = load_rule_modules(rules_dir)
        mandatory_size = generate_bundle(
            [m for m in modules if m.is_mandatory], "1.2.3", "codex"
        ).size_bytes

        bundle = generate_bundle(modules, "1.2.3", "codex", cap=mandatory_size + 200)
        report = "\n".join(bundle.drop_report())

        assert "autonomy" in report
        assert str(mandatory_size + 200) in report

    def test_mandatory_set_over_cap_fails_hard_rather_than_truncating(
        self, rules_dir: Path
    ):
        modules = load_rule_modules(rules_dir)
        with pytest.raises(BundleTooLargeError):
            generate_bundle(modules, "1.2.3", "codex", cap=10)


class TestDirectoryDelivery:
    def test_installs_one_symlink_per_selected_module(self, rules_dir, tmp_path):
        modules = load_rule_modules(rules_dir)
        target = tmp_path / "claude" / "rules"

        outcome = install_module_symlinks(rules_dir, target, modules)

        assert outcome.success
        assert sorted(p.name for p in target.glob("*.md")) == [
            "00-spellbook-core.md",
            "10-spellbook-session.md",
            "60-spellbook-autonomy.md",
            "86-spellbook-review-posture.md",
        ]
        # Real symlinks, not copies. A copy passes a filename-only assertion
        # while silently never tracking edits to the rules/ source again.
        for installed in sorted(target.glob("*.md")):
            assert installed.is_symlink(), f"{installed.name} is not a symlink"
        assert (target / "00-spellbook-core.md").resolve() == (
            rules_dir / "00-core.md"
        ).resolve()

    def test_deselection_removes_the_symlink(self, rules_dir, tmp_path):
        modules = load_rule_modules(rules_dir)
        target = tmp_path / "claude" / "rules"
        install_module_symlinks(rules_dir, target, modules)

        kept = [m for m in modules if m.id != "autonomy"]
        outcome = install_module_symlinks(rules_dir, target, kept)

        assert not (target / "60-spellbook-autonomy.md").exists()
        assert [p.name for p in outcome.removed] == ["60-spellbook-autonomy.md"]

    def test_a_users_own_rule_files_are_left_alone(self, rules_dir, tmp_path):
        target = tmp_path / "claude" / "rules"
        target.mkdir(parents=True)
        mine = target / "10-my-own-rules.md"
        mine.write_text("mine\n", encoding="utf-8")

        install_module_symlinks(rules_dir, target, load_rule_modules(rules_dir))

        assert mine.read_text(encoding="utf-8") == "mine\n"


class TestFlatDelivery:
    def test_writes_a_real_file_not_a_symlink(self, rules_dir, tmp_path):
        modules = load_rule_modules(rules_dir)
        bundle = generate_bundle(modules, "1.2.3", "codex")
        path = tmp_path / "codex" / "AGENTS.md"

        outcome = write_bundle(path, bundle)

        assert outcome.success
        assert path.is_file() and not path.is_symlink()
        assert delivery_marker("1.2.3") in path.read_text(encoding="utf-8")

    def test_a_users_real_file_is_backed_up_before_takeover(self, rules_dir, tmp_path):
        modules = load_rule_modules(rules_dir)
        path = tmp_path / "codex" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        path.write_text("# mine\n", encoding="utf-8")

        write_bundle(path, generate_bundle(modules, "1.2.3", "codex"))

        backups = list(path.parent.glob("AGENTS.md.backup.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "# mine\n"

    def test_reinstall_does_not_back_up_our_own_output(self, rules_dir, tmp_path):
        """Backing up a generated file on every install litters the directory
        with timestamped copies of something the installer can regenerate."""
        modules = load_rule_modules(rules_dir)
        path = tmp_path / "codex" / "AGENTS.md"

        for _ in range(3):
            write_bundle(path, generate_bundle(modules, "1.2.3", "codex"))

        assert list(path.parent.glob("AGENTS.md.backup.*")) == []

    def test_preserve_or_merge_keeps_user_content_byte_intact(
        self, rules_dir, tmp_path
    ):
        modules = load_rule_modules(rules_dir)
        bundle = generate_bundle(modules, "1.2.3", "forgecode")
        path = tmp_path / "forge" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        user_content = "# my rules\n\nDo the thing.\n"
        path.write_text(user_content, encoding="utf-8")

        write_bundle(path, bundle, preserve_existing=True)
        written = path.read_text(encoding="utf-8")

        assert written.startswith(user_content.rstrip())
        assert MERGE_START in written and MERGE_END in written

    def test_reinstall_replaces_only_the_demarcated_region(self, rules_dir, tmp_path):
        modules = load_rule_modules(rules_dir)
        path = tmp_path / "forge" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        user_content = "# my rules\n\nDo the thing.\n"
        path.write_text(user_content, encoding="utf-8")

        write_bundle(
            path, generate_bundle(modules, "1.2.3", "forgecode"), preserve_existing=True
        )
        kept = [m for m in modules if m.id != "autonomy"]
        write_bundle(
            path, generate_bundle(kept, "1.2.3", "forgecode"), preserve_existing=True
        )

        written = path.read_text(encoding="utf-8")
        assert written.startswith(user_content.rstrip())
        assert written.count(MERGE_START) == 1
        assert "autonomy" not in parse_bundle_module_ids(written)


class TestDetection:
    def test_a_dangling_legacy_symlink_is_detected(self, tmp_path: Path):
        """Path.exists() follows symlinks and reports a broken one as absent.

        A detector using it classifies an upgrading user as FRESH, skips
        migration, and leaves the dead link in place forever.
        """
        config = tmp_path / "claude"
        (config / "rules").mkdir(parents=True)
        link = config / "rules" / "spellbook.md"
        link.symlink_to(tmp_path / "gone" / "AGENTS.spellbook.md")

        assert not link.exists(), "precondition: the link is dangling"

        state, evidence = detect_platform_state(
            module_dir=config / "rules",
            bundle_path=None,
            legacy_paths=[link],
            context_files=[],
            version="1.2.3",
        )

        assert state is InstallState.SYMLINK
        assert "dangling" in evidence[0]

    def test_a_dangling_link_is_removed(self, tmp_path: Path):
        link = tmp_path / "spellbook.md"
        link.symlink_to(tmp_path / "gone.md")

        removed = remove_legacy_artifacts([link])

        assert removed == [link]
        assert not os.path.lexists(link)

    def test_module_files_report_modular(self, tmp_path: Path):
        rules = tmp_path / "rules"
        rules.mkdir()
        (rules / "00-spellbook-core.md").write_text("x", encoding="utf-8")

        state, _ = detect_platform_state(
            module_dir=rules,
            bundle_path=None,
            legacy_paths=[],
            context_files=[],
            version="1.2.3",
        )
        assert state is InstallState.MODULAR

    def test_a_demarcated_block_reports_legacy(self, tmp_path: Path):
        context = tmp_path / "CLAUDE.md"
        context.write_text(
            "# mine\n\n<!-- SPELLBOOK:START version=0.5.0 -->\nrules\n"
            "<!-- SPELLBOOK:END -->\n",
            encoding="utf-8",
        )

        state, _ = detect_platform_state(
            module_dir=None,
            bundle_path=None,
            legacy_paths=[],
            context_files=[context],
            version="1.2.3",
        )
        assert state is InstallState.LEGACY

    def test_nothing_installed_reports_fresh(self, tmp_path: Path):
        state, _ = detect_platform_state(
            module_dir=tmp_path / "rules",
            bundle_path=tmp_path / "AGENTS.md",
            legacy_paths=[tmp_path / "AGENTS.spellbook.md"],
            context_files=[tmp_path / "CLAUDE.md"],
            version="1.2.3",
        )
        assert state is InstallState.FRESH


class TestShippedModules:
    """Assertions against the real rules/ directory, not a fixture."""

    @pytest.fixture
    def shipped(self):
        repo_root = Path(__file__).resolve().parents[2]
        modules = load_rule_modules(repo_root / "rules")
        # Deliberately not a skip. A regression in load_rule_modules that
        # returns [] against the real rules/ directory would turn every
        # assertion in this class into a silent pass.
        assert modules, "the checkout must ship rule modules in rules/"
        return modules

    def test_every_preference_module_can_explain_itself(self, shipped):
        """A preference module without benefit text is an unexplainable checkbox."""
        for module in preference_modules(shipped):
            assert module.benefit.strip()
            assert module.declining_means.strip()

    def test_ids_are_unique_and_well_formed(self, shipped):
        ids = [m.id for m in shipped]
        assert len(ids) == len(set(ids))
        for module_id in ids:
            assert module_id.replace("-", "").isalnum()

    def test_no_module_exceeds_the_antigravity_per_file_cap(self, shipped):
        from installer.components.rule_modules import PER_FILE_CAP_BYTES

        for module in shipped:
            assert module.size_bytes <= PER_FILE_CAP_BYTES, module.id

    def test_the_core_module_is_mandatory(self, shipped):
        """The delivery marker rides in core, so core must be unconditional."""
        core = next(m for m in shipped if m.id == "core")
        assert core.is_mandatory

    def test_rule_module_defaults_are_not_resolved_at_config_import(self):
        """Importing spellbook.core.config must not glob and parse rules/.

        This module is imported by the PreToolUse bash gate, which runs on
        every single Bash call. Registering the defaults at import time made
        every one of those calls parse the whole ruleset.
        """
        from spellbook.core.config import CONFIG_DEFAULTS

        assert not [k for k in CONFIG_DEFAULTS if k.startswith("rules.module.")]


REPO_ROOT = Path(__file__).resolve().parents[2]

# The exact rule modules this release ships, keyed by the stable opaque ``id``
# rather than by filename, so renumbering a file is not a change and renaming a
# module IS one. Adding, removing, or renaming a module must be a deliberate
# edit here. A count would not do: swapping one module for another keeps the
# count and loses the module.
EXPECTED_MANDATORY_IDS = frozenset(
    {
        "core",
        "core-philosophy",
        "diff-semantics",
        "git-safety",
        "intent-routing",
        "orchestration",
        "role",
        "verification",
    }
)

EXPECTED_PREFERENCE_IDS = frozenset(
    {
        "ai-attribution",
        "autonomy",
        "code-quality",
        "communication",
        "develop-discipline",
        "file-reading",
        "language-python",
        "opportunity-awareness",
        "pr-conventions",
        "session",
        "stated-action",
        "testing",
        "worktrees",
    }
)

EXPECTED_MODULE_IDS = EXPECTED_MANDATORY_IDS | EXPECTED_PREFERENCE_IDS


class TestShippedModuleSetIsPinned:
    """Pin the shipped module set so an unstaged module cannot ship silently.

    The near-miss this guards: a rule module was authored on disk but never
    staged. Every other check passed. The schema validator reads the FILESYSTEM,
    so it saw the new module and approved it; CI checks out the COMMITTED tree,
    so it saw one fewer module and also approved it. Neither compares the two.
    """

    @pytest.fixture
    def shipped(self):
        # get_rules_dir is the same resolver installer/core.py uses, so this
        # reads the module set through the installer's own entry point rather
        # than through a path this test invented.
        modules = load_rule_modules(get_rules_dir(REPO_ROOT))
        assert modules, "the checkout must ship rule modules in rules/"
        return modules

    def test_the_shipped_module_ids_are_exactly_the_pinned_set(self, shipped):
        assert {m.id for m in shipped} == set(EXPECTED_MODULE_IDS)

    def test_each_module_keeps_its_pinned_class(self, shipped):
        """A module flipped between mandatory and preference changes what every
        install delivers, so the class is pinned per id, not just the totals."""
        assert {m.id for m in shipped if m.is_mandatory} == set(
            EXPECTED_MANDATORY_IDS
        )
        assert {m.id for m in preference_modules(shipped)} == set(
            EXPECTED_PREFERENCE_IDS
        )

    def test_every_rule_module_on_disk_is_tracked_by_git(self):
        """The assertion that would actually have caught the near-miss.

        ``load_rule_modules`` reads the working tree, so an untracked module is
        indistinguishable from a committed one until the commit lands without
        it. Compare the two listings directly.
        """
        tracked = subprocess.run(
            ["git", "ls-files", "--", "rules/*.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked_names = {
            Path(line).name for line in tracked.stdout.splitlines() if line
        }
        on_disk = {p.name for p in get_rules_dir(REPO_ROOT).glob("*.md")}

        assert on_disk - tracked_names == set(), (
            "rule module(s) exist on disk but are untracked; they would be "
            "absent from the commit while every filesystem-reading check passes"
        )
        assert tracked_names - on_disk == set(), (
            "rule module(s) are tracked by git but missing from the working tree"
        )


class TestOpenCodeRegistrationPathRendering:
    def test_paths_under_home_are_rendered_portably(self, tmp_path, monkeypatch):
        from installer.platforms.opencode import OpenCodeInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        # Path.home() resolves through ntpath.expanduser on Windows, which
        # reads USERPROFILE (then HOMEPATH) and never consults HOME. Without
        # this the probe path is not under home, relative_to() raises, and the
        # renderer correctly falls back to the absolute path -- green on POSIX
        # and red on Windows for no behavioural reason.
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        config_dir = tmp_path / ".config" / "opencode"
        config_dir.mkdir(parents=True)

        installer = OpenCodeInstaller(tmp_path / "spellbook", config_dir, "1.2.3")
        rendered = installer._instructions_config_path(
            config_dir / "instructions" / "00-spellbook-core.md"
        )

        assert rendered == "~/.config/opencode/instructions/00-spellbook-core.md"


class TestInstalledVersionStamp:
    def test_round_trips_through_the_stamp(self, tmp_path, monkeypatch):
        """previous_version used to read a marker the installer strips every
        run, so it was permanently None and every install claimed to be fresh."""
        from installer.version import read_installed_version, write_installed_version

        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(tmp_path))

        assert read_installed_version() is None
        write_installed_version("1.2.3")
        assert read_installed_version() == "1.2.3"

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        from installer.version import read_installed_version, write_installed_version

        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(tmp_path))

        write_installed_version("1.2.3", dry_run=True)
        assert read_installed_version() is None


class TestTripwire:
    def test_a_missing_marker_is_a_failure_not_a_warning(self, tmp_path):
        from installer.components.rule_tripwire import TripwireStatus, verify_platform

        bundle = tmp_path / "AGENTS.md"
        bundle.write_text("no marker here\n", encoding="utf-8")

        result = verify_platform("pi", "1.2.3", bundle_path=bundle)

        assert result.status is TripwireStatus.FAILED
        assert not result.ok

    def test_a_present_marker_is_reported_as_degraded_not_verified(self, tmp_path):
        """The assembled prompt is not obtainable for this harness, and the
        report must say so rather than claim verification."""
        from installer.components.rule_tripwire import TripwireStatus, verify_platform

        bundle = tmp_path / "AGENTS.md"
        bundle.write_text(delivery_marker("1.2.3") + "\n", encoding="utf-8")

        result = verify_platform("pi", "1.2.3", bundle_path=bundle)

        assert result.status is TripwireStatus.DEGRADED
        assert result.method == "content-asserted"
        assert result.ok

    def test_unregistered_modules_are_a_failure(self, tmp_path):
        """On opencode a file that is not in the instructions array does not
        load, so path presence alone is not delivery."""
        from installer.components.rule_tripwire import TripwireStatus, verify_platform

        rules = tmp_path / "instructions"
        rules.mkdir()
        source = tmp_path / "00-core.md"
        source.write_text("x", encoding="utf-8")
        (rules / "00-spellbook-core.md").symlink_to(source)

        result = verify_platform(
            "opencode", "1.2.3", module_dir=rules, registered=False
        )

        assert result.status is TripwireStatus.FAILED

    def test_a_dangling_core_link_is_a_failure(self, tmp_path):
        from installer.components.rule_tripwire import TripwireStatus, verify_platform

        rules = tmp_path / "rules"
        rules.mkdir()
        (rules / "00-spellbook-core.md").symlink_to(tmp_path / "gone.md")

        result = verify_platform("claude_code", "1.2.3", module_dir=rules)

        assert result.status is TripwireStatus.FAILED


class TestNonTtyConfigSafety:
    def test_a_non_interactive_install_records_nothing(self, tmp_path, monkeypatch):
        """The branch K5 cares most about: a scripted install must never write
        an opt-in module to True on the user's behalf."""
        import argparse

        from spellbook.cli.commands.install import _select_rule_modules

        # HOME, not SPELLBOOK_CONFIG_DIR: ``spellbook.core.compat.get_config_dir``
        # -- the resolver every installer config read and write goes through --
        # does not consult SPELLBOOK_CONFIG_DIR, so setting it redirects nothing
        # and the assertions below would run against the developer's own machine.
        monkeypatch.setenv("HOME", str(tmp_path))

        class _Installer:
            spellbook_dir = Path(__file__).resolve().parents[2]

        args = argparse.Namespace(dry_run=False, yes=True, no_interactive=False)
        assert _select_rule_modules(_Installer(), None, args) is None

        args = argparse.Namespace(dry_run=True, yes=False, no_interactive=False)
        assert _select_rule_modules(_Installer(), None, args) is None

        args = argparse.Namespace(dry_run=False, yes=False, no_interactive=True)
        assert _select_rule_modules(_Installer(), None, args) is None

        # Unconditional, and directory-wide. A conditional assertion on one
        # filename never executes on the passing path, so a regression that
        # persists through any other path or filename goes undetected.
        config = tmp_path / "spellbook.json"
        assert not config.exists(), "a non-interactive install must write no config"
        assert not list(tmp_path.rglob("*.json")), "nothing may be persisted"

    def test_the_selector_returns_no_answer_when_it_cannot_prompt(self):
        """The property the class name claims, at the layer that decides it.

        ``interactive_module_select`` used to return the pre-resolved selection
        on a non-tty. Callers persist a returned list, so that recorded True for
        every default-on module AND False for every default-off one -- marking
        modules declined that the user was never shown.
        """
        from installer import tui

        rules_dir = Path(__file__).resolve().parents[2] / "rules"
        selection = resolve_selection(load_rule_modules(rules_dir))
        assert selection.selected_ids, "precondition: something would be recorded"

        # pytest's stdin is genuinely not a tty, so this needs no substitution.
        assert tui.module_select_available() is False
        assert tui.interactive_module_select(selection) is None

    def test_the_selector_returns_no_answer_on_windows(self):
        """A real tty with no termios -- the shape the isatty guards miss.

        On Windows stdin IS a tty and ``termios`` is absent, so every upstream
        ``isatty`` gate passes and only this layer stops the write.
        """
        from installer import tui

        rules_dir = Path(__file__).resolve().parents[2] / "rules"
        selection = resolve_selection(load_rule_modules(rules_dir))
        assert selection.selected_ids, "precondition: something would be recorded"

        isatty = tripwire.mock.object(sys.stdin, "isatty")
        isatty.returns(True).returns(True)
        has_termios = tripwire.mock("installer.tui:termios_available")
        has_termios.returns(False).returns(False)

        with tripwire:
            assert tui.module_select_available() is False
            assert tui.interactive_module_select(selection) is None

        isatty.assert_call(args=(), kwargs={})
        has_termios.assert_call(args=(), kwargs={})
        isatty.assert_call(args=(), kwargs={})
        has_termios.assert_call(args=(), kwargs={})

    @pytest.mark.parametrize("key", ["q", "\x1b", "\x03"])
    def test_cancelling_the_selector_is_not_an_answer(self, key):
        """q / ESC / Ctrl-C must return the not-asked sentinel, not a list.

        Returning the currently-checked options on cancel would record the
        pre-checked defaults as the user's explicit answer, which is
        indistinguishable at the config layer from them having chosen it.
        """
        from installer import tui

        rules_dir = Path(__file__).resolve().parents[2] / "rules"
        selection = resolve_selection(load_rule_modules(rules_dir))

        available = tripwire.mock("installer.tui:module_select_available")
        available.returns(True)
        read_key = tripwire.mock("installer.tui:read_key")
        read_key.returns(key)

        with tripwire:
            assert tui.interactive_module_select(selection) is None, (
                f"{key!r} recorded an answer the user did not give"
            )

        available.assert_call(args=(), kwargs={})
        read_key.assert_call(args=(), kwargs={})

    def test_the_root_installer_records_nothing_when_it_cannot_prompt(
        self, tmp_path, monkeypatch
    ):
        """The curl-pipe entry point, which had no coverage at all.

        ``spellbook/cli/commands/install.py`` was the only path tested, and it
        is the one that was already gated. Root ``install.py`` derives
        ``no_interactive`` from the CLI flag alone, so on a terminal without
        termios it reached the selector and persisted all 15 keys unprompted.
        """
        import importlib.util

        monkeypatch.setenv("HOME", str(tmp_path))

        repo_root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "_root_install_under_test", repo_root / "install.py"
        )
        root_install = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = root_install
        try:
            spec.loader.exec_module(root_install)

            class _Installer:
                spellbook_dir = repo_root

            selection = root_install._resolve_rule_precheck(_Installer())
            assert selection is not None, "precondition: the selector would open"

            # A terminal that cannot drive the checkbox UI -- the Windows shape,
            # where every isatty gate upstream passes and only the selector's
            # own capability check stops the write.
            interactive = tripwire.mock(f"{spec.name}:is_interactive")
            interactive.returns(True)
            available = tripwire.mock("installer.tui:module_select_available")
            available.returns(False)

            import argparse

            args = argparse.Namespace(dry_run=False, yes=False)
            with tripwire:
                root_install._reconfigure_rule_selection(_Installer(), args)

            interactive.assert_call(args=(), kwargs={})
            available.assert_call(args=(), kwargs={})
        finally:
            sys.modules.pop(spec.name, None)

        assert not list(tmp_path.rglob("*.json")), "nothing may be persisted"


class TestFlatDeliveryDataLoss:
    """The two shapes that had no coverage and hid two CRITICAL data-loss bugs.

    Both existing preserve-or-merge tests pre-create a user file, so neither
    exercised the fresh-install path (which wrote an unmarked bundle that the
    next install read back as user content) nor uninstall against a file
    spellbook never wrote.
    """

    def test_forgecode_reinstall_does_not_double_the_ruleset(
        self, rules_dir, tmp_path
    ):
        """No pre-existing file, which is the case that doubled.

        Writing a bare, unmarked bundle on the first install made ``_split_merged``
        return had_ours=False on the second, so spellbook's own 47KB of output
        was preserved as "user content" and prepended verbatim -- permanently.
        """
        from installer.components.rule_bundle import MODULE_MARKER_PREFIX

        modules = load_rule_modules(rules_dir)
        path = tmp_path / "forge" / "AGENTS.md"
        assert not path.exists(), "precondition: no pre-existing file"

        sizes = []
        markers = []
        for _ in range(3):
            outcome = write_bundle(
                path,
                generate_bundle(modules, "1.2.3", "forgecode"),
                preserve_existing=True,
            )
            assert outcome.success
            written = path.read_text(encoding="utf-8")
            sizes.append(len(written.encode("utf-8")))
            markers.append(written.count(MODULE_MARKER_PREFIX))

        assert len(set(sizes)) == 1, f"bundle size grew across installs: {sizes}"
        assert len(set(markers)) == 1, f"module count grew across installs: {markers}"
        assert markers[0] == len(modules)
        # And it never backs up its own output.
        assert list(path.parent.glob("AGENTS.md.backup.*")) == []

    def test_a_fresh_install_writes_the_merge_markers(self, rules_dir, tmp_path):
        """Which is also what lets uninstall remove exactly its own region."""
        modules = load_rule_modules(rules_dir)
        path = tmp_path / "forge" / "AGENTS.md"

        write_bundle(
            path, generate_bundle(modules, "1.2.3", "forgecode"), preserve_existing=True
        )

        written = path.read_text(encoding="utf-8")
        assert written.count(MERGE_START) == 1
        assert written.count(MERGE_END) == 1

    def test_uninstall_removes_a_bundle_it_wrote(self, rules_dir, tmp_path):
        from installer.components.rule_delivery import remove_bundle

        modules = load_rule_modules(rules_dir)
        path = tmp_path / "forge" / "AGENTS.md"
        write_bundle(
            path, generate_bundle(modules, "1.2.3", "forgecode"), preserve_existing=True
        )

        assert remove_bundle(path, preserve_existing=True) == path
        assert not path.exists()

    def test_uninstall_never_deletes_a_user_authored_instruction_file(
        self, tmp_path
    ):
        """CRITICAL: ``remove_bundle`` unlinked whatever sat at the path.

        ``~/.codex/AGENTS.md`` and ``~/.pi/agent/AGENTS.md`` are the user's own
        global instruction files, and uninstall is gated only on the config dir
        existing -- so this fired on machines spellbook had never installed to.
        """
        from installer.components.rule_delivery import remove_bundle

        path = tmp_path / ".codex" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        original = "# my own global instructions\n\nAlways do the thing.\n"
        path.write_text(original, encoding="utf-8")

        for preserve in (True, False):
            assert remove_bundle(path, preserve_existing=preserve) is None
            assert path.exists(), "the user's file was deleted"
            assert path.read_text(encoding="utf-8") == original

    def test_codex_uninstall_leaves_a_user_authored_agents_md_intact(self, tmp_path):
        """The same property through the real installer, end to end."""
        from installer.platforms.codex import CodexInstaller

        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        agents = config_dir / "AGENTS.md"
        original = "# my own global instructions\n\nAlways do the thing.\n"
        agents.write_text(original, encoding="utf-8")

        installer = CodexInstaller(
            Path(__file__).resolve().parents[2], config_dir, "1.2.3"
        )
        installer.uninstall_rule_modules()

        assert agents.exists(), "uninstall deleted the user's global instructions"
        assert agents.read_text(encoding="utf-8") == original

    def test_codex_install_preserves_a_user_authored_agents_md(self, tmp_path):
        """Codex reads exactly one instruction file, so clobbering it stops the
        user's own instructions loading entirely."""
        from installer.platforms.codex import CodexInstaller

        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        agents = config_dir / "AGENTS.md"
        original = "# my own global instructions\n\nAlways do the thing.\n"
        agents.write_text(original, encoding="utf-8")

        repo_root = Path(__file__).resolve().parents[2]
        installer = CodexInstaller(repo_root, config_dir, "1.2.3")
        assert installer.rule_bundle_preserve_existing() is True

        results = installer.install_rule_modules()
        assert all(r.success for r in results), [r.message for r in results]

        written = agents.read_text(encoding="utf-8")
        assert written.startswith(original.rstrip()), "user content was not kept first"
        assert delivery_marker("1.2.3") in written
        backups = list(config_dir.glob("AGENTS.md.backup.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == original

    def test_pi_preserves_its_users_instruction_file_too(self, tmp_path):
        from installer.platforms.pi import PiInstaller

        installer = PiInstaller(
            Path(__file__).resolve().parents[2], tmp_path / "agent", "1.2.3"
        )
        assert installer.rule_bundle_preserve_existing() is True


class TestEmptyModuleSetIsAHardFailure:
    """Delivering nothing PRUNES everything, so it can never be a silent path."""

    def test_a_resolution_error_refuses_to_touch_delivered_rules(
        self, rules_dir, tmp_path
    ):
        from installer.platforms.claude_code import ClaudeCodeInstaller

        repo_root = Path(__file__).resolve().parents[2]
        config_dir = tmp_path / ".claude"
        rules_target = config_dir / "rules"
        rules_target.mkdir(parents=True)
        for name in ("00-spellbook-core.md", "10-spellbook-session.md"):
            (rules_target / name).write_text("delivered\n", encoding="utf-8")

        installer = ClaudeCodeInstaller(
            repo_root,
            config_dir,
            "1.2.3",
            context={"rule_delivery_error": "rules/ is unreadable"},
        )
        results = installer.install_rule_modules()

        assert results and not any(r.success for r in results)
        assert sorted(p.name for p in rules_target.glob("*.md")) == [
            "00-spellbook-core.md",
            "10-spellbook-session.md",
        ], "an unresolvable module set pruned the delivered rules"

    def test_an_empty_selection_is_a_failure_not_a_delivery_of_nothing(
        self, tmp_path
    ):
        from installer.platforms.claude_code import ClaudeCodeInstaller

        repo_root = Path(__file__).resolve().parents[2]
        config_dir = tmp_path / ".claude"
        rules_target = config_dir / "rules"
        rules_target.mkdir(parents=True)
        (rules_target / "00-spellbook-core.md").write_text("x\n", encoding="utf-8")

        installer = ClaudeCodeInstaller(
            repo_root, config_dir, "1.2.3", context={"rule_modules": []}
        )
        results = installer.install_rule_modules()

        assert results and not any(r.success for r in results)
        assert (rules_target / "00-spellbook-core.md").exists()

    def test_core_resolution_reports_an_error_for_an_absent_rules_dir(self, tmp_path):
        from installer.core import Installer

        installer = Installer.__new__(Installer)
        installer.spellbook_dir = tmp_path
        installer.version = "1.2.3"

        modules, selection, _detection, error = installer._resolve_rule_delivery(
            [], None, None, True
        )

        assert modules == []
        assert selection is None
        assert error, "an unresolvable module set must be reported, not swallowed"

    def _answered(self, rule_selection):
        from installer.core import Installer

        installer = Installer.__new__(Installer)
        installer.spellbook_dir = Path(__file__).resolve().parents[2]
        installer.version = "1.2.3"
        return installer._resolve_rule_delivery([], None, rule_selection, True)

    def test_declining_everything_leaves_no_stale_precheck_state(self):
        """The answer, not the config, defines EVERY field of the selection.

        Patching only selected/declined left ``prechecked_ids`` and
        ``unanswered_ids`` describing the pre-answer state, so the next
        consumer would read a module the user just declined as still checked
        and never offered.
        """
        modules, selection, _detection, error = self._answered([])

        preference_ids = [m.id for m in modules if m.is_preference]
        assert not error
        assert preference_ids, "no preference modules -- the assertions below prove nothing"
        assert selection.selected_ids == []
        assert selection.declined_ids == preference_ids
        assert selection.prechecked_ids == []
        assert selection.unanswered_ids == []

    def test_an_accepted_module_is_neither_prechecked_nor_unanswered(self):
        modules, selection, _detection, error = self._answered([])
        kept = [m.id for m in modules if m.is_preference][0]

        modules, selection, _detection, error = self._answered([kept])

        assert not error
        assert selection.selected_ids == [kept]
        assert kept not in selection.declined_ids
        assert selection.prechecked_ids == []
        assert selection.unanswered_ids == []


class TestBackupIsUnconditionalBeforeSpellbookTakesAPath:
    """The classifier decides what is PRESERVED. It must never decide whether a
    copy exists.

    ``_is_generated_bundle`` is a bare substring test for spellbook's per-module
    marker anywhere in the file. Any user file containing that substring was
    classified as spellbook's own output and discarded with no backup -- and the
    population that hits it is exactly the one this branch creates, where an
    older spellbook wrote a bare unmarked bundle at ``~/.codex/AGENTS.md`` and
    the user appended their own rules below it.
    """

    def _bundle(self, rules_dir):
        return generate_bundle(load_rule_modules(rules_dir), "1.2.3", "codex")

    def test_a_user_file_quoting_the_module_marker_is_backed_up(
        self, rules_dir, tmp_path
    ):
        from installer.components.rule_bundle import MODULE_MARKER_PREFIX

        path = tmp_path / ".codex" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        original = (
            "# my precious rules\n"
            f"{MODULE_MARKER_PREFIX} core (0.1.0) -->\n"
            "my text\n"
        )
        path.write_text(original, encoding="utf-8")

        outcome = write_bundle(path, self._bundle(rules_dir), preserve_existing=True)

        assert outcome.success
        backups = list(path.parent.glob("AGENTS.md.backup.*"))
        assert len(backups) == 1, "the user's bytes were discarded with no copy"
        assert backups[0].read_text(encoding="utf-8") == original
        assert outcome.notes, "a discarded file must be reported, not silent"

    def test_the_unconditional_backup_fires_at_most_once_per_path(
        self, rules_dir, tmp_path
    ):
        """Every later install finds the merge markers, so the branch is skipped.

        Without this the fix would drop a timestamped copy beside the artifact
        on every single run, forever.
        """
        path = tmp_path / ".codex" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        path.write_text("# mine\n", encoding="utf-8")

        for _ in range(3):
            assert write_bundle(
                path, self._bundle(rules_dir), preserve_existing=True
            ).success

        assert len(list(path.parent.glob("AGENTS.md.backup.*"))) == 1

    def test_an_unterminated_region_is_backed_up_before_the_rewrite(
        self, rules_dir, tmp_path
    ):
        """A START with no END makes the tail unattributable.

        ``_split_merged`` keeps only the head, and because it reports
        had_ours=True the backup branch was skipped entirely -- so a hand edit
        that removed the END marker silently deleted everything below it.
        """
        path = tmp_path / ".codex" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        original = (
            "# my rules\nkeep me\n"
            f"{MERGE_START}\nspellbook stuff\nMY IMPORTANT TAIL\n"
        )
        path.write_text(original, encoding="utf-8")

        outcome = write_bundle(path, self._bundle(rules_dir), preserve_existing=True)

        assert outcome.success
        backups = list(path.parent.glob("AGENTS.md.backup.*"))
        assert len(backups) == 1, "the damaged file was rewritten with no copy"
        assert "MY IMPORTANT TAIL" in backups[0].read_text(encoding="utf-8")
        assert outcome.notes

    def test_uninstall_backs_up_an_unterminated_region_too(self, rules_dir, tmp_path):
        from installer.components.rule_delivery import remove_bundle

        path = tmp_path / ".codex" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            f"# my rules\n{MERGE_START}\nstuff\nMY IMPORTANT TAIL\n", encoding="utf-8"
        )

        remove_bundle(path, preserve_existing=True)

        backups = list(path.parent.glob("AGENTS.md.backup.*"))
        assert len(backups) == 1
        assert "MY IMPORTANT TAIL" in backups[0].read_text(encoding="utf-8")


class TestModulesRegisteredComputation:
    """Direct coverage for ``_modules_registered``.

    The existing tripwire test passes ``registered=False`` to ``verify_platform``
    as a literal, so it proves the enum branch and never the computation that
    produces it, nor the wiring between them.
    """

    def _opencode(self, tmp_path):
        from installer.platforms.opencode import OpenCodeInstaller

        config_dir = tmp_path / ".config" / "opencode"
        config_dir.mkdir(parents=True)
        return OpenCodeInstaller(
            Path(__file__).resolve().parents[2], config_dir, "1.2.3", dry_run=True
        )

    def _deliver(self, probe, names=("00-spellbook-core.md",)):
        module_dir = probe.rule_module_dir()
        module_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            (module_dir / name).write_text("x\n", encoding="utf-8")
        return module_dir

    def _write_config(self, probe, payload: str):
        probe.opencode_config_file.parent.mkdir(parents=True, exist_ok=True)
        probe.opencode_config_file.write_text(payload, encoding="utf-8")

    def test_every_module_listed_is_registered(self, tmp_path, monkeypatch):
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = self._deliver(probe)
        entry = probe._instructions_config_path(module_dir / "00-spellbook-core.md")
        self._write_config(probe, json.dumps({"instructions": [entry]}))

        assert _modules_registered("opencode", probe, module_dir) is True

    def test_a_partially_registered_delivery_is_not_registered(
        self, tmp_path, monkeypatch
    ):
        """The all(...) branch: one unlisted module does not load at all."""
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = self._deliver(
            probe, ("00-spellbook-core.md", "10-spellbook-session.md")
        )
        entry = probe._instructions_config_path(module_dir / "00-spellbook-core.md")
        self._write_config(probe, json.dumps({"instructions": [entry]}))

        assert _modules_registered("opencode", probe, module_dir) is False

    def test_a_bare_string_instructions_value_is_normalized(
        self, tmp_path, monkeypatch
    ):
        """``instructions`` is documented as an array, but a hand-edited config
        may hold a single string. Treating that as a list of characters would
        report a correct registration as missing."""
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = self._deliver(probe)
        entry = probe._instructions_config_path(module_dir / "00-spellbook-core.md")
        self._write_config(probe, json.dumps({"instructions": entry}))

        assert _modules_registered("opencode", probe, module_dir) is True

    def test_an_unparseable_config_is_not_registered(self, tmp_path, monkeypatch):
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = self._deliver(probe)
        self._write_config(probe, "{not json")

        assert _modules_registered("opencode", probe, module_dir) is False

    def test_a_non_dict_config_is_not_registered(self, tmp_path, monkeypatch):
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = self._deliver(probe)
        self._write_config(probe, "[]")

        assert _modules_registered("opencode", probe, module_dir) is False

    def test_a_missing_config_is_not_registered(self, tmp_path, monkeypatch):
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = self._deliver(probe)
        assert not probe.opencode_config_file.exists()

        assert _modules_registered("opencode", probe, module_dir) is False

    def test_an_empty_module_dir_is_not_registered(self, tmp_path, monkeypatch):
        """Nothing delivered is not the same as everything registered."""
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = probe.rule_module_dir()
        module_dir.mkdir(parents=True, exist_ok=True)
        self._write_config(probe, json.dumps({"instructions": []}))

        assert _modules_registered("opencode", probe, module_dir) is False

    def test_registration_is_not_a_load_mechanism_off_opencode(
        self, tmp_path, monkeypatch
    ):
        from installer.core import _modules_registered

        monkeypatch.setenv("HOME", str(tmp_path))
        probe = self._opencode(tmp_path)
        module_dir = self._deliver(probe)

        assert _modules_registered("claude_code", probe, module_dir) is None
        assert _modules_registered("opencode", probe, None) is None


class TestVerifyRuleDeliveryWiring:
    """The caller side. ``_modules_registered`` returning the right answer is
    worthless if the tripwire is never handed it."""

    def _installer(self, tmp_path):
        from installer.core import Installer

        installer = Installer.__new__(Installer)
        installer.spellbook_dir = Path(__file__).resolve().parents[2]
        installer.version = "1.2.3"
        return installer

    def test_an_unregistered_opencode_delivery_fails_verification(
        self, tmp_path, monkeypatch
    ):
        from installer.core import InstallResult
        from installer.platforms.opencode import OpenCodeInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        config_dir = tmp_path / ".config" / "opencode"
        config_dir.mkdir(parents=True)

        probe = OpenCodeInstaller(
            Path(__file__).resolve().parents[2], config_dir, "1.2.3", dry_run=True
        )
        module_dir = probe.rule_module_dir()
        module_dir.mkdir(parents=True, exist_ok=True)
        source = tmp_path / "00-core.md"
        source.write_text("x\n", encoding="utf-8")
        (module_dir / "00-spellbook-core.md").symlink_to(source)
        probe.opencode_config_file.parent.mkdir(parents=True, exist_ok=True)
        probe.opencode_config_file.write_text(
            json.dumps({"instructions": []}), encoding="utf-8"
        )

        installer = self._installer(tmp_path)
        results = installer._verify_rule_delivery(
            [("opencode", [config_dir])],
            object(),
            [
                InstallResult(
                    component="rule_modules",
                    platform="opencode",
                    success=True,
                    action="installed",
                    message="ok",
                )
            ],
        )

        assert results, "a delivered platform must produce a verdict"
        assert not results[0].success, (
            "files on disk that opencode never loads reported as delivered"
        )

    def test_a_probe_that_raises_produces_a_failure_not_silence(
        self, tmp_path, monkeypatch
    ):
        """No result at all read exactly like a pass: the platform delivered
        rules and then neither passed nor failed verification."""
        from installer.core import InstallResult

        monkeypatch.setenv("HOME", str(tmp_path))
        installer = self._installer(tmp_path)

        boom = RuntimeError("probe exploded")
        probe = tripwire.mock("installer.core:get_platform_installer")
        probe.raises(boom)

        with tripwire:
            results = installer._verify_rule_delivery(
                [("claude_code", [tmp_path / ".claude"])],
                object(),
                [
                    InstallResult(
                        component="rule_modules",
                        platform="claude_code",
                        success=True,
                        action="installed",
                        message="ok",
                    )
                ],
            )

        probe.assert_call(
            args=("claude_code", installer.spellbook_dir, "1.2.3"),
            kwargs={"dry_run": True, "config_dir_override": tmp_path / ".claude"},
            raised=boom,
        )
        tripwire.log.assert_log(
            "WARNING",
            "Tripwire probe failed for claude_code: probe exploded",
            "installer.core",
        )

        assert len(results) == 1
        assert not results[0].success
        assert "probe exploded" in results[0].message


class TestUnreadableRulesDirectoryIsDiagnosedCorrectly:
    def test_a_permission_error_is_not_reported_as_an_empty_ruleset(self, tmp_path):
        """``Path.glob`` swallows OSError and yields nothing, so an unreadable
        rules/ told the user "no rule modules found" -- the wrong problem."""
        rules = tmp_path / "rules"
        rules.mkdir()
        (rules / "00-core.md").write_text("x\n", encoding="utf-8")
        os.chmod(rules, 0o000)
        try:
            if os.access(rules, os.R_OK):
                pytest.skip("running as a user that ignores directory permissions")
            with pytest.raises(RuleModuleError) as exc:
                load_rule_modules(rules)
        finally:
            os.chmod(rules, 0o755)

        assert "cannot read" in str(exc.value)


class TestRuleModuleDefaultsFollowTheCheckout:
    def test_the_memoized_defaults_are_keyed_on_the_checkout(
        self, tmp_path, monkeypatch
    ):
        """The MCP server is long-lived. A single-slot cache served the previous
        checkout's defaults forever after SPELLBOOK_DIR moved."""
        from spellbook.core.config import rule_module_config_defaults

        repo_root = Path(__file__).resolve().parents[2]
        monkeypatch.setenv("SPELLBOOK_DIR", str(repo_root))
        real = rule_module_config_defaults()
        assert real, "precondition: the real checkout ships preference modules"

        empty_checkout = tmp_path / "elsewhere"
        empty_checkout.mkdir()
        monkeypatch.setenv("SPELLBOOK_DIR", str(empty_checkout))
        assert rule_module_config_defaults() == {}

        monkeypatch.setenv("SPELLBOOK_DIR", str(repo_root))
        assert rule_module_config_defaults() == real
