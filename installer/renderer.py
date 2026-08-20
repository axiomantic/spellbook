"""Abstract base class for installer rendering.

Defines the ``InstallerRenderer`` contract that all concrete renderers must
implement. Two concrete implementations are provided elsewhere:

- ``installer/rich_renderer.py`` -- Rich-based TUI renderer
- ``installer/plain_renderer.py`` -- Plain-text renderer for non-TTY / CI use

Superseded design decisions reflected here:

SD-1: ``render_admin_info`` accepts only ``admin_url: str``. The design doc's
    ``(admin_url, token)`` signature described bearer-token auth, which the
    daemon no longer uses.
"""

from __future__ import annotations

import sys
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
    # Rule module selection (shared by every renderer and both entry points)
    # ------------------------------------------------------------------

    def _should_offer_module_select(self, context: WizardContext) -> bool:
        """Whether the rule module screen may be shown at all.

        One predicate for every renderer. The Rich and plain wizards diverged
        once -- the plain one nested the screen inside its "no ``--platforms``
        flag" branch, so ``install.py --platforms claude_code`` on a real
        terminal was never offered the modules while the same run under Rich
        was. Renderer parity is the contract, so the gate is defined once.

        Gated on a REAL stdin, not on ``--no-interactive`` alone: the caller
        persists whatever comes back, so a screen that could not be answered
        must never be shown.
        """
        return (
            context.rule_selection is not None
            and not context.no_interactive
            and context.is_interactive
            and sys.stdin.isatty()
        )

    def render_rule_module_select(self, selection: Any) -> list[str] | None:
        """Offer the rule module selector outside the upfront wizard.

        The ``spellbook install`` entry point calls this rather than reaching
        for ``installer.tui.interactive_module_select`` itself. Calling the tui
        directly skipped the renderer's Windows fallback, so a user with no
        ``termios`` was offered the modules by ``python3 install.py`` and never
        by ``spellbook install`` -- the entry-point divergence AGENTS.md
        "Divergent install entry points" forbids.

        Returns None for "not asked", which persists nothing.
        """
        context = WizardContext(
            available_platforms=[],
            cli_platforms=None,
            profile_already_configured=True,
            available_profiles=[],
            is_upgrade=False,
            is_interactive=True,
            auto_yes=False,
            no_interactive=False,
            reconfigure=True,
            rule_selection=selection,
        )
        return self._module_select(context)

    def _module_select(self, context: WizardContext) -> list[str] | None:
        """Renderer-specific module screen. Default: cannot prompt, so no answer."""
        return None

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

    def render_profile_wizard(self, reconfigure: bool = False) -> dict[str, Any]:
        """Run the session profile selection wizard.

        Presents available profiles (from ``discover_profiles()``) and lets
        the user pick one. Called post-install and during
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
    def render_admin_info(self, admin_url: str) -> None:
        """Display admin web interface information.

        Args:
            admin_url: URL of the admin interface (e.g.
                ``"http://localhost:8765/admin"``). Pass an empty string
                when admin is disabled.
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

    def render_upfront_wizard(self, context: WizardContext) -> WizardResults | None:
        results = WizardResults()

        try:
            if context.auto_yes:
                results.platforms = context.cli_platforms or context.available_platforms
                return results

            console = self._get_console()

            # --- Section 1: Platform Selection ---
            if context.cli_platforms is not None:
                results.platforms = context.cli_platforms
            elif context.no_interactive:
                results.platforms = context.available_platforms
            else:
                # Ask auto-detect confirmation first
                from rich.prompt import Prompt
                from installer.config import PLATFORM_CONFIG

                names = [PLATFORM_CONFIG.get(p, {}).get("name", p) for p in context.available_platforms]
                console.print(f"\n[cyan]Auto-detected active coding harnesses:[/cyan] {', '.join(names)}")
                choice = Prompt.ask(
                    "Install to detected harnesses? [Y/n/c(ustomize)]",
                    default="y",
                    console=console,
                ).strip().lower()

                if choice in ("y", "yes"):
                    results.platforms = context.available_platforms
                elif choice in ("n", "no"):
                    results.platforms = []
                else:
                    results.platforms = self._wizard_platform_select(console, context)

            # --- Section 2: Rule Module Selection ---
            # Runs after platform selection and before delivery. Skipped
            # entirely when non-interactive, so nothing is recorded that the
            # user did not actually answer.
            if self._should_offer_module_select(context):
                results.rule_modules = self._wizard_module_select(console, context)

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

        from installer.tui import interactive_platform_select
        try:
            res = interactive_platform_select()
            if res is not None:
                return res
        except Exception:
            pass

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
            console.print("[dim]Toggle: enter number(s) | a=all | n=none | d=default | enter=confirm[/dim]")

            choice = Prompt.ask("", default="", console=console).strip().lower()

            if choice == "":
                break
            elif choice in ("a", "all"):
                for opt in options:
                    opt["selected"] = True
            elif choice in ("n", "none"):
                for opt in options:
                    opt["selected"] = False
            elif choice in ("d", "default"):
                for opt in options:
                    opt["selected"] = True
            else:
                # Handle space/comma-separated numbers (e.g. "1 2 3" or "1,2,3")
                tokens = choice.replace(",", " ").split()
                for tok in tokens:
                    if tok.isdigit():
                        idx = int(tok) - 1
                        if 0 <= idx < len(options):
                            options[idx]["selected"] = not options[idx]["selected"]

        return [o["id"] for o in options if o["selected"]]

    def _module_select(self, context: WizardContext) -> list[str] | None:
        return self._wizard_module_select(self._get_console(), context)

    def _wizard_module_select(
        self, console: Any, context: WizardContext
    ) -> list[str] | None:
        """Rule module selector.

        Tries the termios checkbox selector first, then falls back to a Rich
        table where termios is unavailable but a terminal is (Windows). The
        fallback is a complete second implementation, not a wrapper, so it must
        carry the same benefit and related-artifact information -- updating only
        the termios path would leave this screen featureless.

        Returns None for "not asked", which keeps ``WizardResults.rule_modules``
        at its not-asked sentinel and persists nothing. Cancelling must be a
        real option: falling through to the Rich table on cancel re-prompted
        with a different UI and recorded whatever that returned, so there was no
        way to decline to answer.
        """
        from rich.table import Table
        from rich.prompt import Prompt

        from installer.tui import (
            get_module_options,
            interactive_module_select,
            module_select_available,
        )

        selection = context.rule_selection
        if selection is None:
            return None

        can_prompt = module_select_available()
        try:
            res = interactive_module_select(selection)
        except Exception as exc:
            # Never swallowed into the fallback: a broken selector re-prompting
            # through a second UI hides the failure and persists an answer the
            # user gave to a screen that should not have been shown.
            console.print(f"[yellow]Rule module selector failed: {exc}[/yellow]")
            return None

        if res is not None:
            return res
        if can_prompt:
            # The selector ran and the user cancelled. Honor that.
            return None
        if not sys.stdin.isatty():
            return None

        options = get_module_options(selection)
        if not options:
            return []

        mandatory_count = sum(1 for m in selection.modules if m.is_mandatory)

        while True:
            table = Table(title="Spellbook Rule Modules", show_header=True)
            table.add_column("#", width=3, justify="right")
            table.add_column("Module")
            table.add_column("Benefit")
            table.add_column("Related")
            table.add_column("Status", justify="center")

            for i, opt in enumerate(options):
                if opt.selected:
                    status = "[green]selected[/green]"
                elif opt.previously_declined:
                    status = "[yellow]previously declined[/yellow]"
                elif not opt.default_on:
                    status = "[dim]opt-in, skipped[/dim]"
                else:
                    status = "[dim]skipped[/dim]"
                related = ", ".join(r.split("/")[-1] for r in opt.related) or "-"
                table.add_row(str(i + 1), opt.name, opt.benefit, related, status)

            console.print(table)
            console.print(
                f"[dim]{mandatory_count} mandatory modules install "
                "unconditionally and are not listed.[/dim]"
            )
            console.print(
                "[dim]Toggle: enter number(s) | a=all | n=none | d=defaults "
                "| ?N=details | enter=confirm[/dim]"
            )

            choice = Prompt.ask("", default="", console=console).strip().lower()

            if choice == "":
                break
            elif choice in ("a", "all"):
                for opt in options:
                    opt.selected = True
            elif choice in ("n", "none"):
                for opt in options:
                    opt.selected = False
            elif choice in ("d", "default", "defaults"):
                for opt in options:
                    opt.selected = opt.default_on
            elif choice.startswith("?"):
                token = choice[1:].strip()
                if token.isdigit() and 1 <= int(token) <= len(options):
                    opt = options[int(token) - 1]
                    console.print(f"\n[cyan]{opt.name}[/cyan] "
                                  f"({opt.size_bytes / 1024:.1f} KB, "
                                  f"default: {'on' if opt.default_on else 'off'})")
                    console.print(f"  What it does: {opt.benefit}")
                    console.print(f"  If you decline it: {opt.declining_means}")
                    console.print(
                        "  Related: "
                        + (", ".join(opt.related) if opt.related else "(none)")
                        + "\n"
                    )
            else:
                tokens = choice.replace(",", " ").split()
                for tok in tokens:
                    if tok.isdigit():
                        idx = int(tok) - 1
                        if 0 <= idx < len(options):
                            options[idx].selected = not options[idx].selected

        return [o.id for o in options if o.selected]

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
        return True

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

    def render_admin_info(self, admin_url: str) -> None:
        from .tui import render_admin_info as _tui_admin
        console = self._get_console()
        _tui_admin(console, admin_enabled=bool(admin_url))

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
            heading = "[bold red]Error[/bold red]"
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

    def render_upfront_wizard(self, context: WizardContext) -> WizardResults | None:
        results = WizardResults()

        try:
            if context.auto_yes:
                results.platforms = context.cli_platforms or context.available_platforms
                return results

            # --- Section 1: Platform Selection ---
            if context.cli_platforms is not None:
                results.platforms = context.cli_platforms
            elif context.no_interactive:
                results.platforms = context.available_platforms
            else:
                results.platforms = self._wizard_platform_select_plain(context)

            # --- Section 2: Rule Module Selection ---
            # At the OUTER level, matching the Rich renderer. Nested inside the
            # platform branch above, a run that passed --platforms skipped the
            # module screen entirely on this renderer and not on the other one.
            if self._should_offer_module_select(context):
                results.rule_modules = self._wizard_module_select_plain(context)

            # --- Section 4: Profile Selection ---
            if context.available_profiles and (
                not context.profile_already_configured or context.reconfigure
            ):
                results.profile_selection = self._wizard_profile_plain(context)

            return results
        except (KeyboardInterrupt, EOFError):
            return None

    def _module_select(self, context: WizardContext) -> list[str] | None:
        try:
            return self._wizard_module_select_plain(context)
        except (KeyboardInterrupt, EOFError):
            # Cancelled, or no stdin to read. Neither is an answer.
            return None

    def _wizard_module_select_plain(self, context: WizardContext) -> list[str]:
        """Plain-text rule module selector using numbered toggle.

        Carries the same benefit text and related-artifact pointers the Rich
        and termios selectors show, so a plain-text install is not asked to
        choose between modules it cannot tell apart.
        """
        from installer.tui import get_module_options

        selection = context.rule_selection
        if selection is None:
            return []

        options = get_module_options(selection)
        if not options:
            return []

        mandatory_count = sum(1 for m in selection.modules if m.is_mandatory)

        while True:
            print("\nSpellbook rule modules:")
            for i, opt in enumerate(options):
                mark = "x" if opt.selected else " "
                note = ""
                if opt.previously_declined:
                    note = " (previously declined)"
                elif not opt.default_on:
                    note = " (opt-in)"
                print(f"  [{mark}] {i + 1:<3} {opt.name:<26} {opt.benefit}{note}")
            print(
                f"\n  {mandatory_count} mandatory modules install "
                "unconditionally and are not listed."
            )
            print(
                "  Toggle: number(s) | a=all | n=none | d=defaults "
                "| ?N=details | enter=confirm"
            )

            choice = input("> ").strip().lower()

            if choice == "":
                break
            elif choice in ("a", "all"):
                for opt in options:
                    opt.selected = True
            elif choice in ("n", "none"):
                for opt in options:
                    opt.selected = False
            elif choice in ("d", "default", "defaults"):
                for opt in options:
                    opt.selected = opt.default_on
            elif choice.startswith("?"):
                token = choice[1:].strip()
                if token.isdigit() and 1 <= int(token) <= len(options):
                    opt = options[int(token) - 1]
                    print(f"\n{opt.name} "
                          f"({opt.size_bytes / 1024:.1f} KB, "
                          f"default: {'on' if opt.default_on else 'off'})")
                    print(f"  What it does: {opt.benefit}")
                    print(f"  If you decline it: {opt.declining_means}")
                    print("  Related: "
                          + (", ".join(opt.related) if opt.related else "(none)"))
            else:
                for tok in choice.replace(",", " ").split():
                    if tok.isdigit():
                        idx = int(tok) - 1
                        if 0 <= idx < len(options):
                            options[idx].selected = not options[idx].selected

        return [o.id for o in options if o.selected]

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
            print("  Toggle: enter number(s) | a=all | n=none | d=default | enter=confirm")

            choice = input("> ").strip().lower()
            if choice == "":
                break
            elif choice in ("a", "all"):
                for opt in options:
                    opt["selected"] = True
            elif choice in ("n", "none"):
                for opt in options:
                    opt["selected"] = False
            elif choice in ("d", "default"):
                for opt in options:
                    opt["selected"] = True
            else:
                tokens = choice.replace(",", " ").split()
                for tok in tokens:
                    if tok.isdigit():
                        idx = int(tok) - 1
                        if 0 <= idx < len(options):
                            options[idx]["selected"] = not options[idx]["selected"]

        return [o["id"] for o in options if o["selected"]]


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

    def render_admin_info(self, admin_url: str) -> None:
        if admin_url:
            print(f"\nAdmin interface: {admin_url}")
        else:
            print("\nAdmin interface: disabled")

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
