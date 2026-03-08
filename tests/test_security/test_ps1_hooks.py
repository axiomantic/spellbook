"""Tests for PowerShell (.ps1) hook implementations used on Windows.

The hook system provides 12 hooks, each with a .sh (Unix) and .ps1 (Windows) variant.
This test module covers the 10 standard hooks that follow the common PS1 structure:

Security hooks (fail-closed, exit 2 on block):
  - bash-gate: blocks dangerous bash commands via check.py
  - spawn-guard: blocks injection in spawn prompts via check.py
  - state-sanitize: blocks injection in workflow state via check.py

Audit hooks (fail-open, exit 0 always):
  - audit-log: logs tool calls via check.py --mode audit
  - canary-check: scans for canary tokens via check.py --mode canary
  - tts-timer-start: records tool start timestamp to temp file

Notification hooks (fail-open, exit 0 always):
  - tts-notify: speaks notifications via MCP
  - notify-on-complete: sends desktop notifications

Compaction hooks (fail-open, exit 0 always):
  - pre-compact-save: saves workflow state before compaction via MCP
  - post-compact-recover: injects recovery context after compaction

Note: memory-capture and memory-inject hooks use a different PS1 structure
and are validated separately via the installer integration tests.

This test module validates file existence, content structure, behavioral
parity with .sh counterparts, and correctness of PowerShell patterns.
These tests run on ALL platforms (content validation, not execution).
"""

import json
import os
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = PROJECT_ROOT / "hooks"

# All PS1 hooks grouped by category
SECURITY_HOOKS = ["bash-gate", "spawn-guard", "state-sanitize"]
AUDIT_HOOKS = ["audit-log", "canary-check", "tts-timer-start"]
NOTIFICATION_HOOKS = ["tts-notify", "notify-on-complete"]
COMPACTION_HOOKS = ["pre-compact-save", "post-compact-recover"]

ALL_PS1_HOOKS = SECURITY_HOOKS + AUDIT_HOOKS + NOTIFICATION_HOOKS + COMPACTION_HOOKS

FAIL_CLOSED_HOOKS = SECURITY_HOOKS
FAIL_OPEN_HOOKS = AUDIT_HOOKS + NOTIFICATION_HOOKS + COMPACTION_HOOKS


def _read_ps1(hook_name: str) -> str:
    """Read a PS1 hook file and return its content."""
    path = HOOKS_DIR / f"{hook_name}.ps1"
    return path.read_text(encoding="utf-8")


def _read_ps1_lines(hook_name: str) -> list[str]:
    """Read a PS1 hook file and return its lines."""
    return _read_ps1(hook_name).splitlines()


def _find_line(lines: list[str], text: str) -> tuple[int, str]:
    """Find a line containing text and return (index, line). Raises if not found."""
    for i, line in enumerate(lines):
        if text in line:
            return i, line.strip()
    raise AssertionError(f"Text {text!r} not found in any line")


def _find_line_exact(lines: list[str], exact: str) -> int:
    """Find a line matching exactly (stripped) and return its index."""
    for i, line in enumerate(lines):
        if line.strip() == exact:
            return i
    raise AssertionError(f"Exact line {exact!r} not found in any line")


# #############################################################################
# SECTION 1: File existence and basic structure (ALL hooks)
# #############################################################################


