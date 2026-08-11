"""Integration tests for the Prime Agent rule-module + extension install path.

Verifies the new delivery mechanism (PR for fix/prime-agent-rules-via-extension):

- Rule modules from ``<spellbook>/rules/`` are symlinked to
  ``<config_dir>/rules/XX-spellbook-<id>.md``, honoring the same
  ``rules.module.<id>`` selection every other platform uses.
- Deselection removes the symlink (the same artifact is the only signal
  Prime Agent has that a rule is gone, so pruning is required).
- The ``spellbook-rules.ts`` extension is symlinked at
  ``<config_dir>/extensions/spellbook-rules.ts`` and points at the
  spellbook checkout, so upgrades flow through without reinstalling.
- ``~/.prime/agent/AGENTS.md`` is NEVER created -- that file belongs to
  the user.
- Install is idempotent: re-running produces the same filesystem state.
- Uninstall is complete: rule symlinks and the extension are removed;
  ``detect()`` flips back to installed=False.
"""

from pathlib import Path

from installer.platforms.prime_agent import PrimeAgentInstaller


def _make_spellbook(tmp_path: Path, *, rule_modules: list[str] | None = None) -> Path:
    """Build a minimal spellbook checkout under tmp_path with the given rule modules.

    A bare spellbook dir needs at least one skill (so the skill step does
    not trip over a missing source), and the rule modules requested.
    """
    rule_modules = rule_modules or ["00-core"]
    spellbook_dir = tmp_path / "spellbook"
    (spellbook_dir / "skills").mkdir(parents=True)
    (spellbook_dir / "commands").mkdir(parents=True)
    (spellbook_dir / "extensions" / "prime-agent").mkdir(parents=True)

    # Minimal skill: anything non-empty so the skill symlink step succeeds.
    skill_dir = spellbook_dir / "skills" / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# test skill\n")

    # Rule modules: real frontmatter, real body -- the installer's
    # ``load_rule_modules`` reads them with the production parser.
    rules_dir = spellbook_dir / "rules"
    rules_dir.mkdir()
    for slug in rule_modules:
        prefix = slug.split("-", 1)[0]
        is_mandatory = prefix == "00" or slug.endswith("-mandatory")
        cls = "mandatory" if is_mandatory else "preference"
        default_block = (
            ""
            if is_mandatory
            else '\ndefault: "on"\nbenefit: "helpful for tests"\ndeclining_means: "less coverage"'
        )
        (rules_dir / f"{slug}.md").write_text(
            f"---\n"
            f"id: {slug.split('-', 1)[1]}\n"
            f"name: Test {slug}\n"
            f"class: {cls}\n"
            f"description: Test module {slug}.\n"
            f"related: []\n"
            f"renamed_from: []\n"
            f"superseded_by: null\n"
            f"paths: []\n"
            f"{default_block}\n"
            f"---\n\n"
            f"Body of {slug}.\n"
        )

    # Extension source: any non-empty .ts file passes the "source exists"
    # check. We do not run the extension here; that lives inside Prime Agent.
    (spellbook_dir / "extensions" / "prime-agent" / "spellbook-rules.ts").write_text(
        "// stub for tests\nexport default function () {};\n"
    )

    return spellbook_dir


def _new_installer(spellbook_dir: Path, config_dir: Path, *, dry_run: bool = False) -> PrimeAgentInstaller:
    return PrimeAgentInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=config_dir,
        version="0.84.0",
        dry_run=dry_run,
    )


def test_install_creates_rule_symlinks_for_mandatory_and_preference(tmp_path):
    """Mandatory modules always install; preference modules install by default."""
    spellbook = _make_spellbook(tmp_path, rule_modules=["00-core", "10-session", "20-extra"])
    config_dir = tmp_path / ".prime" / "agent"

    installer = _new_installer(spellbook, config_dir)
    results = installer.install()
    assert all(r.success for r in results), [r.message for r in results if not r.success]

    rules_dir = config_dir / "rules"
    assert (rules_dir / "00-spellbook-core.md").is_symlink()
    assert (rules_dir / "10-spellbook-session.md").is_symlink()
    assert (rules_dir / "20-spellbook-extra.md").is_symlink()

    for sym in rules_dir.iterdir():
        assert sym.resolve() == (spellbook / "rules" / sym.name.replace("spellbook-", "")).resolve()


def _installer_with_selection(spellbook_dir, config_dir, *, selected_ids, dry_run=False):
    """Build an installer whose install_rule_modules sees a fixed ModuleSelection.

    Selection resolution happens in the orchestrator layer; the installer
    receives a pre-resolved selection via context. Building the selection
    here directly is the simplest way to express "the user declined X" in
    a test -- no monkey-patching of the config layer required.
    """
    from installer.components.rule_modules import load_rule_modules

    modules = load_rule_modules(spellbook_dir / "rules")
    modules_by_id = {m.id: m for m in modules}

    selected = [modules_by_id[i] for i in selected_ids if i in modules_by_id]
    mandatory = [m for m in modules if m.is_mandatory]
    combined = mandatory + [m for m in selected if not m.is_mandatory]

    # Rebuild a ModuleSelection-like object the installer can consume via
    # ``context["rule_selection"]``. selected_rule_modules only reads
    # ``selected_ids``, so a minimal stand-in is sufficient.
    class _Selection:
        def __init__(self, ids):
            self.selected_ids = list(ids)
            self.prechecked_ids = list(ids)
            self.declined_ids = []
            self.unanswered_ids = []
            self.modules = combined

    selection = _Selection(selected_ids)
    context = {"rule_selection": selection}
    return PrimeAgentInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=config_dir,
        version="0.84.0",
        dry_run=dry_run,
        context=context,
    )


