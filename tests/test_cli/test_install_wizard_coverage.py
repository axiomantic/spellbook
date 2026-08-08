"""Coverage tests for the shared installer wizards.

Exercises the three-point contract defined in AGENTS.md "Adding Config
Options":

1. Each new config key has a prompt path (fresh install fires a prompt).
2. Idempotency: prompt is skipped when ``config_is_explicitly_set(key)``
   returns True.
3. ``--reconfigure`` bypasses the skip and forces the prompt.
4. Non-tty stdin (CI / piped install) is a noop for every wizard.
5. Both install entry paths import the shared wizards.

Uses the same captured_config / scripted_input / stdin-tty patterns as
``tests/test_worker_llm/test_installer_wizard.py`` so behavior is
consistent across the test suite.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import tripwire


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def captured_config(monkeypatch):
    """Intercept ``config_set`` and pin ``config_is_explicitly_set`` to False.

    Returns (calls_list, explicit_map). Mutating ``explicit_map[key]=True``
    simulates "already set in spellbook.json".
    """
    calls: list[tuple[str, object]] = []
    explicit: dict[str, bool] = {}

    def _fake_config_set(key, value):
        calls.append((key, value))
        return {"status": "ok"}

    def _fake_is_explicit(key):
        return explicit.get(key, False)

    from spellbook.core import config as _core_cfg

    monkeypatch.setattr(_core_cfg, "config_set", _fake_config_set)
    monkeypatch.setattr(_core_cfg, "config_is_explicitly_set", _fake_is_explicit)
    return calls, explicit


@pytest.fixture
def scripted_input(monkeypatch):
    """Drive ``builtins.input`` from an ordered answer queue.

    Returns a callable ``set_answers(list[str])``.
    """
    queue: list[str] = []

    def _input(prompt: str = "") -> str:
        if not queue:
            raise AssertionError(
                f"scripted_input exhausted; unexpected prompt: {prompt!r}"
            )
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", _input)

    def _set_answers(answers):
        queue.clear()
        queue.extend(answers)

    return _set_answers


@pytest.fixture
def tty(monkeypatch):
    """Pretend stdin is a tty so the wizard prompts rather than returning."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)


@pytest.fixture
def stub_config_get(monkeypatch):
    """Return a controllable ``config_get`` that consults a dict fixture.

    Use this when a wizard must see a specific current value.
    """
    state: dict[str, object] = {}

    from spellbook.core import config as _core_cfg

    def _fake_get(key):
        return state.get(key)

    monkeypatch.setattr(_core_cfg, "config_get", _fake_get)
    # defaults.py does a late import from spellbook.core.config; patching
    # the top-level module is enough for the import-time binding to pick
    # up the replacement.
    return state


# ---------------------------------------------------------------------------
# Defaults wizard: per-key prompt coverage
# ---------------------------------------------------------------------------


_DEFAULTS_KEY_SCRIPT = [
    # (key, default-accept-answer, expected-value)
    # Order MUST match the prompt order in run_defaults_wizard (scripted_input
    # is a FIFO consumed per input() call). All accept bare Enter except
    # session_mode (needs choice index "1" -> none).
    ("security_gates_enabled", "", False),
    ("notify_enabled", "", True),
    ("notify_title", "", "Spellbook"),
    ("auto_update", "", True),
    ("session_mode", "", "none"),
]