class TestPs1HookExistence:
    """Every .ps1 hook file must exist alongside its .sh counterpart."""

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_file_exists(self, hook_name):
        ps1_path = HOOKS_DIR / f"{hook_name}.ps1"
        assert ps1_path.is_file(), f"{hook_name}.ps1 not found at {ps1_path}"

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_sh_counterpart_exists(self, hook_name):
        sh_path = HOOKS_DIR / f"{hook_name}.sh"
        assert sh_path.is_file(), f"{hook_name}.sh not found at {sh_path}"

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_has_error_action_preference(self, hook_name):
        """All PS1 hooks must set $ErrorActionPreference = 'Stop' at line 5."""
        lines = _read_ps1_lines(hook_name)
        assert lines[4] == '$ErrorActionPreference = "Stop"', (
            f"{hook_name}.ps1 line 5 should be '$ErrorActionPreference = \"Stop\"', "
            f"got: {lines[4]}"
        )

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_has_try_catch(self, hook_name):
        """All PS1 hooks must have a top-level try/catch block."""
        lines = _read_ps1_lines(hook_name)
        try_idx = _find_line_exact(lines, "try {")
        # Find the matching catch block (} catch {) after the try
        catch_found = False
        for i in range(try_idx + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped == "} catch {":
                catch_found = True
                break
        assert catch_found, (
            f"{hook_name}.ps1 missing catch block after try at line {try_idx + 1}"
        )

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_has_comment_header(self, hook_name):
        """All PS1 hooks must start with a comment identifying the hook."""
        lines = _read_ps1_lines(hook_name)
        assert lines[0] == f"# hooks/{hook_name}.ps1", (
            f"{hook_name}.ps1 first line should be '# hooks/{hook_name}.ps1', got: {lines[0]}"
        )


# #############################################################################
# SECTION 2: Fail-closed security hooks (bash-gate, spawn-guard, state-sanitize)
# #############################################################################


class TestSecurityHookStructure:
    """Security hooks must be fail-closed with proper Block-Tool function."""

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_has_block_tool_function(self, hook_name):
        """Fail-closed hooks must define a Block-Tool function."""
        lines = _read_ps1_lines(hook_name)
        idx = _find_line_exact(lines, "function Block-Tool {")
        assert idx == 6, (
            f"{hook_name}.ps1 Block-Tool function at line {idx + 1}, expected line 7"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_block_tool_exits_2(self, hook_name):
        """Block-Tool must exit 2 (fail-closed)."""
        lines = _read_ps1_lines(hook_name)
        # Block-Tool function body: exit 2 at line 10 (index 9)
        assert lines[9].strip() == "exit 2", (
            f"{hook_name}.ps1 Block-Tool body should have 'exit 2' at line 10, "
            f"got: {lines[9].strip()}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_catch_block_calls_block_tool(self, hook_name):
        """Top-level catch must call Block-Tool (fail-closed on exception)."""
        lines = _read_ps1_lines(hook_name)
        # Find the last "} catch {" which is the outer catch
        catch_indices = [i for i, l in enumerate(lines) if l.strip() == "} catch {"]
        assert len(catch_indices) >= 1, f"{hook_name}.ps1 has no catch blocks"
        outer_catch = catch_indices[-1]
        catch_body = lines[outer_catch + 1].strip()
        assert catch_body == 'Block-Tool "Security check failed: internal error"', (
            f"{hook_name}.ps1 outer catch body should call Block-Tool with internal error, "
            f"got: {catch_body}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_reads_stdin_json(self, hook_name):
        """Security hooks must read JSON from stdin via [Console]::In.ReadToEnd()."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "[Console]::In.ReadToEnd()")
        assert line == "$InputJson = [Console]::In.ReadToEnd()", (
            f"{hook_name}.ps1 stdin read line should be "
            f"'$InputJson = [Console]::In.ReadToEnd()', got: {line}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_invokes_security_check_module(self, hook_name):
        """Security hooks must invoke python3 -m spellbook_mcp.security.check."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "spellbook_mcp.security.check")
        assert line == '$process.StartInfo.Arguments = "-m spellbook_mcp.security.check"', (
            f"{hook_name}.ps1 security check invocation should be "
            f"exact argument string, got: {line}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_locates_project_root(self, hook_name):
        """Security hooks must locate the project root via env or script path."""
        lines = _read_ps1_lines(hook_name)
        idx_env, line_env = _find_line(lines, "$env:SPELLBOOK_DIR")
        assert line_env == "if ($env:SPELLBOOK_DIR) {", (
            f"{hook_name}.ps1 env check should be 'if ($env:SPELLBOOK_DIR) {{', got: {line_env}"
        )
        idx_split, line_split = _find_line(lines, "Split-Path -Parent $MyInvocation")
        assert line_split == "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path", (
            f"{hook_name}.ps1 Split-Path line incorrect, got: {line_split}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_verifies_check_module_exists(self, hook_name):
        """Security hooks must verify check.py exists before invoking it."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "Test-Path $CheckModule")
        assert line == "if (-not (Test-Path $CheckModule)) {", (
            f"{hook_name}.ps1 Test-Path check incorrect, got: {line}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_blocks_on_empty_stdin(self, hook_name):
        """Security hooks must block (exit 2) when stdin is empty."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "no input received")
        assert line == 'Block-Tool "Security check failed: no input received"', (
            f"{hook_name}.ps1 empty stdin block line incorrect, got: {line}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_exit_code_switch_statement(self, hook_name):
        """Security hooks must have a switch on exit code: 0=allow, 2=block."""
        lines = _read_ps1_lines(hook_name)
        idx_switch, line_switch = _find_line(lines, "switch ($process.ExitCode)")
        assert line_switch == "switch ($process.ExitCode) {", (
            f"{hook_name}.ps1 switch statement incorrect, got: {line_switch}"
        )
        # Verify exit 0 case follows
        assert lines[idx_switch + 1].strip() == "0 { exit 0 }", (
            f"{hook_name}.ps1 exit 0 case incorrect, got: {lines[idx_switch + 1].strip()}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_sets_pythonpath(self, hook_name):
        """Security hooks must set PYTHONPATH to project root."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "PYTHONPATH")
        assert line == "$env:PYTHONPATH = $ProjectRoot", (
            f"{hook_name}.ps1 PYTHONPATH line should be '$env:PYTHONPATH = $ProjectRoot', "
            f"got: {line}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_redirects_all_streams(self, hook_name):
        """Security hooks must redirect stdin, stdout, stderr for subprocess."""
        lines = _read_ps1_lines(hook_name)
        idx_in, line_in = _find_line(lines, "RedirectStandardInput")
        assert line_in == "$process.StartInfo.RedirectStandardInput = $true", (
            f"{hook_name}.ps1 RedirectStandardInput line incorrect, got: {line_in}"
        )
        idx_out, line_out = _find_line(lines, "RedirectStandardOutput")
        assert line_out == "$process.StartInfo.RedirectStandardOutput = $true", (
            f"{hook_name}.ps1 RedirectStandardOutput line incorrect, got: {line_out}"
        )
        idx_err, line_err = _find_line(lines, "RedirectStandardError")
        assert line_err == "$process.StartInfo.RedirectStandardError = $true", (
            f"{hook_name}.ps1 RedirectStandardError line incorrect, got: {line_err}"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        """Security hooks must document FAIL-CLOSED policy in header."""
        lines = _read_ps1_lines(hook_name)
        assert lines[2] == "# Failure policy: FAIL-CLOSED (exit 2 on any error)", (
            f"{hook_name}.ps1 line 3 should be failure policy comment, "
            f"got: {lines[2]}"
        )


class TestBashGatePs1:
    """Specific tests for bash-gate.ps1."""

    def test_exact_block_reason_for_exit_2(self):
        """bash-gate must output 'dangerous pattern detected' for exit 2 without stdout."""
        lines = _read_ps1_lines("bash-gate")
        idx, line = _find_line(lines, "dangerous pattern detected")
        assert line == (
            '@{ error = "Security check failed: dangerous pattern detected" } '
            "| ConvertTo-Json -Compress | Write-Output"
        ), f"bash-gate.ps1 block reason line incorrect, got: {line}"

    def test_does_not_normalize_tool_name(self):
        """bash-gate does not normalize tool_name (unlike spawn-guard/state-sanitize)."""
        content = _read_ps1("bash-gate")
        lines = content.splitlines()
        # bash-gate should have no tool_name reassignment lines
        normalization_lines = [
            l.strip() for l in lines
            if '$data.tool_name = "' in l
        ]
        assert normalization_lines == [], (
            f"bash-gate.ps1 should not normalize tool_name, found: {normalization_lines}"
        )


class TestSpawnGuardPs1:
    """Specific tests for spawn-guard.ps1."""

    def test_normalizes_tool_name_to_spawn_claude_session(self):
        """spawn-guard must normalize tool_name to 'spawn_claude_session'."""
        lines = _read_ps1_lines("spawn-guard")
        idx, line = _find_line(lines, '$data.tool_name = "')
        assert line == '$data.tool_name = "spawn_claude_session"', (
            f"spawn-guard.ps1 tool_name normalization incorrect, got: {line}"
        )

    def test_normalization_in_try_catch(self):
        """Tool name normalization must be wrapped in its own try/catch."""
        lines = _read_ps1_lines("spawn-guard")
        idx, line = _find_line(lines, "input normalization error")
        assert line == 'Block-Tool "Security check failed: input normalization error"', (
            f"spawn-guard.ps1 normalization error handling incorrect, got: {line}"
        )

    def test_uses_convert_to_json_depth_10(self):
        """After normalization, must re-serialize with -Depth 10."""
        lines = _read_ps1_lines("spawn-guard")
        idx, line = _find_line(lines, "ConvertTo-Json -Depth 10")
        assert line == "$InputJson = $data | ConvertTo-Json -Depth 10 -Compress", (
            f"spawn-guard.ps1 JSON re-serialization incorrect, got: {line}"
        )

    def test_blocked_output_message(self):
        """spawn-guard must output 'blocked by policy' for exit 2 without stdout."""
        lines = _read_ps1_lines("spawn-guard")
        idx, line = _find_line(lines, "blocked by policy")
        assert line == (
            '@{ error = "Security check failed: blocked by policy" } '
            "| ConvertTo-Json -Compress | Write-Output"
        ), f"spawn-guard.ps1 block message incorrect, got: {line}"


class TestStateSanitizePs1:
    """Specific tests for state-sanitize.ps1."""

    def test_normalizes_tool_name_to_workflow_state_save(self):
        """state-sanitize must normalize tool_name to 'workflow_state_save'."""
        lines = _read_ps1_lines("state-sanitize")
        idx, line = _find_line(lines, '$data.tool_name = "')
        assert line == '$data.tool_name = "workflow_state_save"', (
            f"state-sanitize.ps1 tool_name normalization incorrect, got: {line}"
        )

    def test_normalization_in_try_catch(self):
        """Tool name normalization must be wrapped in its own try/catch."""
        lines = _read_ps1_lines("state-sanitize")
        idx, line = _find_line(lines, "input normalization error")
        assert line == 'Block-Tool "Security check failed: input normalization error"', (
            f"state-sanitize.ps1 normalization error handling incorrect, got: {line}"
        )

    def test_blocked_output_message(self):
        """state-sanitize must output 'injection pattern detected' for exit 2 without stdout."""
        lines = _read_ps1_lines("state-sanitize")
        idx, line = _find_line(lines, "injection pattern detected in workflow state")
        assert line == (
            '@{ error = "Security check failed: injection pattern detected in workflow state" } '
            "| ConvertTo-Json -Compress | Write-Output"
        ), f"state-sanitize.ps1 block message incorrect, got: {line}"


# #############################################################################
# SECTION 3: Fail-open audit hooks (audit-log, canary-check, tts-timer-start)
# #############################################################################


class TestAuditHookStructure:
    """Audit hooks must be fail-open (exit 0 always)."""

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_no_block_tool_function(self, hook_name):
        """Fail-open hooks must NOT define Block-Tool."""
        lines = _read_ps1_lines(hook_name)
        block_tool_lines = [l.strip() for l in lines if l.strip() == "function Block-Tool {"]
        assert block_tool_lines == [], (
            f"{hook_name}.ps1 defines Block-Tool but should be fail-open"
        )

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_catch_exits_0(self, hook_name):
        """Fail-open hooks must exit 0 in catch block."""
        lines = _read_ps1_lines(hook_name)
        # Find the outermost catch block (last "} catch {")
        catch_indices = [i for i, l in enumerate(lines) if l.strip() == "} catch {"]
        assert len(catch_indices) >= 1, f"{hook_name}.ps1 has no catch blocks"
        outer_catch = catch_indices[-1]
        catch_body = lines[outer_catch + 1].strip()
        assert catch_body == "exit 0", (
            f"{hook_name}.ps1 outer catch body should be 'exit 0', got: {catch_body}"
        )

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        """Audit hooks must document FAIL-OPEN policy in header."""
        lines = _read_ps1_lines(hook_name)
        assert lines[2] == "# Failure policy: FAIL-OPEN (exit 0 always)", (
            f"{hook_name}.ps1 line 3 should be FAIL-OPEN policy comment, got: {lines[2]}"
        )

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_reads_stdin(self, hook_name):
        """Audit hooks must read stdin."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "[Console]::In.ReadToEnd()")
        assert "[Console]::In.ReadToEnd()" in line, (
            f"{hook_name}.ps1 stdin read line incorrect, got: {line}"
        )


class TestAuditLogPs1:
    """Specific tests for audit-log.ps1."""

    def test_calls_check_with_audit_mode(self):
        """audit-log must pass --mode audit to check.py."""
        lines = _read_ps1_lines("audit-log")
        idx, line = _find_line(lines, "--mode audit")
        assert line == '$process.StartInfo.Arguments = "-m spellbook_mcp.security.check --mode audit"', (
            f"audit-log.ps1 audit mode invocation incorrect, got: {line}"
        )

    def test_invokes_security_check(self):
        """audit-log must invoke the security check module."""
        lines = _read_ps1_lines("audit-log")
        idx, line = _find_line(lines, "spellbook_mcp.security.check")
        assert line == '$process.StartInfo.Arguments = "-m spellbook_mcp.security.check --mode audit"', (
            f"audit-log.ps1 security check invocation incorrect, got: {line}"
        )

    def test_redirects_stderr(self):
        """audit-log must redirect stderr (unlike canary-check)."""
        lines = _read_ps1_lines("audit-log")
        idx, line = _find_line(lines, "RedirectStandardError")
        assert line == "$process.StartInfo.RedirectStandardError = $true", (
            f"audit-log.ps1 RedirectStandardError should be $true, got: {line}"
        )

    def test_locates_project_root(self):
        lines = _read_ps1_lines("audit-log")
        idx_env, line_env = _find_line(lines, "$env:SPELLBOOK_DIR")
        assert line_env == "if ($env:SPELLBOOK_DIR) {", (
            f"audit-log.ps1 env check incorrect, got: {line_env}"
        )
        idx_split, line_split = _find_line(lines, "Split-Path -Parent $MyInvocation")
        assert line_split == "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path", (
            f"audit-log.ps1 Split-Path line incorrect, got: {line_split}"
        )


class TestCanaryCheckPs1:
    """Specific tests for canary-check.ps1."""

    def test_calls_check_with_canary_mode(self):
        """canary-check must pass --mode canary to check.py."""
        lines = _read_ps1_lines("canary-check")
        idx, line = _find_line(lines, "--mode canary")
        assert line == '$process.StartInfo.Arguments = "-m spellbook_mcp.security.check --mode canary"', (
            f"canary-check.ps1 canary mode invocation incorrect, got: {line}"
        )

    def test_does_not_redirect_stderr(self):
        """canary-check must NOT redirect stderr (let warnings pass through)."""
        lines = _read_ps1_lines("canary-check")
        idx, line = _find_line(lines, "RedirectStandardError")
        assert line == "$process.StartInfo.RedirectStandardError = $false", (
            f"canary-check.ps1 RedirectStandardError should be $false, got: {line}"
        )

    def test_locates_project_root(self):
        lines = _read_ps1_lines("canary-check")
        idx_env, line_env = _find_line(lines, "$env:SPELLBOOK_DIR")
        assert line_env == "if ($env:SPELLBOOK_DIR) {", (
            f"canary-check.ps1 env check incorrect, got: {line_env}"
        )


class TestTtsTimerStartPs1:
    """Specific tests for tts-timer-start.ps1."""

    def test_writes_tts_timer_file(self):
        """Must write claude-tool-start-{id} temp file."""
        lines = _read_ps1_lines("tts-timer-start")
        idx, line = _find_line(lines, "claude-tool-start-")
        assert line == '$ttsFile = Join-Path $tempDir "claude-tool-start-$toolUseId"', (
            f"tts-timer-start.ps1 TTS timer file path incorrect, got: {line}"
        )

    def test_writes_notify_timer_file(self):
        """Must write claude-notify-start-{id} temp file."""
        lines = _read_ps1_lines("tts-timer-start")
        idx, line = _find_line(lines, "claude-notify-start-")
        assert line == '$notifyFile = Join-Path $tempDir "claude-notify-start-$toolUseId"', (
            f"tts-timer-start.ps1 notification timer file path incorrect, got: {line}"
        )

    def test_extracts_tool_use_id(self):
        """Must extract tool_use_id from input JSON."""
        lines = _read_ps1_lines("tts-timer-start")
        idx, line = _find_line(lines, "$data.tool_use_id")
        assert line == "$toolUseId = $data.tool_use_id", (
            f"tts-timer-start.ps1 tool_use_id extraction incorrect, got: {line}"
        )

    def test_validates_tool_use_id_present(self):
        """Must exit early if tool_use_id is missing."""
        lines = _read_ps1_lines("tts-timer-start")
        idx, line = _find_line(lines, "if (-not $toolUseId)")
        assert line == "if (-not $toolUseId) { exit 0 }", (
            f"tts-timer-start.ps1 tool_use_id validation incorrect, got: {line}"
        )

    def test_validates_tool_use_id_path_traversal(self):
        """Must validate tool_use_id against path traversal."""
        lines = _read_ps1_lines("tts-timer-start")
        validation_lines = [
            l.strip() for l in lines if r"\.\." in l and "match" in l.lower()
        ]
        assert len(validation_lines) >= 1, (
            "tts-timer-start.ps1 missing tool_use_id path traversal validation"
        )
        validation_text = " ".join(validation_lines)
        assert r"[\\\\/]" in validation_text, (
            "tts-timer-start.ps1 path traversal validation missing slash check"
        )
        assert r"\s" in validation_text, (
            "tts-timer-start.ps1 path traversal validation missing whitespace check"
        )

    def test_uses_temp_path(self):
        """Must use system temp directory."""
        lines = _read_ps1_lines("tts-timer-start")
        idx, line = _find_line(lines, "GetTempPath")
        assert line == "$tempDir = [System.IO.Path]::GetTempPath()", (
            f"tts-timer-start.ps1 temp path line incorrect, got: {line}"
        )

    def test_does_not_invoke_security_check(self):
        """tts-timer-start does NOT call security check module."""
        content = _read_ps1("tts-timer-start")
        lines = content.splitlines()
        security_lines = [
            l.strip() for l in lines if "spellbook_mcp.security.check" in l
        ]
        assert security_lines == [], (
            f"tts-timer-start.ps1 should not invoke security check, found: {security_lines}"
        )

    def test_computes_unix_timestamp(self):
        """Must compute Unix epoch timestamp from 1970-01-01."""
        lines = _read_ps1_lines("tts-timer-start")
        idx, line = _find_line(lines, "1970-01-01")
        assert line == (
            '(New-TimeSpan -Start (Get-Date "1970-01-01") '
            "-End (Get-Date).ToUniversalTime()).TotalSeconds.ToString(\"F0\")"
        ), f"tts-timer-start.ps1 Unix timestamp line incorrect, got: {line}"


# #############################################################################
# SECTION 4: Notification hooks (tts-notify, notify-on-complete)
# #############################################################################


class TestNotificationHookStructure:
    """Notification hooks must be fail-open."""

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_no_block_tool_function(self, hook_name):
        lines = _read_ps1_lines(hook_name)
        block_tool_lines = [l.strip() for l in lines if l.strip() == "function Block-Tool {"]
        assert block_tool_lines == [], (
            f"{hook_name}.ps1 defines Block-Tool but should be fail-open"
        )

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_catch_exits_0(self, hook_name):
        lines = _read_ps1_lines(hook_name)
        catch_indices = [i for i, l in enumerate(lines) if l.strip() == "} catch {"]
        assert len(catch_indices) >= 1, f"{hook_name}.ps1 has no catch blocks"
        outer_catch = catch_indices[-1]
        catch_body = lines[outer_catch + 1].strip()
        assert catch_body == "exit 0", (
            f"{hook_name}.ps1 outer catch body should be 'exit 0', got: {catch_body}"
        )

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        lines = _read_ps1_lines(hook_name)
        assert lines[2] == "# Failure policy: FAIL-OPEN (exit 0 always)", (
            f"{hook_name}.ps1 line 3 should be FAIL-OPEN policy comment, got: {lines[2]}"
        )

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_has_tool_blacklist(self, hook_name):
        """Notification hooks must blacklist interactive/management tools."""
        lines = _read_ps1_lines(hook_name)
        # Find the blacklist array definition
        blacklist_start = None
        blacklist_end = None
        for i, l in enumerate(lines):
            if "$blacklist = @(" in l:
                blacklist_start = i
            if blacklist_start is not None and l.strip() == ")":
                blacklist_end = i
                break
        assert blacklist_start is not None and blacklist_end is not None, (
            f"{hook_name}.ps1 missing $blacklist array definition"
        )
        blacklist_text = " ".join(
            lines[j].strip() for j in range(blacklist_start, blacklist_end + 1)
        )
        expected_tools = [
            "AskUserQuestion", "TodoRead", "TodoWrite",
            "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
        ]
        for tool in expected_tools:
            assert f'"{tool}"' in blacklist_text, (
                f"{hook_name}.ps1 blacklist missing {tool}. "
                f"Blacklist definition: {blacklist_text}"
            )

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_validates_tool_use_id(self, hook_name):
        """Must validate tool_use_id against path traversal."""
        lines = _read_ps1_lines(hook_name)
        validation_lines = [
            l.strip() for l in lines if r"\.\." in l and "match" in l.lower()
        ]
        assert len(validation_lines) >= 1, (
            f"{hook_name}.ps1 missing tool_use_id path traversal validation"
        )
        # Verify the validation pattern includes slash and whitespace checks too
        validation_text = " ".join(validation_lines)
        assert r"[\\\\/]" in validation_text, (
            f"{hook_name}.ps1 path traversal validation missing slash check"
        )
        assert r"\s" in validation_text, (
            f"{hook_name}.ps1 path traversal validation missing whitespace check"
        )


class TestTtsNotifyPs1:
    """Specific tests for tts-notify.ps1."""

    def test_reads_tts_timer_file(self):
        """Must read claude-tool-start-{id} temp file."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, "claude-tool-start-")
        assert line == '$startFile = Join-Path $tempDir "claude-tool-start-$toolUseId"', (
            f"tts-notify.ps1 timer file path incorrect, got: {line}"
        )

    def test_deletes_timer_file_after_read(self):
        """Must delete timer file after reading."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, "Remove-Item")
        assert line == "Remove-Item $startFile -Force", (
            f"tts-notify.ps1 timer file deletion line incorrect, got: {line}"
        )

    def test_checks_threshold(self):
        """Must compare elapsed time against threshold."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, "SPELLBOOK_TTS_THRESHOLD")
        assert line == (
            "$threshold = if ($env:SPELLBOOK_TTS_THRESHOLD) "
            "{ [int]$env:SPELLBOOK_TTS_THRESHOLD } else { 30 }"
        ), f"tts-notify.ps1 threshold line incorrect, got: {line}"

    def test_default_threshold_30(self):
        """Default threshold must be 30 seconds."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, "SPELLBOOK_TTS_THRESHOLD")
        # The threshold line includes the default of 30
        assert line.endswith("else { 30 }"), (
            f"tts-notify.ps1 default threshold should be 30, got line: {line}"
        )

    def test_sends_to_mcp_speak_endpoint(self):
        """Must POST to /api/speak."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, "/api/speak")
        assert line == '$speakUrl = "http://${mcpHost}:${mcpPort}/api/speak"', (
            f"tts-notify.ps1 speak URL line incorrect, got: {line}"
        )

    def test_uses_invoke_webrequest(self):
        """Must use Invoke-WebRequest for HTTP."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, "Invoke-WebRequest")
        assert line.startswith("Invoke-WebRequest -Uri $speakUrl -Method Post"), (
            f"tts-notify.ps1 Invoke-WebRequest line incorrect, got: {line}"
        )

    def test_builds_message_with_project_and_tool(self):
        """Message must include 'finished' and join project/tool parts."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, "finished")
        assert line == '$msgParts += "finished"', (
            f"tts-notify.ps1 message 'finished' line incorrect, got: {line}"
        )

    def test_handles_bash_command_detail(self):
        """Must extract command basename for Bash tools."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, '"Bash"')
        assert line == 'if ($toolName -eq "Bash" -and $inp -and $inp.command) {', (
            f"tts-notify.ps1 Bash handling line incorrect, got: {line}"
        )

    def test_handles_task_description_detail(self):
        """Must extract description for Task tools."""
        lines = _read_ps1_lines("tts-notify")
        idx, line = _find_line(lines, '"Task"')
        assert line == '} elseif ($toolName -eq "Task" -and $inp -and $inp.description) {', (
            f"tts-notify.ps1 Task handling line incorrect, got: {line}"
        )


class TestNotifyOnCompletePs1:
    """Specific tests for notify-on-complete.ps1."""

    def test_reads_notify_timer_file(self):
        """Must read claude-notify-start-{id} temp file."""
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "claude-notify-start-")
        assert line == '$startFile = Join-Path $tempDir "claude-notify-start-$toolUseId"', (
            f"notify-on-complete.ps1 timer file path incorrect, got: {line}"
        )

    def test_deletes_timer_file_after_read(self):
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "Remove-Item")
        assert line == "Remove-Item $startFile -Force", (
            f"notify-on-complete.ps1 timer file deletion incorrect, got: {line}"
        )

    def test_checks_notify_enabled_env(self):
        """Must check SPELLBOOK_NOTIFY_ENABLED env var."""
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "SPELLBOOK_NOTIFY_ENABLED")
        assert line == (
            '$notifyEnabled = if ($env:SPELLBOOK_NOTIFY_ENABLED) '
            '{ $env:SPELLBOOK_NOTIFY_ENABLED } else { "true" }'
        ), f"notify-on-complete.ps1 NOTIFY_ENABLED line incorrect, got: {line}"

    def test_checks_threshold(self):
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "SPELLBOOK_NOTIFY_THRESHOLD")
        assert line == (
            "$threshold = if ($env:SPELLBOOK_NOTIFY_THRESHOLD) "
            "{ [int]$env:SPELLBOOK_NOTIFY_THRESHOLD } else { 30 }"
        ), f"notify-on-complete.ps1 threshold line incorrect, got: {line}"

    def test_default_threshold_30(self):
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "SPELLBOOK_NOTIFY_THRESHOLD")
        assert line.endswith("else { 30 }"), (
            f"notify-on-complete.ps1 default threshold should be 30, got line: {line}"
        )

    def test_uses_notify_title(self):
        """Must use SPELLBOOK_NOTIFY_TITLE or default 'Spellbook'."""
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "SPELLBOOK_NOTIFY_TITLE")
        assert line == (
            '$title = if ($env:SPELLBOOK_NOTIFY_TITLE) '
            '{ $env:SPELLBOOK_NOTIFY_TITLE } else { "Spellbook" }'
        ), f"notify-on-complete.ps1 NOTIFY_TITLE line incorrect, got: {line}"

    def test_uses_get_command_pwsh(self):
        """Must prefer pwsh over legacy powershell via Get-Command."""
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "Get-Command pwsh")
        assert line == (
            '$shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) '
            '{ "pwsh" } else { "powershell" }'
        ), f"notify-on-complete.ps1 pwsh detection line incorrect, got: {line}"

    def test_sends_windows_toast(self):
        """Must send Windows toast notification via BurntToast or ToastNotification."""
        lines = _read_ps1_lines("notify-on-complete")
        idx_burnt, line_burnt = _find_line(lines, "BurntToast")
        assert line_burnt == "Import-Module BurntToast -ErrorAction Stop", (
            f"notify-on-complete.ps1 BurntToast import line incorrect, got: {line_burnt}"
        )
        idx_toast, line_toast = _find_line(lines, "ToastNotificationManager")
        assert "Windows.UI.Notifications.ToastNotificationManager" in line_toast, (
            f"notify-on-complete.ps1 ToastNotification fallback line incorrect, got: {line_toast}"
        )

    def test_body_includes_elapsed_time(self):
        """Notification body must include elapsed time."""
        lines = _read_ps1_lines("notify-on-complete")
        idx, line = _find_line(lines, "${elapsed}")
        assert line == '$body = "$toolName finished (${elapsed}s)"', (
            f"notify-on-complete.ps1 body line incorrect, got: {line}"
        )


# #############################################################################
# SECTION 5: Compaction hooks (pre-compact-save, post-compact-recover)
# #############################################################################


class TestCompactionHookStructure:
    """Compaction hooks must be fail-open."""

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_no_block_tool_function(self, hook_name):
        lines = _read_ps1_lines(hook_name)
        block_tool_lines = [l.strip() for l in lines if l.strip() == "function Block-Tool {"]
        assert block_tool_lines == [], (
            f"{hook_name}.ps1 defines Block-Tool but should be fail-open"
        )

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        lines = _read_ps1_lines(hook_name)
        # Compaction hooks have longer policy comment (different suffix)
        policy_line = lines[2]
        assert policy_line.startswith("# Failure policy: FAIL-OPEN"), (
            f"{hook_name}.ps1 line 3 should start with FAIL-OPEN policy, got: {policy_line}"
        )

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_uses_mcp_http_endpoint(self, hook_name):
        """Compaction hooks communicate with MCP via HTTP."""
        lines = _read_ps1_lines(hook_name)
        idx_host, line_host = _find_line(lines, "SPELLBOOK_MCP_HOST")
        assert "$env:SPELLBOOK_MCP_HOST" in line_host, (
            f"{hook_name}.ps1 MCP host line incorrect, got: {line_host}"
        )
        idx_port, line_port = _find_line(lines, "SPELLBOOK_MCP_PORT")
        assert "$env:SPELLBOOK_MCP_PORT" in line_port, (
            f"{hook_name}.ps1 MCP port line incorrect, got: {line_port}"
        )

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_has_invoke_mcp_tool_function(self, hook_name):
        """Compaction hooks must define Invoke-McpTool helper."""
        lines = _read_ps1_lines(hook_name)
        idx = _find_line_exact(lines, "function Invoke-McpTool {")
        assert idx is not None, (
            f"{hook_name}.ps1 missing Invoke-McpTool function definition"
        )

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_parses_sse_response(self, hook_name):
        """Compaction hooks must parse SSE data: lines from MCP response."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, 'StartsWith("data: ")')
        assert line == 'if ($line.StartsWith("data: ")) {', (
            f"{hook_name}.ps1 SSE parsing line incorrect, got: {line}"
        )

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_has_write_log_function(self, hook_name):
        """Compaction hooks must define Write-Log helper."""
        lines = _read_ps1_lines(hook_name)
        idx = _find_line_exact(lines, "function Write-Log {")
        assert idx is not None, (
            f"{hook_name}.ps1 missing Write-Log function definition"
        )

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_logs_to_spellbook_logs_dir(self, hook_name):
        """Compaction hooks must log to ~/.local/spellbook/logs/."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "$LogDir")
        assert line == '$LogDir = Join-Path $HOME ".local" "spellbook" "logs"', (
            f"{hook_name}.ps1 log directory line incorrect, got: {line}"
        )


class TestPreCompactSavePs1:
    """Specific tests for pre-compact-save.ps1."""

    def test_reads_cwd_from_stdin(self):
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, "$data.cwd")
        assert line == "$projectPath = if ($data.cwd) { $data.cwd } else { \"\" }", (
            f"pre-compact-save.ps1 cwd extraction incorrect, got: {line}"
        )

    def test_calls_workflow_state_load(self):
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, "workflow_state_load")
        assert line == '$loadResult = Invoke-McpTool -ToolName "workflow_state_load" -Arguments @{', (
            f"pre-compact-save.ps1 workflow_state_load call incorrect, got: {line}"
        )

    def test_calls_workflow_state_save(self):
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, "workflow_state_save")
        assert line == '$saveResult = Invoke-McpTool -ToolName "workflow_state_save" -Arguments @{', (
            f"pre-compact-save.ps1 workflow_state_save call incorrect, got: {line}"
        )

    def test_checks_freshness(self):
        """Must check if state is fresh (< 5 min = 0.083 hours)."""
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, "0.083")
        assert line == "if ($found -and $ageHours -ne $null -and [double]$ageHours -lt 0.083) {", (
            f"pre-compact-save.ps1 freshness check incorrect, got: {line}"
        )

    def test_sets_compaction_flag(self):
        """Must set compaction_flag in saved state."""
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, "compaction_flag")
        assert line == 'if (-not $state.ContainsKey("compaction_flag")) {', (
            f"pre-compact-save.ps1 compaction_flag check incorrect, got: {line}"
        )

    def test_uses_trigger_auto(self):
        """Must save with trigger=auto."""
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, 'trigger = "auto"')
        assert line == 'trigger = "auto"', (
            f"pre-compact-save.ps1 trigger auto line incorrect, got: {line}"
        )

    def test_logs_to_pre_compact_log(self):
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, "pre-compact.log")
        assert line == '$LogFile = Join-Path $LogDir "pre-compact.log"', (
            f"pre-compact-save.ps1 log file line incorrect, got: {line}"
        )

    def test_catch_exits_0(self):
        """Must exit 0 even on errors."""
        lines = _read_ps1_lines("pre-compact-save")
        catch_indices = [i for i, l in enumerate(lines) if l.strip() == "} catch {"]
        assert len(catch_indices) >= 1, "pre-compact-save.ps1 has no catch blocks"
        outer_catch = catch_indices[-1]
        # The outer catch has Write-Log then exit 0
        exit_line = None
        for i in range(outer_catch + 1, min(outer_catch + 4, len(lines))):
            if lines[i].strip() == "exit 0":
                exit_line = i
                break
        assert exit_line is not None, (
            "pre-compact-save.ps1 outer catch block missing exit 0"
        )

    def test_uses_jsonrpc(self):
        """Must use JSON-RPC format for MCP calls."""
        lines = _read_ps1_lines("pre-compact-save")
        idx_jsonrpc, line_jsonrpc = _find_line(lines, 'jsonrpc = "2.0"')
        assert line_jsonrpc == 'jsonrpc = "2.0"', (
            f"pre-compact-save.ps1 jsonrpc line incorrect, got: {line_jsonrpc}"
        )
        idx_method, line_method = _find_line(lines, 'method = "tools/call"')
        assert line_method == 'method = "tools/call"', (
            f"pre-compact-save.ps1 method line incorrect, got: {line_method}"
        )

    def test_handles_pscustomobject_to_hashtable(self):
        """Must convert PSCustomObject to hashtable for state merging."""
        lines = _read_ps1_lines("pre-compact-save")
        idx, line = _find_line(lines, "PSObject.Properties")
        assert line == "$existingState.PSObject.Properties | ForEach-Object { $state[$_.Name] = $_.Value }", (
            f"pre-compact-save.ps1 PSCustomObject conversion incorrect, got: {line}"
        )