def test_install_skips_declined_preference_modules(tmp_path):
    """A preference module the selection did not include is NOT symlinked."""
    spellbook = _make_spellbook(tmp_path, rule_modules=["00-core", "20-extra"])
    config_dir = tmp_path / ".prime" / "agent"

    # Select only the mandatory core. The "extra" preference is declined.
    installer = _installer_with_selection(
        spellbook, config_dir, selected_ids=["core"]
    )
    results = installer.install()

    assert all(r.success for r in results), [r.message for r in results if not r.success]
    rules_dir = config_dir / "rules"
    assert (rules_dir / "00-spellbook-core.md").is_symlink()
    assert not (rules_dir / "20-spellbook-extra.md").exists(), (
        "declined preference module must not be symlinked"
    )


def test_install_prunes_previously_selected_deselected_modules(tmp_path):
    """If a preference module was installed and the user declines it, the next install removes its symlink."""
    spellbook = _make_spellbook(tmp_path, rule_modules=["00-core", "20-extra"])
    config_dir = tmp_path / ".prime" / "agent"

    # First install: select everything (both core + extra).
    installer = _installer_with_selection(
        spellbook, config_dir, selected_ids=["core", "extra"]
    )
    installer.install()
    assert (config_dir / "rules" / "20-spellbook-extra.md").is_symlink()

    # Decline "extra", reinstall, expect the symlink to be gone.
    installer = _installer_with_selection(
        spellbook, config_dir, selected_ids=["core"]
    )
    results = installer.install()

    assert all(r.success for r in results), [r.message for r in results if not r.success]
    assert not (config_dir / "rules" / "20-spellbook-extra.md").exists()


def test_install_creates_rules_extension_symlink(tmp_path):
    """The TypeScript extension is symlinked into the auto-discovery directory."""
    spellbook = _make_spellbook(tmp_path)
    config_dir = tmp_path / ".prime" / "agent"

    installer = _new_installer(spellbook, config_dir)
    installer.install()

    ext = config_dir / "extensions" / "spellbook-rules.ts"
    assert ext.is_symlink(), "extension symlink must be created"
    assert ext.resolve() == (spellbook / "extensions" / "prime-agent" / "spellbook-rules.ts").resolve()


def test_install_does_not_touch_user_agents_md(tmp_path):
    """The user\'s own AGENTS.md is never read or written by the installer."""
    spellbook = _make_spellbook(tmp_path)
    config_dir = tmp_path / ".prime" / "agent"
    user_agents = config_dir / "AGENTS.md"
    user_agents.parent.mkdir(parents=True, exist_ok=True)
    user_agents.write_text("# my project notes\n")

    installer = _new_installer(spellbook, config_dir)
    installer.install()

    # The file is untouched: same path, same bytes.
    assert user_agents.exists()
    assert user_agents.read_text() == "# my project notes\n"


def test_install_is_idempotent(tmp_path):
    """Re-running install leaves the filesystem in the same state."""
    spellbook = _make_spellbook(tmp_path)
    config_dir = tmp_path / ".prime" / "agent"

    installer = _new_installer(spellbook, config_dir)
    installer.install()
    first = sorted(p.relative_to(config_dir) for p in config_dir.rglob("*") if p.is_symlink())

    installer.install()
    second = sorted(p.relative_to(config_dir) for p in config_dir.rglob("*") if p.is_symlink())

    assert first == second


def test_detect_reports_rules_and_extension(tmp_path):
    """detect() surfaces the rules count and extension presence in details."""
    spellbook = _make_spellbook(tmp_path)
    config_dir = tmp_path / ".prime" / "agent"

    installer = _new_installer(spellbook, config_dir)
    status_before = installer.detect()
    assert status_before.installed is False
    assert status_before.details["extension_installed"] is False
    assert status_before.details["rules_installed"] == 0

    installer.install()
    status_after = installer.detect()
    assert status_after.installed is True
    assert status_after.details["extension_installed"] is True
    assert status_after.details["rules_installed"] >= 1


def test_uninstall_removes_rules_and_extension(tmp_path):
    """uninstall() removes every rule symlink and the extension symlink."""
    spellbook = _make_spellbook(tmp_path, rule_modules=["00-core", "10-session", "20-extra"])
    config_dir = tmp_path / ".prime" / "agent"

    installer = _new_installer(spellbook, config_dir)
    installer.install()
    assert list((config_dir / "rules").glob("??-spellbook-*.md"))
    assert (config_dir / "extensions" / "spellbook-rules.ts").is_symlink()

    results = installer.uninstall()
    assert all(r.success for r in results), [r.message for r in results if not r.success]

    assert not list((config_dir / "rules").glob("??-spellbook-*.md"))
    assert not (config_dir / "extensions" / "spellbook-rules.ts").exists()
    assert installer.detect().installed is False


def test_install_fails_loudly_when_extension_source_missing(tmp_path):
    """If the .ts file is missing from the spellbook checkout, the install fails rather than silently skipping."""
    spellbook = _make_spellbook(tmp_path)
    (spellbook / "extensions" / "prime-agent" / "spellbook-rules.ts").unlink()
    config_dir = tmp_path / ".prime" / "agent"

    installer = _new_installer(spellbook, config_dir)
    results = installer.install()
    ext_results = [r for r in results if r.component == "rules_extension"]
    assert ext_results, "expected a rules_extension InstallResult"
    assert ext_results[0].success is False
    assert "source not found" in ext_results[0].message
