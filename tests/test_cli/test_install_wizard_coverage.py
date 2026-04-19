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

from types import SimpleNamespace

import pytest


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

    Use this when a wizard must see a specific current value (e.g.
    ``tts_enabled=True`` gating the voice prompt).
    """
    state: dict[str, object] = {}

    from spellbook.core import config as _core_cfg
    from installer.wizards import defaults as _defaults_mod

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
    # All accept bare Enter except session_mode (needs choice index "1" -> none).
    ("tts_voice", "", ""),
    ("tts_volume", "", 0.3),
    ("notify_enabled", "", True),
    ("notify_title", "", "Spellbook"),
    ("telemetry_enabled", "", False),
    ("auto_update", "", True),
    ("session_mode", "", "none"),
]


class TestDefaultsWizardCoverage:
    """Every key registered in run_defaults_wizard must fire a prompt."""

    def test_fresh_install_prompts_every_key(
        self, captured_config, scripted_input, tty, stub_config_get
    ):
        calls, _ = captured_config
        # tts_enabled True so the voice prompt fires.
        stub_config_get["tts_enabled"] = True

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
        stub_config_get["tts_enabled"] = True

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
        stub_config_get["tts_enabled"] = True

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

    def test_tts_voice_gated_on_tts_enabled(
        self, captured_config, scripted_input, tty, stub_config_get
    ):
        """tts_voice prompt is suppressed when tts_enabled is False."""
        calls, _ = captured_config
        stub_config_get["tts_enabled"] = False

        # Skip the voice answer entirely; provide only the remaining six.
        # tts_volume through session_mode.
        scripted_input([ans for (k, ans, _v) in _DEFAULTS_KEY_SCRIPT
                        if k != "tts_voice"])

        from installer.wizards import run_defaults_wizard

        run_defaults_wizard(SimpleNamespace(dry_run=False, reconfigure=False))

        written_keys = {k for (k, _v) in calls}
        assert "tts_voice" not in written_keys, (
            "tts_voice should not be prompted when tts_enabled is False"
        )
        # Other keys still fire.
        assert "tts_volume" in written_keys
        assert "session_mode" in written_keys


# ---------------------------------------------------------------------------
# Worker-LLM wizard: advanced-tier prompt coverage
# ---------------------------------------------------------------------------


_WORKER_ADVANCED_KEYS = [
    "worker_llm_timeout_s",
    "worker_llm_max_tokens",
    "worker_llm_tool_safety_timeout_s",
    "worker_llm_transcript_harvest_mode",
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
        blank key -> four feature flags n -> advanced y -> [advanced
        answers] -> doctor n.
        """
        return [
            "y",  # Enable wizard
            "1",  # Endpoint
            "1",  # Model
            "",   # API key
            "n", "n", "n", "n",  # Four feature flags
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

        # Seven advanced prompts: accept the default for each.
        # number prompts take bare Enter -> default.
        # bool prompt for allow_prompt_overrides takes Enter -> default True.
        # bool prompt for feature_roundtable takes Enter -> default False.
        # harvest_mode takes Enter -> "replace" default.
        scripted_input(self._script_happy_path_with_advanced(
            ["", "", "", "", "", "", ""]
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