class TestDefaultsWizardCoverage:
    """Every key registered in run_defaults_wizard must fire a prompt."""

    def test_fresh_install_prompts_every_key(
        self, captured_config, scripted_input, tty, stub_config_get
    ):
        calls, _ = captured_config

        # Enter for every default; session_mode is a numbered list so the
        # bare-Enter branch returns the current value without a choice.
        scripted_input([ans for (_k, ans, _v) in _DEFAULTS_KEY_SCRIPT])

        from installer.wizards import run_defaults_wizard

        run_defaults_wizard(SimpleNamespace(dry_run=False, reconfigure=False))

        written_keys = [k for (k, _v) in calls]
        for key, _ans, _expected in _DEFAULTS_KEY_SCRIPT:
            assert key in written_keys, (
                f"run_defaults_wizard did not write {key!r}; got {written_keys!r}"
            )

    @pytest.mark.parametrize("key", [k for (k, _a, _v) in _DEFAULTS_KEY_SCRIPT])
    def test_already_set_is_skipped(
        self, captured_config, scripted_input, tty, stub_config_get, key
    ):
        """When a key is already explicit, no prompt fires for that key."""
        calls, explicit = captured_config
        explicit[key] = True

        # Supply Enter answers for the remaining keys. If the code under
        # test prompts for the "already set" key, the queue length would
        # mismatch and the test would fail with AssertionError from the
        # scripted_input fixture.
        remaining = [ans for (k, ans, _v) in _DEFAULTS_KEY_SCRIPT if k != key]
        scripted_input(remaining)

        from installer.wizards import run_defaults_wizard

        run_defaults_wizard(SimpleNamespace(dry_run=False, reconfigure=False))

        written_keys = {k for (k, _v) in calls}
        assert key not in written_keys, (
            f"{key} should have been skipped (already explicitly set)"
        )

    def test_reconfigure_bypasses_skip(
        self, captured_config, scripted_input, tty, stub_config_get
    ):
        """--reconfigure forces every key to prompt, even when set."""
        calls, explicit = captured_config
        # Mark every key as already set.
        for key, _a, _v in _DEFAULTS_KEY_SCRIPT:
            explicit[key] = True

        scripted_input([ans for (_k, ans, _v) in _DEFAULTS_KEY_SCRIPT])

        from installer.wizards import run_defaults_wizard

        run_defaults_wizard(SimpleNamespace(dry_run=False, reconfigure=True))

        written_keys = {k for (k, _v) in calls}
        for key, _a, _v in _DEFAULTS_KEY_SCRIPT:
            assert key in written_keys, (
                f"--reconfigure did not re-prompt for {key!r}"
            )

    def test_non_tty_is_noop(self, captured_config, monkeypatch):
        """Non-interactive stdin must never prompt or write."""
        calls, _ = captured_config
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        def _explode(*_a, **_kw):
            raise AssertionError("input() must not be called for non-tty")

        monkeypatch.setattr("builtins.input", _explode)

        from installer.wizards import run_defaults_wizard

        run_defaults_wizard(SimpleNamespace(dry_run=False, reconfigure=False))

        assert calls == []

    def test_dry_run_is_noop(self, captured_config, monkeypatch):
        """--dry-run short-circuits the wizard regardless of tty."""
        calls, _ = captured_config
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def _explode(*_a, **_kw):
            raise AssertionError("input() must not be called under --dry-run")

        monkeypatch.setattr("builtins.input", _explode)

        from installer.wizards import run_defaults_wizard

        run_defaults_wizard(SimpleNamespace(dry_run=True, reconfigure=False))

        assert calls == []

# ---------------------------------------------------------------------------
# Worker-LLM wizard: advanced-tier prompt coverage
# ---------------------------------------------------------------------------


_WORKER_ADVANCED_KEYS = [
    "worker_llm_timeout_s",
    "worker_llm_max_tokens",
    "worker_llm_tool_safety_timeout_s",
    "worker_llm_allow_prompt_overrides",
    "worker_llm_feature_roundtable",
    "worker_llm_safety_cache_ttl_s",
]