class TestPostCompactRecoverPs1:
    """Specific tests for post-compact-recover.ps1."""

    def test_checks_source_is_compact(self):
        """Must verify source == 'compact' before acting."""
        lines = _read_ps1_lines("post-compact-recover")
        idx, line = _find_line(lines, '"compact"')
        assert line == 'if ($source -ne "compact") { exit 0 }', (
            f"post-compact-recover.ps1 compact check incorrect, got: {line}"
        )

    def test_has_output_fallback_function(self):
        """Must define Output-Fallback for error cases."""
        lines = _read_ps1_lines("post-compact-recover")
        idx = _find_line_exact(lines, "function Output-Fallback {")
        assert idx is not None, (
            "post-compact-recover.ps1 missing Output-Fallback function definition"
        )

    def test_fallback_mentions_session_init(self):
        """Fallback must mention spellbook_session_init."""
        lines = _read_ps1_lines("post-compact-recover")
        idx, line = _find_line(lines, "spellbook_session_init")
        assert line == (
            '$directive = "COMPACTION OCCURRED. '
            'Call spellbook_session_init to restore workflow state."'
        ), f"post-compact-recover.ps1 fallback directive incorrect, got: {line}"

    def test_outputs_hook_specific_output_json(self):
        """Must output hookSpecificOutput JSON on stdout."""
        lines = _read_ps1_lines("post-compact-recover")
        idx_hook, line_hook = _find_line(lines, "hookSpecificOutput")
        assert line_hook == "hookSpecificOutput = @{", (
            f"post-compact-recover.ps1 hookSpecificOutput line incorrect, got: {line_hook}"
        )
        idx_event, line_event = _find_line(lines, "hookEventName")
        assert line_event == 'hookEventName = "SessionStart"', (
            f"post-compact-recover.ps1 hookEventName line incorrect, got: {line_event}"
        )
        idx_ctx, line_ctx = _find_line(lines, "additionalContext")
        assert line_ctx == "additionalContext = $directive", (
            f"post-compact-recover.ps1 additionalContext line incorrect, got: {line_ctx}"
        )

    def test_calls_workflow_state_load(self):
        lines = _read_ps1_lines("post-compact-recover")
        idx, line = _find_line(lines, "workflow_state_load")
        assert line == '$loadResult = Invoke-McpTool -ToolName "workflow_state_load" -Arguments @{', (
            f"post-compact-recover.ps1 workflow_state_load call incorrect, got: {line}"
        )

    def test_optionally_calls_skill_instructions_get(self):
        """Must call skill_instructions_get when active_skill is present."""
        lines = _read_ps1_lines("post-compact-recover")
        idx, line = _find_line(lines, "skill_instructions_get")
        assert line == '$skillResult = Invoke-McpTool -ToolName "skill_instructions_get" -Arguments @{', (
            f"post-compact-recover.ps1 skill_instructions_get call incorrect, got: {line}"
        )

    def test_extracts_state_fields(self):
        """Must extract active_skill, skill_phase, binding_decisions, etc."""
        lines = _read_ps1_lines("post-compact-recover")
        expected_extractions = {
            "active_skill": '$activeSkill = if ($state.active_skill) { $state.active_skill } else { "" }',
            "skill_phase": '$skillPhase = if ($state.skill_phase) { $state.skill_phase } else { "" }',
            "binding_decisions": '$bindingDecisions = if ($state.binding_decisions) { $state.binding_decisions } else { "" }',
            "next_action": '$nextAction = if ($state.next_action) { $state.next_action } else { "" }',
        }
        for field, expected_line in expected_extractions.items():
            idx, line = _find_line(lines, f"$state.{field}")
            assert line == expected_line, (
                f"post-compact-recover.ps1 extraction of '{field}' incorrect, got: {line}"
            )

    def test_logs_to_post_compact_log(self):
        lines = _read_ps1_lines("post-compact-recover")
        idx, line = _find_line(lines, "post-compact.log")
        assert line == '$LogFile = Join-Path $LogDir "post-compact.log"', (
            f"post-compact-recover.ps1 log file line incorrect, got: {line}"
        )

    def test_catch_calls_output_fallback(self):
        """On error, must output fallback directive rather than silently failing."""
        lines = _read_ps1_lines("post-compact-recover")
        catch_indices = [i for i, l in enumerate(lines) if l.strip() == "} catch {"]
        assert len(catch_indices) >= 1, "post-compact-recover.ps1 has no catch blocks"
        outer_catch = catch_indices[-1]
        # The outer catch should call Output-Fallback (within a few lines)
        found_fallback = False
        for i in range(outer_catch + 1, min(outer_catch + 4, len(lines))):
            if "Output-Fallback" in lines[i]:
                found_fallback = True
                assert lines[i].strip() == "Output-Fallback", (
                    f"post-compact-recover.ps1 catch fallback line incorrect, "
                    f"got: {lines[i].strip()}"
                )
                break
        assert found_fallback, (
            "post-compact-recover.ps1 outer catch block missing Output-Fallback call"
        )

    def test_reads_cwd_from_stdin(self):
        lines = _read_ps1_lines("post-compact-recover")
        idx, line = _find_line(lines, "$data.cwd")
        assert '$cwd = if ($data.cwd) { $data.cwd } else { "" }' == line, (
            f"post-compact-recover.ps1 cwd extraction incorrect, got: {line}"
        )


