"""Abstract base class for installer rendering.

Defines the ``InstallerRenderer`` contract that all concrete renderers must
implement. Two concrete implementations are provided elsewhere:

- ``installer/rich_renderer.py`` -- Rich-based TUI renderer
- ``installer/plain_renderer.py`` -- Plain-text renderer for non-TTY / CI use

Superseded design decisions reflected here:

SD-1: ``render_admin_info`` accepts ``admin_url: str`` and ``show_token: bool``
    rather than the original ``(admin_url, token)`` from the design doc. The
    raw token is never passed to the renderer; the caller controls whether
    token visibility is requested.

SD-2: ``render_tts_wizard()`` is a separate top-level method rather than a
    step inside ``render_config_wizard()``. TTS configuration is a post-install
    step because it requires confirming that TTS dependencies are installed,
    which only makes sense after the install loop completes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from installer.wizard import WizardContext, WizardResults


class InstallerRenderer(ABC):
    """Abstract base class defining the full installer rendering contract.

    Concrete subclasses handle all user-facing output and interactive prompts.
    Install logic in ``installer/core.py`` and ``install.py`` should delegate
    all I/O to a renderer instance, never call Rich or print directly.

    Args:
        auto_yes: When ``True``, all interactive prompts must return their
            default value without blocking on user input.
    """

    def __init__(self, auto_yes: bool = False) -> None:
        self.auto_yes = auto_yes

    # ------------------------------------------------------------------
    # Welcome and configuration wizard
    # ------------------------------------------------------------------

    @abstractmethod
    def render_welcome(self, version: str, is_upgrade: bool) -> None:
        """Display the installer welcome screen.

        Must show the spellbook version. When ``is_upgrade`` is ``True``,
        the display should indicate this is an upgrade rather than a fresh
        install.

        Args:
            version: Spellbook version string (e.g. ``"1.2.3"``).
            is_upgrade: ``True`` when a previous installation was detected.
        """
        ...

    @abstractmethod
    def render_config_wizard(
        self,
        unset_keys: list[str],
        existing_config: dict[str, Any],
        is_upgrade: bool,
    ) -> dict[str, Any]:
        """Run the interactive configuration wizard and return collected config.

        Only prompts for keys listed in ``unset_keys``. When ``unset_keys``
        is empty, must return ``{}`` immediately without prompting.

        When ``is_upgrade`` is ``True`` and ``existing_config`` is non-empty,
        the renderer should display existing configuration before prompting for
        new keys.

        When ``self.auto_yes`` is ``True``, must return ``{}`` without
        prompting for any input.

        The returned dict must be compatible with the ``security_selections``
        parameter expected by ``Installer.run()``. Keys are feature IDs
        (e.g. ``"spotlighting"``, ``"crypto"``) with ``bool`` values.

        Args:
            unset_keys: Config keys not yet explicitly set in ``spellbook.json``.
                From ``get_unset_config_keys()`` or ``WIZARD_CONFIG_KEYS``
                when ``--reconfigure`` is active.
            existing_config: Current resolved config dict for display during
                upgrades. May be empty on a fresh install.
            is_upgrade: ``True`` when a previous installation was detected.

        Returns:
            Dict of security feature selections, or ``{}`` to skip security
            configuration entirely.
        """
        ...

    @abstractmethod
    def render_upfront_wizard(self, context: WizardContext) -> WizardResults | None:
        """Run the consolidated upfront wizard.

        Collects all pre-determinable user decisions in a single
        interactive flow. Each section is skipped when:
        - The relevant CLI flag pre-answers the question
        - auto_yes is True (return defaults)
        - The config is already set and not reconfiguring

        Returns None on KeyboardInterrupt/EOFError (user cancelled).

        Args:
            context: Pre-assembled wizard context with detected state
                and CLI flag overrides.

        Returns:
            WizardResults with all collected decisions, or None if cancelled.
        """
        ...

    @abstractmethod
    def render_config_summary(
        self, config: dict[str, Any], confirmed: bool
    ) -> bool:
        """Display a summary of collected configuration and optionally confirm.

        When ``self.auto_yes`` is ``True`` or ``confirmed`` is ``True``, must
        return ``True`` without prompting.

        Args:
            config: Configuration dict to display (e.g. security selections).
            confirmed: If ``True``, treat as already confirmed and skip prompt.

        Returns:
            ``True`` if the user confirmed (or auto-yes), ``False`` to abort.
        """
        ...

    @abstractmethod
    def render_tts_wizard(self) -> dict[str, Any]:
        """Run the TTS (text-to-speech) configuration wizard post-install.

        Called after ``render_completion()``, not before the install loop.
        TTS setup is post-install because it requires confirming that the
        ``[tts]`` extras are installed (SD-2).

        When ``self.auto_yes`` is ``True`` or in non-interactive contexts,
        must return ``{}`` without prompting.

        Returns:
            Dict of TTS config keys to persist, or ``{}`` to skip TTS setup.
        """
        ...

    def render_profile_wizard(self, reconfigure: bool = False) -> dict[str, Any]:
        """Run the session profile selection wizard.

        Presents available profiles (from ``discover_profiles()``) and lets
        the user pick one. Called post-install (after TTS wizard) and during
        ``--reconfigure``.

        When ``self.auto_yes`` is ``True``, no profiles are available, or
        the profile is already configured (and not reconfiguring), returns
        ``{}`` without prompting.

        Args:
            reconfigure: If ``True``, always prompt even if already
                configured. Shows the current profile as the default.

        Returns:
            Dict with ``"profile.default"`` key set to a slug string
            (profile selected), ``""`` (user chose "None"), or empty dict
            ``{}`` when the wizard was skipped entirely.
        """
        if self.auto_yes:
            return {}

        from spellbook.core.profiles import discover_profiles
        from spellbook.core.config import config_is_explicitly_set

        profiles = discover_profiles()
        if not profiles:
            return {}

        # Skip if already configured and not reconfiguring
        if not reconfigure and config_is_explicitly_set("profile.default"):
            return {}

        # Build choices: "None" first, then each profile
        choices = ["None (no session profile)"]
        slugs = [""]  # empty string sentinel for "None"
        for p in profiles:
            label = f"{p.name} - {p.description}" if p.description else p.name
            if p.is_custom:
                label += " (custom)"
            choices.append(label)
            slugs.append(p.slug)

        # Determine default selection
        default_idx = 0
        if reconfigure:
            try:
                from spellbook.core.config import config_get
                current = config_get("profile.default")
                if current and current in slugs:
                    default_idx = slugs.index(current)
            except (ImportError, KeyError, ValueError):
                pass

        selected = self.prompt_choice(
            "Select a session profile:", choices, default=default_idx
        )
        return {"profile.default": slugs[selected]}

    # ------------------------------------------------------------------
    # Progress display
    # ------------------------------------------------------------------

    @abstractmethod
    def render_progress_start(self, total_steps: int) -> None:
        """Initialize and start the progress display before the install loop.

        Called exactly once before ``render_step()`` is called. Must set up
        any live display context (e.g. Rich Live), stdout redirection, or
        other display infrastructure.

        Args:
            total_steps: Total number of install steps expected, for
                progress percentage or section counting.
        """
        ...

    @abstractmethod
    def render_step(self, event: str, data: dict[str, Any]) -> None:
        """Update the progress display in response to an install event.

        Routes events emitted by ``Installer.run()`` via the ``on_progress``
        callback. Known event types:

        - ``"platform_start"`` -- data: ``{"name", "index", "total"}``
        - ``"platform_skip"`` -- data: ``{"name", "message"}``
        - ``"step"`` -- data: ``{"message"}``
        - ``"result"`` -- data: ``{"result": InstallResult}``
        - ``"daemon_start"`` -- data: ``{}``
        - ``"health_start"`` -- data: ``{}``

        Must be a no-op for unknown event types rather than raising.

        Args:
            event: Event type string from ``Installer.run()``.
            data: Event payload dict. Shape depends on ``event``.
        """
        ...

    @abstractmethod
    def render_progress_end(self) -> None:
        """Finalize and tear down the progress display after the install loop.

        Called in a ``finally`` block so it runs even when the install raises.
        Must restore any redirected stdout and stop any live display context.
        """
        ...

    # ------------------------------------------------------------------
    # Post-install output
    # ------------------------------------------------------------------

    @abstractmethod
    def render_completion(self, results: Any, elapsed: float) -> None:
        """Display the installation completion summary.

        Must show which platforms installed successfully and which failed,
        plus the total elapsed time.

        Args:
            results: ``InstallSession`` instance from ``Installer.run()``.
            elapsed: Total elapsed time in seconds.
        """
        ...

    @abstractmethod
    def render_admin_info(
        self, admin_url: str, show_token: bool = False
    ) -> None:
        """Display admin web interface information.

        Shows the admin URL and optionally indicates that a token is
        available. The raw token string is never passed to this method;
        the caller controls ``show_token`` (SD-1).

        Args:
            admin_url: URL of the admin interface (e.g.
                ``"http://localhost:8765/admin"``). Pass an empty string
                when admin is disabled.
            show_token: If ``True``, indicate that an auth token exists and
                where to find it (e.g. ``~/.local/spellbook/.mcp-token``).
        """
        ...

    @abstractmethod
    def render_post_install(self, notes: list[str]) -> None:
        """Display post-install notes and next steps.

        Each string in ``notes`` is a platform-specific instruction
        (e.g. ``"Restart Gemini CLI to load extension"``). Must handle
        an empty list without output.

        Args:
            notes: List of post-install instruction strings.
        """
        ...

    # ------------------------------------------------------------------
    # Warnings and errors
    # ------------------------------------------------------------------

    @abstractmethod
    def render_error(
        self, error: Exception, context: str | None = None
    ) -> None:
        """Display an error prominently.

        Must not raise. Suitable for fatal install errors shown before exit.

        Args:
            error: The exception to display.
            context: Optional human-readable description of what was
                happening when the error occurred.
        """
        ...

    @abstractmethod
    def render_warning(self, message: str) -> None:
        """Display a non-fatal warning message.

        Must not raise. Used for conditions like non-TTY detection or
        dry-run mode notices.

        Args:
            message: Warning text to display.
        """
        ...

    # ------------------------------------------------------------------
    # Interactive prompts
    # ------------------------------------------------------------------

    @abstractmethod
    def prompt_yn(self, message: str, default: bool = True) -> bool:
        """Prompt the user for a yes/no answer.

        When ``self.auto_yes`` is ``True``, must return ``default`` immediately
        without blocking.

        Args:
            message: Question to display to the user.
            default: Value to return when auto-yes is active or the user
                presses Enter without typing.

        Returns:
            ``True`` for yes, ``False`` for no.
        """
        ...

    @abstractmethod
    def prompt_choice(
        self, message: str, choices: list[str], default: int = 0
    ) -> int:
        """Prompt the user to select one item from a numbered list.

        When ``self.auto_yes`` is ``True``, must return ``default`` immediately
        without blocking.

        Args:
            message: Question or label to display above the choices.
            choices: List of option strings to display.
            default: Zero-based index of the default choice, returned when
                auto-yes is active or the user presses Enter without typing.

        Returns:
            Zero-based index of the selected choice.
        """
        ...


# ---------------------------------------------------------------------------
# Concrete implementation: Rich TUI renderer
# ---------------------------------------------------------------------------


class RichRenderer(InstallerRenderer):
    """Rich-based TUI renderer.

    Delegates panel rendering to ``installer/tui.py`` functions and wires
    progress events to ``LiveProgressDisplay``. All Rich imports are deferred
    to method bodies so the module can be imported in environments where Rich
    is not installed (falls back gracefully because ``supports_rich()`` guards
    the interactive paths).

    Args:
        auto_yes: When ``True``, all prompts return their default value.
        console: Optional ``rich.console.Console`` to use. If ``None``, a
            default console is created on first use.
    """

    def __init__(self, auto_yes: bool = False, console: Any = None) -> None:
        super().__init__(auto_yes=auto_yes)
        self._console = console
        self._live: Any = None  # LiveProgressDisplay instance

    def _get_console(self) -> Any:
        """Return (or lazily create) the Rich Console."""
        if self._console is None:
            from rich.console import Console
            self._console = Console()
        return self._console

    # ------------------------------------------------------------------
    # Welcome and configuration wizard
    # ------------------------------------------------------------------

    def render_welcome(self, version: str, is_upgrade: bool) -> None:
        from .tui import render_welcome_panel
        console = self._get_console()
        if is_upgrade:
            from rich.panel import Panel
            console.print(Panel(
                f"Upgrading to version [bold cyan]{version}[/bold cyan]",
                title="[bold cyan]Spellbook Upgrade[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            ))
        else:
            render_welcome_panel(console, version=version, auto_yes=self.auto_yes)

    def render_config_wizard(
        self,
        unset_keys: list[str],
        existing_config: dict[str, Any],
        is_upgrade: bool,
    ) -> dict[str, Any]:
        if self.auto_yes or not unset_keys:
            return {}

        from .tui import get_feature_groups, render_feature_table
        console = self._get_console()

        if is_upgrade and existing_config:
            from rich.panel import Panel
            from rich.text import Text
            lines = [f"  {k}: {v}" for k, v in existing_config.items()]
            console.print(Panel(
                "\n".join(lines),
                title="Existing Configuration",
                border_style="dim",
            ))

        groups = get_feature_groups()
        # Filter groups to only include features that are in unset_keys
        filtered_groups = []
        for group in groups:
            filtered_features = [
                f for f in group["features"]
                if f["id"] in unset_keys
                or any(
                    f".{f['id']}." in k or k.startswith(f"{f['id']}.")
                    for k in unset_keys
                )
            ]
            if filtered_features:
                filtered_groups.append({**group, "features": filtered_features})

        if not filtered_groups:
            return {}

        render_feature_table(console, filtered_groups)

        from rich.prompt import Confirm
        selections: dict[str, Any] = {}
        for group in filtered_groups:
            for feat in group["features"]:
                enabled = Confirm.ask(
                    f"Enable [cyan]{feat['name']}[/cyan]?",
                    default=feat["default"],
                    console=console,
                )
                selections[feat["id"]] = enabled

        return selections

    def render_upfront_wizard(self, context: WizardContext) -> WizardResults | None:
        from installer.wizard import _matches_unset_key

        results = WizardResults()

        try:
            if context.auto_yes:
                results.platforms = context.cli_platforms or context.available_platforms
                if context.tts_disabled:
                    results.tts_intent = False
                return results

            console = self._get_console()

            # --- Section 1: Platform Selection ---
            if context.cli_platforms is not None:
                results.platforms = context.cli_platforms
            elif context.no_interactive:
                results.platforms = context.available_platforms
            else:
                results.platforms = self._wizard_platform_select(console, context)

            # --- Section 2: Security Configuration ---
            if context.security_level is not None:
                results.security_selections = None
            elif context.unset_security_keys and context.security_wizard:
                results.security_selections = self._wizard_security(console, context)

            # --- Section 3: TTS Intent ---
            if context.tts_disabled:
                results.tts_intent = False
            elif not context.tts_already_configured:
                results.tts_intent = self._wizard_tts_intent(console)

            # --- Section 4: Profile Selection ---
            if context.available_profiles and (
                not context.profile_already_configured or context.reconfigure
            ):
                results.profile_selection = self._wizard_profile(console, context)

            return results
        except (KeyboardInterrupt, EOFError):
            return None

    def _wizard_platform_select(self, console: Any, context: WizardContext) -> list[str]:
        """Rich-based platform selector with numbered toggle."""
        from rich.table import Table
        from rich.prompt import Prompt
        from installer.config import PLATFORM_CONFIG

        options: list[dict[str, Any]] = []
        for pid in context.available_platforms:
            name = PLATFORM_CONFIG.get(pid, {}).get("name", pid)
            options.append({"id": pid, "name": name, "selected": True})

        while True:
            table = Table(title="Platform Selection", show_header=True)
            table.add_column("#", width=3, justify="right")
            table.add_column("Platform")
            table.add_column("Status", justify="center")

            for i, opt in enumerate(options):
                status = "[green]selected[/green]" if opt["selected"] else "[dim]skipped[/dim]"
                table.add_row(str(i + 1), opt["name"], status)

            console.print(table)
            console.print("[dim]Toggle: enter number | a=all | n=none | enter=confirm[/dim]")

            choice = Prompt.ask("", default="", console=console).strip().lower()

            if choice == "":
                break
            elif choice == "a":
                for opt in options:
                    opt["selected"] = True
            elif choice == "n":
                for opt in options:
                    opt["selected"] = False
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    options[idx]["selected"] = not options[idx]["selected"]

        return [o["id"] for o in options if o["selected"]]

    def _wizard_tts_intent(self, console: Any) -> bool:
        """Ask if user wants TTS."""
        from rich.panel import Panel
        from rich.prompt import Confirm

        console.print(Panel(
            "Wyoming protocol TTS provides spoken notifications.\n"
            "Requires a running Wyoming TTS server (e.g., wyoming-piper).",
            title="Text-to-Speech",
            border_style="cyan",
        ))

        return Confirm.ask(
            "Enable TTS notifications?",
            default=False,
            console=console,
        )

    def _wizard_security(self, console: Any, context: WizardContext) -> dict[str, bool]:
        """Rich-based security feature configuration."""
        from rich.panel import Panel
        from rich.prompt import Confirm
        from installer.tui import get_feature_groups
        from installer.wizard import _matches_unset_key

        console.print(Panel(
            "Configure security features for this installation.",
            title="Security Configuration",
            border_style="yellow",
        ))

        selections: dict[str, bool] = {}
        for group in get_feature_groups():
            for feature in group["features"]:
                if not _matches_unset_key(feature["id"], context.unset_security_keys):
                    continue
                enabled = Confirm.ask(
                    f"Enable {feature['name']}? {feature.get('description', '')}",
                    default=feature.get("default", False),
                    console=console,
                )
                selections[feature["id"]] = enabled

        return selections

    def _wizard_profile(self, console: Any, context: WizardContext) -> str | None:
        """Collect profile selection by delegating to render_profile_wizard().

        Returns the profile slug, empty string for "None" choice, or None
        if the wizard was skipped.
        """
        result = self.render_profile_wizard(
            reconfigure=context.reconfigure,
        )
        return result.get("profile.default") if result else None

    def render_config_summary(
        self, config: dict[str, Any], confirmed: bool
    ) -> bool:
        if not config:
            return True

        from .tui import render_security_config_panel
        console = self._get_console()
        render_security_config_panel(console, config)

        if confirmed or self.auto_yes:
            return True

        from rich.prompt import Confirm
        return Confirm.ask("Proceed with this configuration?", default=True, console=console)

    def render_tts_wizard(self) -> dict[str, Any]:
        if self.auto_yes:
            return {}

        from .tui import supports_rich
        console = self._get_console()

        # Check if TTS is already configured
        try:
            from spellbook.core.config import config_get as _cfg_get
            existing = _cfg_get("tts_enabled")
        except (ImportError, Exception):
            existing = None

        from installer.utils import check_tts_available

        if existing is not None:
            console.print(
                f"[dim]TTS already configured (enabled={existing})[/dim]"
            )
            return {}

        from rich.prompt import Confirm

        server_available = check_tts_available()
        enabled = Confirm.ask(
            "Enable text-to-speech notifications? (Requires a Wyoming TTS server)",
            default=server_available,
            console=console,
        )
        if enabled:
            from rich.panel import Panel
            msg = "[green]TTS enabled[/green]\n"
            if server_available:
                msg += "Wyoming TTS server: detected\n"
            else:
                msg += "Wyoming TTS server: not detected (start one on localhost:10200)\n"
            msg += (
                "Change settings with tts_session_set or tts_config_set MCP tools\n"
                "[dim]Ensure a Wyoming-compatible TTS server (Piper, Kokoro, etc.) is running[/dim]"
            )
            console.print(Panel(
                msg,
                title="Text-to-Speech",
                border_style="green",
                padding=(0, 2),
            ))
        else:
            console.print("[dim]TTS disabled. Enable later with tts_config_set MCP tool.[/dim]")
        return {"tts_enabled": enabled}

    # ------------------------------------------------------------------
    # Progress display
    # ------------------------------------------------------------------

    def render_progress_start(self, total_steps: int) -> None:
        from .tui import LiveProgressDisplay
        console = self._get_console()
        self._live = LiveProgressDisplay(console=console)
        self._live.start()

    def render_step(self, event: str, data: dict[str, Any]) -> None:
        if self._live is None:
            return

        if event == "platform_start":
            self._live.begin_section(
                data.get("name", ""),
                index=data.get("index", 0),
                total=data.get("total", 0),
            )
        elif event == "platform_skip":
            self._live.skip_section(data.get("message", ""))
        elif event == "step":
            self._live.add_step(data.get("message", ""))
        elif event == "result":
            result = data.get("result")
            success = getattr(result, "success", True) if result is not None else True
            self._live.complete_step(success=success)
        elif event in ("daemon_start", "health_start"):
            label = "Starting daemon..." if event == "daemon_start" else "Health check..."
            self._live.add_step(label)
        # Unknown events are silently ignored per the ABC contract.

    def render_progress_end(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    # ------------------------------------------------------------------
    # Post-install output
    # ------------------------------------------------------------------

    def render_completion(self, results: Any, elapsed: float) -> None:
        from .tui import render_completion_summary
        console = self._get_console()
        installed = getattr(results, "platforms_installed", [])
        failed = getattr(results, "platforms_failed", [])
        render_completion_summary(
            console,
            platforms_installed=installed,
            platforms_failed=failed,
            elapsed_seconds=elapsed,
        )

    def render_admin_info(self, admin_url: str, show_token: bool = False) -> None:
        from .tui import render_admin_info as _tui_admin
        console = self._get_console()
        admin_enabled = bool(admin_url)
        _tui_admin(console, admin_enabled=admin_enabled)
        if show_token and admin_enabled:
            from rich.panel import Panel
            console.print(Panel(
                "Auth token: [dim]~/.local/spellbook/.mcp-token[/dim]",
                border_style="dim",
                padding=(0, 2),
            ))

    def render_post_install(self, notes: list[str]) -> None:
        if not notes:
            return
        from rich.panel import Panel
        console = self._get_console()
        body = "\n".join(notes)
        console.print(Panel(body, title="Next Steps", border_style="dim", padding=(0, 2)))

    # ------------------------------------------------------------------
    # Warnings and errors
    # ------------------------------------------------------------------

    def render_error(self, error: Exception, context: str | None = None) -> None:
        try:
            from rich.panel import Panel
            console = self._get_console()
            heading = f"[bold red]Error[/bold red]"
            if context:
                heading = f"[bold red]Error during {context}[/bold red]"
            body = f"{heading}\n{error}"
            console.print(Panel(body, border_style="red", padding=(0, 2)))
        except Exception:
            import sys
            prefix = f"Error ({context}): " if context else "Error: "
            print(f"{prefix}{error}", file=sys.stderr)

    def render_warning(self, message: str) -> None:
        try:
            from rich.panel import Panel
            console = self._get_console()
            console.print(Panel(
                f"[bold yellow]Warning[/bold yellow]\n{message}",
                border_style="yellow",
                padding=(0, 2),
            ))
        except Exception:
            import sys
            print(f"Warning: {message}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Interactive prompts
    # ------------------------------------------------------------------

    def prompt_yn(self, message: str, default: bool = True) -> bool:
        if self.auto_yes:
            return default
        from rich.prompt import Confirm
        return Confirm.ask(message, default=default, console=self._get_console())

    def prompt_choice(
        self, message: str, choices: list[str], default: int = 0
    ) -> int:
        if self.auto_yes:
            return default
        from rich.prompt import IntPrompt
        console = self._get_console()
        console.print(f"\n{message}")
        for i, choice in enumerate(choices):
            marker = "[cyan]*[/cyan]" if i == default else " "
            console.print(f"  {marker} {i + 1}. {choice}")
        raw = IntPrompt.ask(
            "Enter number",
            default=default + 1,
            console=console,
        )
        # Clamp to valid range and convert to 0-based index
        idx = max(1, min(raw, len(choices))) - 1
        return idx


# ---------------------------------------------------------------------------
# Concrete implementation: plain-text renderer (no Rich dependency)
# ---------------------------------------------------------------------------


class PlainTextRenderer(InstallerRenderer):
    """Plain-text renderer suitable for non-TTY and CI environments.

    Uses only ``print()`` for output and ``input()`` for prompts. Never
    imports Rich at the module level (or at all). Errors and warnings go to
    ``sys.stderr``.

    Args:
        auto_yes: When ``True``, all prompts return their default value.
    """

    # ------------------------------------------------------------------
    # Welcome and configuration wizard
    # ------------------------------------------------------------------

    def render_welcome(self, version: str, is_upgrade: bool) -> None:
        label = "Upgrading" if is_upgrade else "Installing"
        print(f"=== Spellbook Installer - {label} {version} ===")

    def render_config_wizard(
        self,
        unset_keys: list[str],
        existing_config: dict[str, Any],
        is_upgrade: bool,
    ) -> dict[str, Any]:
        if self.auto_yes or not unset_keys:
            return {}

        # Feature metadata mirrored from tui.get_feature_groups() to avoid
        # importing tui (which itself imports Rich at the module level).
        _feature_meta: dict[str, dict[str, Any]] = {
            "spotlighting": {"name": "Spotlighting", "default": True},
            "crypto": {"name": "Cryptographic Provenance", "default": True},
            "sleuth": {"name": "PromptSleuth Semantic Analysis", "default": False},
            "lodo": {"name": "LODO Evaluation", "default": True},
        }

        if is_upgrade and existing_config:
            print("\nExisting configuration:")
            for k, v in existing_config.items():
                print(f"  {k}: {v}")

        print("\nSecurity feature configuration:")
        selections: dict[str, Any] = {}
        for key in unset_keys:
            # Extract bare feature ID from dotted key
            # e.g. "security.crypto.enabled" -> "crypto"
            bare_id = key
            parts = key.split(".")
            if len(parts) >= 3 and parts[0] == "security":
                bare_id = parts[1]
            meta = _feature_meta.get(bare_id, _feature_meta.get(key, {"name": key, "default": True}))
            default = meta["default"]
            default_hint = "Y/n" if default else "y/N"
            answer = input(
                f"  Enable {meta['name']}? [{default_hint}] "
            ).strip().lower()
            if answer == "":
                selections[bare_id] = default
            else:
                selections[bare_id] = answer in ("y", "yes")
        return selections

    def render_upfront_wizard(self, context: WizardContext) -> WizardResults | None:
        from installer.wizard import _matches_unset_key

        results = WizardResults()

        try:
            if context.auto_yes:
                results.platforms = context.cli_platforms or context.available_platforms
                if context.tts_disabled:
                    results.tts_intent = False
                return results

            # --- Section 1: Platform Selection ---
            if context.cli_platforms is not None:
                results.platforms = context.cli_platforms
            elif context.no_interactive:
                results.platforms = context.available_platforms
            else:
                results.platforms = self._wizard_platform_select_plain(context)

            # --- Section 2: Security Configuration ---
            if context.security_level is not None:
                results.security_selections = None
            elif context.unset_security_keys and context.security_wizard:
                results.security_selections = self._wizard_security_plain(context)

            # --- Section 3: TTS Intent ---
            if context.tts_disabled:
                results.tts_intent = False
            elif not context.tts_already_configured:
                answer = input("Enable TTS notifications? [y/N] ").strip().lower()
                results.tts_intent = answer in ("y", "yes")

            # --- Section 4: Profile Selection ---
            if context.available_profiles and (
                not context.profile_already_configured or context.reconfigure
            ):
                results.profile_selection = self._wizard_profile_plain(context)

            return results
        except (KeyboardInterrupt, EOFError):
            return None

    def _wizard_platform_select_plain(self, context: WizardContext) -> list[str]:
        """Plain-text platform selector using numbered toggle."""
        from installer.config import PLATFORM_CONFIG

        options: list[dict[str, Any]] = []
        for pid in context.available_platforms:
            name = PLATFORM_CONFIG.get(pid, {}).get("name", pid)
            options.append({"id": pid, "name": name, "selected": True})

        while True:
            print("\nPlatform Selection:")
            for i, opt in enumerate(options):
                status = "[x]" if opt["selected"] else "[ ]"
                print(f"  {i + 1}. {status} {opt['name']}")
            print("  Toggle: enter number | a=all | n=none | enter=confirm")

            choice = input("> ").strip().lower()
            if choice == "":
                break
            elif choice == "a":
                for opt in options:
                    opt["selected"] = True
            elif choice == "n":
                for opt in options:
                    opt["selected"] = False
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    options[idx]["selected"] = not options[idx]["selected"]

        return [o["id"] for o in options if o["selected"]]

    def _wizard_security_plain(self, context: WizardContext) -> dict[str, bool]:
        """Plain-text security feature configuration."""
        from installer.tui import get_feature_groups
        from installer.wizard import _matches_unset_key

        print("\nSecurity Configuration:")
        selections: dict[str, bool] = {}
        for group in get_feature_groups():
            for feature in group["features"]:
                if not _matches_unset_key(feature["id"], context.unset_security_keys):
                    continue
                default = feature.get("default", False)
                default_hint = "Y/n" if default else "y/N"
                answer = input(
                    f"  Enable {feature['name']}? [{default_hint}] "
                ).strip().lower()
                if default:
                    enabled = answer not in ("n", "no")
                else:
                    enabled = answer in ("y", "yes")
                selections[feature["id"]] = enabled

        return selections

    def _wizard_profile_plain(self, context: WizardContext) -> str | None:
        """Collect profile selection by delegating to render_profile_wizard().

        render_profile_wizard() returns {"profile.default": slug} or {} if skipped.
        """
        result = self.render_profile_wizard(
            reconfigure=context.reconfigure,
        )
        return result.get("profile.default") if result else None

    def render_config_summary(
        self, config: dict[str, Any], confirmed: bool
    ) -> bool:
        if not config:
            return True

        print("\nConfiguration summary:")
        for k, v in config.items():
            print(f"  {k}: {'enabled' if v else 'disabled'}")

        if confirmed or self.auto_yes:
            return True

        answer = input("Proceed with this configuration? [Y/n] ").strip().lower()
        return answer in ("", "y", "yes")

    def render_tts_wizard(self) -> dict[str, Any]:
        if self.auto_yes:
            return {}

        try:
            from spellbook.core.config import config_get as _cfg_get
            existing = _cfg_get("tts_enabled")
        except (ImportError, Exception):
            existing = None

        if existing is not None:
            print(f"TTS already configured (enabled={existing})")
            return {}

        answer = input(
            "Enable text-to-speech notifications? (Requires a Wyoming TTS server) [Y/n] "
        ).strip().lower()
        enabled = answer in ("", "y", "yes")
        if enabled:
            print("TTS enabled. Wyoming TTS server: localhost:10200")
            print("Ensure a Wyoming-compatible TTS server (Piper, Kokoro, etc.) is running.")
        else:
            print("TTS disabled. Enable later with tts_config_set MCP tool.")
        return {"tts_enabled": enabled}

    # ------------------------------------------------------------------
    # Progress display
    # ------------------------------------------------------------------

    def render_progress_start(self, total_steps: int) -> None:
        print(f"\nStarting installation ({total_steps} steps)...")

    def render_step(self, event: str, data: dict[str, Any]) -> None:
        if event == "platform_start":
            name = data.get("name", "")
            index = data.get("index", 0)
            total = data.get("total", 0)
            if index and total:
                print(f"\n[{index}/{total}] {name}")
            else:
                print(f"\n{name}")
        elif event == "platform_skip":
            print(f"  Skipped: {data.get('message', '')}")
        elif event == "step":
            print(f"  {data.get('message', '')}")
        elif event == "result":
            result = data.get("result")
            if result is not None:
                success = getattr(result, "success", True)
                status = "OK" if success else "FAILED"
                print(f"    [{status}]")
        elif event == "daemon_start":
            print("  Starting daemon...")
        elif event == "health_start":
            print("  Health check...")
        # Unknown events silently ignored.

    def render_progress_end(self) -> None:
        pass  # No live display to tear down.

    # ------------------------------------------------------------------
    # Post-install output
    # ------------------------------------------------------------------

    def render_completion(self, results: Any, elapsed: float) -> None:
        installed = getattr(results, "platforms_installed", [])
        failed = getattr(results, "platforms_failed", [])

        minutes, seconds = divmod(int(elapsed), 60)
        time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

        print(f"\n=== Installation complete - {time_str} ===")
        for p in installed:
            print(f"  [OK]     {p}")
        for p in failed:
            print(f"  [FAILED] {p}")

    def render_admin_info(self, admin_url: str, show_token: bool = False) -> None:
        if admin_url:
            print(f"\nAdmin interface: {admin_url}")
        else:
            print("\nAdmin interface: disabled")
        if show_token and admin_url:
            print("Auth token: ~/.local/spellbook/.mcp-token")

    def render_post_install(self, notes: list[str]) -> None:
        if not notes:
            return
        print("\nNext steps:")
        for note in notes:
            print(f"  - {note}")

    # ------------------------------------------------------------------
    # Warnings and errors
    # ------------------------------------------------------------------

    def render_error(self, error: Exception, context: str | None = None) -> None:
        import sys
        prefix = f"Error ({context}): " if context else "Error: "
        print(f"{prefix}{error}", file=sys.stderr)

    def render_warning(self, message: str) -> None:
        import sys
        print(f"Warning: {message}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Interactive prompts
    # ------------------------------------------------------------------

    def prompt_yn(self, message: str, default: bool = True) -> bool:
        if self.auto_yes:
            return default
        hint = "Y/n" if default else "y/N"
        answer = input(f"{message} [{hint}] ").strip().lower()
        if answer == "":
            return default
        return answer in ("y", "yes")

    def prompt_choice(
        self, message: str, choices: list[str], default: int = 0
    ) -> int:
        if self.auto_yes:
            return default
        print(f"\n{message}")
        for i, choice in enumerate(choices):
            marker = "*" if i == default else " "
            print(f"  {marker} {i + 1}. {choice}")
        raw = input(f"Enter number [{default + 1}]: ").strip()
        if not raw:
            return default
        try:
            idx = int(raw) - 1
            return max(0, min(idx, len(choices) - 1))
        except ValueError:
            return default