class TestWorkerLLMIdempotency:
    """Idempotency gate + --reconfigure bypass for the worker-LLM wizard."""

    def test_skip_when_base_url_already_set(
        self, captured_config, tty, monkeypatch
    ):
        calls, explicit = captured_config
        explicit["worker_llm_base_url"] = True

        def _explode(*_a, **_kw):
            raise AssertionError("wizard must not prompt when base_url is set")

        monkeypatch.setattr("builtins.input", _explode)

        from installer.wizards import run_worker_llm_wizard

        run_worker_llm_wizard(SimpleNamespace(dry_run=False, reconfigure=False))
        assert calls == []

    def test_reconfigure_bypasses_base_url_skip(
        self, captured_config, scripted_input, tty, monkeypatch
    ):
        """--reconfigure lets the user re-answer the opener."""
        calls, explicit = captured_config
        explicit["worker_llm_base_url"] = True

        # Probe bypassed: fake probe_all returning no endpoints.
        from spellbook.worker_llm import probe as _probe_mod

        async def _no_endpoints():
            return []

        monkeypatch.setattr(
            _probe_mod, "probe_all", lambda timeout_total_s=2.0: _no_endpoints()
        )

        # Decline the opener again; only the sentinel should be written.
        scripted_input(["n"])

        from installer.wizards import run_worker_llm_wizard

        run_worker_llm_wizard(SimpleNamespace(dry_run=False, reconfigure=True))

        # When user declines under --reconfigure and the key was already
        # set, the sentinel-write branch is skipped (idempotency already
        # satisfied).
        written = [k for (k, _v) in calls]
        assert "worker_llm_base_url" not in written, (
            "decline during --reconfigure must not overwrite with sentinel"
        )

    def test_decline_fresh_writes_sentinel(
        self, captured_config, scripted_input, tty, monkeypatch
    ):
        """Fresh install + decline: write the empty sentinel once."""
        calls, _ = captured_config
        from spellbook.worker_llm import probe as _probe_mod

        async def _no_endpoints():
            return []

        monkeypatch.setattr(
            _probe_mod, "probe_all", lambda timeout_total_s=2.0: _no_endpoints()
        )

        scripted_input(["n"])

        from installer.wizards import run_worker_llm_wizard

        run_worker_llm_wizard(SimpleNamespace(dry_run=False, reconfigure=False))

        assert calls == [("worker_llm_base_url", "")]

    def test_non_tty_noop(self, captured_config, monkeypatch):
        calls, _ = captured_config
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        def _explode(*_a, **_kw):
            raise AssertionError("input() must not be called for non-tty")

        monkeypatch.setattr("builtins.input", _explode)

        from installer.wizards import run_worker_llm_wizard

        run_worker_llm_wizard(SimpleNamespace(dry_run=False, reconfigure=False))
        assert calls == []

    def test_dry_run_noop(self, captured_config, monkeypatch):
        calls, _ = captured_config
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def _explode(*_a, **_kw):
            raise AssertionError("input() must not be called under --dry-run")

        monkeypatch.setattr("builtins.input", _explode)

        from installer.wizards import run_worker_llm_wizard

        run_worker_llm_wizard(SimpleNamespace(dry_run=True, reconfigure=False))
        assert calls == []


class TestWorkerLLMAdvancedTier:
    """Opt-in advanced-settings tier covers all 7 previously-hidden keys."""

    def _script_happy_path_with_advanced(self, advanced_answers: list[str]) -> list[str]:
        """Build a full wizard script that accepts the advanced tier.

        The happy path: enable -> pick endpoint 1 -> pick model 1 ->
        blank key -> one feature flag n -> advanced y -> [advanced
        answers] -> doctor n.
        """
        return [
            "y",  # Enable wizard
            "1",  # Endpoint
            "1",  # Model
            "",   # API key
            "n",  # One feature flag (tool_safety)
            "y",  # Advanced? yes
            *advanced_answers,
            "n",  # Doctor
        ]

    def test_advanced_tier_covers_all_keys(
        self, captured_config, scripted_input, tty, monkeypatch
    ):
        calls, _ = captured_config
        from spellbook.worker_llm.probe import DetectedEndpoint
        from spellbook.worker_llm import probe as _probe_mod

        async def _one_endpoint():
            return [DetectedEndpoint(
                base_url="http://localhost:11434/v1",
                label="Ollama",
                models=["qwen2.5-coder:7b"],
                reachable=True,
            )]

        monkeypatch.setattr(
            _probe_mod, "probe_all", lambda timeout_total_s=2.0: _one_endpoint()
        )

        # Six advanced prompts: accept the default for each.
        # number prompts take bare Enter -> default.
        # bool prompt for allow_prompt_overrides takes Enter -> default True.
        # bool prompt for feature_roundtable takes Enter -> default False.
        scripted_input(self._script_happy_path_with_advanced(
            ["", "", "", "", "", ""]
        ))

        from installer.wizards import run_worker_llm_wizard

        run_worker_llm_wizard(SimpleNamespace(dry_run=False, reconfigure=False))

        written = {k for (k, _v) in calls}
        for k in _WORKER_ADVANCED_KEYS:
            assert k in written, f"advanced tier did not write {k!r}"

    @pytest.mark.parametrize("key", _WORKER_ADVANCED_KEYS)
    def test_already_set_advanced_key_is_skipped(
        self, captured_config, scripted_input, tty, monkeypatch, key
    ):
        """An explicit advanced key is skipped when reconfigure is off."""
        calls, explicit = captured_config
        explicit[key] = True
        # Also mark base_url as unset so the wizard runs.
        from spellbook.worker_llm.probe import DetectedEndpoint
        from spellbook.worker_llm import probe as _probe_mod

        async def _one_endpoint():
            return [DetectedEndpoint(
                base_url="http://localhost:11434/v1",
                label="Ollama",
                models=["qwen2.5-coder:7b"],
                reachable=True,
            )]

        monkeypatch.setattr(
            _probe_mod, "probe_all", lambda timeout_total_s=2.0: _one_endpoint()
        )

        # Six remaining advanced prompts.
        remaining = [""] * (len(_WORKER_ADVANCED_KEYS) - 1)
        scripted_input(self._script_happy_path_with_advanced(remaining))

        from installer.wizards import run_worker_llm_wizard

        run_worker_llm_wizard(SimpleNamespace(dry_run=False, reconfigure=False))

        # The skipped key must not have been written during the advanced
        # tier (it may still be unrelated to the core keys).
        calls_after_features = [k for (k, _v) in calls]
        # Core keys are always written; skipped advanced key is not.
        assert calls_after_features.count(key) == 0, (
            f"{key!r} was already set and should have been skipped"
        )