# #############################################################################
# SECTION 6: Cross-hook consistency checks
# #############################################################################


class TestCrossHookConsistency:
    """Verify consistency between .sh and .ps1 hooks."""

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_security_hook_error_messages_match_sh(self, hook_name):
        """PS1 security hooks must use 'Security check unavailable' as default block reason."""
        lines = _read_ps1_lines(hook_name)
        idx, line = _find_line(lines, "Security check unavailable")
        assert line == 'param([string]$Reason = "Security check unavailable")', (
            f"{hook_name}.ps1 default block reason line incorrect, got: {line}"
        )

    @pytest.mark.parametrize("hook_name", ["spawn-guard", "state-sanitize"])
    def test_normalizing_hooks_match_sh_tool_names(self, hook_name):
        """PS1 normalizing hooks must use same tool_name as .sh."""
        ps1_lines = _read_ps1_lines(hook_name)
        sh_path = HOOKS_DIR / f"{hook_name}.sh"
        sh_content = sh_path.read_text(encoding="utf-8")

        expected_names = {
            "spawn-guard": "spawn_claude_session",
            "state-sanitize": "workflow_state_save",
        }
        tool_name = expected_names[hook_name]
        idx_ps1, line_ps1 = _find_line(ps1_lines, f'"{tool_name}"')
        assert f'"{tool_name}"' in line_ps1, (
            f"{hook_name}.ps1 tool_name {tool_name} not found"
        )
        sh_lines = sh_content.splitlines()
        idx_sh, line_sh = _find_line(sh_lines, tool_name)
        assert tool_name in line_sh, (
            f"{hook_name}.sh tool_name {tool_name} not found"
        )

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_and_sh_have_same_failure_policy(self, hook_name):
        """PS1 and SH variants must agree on failure policy."""
        ps1_lines = _read_ps1_lines(hook_name)
        sh_path = HOOKS_DIR / f"{hook_name}.sh"
        sh_content = sh_path.read_text(encoding="utf-8")

        # Check PS1 policy from line 3 (index 2)
        ps1_policy_line = ps1_lines[2]
        ps1_is_fail_closed = "FAIL-CLOSED" in ps1_policy_line
        ps1_is_fail_open = "FAIL-OPEN" in ps1_policy_line

        sh_is_fail_closed = "fail-closed" in sh_content.lower() or "FAIL-CLOSED" in sh_content
        sh_is_fail_open = "fail-open" in sh_content.lower() or "FAIL-OPEN" in sh_content

        # At least one policy must be declared in both
        if ps1_is_fail_closed:
            assert sh_is_fail_closed or not sh_is_fail_open, (
                f"{hook_name}: PS1 is FAIL-CLOSED but SH is not"
            )
        if ps1_is_fail_open:
            assert sh_is_fail_open or not sh_is_fail_closed, (
                f"{hook_name}: PS1 is FAIL-OPEN but SH is not"
            )