# ---------------------------------------------------------------------------
# Import-path assertions: both entry points wire the shared wizards
# ---------------------------------------------------------------------------


class TestEntryPointsShareWizards:
    """Assert both install entry paths import and use the shared wizards.

    We check source text rather than runtime behavior because actually
    running the root install.py end-to-end inside pytest would touch the
    network, write files, and spin up services. The contract is: if the
    file mentions ``run_defaults_wizard`` and ``run_worker_llm_wizard``,
    the wiring exists.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "install.py",
            "spellbook/cli/commands/install.py",
        ],
    )
    def test_entry_path_invokes_both_shared_wizards(self, path):
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        source = (repo_root / path).read_text(encoding="utf-8")
        assert "run_defaults_wizard" in source, (
            f"{path} does not invoke run_defaults_wizard; "
            "shared wizard coverage contract broken"
        )
        assert "run_worker_llm_wizard" in source, (
            f"{path} does not invoke run_worker_llm_wizard; "
            "shared wizard coverage contract broken"
        )


# ---------------------------------------------------------------------------
# Rule module selection: rules.module.* key coverage
# ---------------------------------------------------------------------------
#
# These use a REAL config file under a tmp SPELLBOOK_CONFIG_DIR rather than
# substituting ``config_is_explicitly_set``. The answered/unanswered state is
# the thing under test, and reading it from disk is what the installer actually
# does -- so the test exercises the same tri-state the product does.


def _repo_root():
    return Path(__file__).resolve().parents[2]


def _shipped_preference_keys():
    from installer.components.rule_modules import (
        get_rules_dir,
        load_rule_modules,
        preference_modules,
    )

    modules = load_rule_modules(get_rules_dir(_repo_root()))
    assert modules, "the checkout must ship rule modules in rules/"
    # Derived, never counted. The module set changes as rules are split.
    return [m.config_key for m in preference_modules(modules)]


def _config_path(home: Path) -> Path:
    """Where ``get_config_dir()`` resolves to for a given HOME.

    HOME, not SPELLBOOK_CONFIG_DIR: ``spellbook.core.compat.get_config_dir`` --
    the resolver the installer's config reads and writes go through -- does not
    consult SPELLBOOK_CONFIG_DIR at all, so setting it redirects nothing.
    """
    return home / ".config" / "spellbook" / "spellbook.json"


def _write_answers(home: Path, keys) -> None:
    """Write real answers for ``keys``, the way ``config_set_many`` would."""
    path = _config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: True for key in keys}), encoding="utf-8")


class _StubInstaller:
    def __init__(self):
        self.spellbook_dir = _repo_root()


@pytest.fixture
def cli_install_module():
    """The ``spellbook install`` entry path."""
    import spellbook.cli.commands.install as mod

    return mod


@pytest.fixture
def root_install_module():
    """The curl-pipe root ``install.py``, loaded by path.

    Loaded as a throwaway module name so importing it cannot shadow the
    ``install`` package name for other tests.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_root_install_wizard_coverage", _repo_root() / "install.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(spec.name, None)