class TestHookTransformationPs1:
    """Verify that the installer produces correct .ps1 paths on Windows."""

    def test_get_hook_path_windows_converts_to_ps1(self):
        """On Windows, .sh paths must be converted to PowerShell invocation."""
        from unittest import mock

        from installer.components.hooks import _get_hook_path_for_platform

        with mock.patch("sys.platform", "win32"):
            result = _get_hook_path_for_platform("$SPELLBOOK_DIR/hooks/bash-gate.sh")
            assert result == "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/bash-gate.ps1"

    def test_all_hook_definitions_are_transformable_to_ps1(self):
        """Every hook in HOOK_DEFINITIONS can be transformed for Windows (.ps1)."""
        from unittest import mock

        from installer.components.hooks import HOOK_DEFINITIONS, _transform_hook_for_platform

        with mock.patch("sys.platform", "win32"):
            for phase, defs in HOOK_DEFINITIONS.items():
                for hook_def in defs:
                    for hook in hook_def["hooks"]:
                        result = _transform_hook_for_platform(hook)
                        if isinstance(result, str):
                            assert result.startswith("powershell -ExecutionPolicy Bypass -File "), (
                                f"String hook not converted to PowerShell wrapper: {result}"
                            )
                            assert result.endswith(".ps1"), (
                                f"String hook does not end with .ps1: {result}"
                            )
                        else:
                            assert result["command"].startswith(
                                "powershell -ExecutionPolicy Bypass -File "
                            ), (
                                f"Dict hook command not converted to PowerShell wrapper: "
                                f"{result['command']}"
                            )
                            assert result["command"].endswith(".ps1"), (
                                f"Dict hook command does not end with .ps1: {result['command']}"
                            )

    def test_installed_hooks_use_ps1_on_windows(self, tmp_path):
        """install_hooks() produces .ps1 paths on (mocked) Windows."""
        from unittest import mock

        from installer.components.hooks import install_hooks

        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("{}", encoding="utf-8")

        with mock.patch("sys.platform", "win32"), \
             mock.patch("shutil.which", return_value="/usr/bin/powershell"):
            result = install_hooks(settings_path)

        assert result.success is True

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        hooks_section = settings.get("hooks", {})

        all_paths = []
        for phase in hooks_section.values():
            for entry in phase:
                for hook in entry.get("hooks", []):
                    if isinstance(hook, str):
                        all_paths.append(hook)
                    elif isinstance(hook, dict) and "command" in hook:
                        all_paths.append(hook["command"])

        expected_paths = [
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/bash-gate.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/spawn-guard.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/state-sanitize.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/tts-timer-start.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/audit-log.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/canary-check.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/memory-inject.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/notify-on-complete.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/tts-notify.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/memory-capture.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/pre-compact-save.ps1",
            "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/post-compact-recover.ps1",
        ]
        assert len(all_paths) == 12, (
            f"Expected 12 hook paths installed, got {len(all_paths)}: {all_paths}"
        )
        assert sorted(all_paths) == sorted(expected_paths), (
            f"Installed hook paths do not match expected.\n"
            f"Got: {sorted(all_paths)}\n"
            f"Expected: {sorted(expected_paths)}"
        )