class TestRuleModuleKeyCoverage:
    """The three-point contract of AGENTS.md "Adding Config Options", applied
    to every shipped ``rules.module.*`` key.

    Counts are derived from ``rules/`` rather than hardcoded, so splitting a
    module out does not turn this into a false failure -- or a false pass.
    """

    def test_every_shipped_module_registers_a_config_key(self):
        from spellbook.admin.routes.config import KNOWN_KEYS
        from spellbook.core.config import rule_module_config_defaults

        keys = _shipped_preference_keys()
        assert keys
        defaults = rule_module_config_defaults()
        for key in keys:
            assert key in defaults, f"{key} has no runtime default"
            assert key in KNOWN_KEYS, f"{key} is invisible to the admin UI"

    def test_fresh_install_opens_the_selector(
        self, monkeypatch, tmp_path, root_install_module
    ):
        """Point 1: unanswered keys must produce a prompt."""
        monkeypatch.setenv("HOME", str(tmp_path))

        selection = root_install_module._resolve_rule_precheck(_StubInstaller())

        assert selection is not None, "a fresh install must offer the selector"
        assert selection.unanswered_ids

    def test_reinstall_skips_the_selector_once_every_key_is_answered(
        self, monkeypatch, tmp_path, root_install_module
    ):
        """Point 3: an answered key is never re-prompted."""
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_answers(tmp_path, _shipped_preference_keys())

        assert root_install_module._resolve_rule_precheck(_StubInstaller()) is None

    def test_a_newly_shipped_module_reopens_the_selector(
        self, monkeypatch, tmp_path, root_install_module
    ):
        """Point 2: still unset means still asked, per key.

        A module split out of an existing one arrives with its key absent, so
        the selector must offer that module even though every other key is
        answered.
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        keys = _shipped_preference_keys()
        _write_answers(tmp_path, keys[1:])  # the first module is "new"

        selection = root_install_module._resolve_rule_precheck(_StubInstaller())

        assert selection is not None
        assert keys[0].split(".")[-1] in selection.unanswered_ids

    def test_reconfigure_bypasses_the_idempotency_gate(
        self, monkeypatch, tmp_path, root_install_module
    ):
        """--reconfigure is the only way back to a module the user declined."""
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_answers(tmp_path, _shipped_preference_keys())

        assert (
            root_install_module._resolve_rule_precheck(
                _StubInstaller(), reconfigure=True
            )
            is not None
        )

    def test_non_tty_is_a_noop_in_the_cli_entry_path(
        self, monkeypatch, tmp_path, cli_install_module
    ):
        """Point 4: a scripted install records nothing.

        pytest's stdin is genuinely not a tty, so the gate is exercised for
        real rather than through a substituted ``isatty``.
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        assert not sys.stdin.isatty(), "precondition: pytest stdin is not a tty"

        args = argparse.Namespace(
            dry_run=False, yes=False, no_interactive=False, reconfigure=False
        )
        assert (
            cli_install_module._select_rule_modules(_StubInstaller(), None, args)
            is None
        )
        assert not list(tmp_path.rglob("*.json"))

    def test_cli_entry_path_honors_the_idempotency_gate(
        self, monkeypatch, tmp_path, capsys, cli_install_module
    ):
        """Answered keys, a real tty, and still no screen.

        Asserted on the ARTIFACT -- what reached the terminal -- because the
        return value alone cannot tell "skipped" from "opened and failed":
        both are None.
        """
        from installer.renderer import PlainTextRenderer

        monkeypatch.setenv("HOME", str(tmp_path))
        _write_answers(tmp_path, _shipped_preference_keys())

        isatty = tripwire.mock.object(sys.stdin, "isatty")
        isatty.returns(True)

        args = argparse.Namespace(
            dry_run=False, yes=False, no_interactive=False, reconfigure=False
        )
        with tripwire:
            result = cli_install_module._select_rule_modules(
                _StubInstaller(), PlainTextRenderer(), args
            )

        isatty.assert_call(args=(), kwargs={})

        assert result is None
        out = capsys.readouterr().out
        assert "Spellbook rule modules" not in out, (
            "the selector screen was drawn for keys that were already answered"
        )
        assert "selector unavailable" not in out

    def test_cli_reconfigure_bypasses_the_idempotency_gate(
        self, monkeypatch, tmp_path, cli_install_module
    ):
        """The one path back to a declined module, on the ``spellbook install``
        entry point. Without the bypass a decline is permanent."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setenv("HOME", str(tmp_path))
        _write_answers(tmp_path, _shipped_preference_keys())

        renderer = PlainTextRenderer()
        isatty = tripwire.mock.object(sys.stdin, "isatty")
        isatty.returns(True)
        seen = []
        screen = tripwire.mock.object(renderer, "render_rule_module_select")
        screen.calls(lambda *a: (seen.append(a), ["core-philosophy"])[1])

        args = argparse.Namespace(
            dry_run=False, yes=False, no_interactive=False, reconfigure=True
        )
        with tripwire:
            result = cli_install_module._select_rule_modules(
                _StubInstaller(), renderer, args
            )

        isatty.assert_call(args=(), kwargs={})
        screen.assert_call(args=seen[0], kwargs={})

        assert result == ["core-philosophy"], (
            "--reconfigure did not reopen the selector"
        )

    def test_the_cli_entry_path_routes_through_the_renderer(
        self, monkeypatch, tmp_path, cli_install_module
    ):
        """AGENTS.md "Divergent install entry points": parity is the contract.

        The renderer owns the Windows fallback (a Rich table where termios is
        absent). Calling ``installer.tui.interactive_module_select`` directly
        from here meant a Windows user running ``spellbook install`` was never
        offered the modules while the same user running ``python3 install.py``
        was.
        """
        from installer.renderer import PlainTextRenderer

        monkeypatch.setenv("HOME", str(tmp_path))

        renderer = PlainTextRenderer()
        isatty = tripwire.mock.object(sys.stdin, "isatty")
        isatty.returns(True)
        seen = []
        screen = tripwire.mock.object(renderer, "render_rule_module_select")
        screen.calls(lambda *a: (seen.append(a), ["session"])[1])

        args = argparse.Namespace(
            dry_run=False, yes=False, no_interactive=False, reconfigure=False
        )
        with tripwire:
            result = cli_install_module._select_rule_modules(
                _StubInstaller(), renderer, args
            )

        isatty.assert_call(args=(), kwargs={})
        screen.assert_call(args=seen[0], kwargs={})

        assert result == ["session"]

    def test_the_renderer_module_screen_survives_a_missing_renderer(
        self, monkeypatch, tmp_path, cli_install_module
    ):
        """``_create_renderer`` can return None. That must not resurrect the
        direct-to-tui call the parity fix removed."""
        monkeypatch.setenv("HOME", str(tmp_path))

        isatty = tripwire.mock.object(sys.stdin, "isatty")
        isatty.returns(True)
        seen = []
        screen = tripwire.mock(
            "installer.renderer:PlainTextRenderer.render_rule_module_select"
        )
        screen.calls(lambda *a: (seen.append(a), [])[1])

        args = argparse.Namespace(
            dry_run=False, yes=False, no_interactive=False, reconfigure=False
        )
        with tripwire:
            result = cli_install_module._select_rule_modules(
                _StubInstaller(), None, args
            )

        isatty.assert_call(args=(), kwargs={})
        screen.assert_call(args=seen[0], kwargs={})

        assert result == []


class TestNotAskedIsNeverPersisted:
    """The not-asked sentinel, at BOTH entry points.

    ``None`` means the user was never shown the screen. Persisting it writes an
    explicit True or False for every preference module on their behalf, which
    permanently marks as declined modules they never saw. Each entry point owns
    its own copy of this guard, so each is tested.
    """

    def test_the_root_entry_point_persists_nothing_for_a_non_answer(
        self, monkeypatch, tmp_path, root_install_module
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        root_install_module._persist_rule_selection_if_answered(_StubInstaller(), None)

        assert not list(tmp_path.rglob("*.json")), "a non-answer was recorded"

    def test_the_cli_entry_point_persists_nothing_for_a_non_answer(
        self, monkeypatch, tmp_path, cli_install_module
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        cli_install_module._persist_rule_modules_if_answered(
            _StubInstaller(), None, False
        )

        assert not list(tmp_path.rglob("*.json")), "a non-answer was recorded"

    def test_a_dry_run_persists_nothing_at_either_entry_point(
        self, monkeypatch, tmp_path, root_install_module, cli_install_module
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        root_install_module._persist_rule_selection_if_answered(
            _StubInstaller(), ["session"], True
        )
        cli_install_module._persist_rule_modules_if_answered(
            _StubInstaller(), ["session"], True
        )

        assert not list(tmp_path.rglob("*.json"))

    @pytest.mark.parametrize("entry", ["root", "cli"])
    def test_a_real_answer_is_recorded_at_both_entry_points(
        self, monkeypatch, tmp_path, root_install_module, cli_install_module, entry
    ):
        """The positive half. Without it the guards above are satisfied by a
        function that never writes anything at all."""
        monkeypatch.setenv("HOME", str(tmp_path))

        keys = _shipped_preference_keys()
        kept = keys[0].split(".")[-1]

        if entry == "root":
            root_install_module._persist_rule_selection_if_answered(
                _StubInstaller(), [kept]
            )
        else:
            cli_install_module._persist_rule_modules_if_answered(
                _StubInstaller(), [kept], False
            )

        written = json.loads(_config_path(tmp_path).read_text(encoding="utf-8"))
        assert written[keys[0]] is True
        assert all(written[key] is False for key in keys[1:])


class TestRendererModuleScreenParity:
    """Both renderers gate the module screen identically, and both offer it at
    the same point in the flow.

    The plain renderer nested the screen inside its "no --platforms flag"
    branch, so ``install.py --platforms claude_code`` on a real terminal was
    never offered the modules while the same run under Rich was.
    """

    def _context(self, selection, **overrides):
        from installer.wizard import WizardContext

        kwargs = dict(
            available_platforms=["claude_code"],
            cli_platforms=["claude_code"],
            profile_already_configured=True,
            available_profiles=[],
            is_upgrade=False,
            is_interactive=True,
            auto_yes=False,
            no_interactive=False,
            reconfigure=False,
            rule_selection=selection,
        )
        kwargs.update(overrides)
        return WizardContext(**kwargs)

    @pytest.fixture
    def selection(self):
        from installer.components.rule_modules import (
            get_rules_dir,
            load_rule_modules,
            resolve_selection,
        )

        return resolve_selection(load_rule_modules(get_rules_dir(_repo_root())))

    @pytest.mark.parametrize("renderer_name", ["rich", "plain"])
    def test_platforms_flag_does_not_suppress_the_module_screen(
        self, selection, renderer_name
    ):
        from installer.renderer import PlainTextRenderer, RichRenderer

        renderer = RichRenderer() if renderer_name == "rich" else PlainTextRenderer()
        hook = (
            "_wizard_module_select"
            if renderer_name == "rich"
            else "_wizard_module_select_plain"
        )

        isatty = tripwire.mock.object(sys.stdin, "isatty")
        isatty.returns(True)
        seen = []
        screen = tripwire.mock.object(renderer, hook)
        screen.calls(lambda *a: (seen.append(a), ["session"])[1])

        with tripwire:
            results = renderer.render_upfront_wizard(self._context(selection))

        isatty.assert_call(args=(), kwargs={})
        screen.assert_call(args=seen[0], kwargs={})

        assert results is not None
        assert results.rule_modules == ["session"], (
            f"{renderer_name} skipped the module screen when --platforms was passed"
        )

    @pytest.mark.parametrize("renderer_name", ["rich", "plain"])
    def test_a_screen_that_cannot_be_answered_is_never_shown(
        self, selection, renderer_name
    ):
        """The gate is on a REAL stdin, not on --no-interactive alone.

        pytest's stdin is not a tty, so dropping the isatty term from the gate
        makes this go red: the screen is reached and something is recorded.
        """
        from installer.renderer import PlainTextRenderer, RichRenderer

        renderer = RichRenderer() if renderer_name == "rich" else PlainTextRenderer()

        assert (
            renderer._should_offer_module_select(self._context(selection)) is False
        ), "a screen the user cannot answer was offered"

    def test_the_gate_is_open_on_a_real_terminal(self, selection):
        """The positive half: the gate is not simply always closed."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        isatty = tripwire.mock.object(sys.stdin, "isatty")
        isatty.returns(True)

        with tripwire:
            opened = renderer._should_offer_module_select(self._context(selection))

        isatty.assert_call(args=(), kwargs={})
        assert opened is True

    @pytest.mark.parametrize(
        "overrides",
        [
            {"rule_selection": None},
            {"no_interactive": True},
            {"is_interactive": False},
        ],
        ids=["no-modules", "no-interactive-flag", "not-interactive"],
    )
    def test_every_other_gate_term_also_closes_the_screen(self, selection, overrides):
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        context = self._context(selection, **overrides)

        # No isatty mock: each of these must close the gate on its own, and a
        # term that short-circuits before isatty never reaches it.
        assert renderer._should_offer_module_select(context) is False
