"""Tests for PowerShell (.ps1) hook implementations used on Windows.

The hook system provides 10 hooks, each with a .sh (Unix) and .ps1 (Windows) variant:

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
        """All PS1 hooks must set $ErrorActionPreference = 'Stop'."""
        content = _read_ps1(hook_name)
        assert '$ErrorActionPreference = "Stop"' in content, (
            f"{hook_name}.ps1 missing $ErrorActionPreference = \"Stop\""
        )

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_has_try_catch(self, hook_name):
        """All PS1 hooks must have a top-level try/catch block."""
        content = _read_ps1(hook_name)
        assert "try {" in content, f"{hook_name}.ps1 missing try block"
        assert "} catch {" in content, f"{hook_name}.ps1 missing catch block"

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_has_comment_header(self, hook_name):
        """All PS1 hooks must start with a comment identifying the hook."""
        content = _read_ps1(hook_name)
        first_line = content.strip().splitlines()[0]
        assert first_line.startswith(f"# hooks/{hook_name}.ps1"), (
            f"{hook_name}.ps1 first line should be '# hooks/{hook_name}.ps1', got: {first_line}"
        )


# #############################################################################
# SECTION 2: Fail-closed security hooks (bash-gate, spawn-guard, state-sanitize)
# #############################################################################


class TestSecurityHookStructure:
    """Security hooks must be fail-closed with proper Block-Tool function."""

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_has_block_tool_function(self, hook_name):
        """Fail-closed hooks must define a Block-Tool function."""
        content = _read_ps1(hook_name)
        assert "function Block-Tool {" in content, (
            f"{hook_name}.ps1 missing Block-Tool function"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_block_tool_exits_2(self, hook_name):
        """Block-Tool must exit 2 (fail-closed)."""
        content = _read_ps1(hook_name)
        # Block-Tool outputs JSON error and exits 2
        assert "exit 2" in content, (
            f"{hook_name}.ps1 Block-Tool missing 'exit 2'"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_catch_block_calls_block_tool(self, hook_name):
        """Top-level catch must call Block-Tool (fail-closed on exception)."""
        content = _read_ps1(hook_name)
        # The catch block should invoke Block-Tool with an error message
        catch_match = re.search(
            r'\}\s*catch\s*\{[^}]*Block-Tool\s+"Security check failed: internal error"',
            content,
        )
        assert catch_match is not None, (
            f"{hook_name}.ps1 catch block does not call Block-Tool with internal error message"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_reads_stdin_json(self, hook_name):
        """Security hooks must read JSON from stdin via [Console]::In.ReadToEnd()."""
        content = _read_ps1(hook_name)
        assert "[Console]::In.ReadToEnd()" in content, (
            f"{hook_name}.ps1 missing [Console]::In.ReadToEnd()"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_invokes_security_check_module(self, hook_name):
        """Security hooks must invoke python3 -m spellbook_mcp.security.check."""
        content = _read_ps1(hook_name)
        assert "spellbook_mcp.security.check" in content, (
            f"{hook_name}.ps1 missing spellbook_mcp.security.check invocation"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_locates_project_root(self, hook_name):
        """Security hooks must locate the project root via env or script path."""
        content = _read_ps1(hook_name)
        assert "$env:SPELLBOOK_DIR" in content, (
            f"{hook_name}.ps1 missing $env:SPELLBOOK_DIR check"
        )
        assert "Split-Path" in content, (
            f"{hook_name}.ps1 missing Split-Path for script-relative root derivation"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_verifies_check_module_exists(self, hook_name):
        """Security hooks must verify check.py exists before invoking it."""
        content = _read_ps1(hook_name)
        assert "Test-Path" in content, (
            f"{hook_name}.ps1 missing Test-Path check for check module"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_blocks_on_empty_stdin(self, hook_name):
        """Security hooks must block (exit 2) when stdin is empty."""
        content = _read_ps1(hook_name)
        assert "no input received" in content, (
            f"{hook_name}.ps1 missing 'no input received' error for empty stdin"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_exit_code_switch_statement(self, hook_name):
        """Security hooks must have a switch on exit code: 0=allow, 2=block."""
        content = _read_ps1(hook_name)
        assert "switch ($process.ExitCode)" in content, (
            f"{hook_name}.ps1 missing switch on process exit code"
        )
        # Must handle exit 0 (allow)
        assert "0 { exit 0 }" in content, (
            f"{hook_name}.ps1 missing 'exit 0' case in switch"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_sets_pythonpath(self, hook_name):
        """Security hooks must set PYTHONPATH to project root."""
        content = _read_ps1(hook_name)
        assert "PYTHONPATH" in content, (
            f"{hook_name}.ps1 missing PYTHONPATH setup"
        )

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_redirects_all_streams(self, hook_name):
        """Security hooks must redirect stdin, stdout, stderr for subprocess."""
        content = _read_ps1(hook_name)
        assert "RedirectStandardInput = $true" in content
        assert "RedirectStandardOutput = $true" in content
        assert "RedirectStandardError = $true" in content

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        """Security hooks must document FAIL-CLOSED policy in header."""
        content = _read_ps1(hook_name)
        assert "FAIL-CLOSED" in content, (
            f"{hook_name}.ps1 missing FAIL-CLOSED policy comment"
        )


class TestBashGatePs1:
    """Specific tests for bash-gate.ps1."""

    def test_exact_block_reason_for_exit_2(self):
        """bash-gate must output 'dangerous pattern detected' for exit 2 without stdout."""
        content = _read_ps1("bash-gate")
        assert "dangerous pattern detected" in content

    def test_does_not_normalize_tool_name(self):
        """bash-gate does not normalize tool_name (unlike spawn-guard/state-sanitize)."""
        content = _read_ps1("bash-gate")
        # bash-gate should NOT have ConvertFrom-Json -> tool_name reassignment
        assert 'data.tool_name = "' not in content.replace("$data.tool_name", "")


class TestSpawnGuardPs1:
    """Specific tests for spawn-guard.ps1."""

    def test_normalizes_tool_name_to_spawn_claude_session(self):
        """spawn-guard must normalize tool_name to 'spawn_claude_session'."""
        content = _read_ps1("spawn-guard")
        assert '$data.tool_name = "spawn_claude_session"' in content, (
            "spawn-guard.ps1 must normalize tool_name to spawn_claude_session"
        )

    def test_normalization_in_try_catch(self):
        """Tool name normalization must be wrapped in its own try/catch."""
        content = _read_ps1("spawn-guard")
        # The normalization block should have its own error handling
        assert "input normalization error" in content, (
            "spawn-guard.ps1 must handle normalization errors"
        )

    def test_uses_convert_to_json_depth_10(self):
        """After normalization, must re-serialize with -Depth 10."""
        content = _read_ps1("spawn-guard")
        assert "ConvertTo-Json -Depth 10" in content, (
            "spawn-guard.ps1 must use -Depth 10 when re-serializing normalized input"
        )

    def test_blocked_output_message(self):
        """spawn-guard must output 'blocked by policy' for exit 2 without stdout."""
        content = _read_ps1("spawn-guard")
        assert "blocked by policy" in content


class TestStateSanitizePs1:
    """Specific tests for state-sanitize.ps1."""

    def test_normalizes_tool_name_to_workflow_state_save(self):
        """state-sanitize must normalize tool_name to 'workflow_state_save'."""
        content = _read_ps1("state-sanitize")
        assert '$data.tool_name = "workflow_state_save"' in content, (
            "state-sanitize.ps1 must normalize tool_name to workflow_state_save"
        )

    def test_normalization_in_try_catch(self):
        """Tool name normalization must be wrapped in its own try/catch."""
        content = _read_ps1("state-sanitize")
        assert "input normalization error" in content

    def test_blocked_output_message(self):
        """state-sanitize must output 'injection pattern detected' for exit 2 without stdout."""
        content = _read_ps1("state-sanitize")
        assert "injection pattern detected in workflow state" in content


# #############################################################################
# SECTION 3: Fail-open audit hooks (audit-log, canary-check, tts-timer-start)
# #############################################################################


class TestAuditHookStructure:
    """Audit hooks must be fail-open (exit 0 always)."""

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_no_block_tool_function(self, hook_name):
        """Fail-open hooks must NOT define Block-Tool."""
        content = _read_ps1(hook_name)
        assert "function Block-Tool" not in content, (
            f"{hook_name}.ps1 defines Block-Tool but should be fail-open"
        )

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_catch_exits_0(self, hook_name):
        """Fail-open hooks must exit 0 in catch block."""
        content = _read_ps1(hook_name)
        # The outermost catch block must contain exit 0
        catch_pattern = re.search(r'\}\s*catch\s*\{[^}]*exit 0[^}]*\}', content)
        assert catch_pattern is not None, (
            f"{hook_name}.ps1 catch block does not exit 0 (fail-open violated)"
        )

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        """Audit hooks must document FAIL-OPEN policy in header."""
        content = _read_ps1(hook_name)
        assert "FAIL-OPEN" in content, (
            f"{hook_name}.ps1 missing FAIL-OPEN policy comment"
        )

    @pytest.mark.parametrize("hook_name", AUDIT_HOOKS)
    def test_reads_stdin(self, hook_name):
        """Audit hooks must read stdin."""
        content = _read_ps1(hook_name)
        assert "[Console]::In.ReadToEnd()" in content


class TestAuditLogPs1:
    """Specific tests for audit-log.ps1."""

    def test_calls_check_with_audit_mode(self):
        """audit-log must pass --mode audit to check.py."""
        content = _read_ps1("audit-log")
        assert "--mode audit" in content, (
            "audit-log.ps1 must invoke check.py with --mode audit"
        )

    def test_invokes_security_check(self):
        """audit-log must invoke the security check module."""
        content = _read_ps1("audit-log")
        assert "spellbook_mcp.security.check" in content

    def test_redirects_stderr(self):
        """audit-log must redirect stderr (unlike canary-check)."""
        content = _read_ps1("audit-log")
        assert "RedirectStandardError = $true" in content

    def test_locates_project_root(self):
        content = _read_ps1("audit-log")
        assert "$env:SPELLBOOK_DIR" in content
        assert "Split-Path" in content


class TestCanaryCheckPs1:
    """Specific tests for canary-check.ps1."""

    def test_calls_check_with_canary_mode(self):
        """canary-check must pass --mode canary to check.py."""
        content = _read_ps1("canary-check")
        assert "--mode canary" in content, (
            "canary-check.ps1 must invoke check.py with --mode canary"
        )

    def test_does_not_redirect_stderr(self):
        """canary-check must NOT redirect stderr (let warnings pass through)."""
        content = _read_ps1("canary-check")
        assert "RedirectStandardError = $false" in content, (
            "canary-check.ps1 must set RedirectStandardError = $false "
            "so canary token warnings pass through to parent stderr"
        )

    def test_locates_project_root(self):
        content = _read_ps1("canary-check")
        assert "$env:SPELLBOOK_DIR" in content


class TestTtsTimerStartPs1:
    """Specific tests for tts-timer-start.ps1."""

    def test_writes_tts_timer_file(self):
        """Must write claude-tool-start-{id} temp file."""
        content = _read_ps1("tts-timer-start")
        assert "claude-tool-start-" in content, (
            "tts-timer-start.ps1 missing TTS timer file write"
        )

    def test_writes_notify_timer_file(self):
        """Must write claude-notify-start-{id} temp file."""
        content = _read_ps1("tts-timer-start")
        assert "claude-notify-start-" in content, (
            "tts-timer-start.ps1 missing notification timer file write"
        )

    def test_extracts_tool_use_id(self):
        """Must extract tool_use_id from input JSON."""
        content = _read_ps1("tts-timer-start")
        assert "tool_use_id" in content

    def test_validates_tool_use_id_present(self):
        """Must exit early if tool_use_id is missing."""
        content = _read_ps1("tts-timer-start")
        assert "$toolUseId" in content or "$data.tool_use_id" in content

    def test_uses_temp_path(self):
        """Must use system temp directory."""
        content = _read_ps1("tts-timer-start")
        assert "[System.IO.Path]::GetTempPath()" in content

    def test_does_not_invoke_security_check(self):
        """tts-timer-start does NOT call security check module."""
        content = _read_ps1("tts-timer-start")
        assert "spellbook_mcp.security.check" not in content

    def test_computes_unix_timestamp(self):
        """Must compute Unix epoch timestamp."""
        content = _read_ps1("tts-timer-start")
        assert "1970-01-01" in content, (
            "tts-timer-start.ps1 must compute Unix epoch timestamp"
        )


# #############################################################################
# SECTION 4: Notification hooks (tts-notify, notify-on-complete)
# #############################################################################


class TestNotificationHookStructure:
    """Notification hooks must be fail-open."""

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_no_block_tool_function(self, hook_name):
        content = _read_ps1(hook_name)
        assert "function Block-Tool" not in content

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_catch_exits_0(self, hook_name):
        content = _read_ps1(hook_name)
        catch_pattern = re.search(r'\}\s*catch\s*\{[^}]*exit 0[^}]*\}', content)
        assert catch_pattern is not None, (
            f"{hook_name}.ps1 catch block does not exit 0"
        )

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        content = _read_ps1(hook_name)
        assert "FAIL-OPEN" in content

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_has_tool_blacklist(self, hook_name):
        """Notification hooks must blacklist interactive/management tools."""
        content = _read_ps1(hook_name)
        for tool in ["AskUserQuestion", "TodoRead", "TodoWrite",
                      "TaskCreate", "TaskUpdate", "TaskGet", "TaskList"]:
            assert tool in content, (
                f"{hook_name}.ps1 missing blacklisted tool: {tool}"
            )

    @pytest.mark.parametrize("hook_name", NOTIFICATION_HOOKS)
    def test_validates_tool_use_id(self, hook_name):
        """Must validate tool_use_id against path traversal."""
        content = _read_ps1(hook_name)
        assert ".." in content or "path traversal" in content.lower(), (
            f"{hook_name}.ps1 missing tool_use_id path traversal validation"
        )


class TestTtsNotifyPs1:
    """Specific tests for tts-notify.ps1."""

    def test_reads_tts_timer_file(self):
        """Must read claude-tool-start-{id} temp file."""
        content = _read_ps1("tts-notify")
        assert "claude-tool-start-" in content

    def test_deletes_timer_file_after_read(self):
        """Must delete timer file after reading."""
        content = _read_ps1("tts-notify")
        assert "Remove-Item" in content

    def test_checks_threshold(self):
        """Must compare elapsed time against threshold."""
        content = _read_ps1("tts-notify")
        assert "SPELLBOOK_TTS_THRESHOLD" in content

    def test_default_threshold_30(self):
        """Default threshold must be 30 seconds."""
        content = _read_ps1("tts-notify")
        # Pattern: default value of 30 for threshold
        assert "30" in content

    def test_sends_to_mcp_speak_endpoint(self):
        """Must POST to /api/speak."""
        content = _read_ps1("tts-notify")
        assert "/api/speak" in content

    def test_uses_invoke_webrequest(self):
        """Must use Invoke-WebRequest for HTTP."""
        content = _read_ps1("tts-notify")
        assert "Invoke-WebRequest" in content

    def test_builds_message_with_project_and_tool(self):
        """Message must include project name and tool name."""
        content = _read_ps1("tts-notify")
        assert "finished" in content

    def test_handles_bash_command_detail(self):
        """Must extract command basename for Bash tools."""
        content = _read_ps1("tts-notify")
        assert "Bash" in content

    def test_handles_task_description_detail(self):
        """Must extract description for Task tools."""
        content = _read_ps1("tts-notify")
        assert "Task" in content


class TestNotifyOnCompletePs1:
    """Specific tests for notify-on-complete.ps1."""

    def test_reads_notify_timer_file(self):
        """Must read claude-notify-start-{id} temp file."""
        content = _read_ps1("notify-on-complete")
        assert "claude-notify-start-" in content

    def test_deletes_timer_file_after_read(self):
        content = _read_ps1("notify-on-complete")
        assert "Remove-Item" in content

    def test_checks_notify_enabled_env(self):
        """Must check SPELLBOOK_NOTIFY_ENABLED env var."""
        content = _read_ps1("notify-on-complete")
        assert "SPELLBOOK_NOTIFY_ENABLED" in content

    def test_checks_threshold(self):
        content = _read_ps1("notify-on-complete")
        assert "SPELLBOOK_NOTIFY_THRESHOLD" in content

    def test_default_threshold_30(self):
        content = _read_ps1("notify-on-complete")
        assert "30" in content

    def test_uses_notify_title(self):
        """Must use SPELLBOOK_NOTIFY_TITLE or default 'Spellbook'."""
        content = _read_ps1("notify-on-complete")
        assert "SPELLBOOK_NOTIFY_TITLE" in content
        assert "Spellbook" in content

    def test_uses_get_command_pwsh(self):
        """Must prefer pwsh over legacy powershell via Get-Command."""
        content = _read_ps1("notify-on-complete")
        assert "Get-Command pwsh" in content, (
            "notify-on-complete.ps1 must use Get-Command for pwsh detection (PATH-based)"
        )

    def test_sends_windows_toast(self):
        """Must send Windows toast notification."""
        content = _read_ps1("notify-on-complete")
        assert "BurntToast" in content or "ToastNotification" in content, (
            "notify-on-complete.ps1 must send Windows toast notifications"
        )

    def test_body_includes_elapsed_time(self):
        """Notification body must include elapsed time."""
        content = _read_ps1("notify-on-complete")
        assert "elapsed" in content.lower() or "${elapsed}" in content


# #############################################################################
# SECTION 5: Compaction hooks (pre-compact-save, post-compact-recover)
# #############################################################################


class TestCompactionHookStructure:
    """Compaction hooks must be fail-open."""

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_no_block_tool_function(self, hook_name):
        content = _read_ps1(hook_name)
        assert "function Block-Tool" not in content

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_failure_policy_comment(self, hook_name):
        content = _read_ps1(hook_name)
        assert "FAIL-OPEN" in content

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_uses_mcp_http_endpoint(self, hook_name):
        """Compaction hooks communicate with MCP via HTTP."""
        content = _read_ps1(hook_name)
        assert "SPELLBOOK_MCP_HOST" in content
        assert "SPELLBOOK_MCP_PORT" in content

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_has_invoke_mcp_tool_function(self, hook_name):
        """Compaction hooks must define Invoke-McpTool helper."""
        content = _read_ps1(hook_name)
        assert "function Invoke-McpTool" in content or "Invoke-McpTool" in content

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_parses_sse_response(self, hook_name):
        """Compaction hooks must parse SSE data: lines from MCP response."""
        content = _read_ps1(hook_name)
        assert "data: " in content, (
            f"{hook_name}.ps1 must parse SSE data: lines"
        )

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_has_write_log_function(self, hook_name):
        """Compaction hooks must define Write-Log helper."""
        content = _read_ps1(hook_name)
        assert "function Write-Log" in content

    @pytest.mark.parametrize("hook_name", COMPACTION_HOOKS)
    def test_logs_to_spellbook_logs_dir(self, hook_name):
        """Compaction hooks must log to ~/.local/spellbook/logs/."""
        content = _read_ps1(hook_name)
        assert ".local" in content and "spellbook" in content and "logs" in content


class TestPreCompactSavePs1:
    """Specific tests for pre-compact-save.ps1."""

    def test_reads_cwd_from_stdin(self):
        content = _read_ps1("pre-compact-save")
        assert "$data.cwd" in content or "cwd" in content

    def test_calls_workflow_state_load(self):
        content = _read_ps1("pre-compact-save")
        assert "workflow_state_load" in content

    def test_calls_workflow_state_save(self):
        content = _read_ps1("pre-compact-save")
        assert "workflow_state_save" in content

    def test_checks_freshness(self):
        """Must check if state is fresh (< 5 min = 0.083 hours)."""
        content = _read_ps1("pre-compact-save")
        assert "0.083" in content, (
            "pre-compact-save.ps1 must check freshness threshold of 0.083 hours"
        )

    def test_sets_compaction_flag(self):
        """Must set compaction_flag in saved state."""
        content = _read_ps1("pre-compact-save")
        assert "compaction_flag" in content

    def test_uses_trigger_auto(self):
        """Must save with trigger=auto."""
        content = _read_ps1("pre-compact-save")
        assert "auto" in content

    def test_logs_to_pre_compact_log(self):
        content = _read_ps1("pre-compact-save")
        assert "pre-compact.log" in content

    def test_catch_exits_0(self):
        """Must exit 0 even on errors."""
        content = _read_ps1("pre-compact-save")
        # Outermost catch must exit 0
        catch_pattern = re.search(r'\}\s*catch\s*\{[^}]*exit 0[^}]*\}', content)
        assert catch_pattern is not None

    def test_uses_jsonrpc(self):
        """Must use JSON-RPC format for MCP calls."""
        content = _read_ps1("pre-compact-save")
        assert "jsonrpc" in content
        assert "tools/call" in content

    def test_handles_pscustomobject_to_hashtable(self):
        """Must convert PSCustomObject to hashtable for state merging."""
        content = _read_ps1("pre-compact-save")
        assert "PSCustomObject" in content or "PSObject.Properties" in content


class TestPostCompactRecoverPs1:
    """Specific tests for post-compact-recover.ps1."""

    def test_checks_source_is_compact(self):
        """Must verify source == 'compact' before acting."""
        content = _read_ps1("post-compact-recover")
        assert '"compact"' in content

    def test_has_output_fallback_function(self):
        """Must define Output-Fallback for error cases."""
        content = _read_ps1("post-compact-recover")
        assert "function Output-Fallback" in content or "Output-Fallback" in content

    def test_fallback_mentions_session_init(self):
        """Fallback must mention spellbook_session_init."""
        content = _read_ps1("post-compact-recover")
        assert "spellbook_session_init" in content

    def test_outputs_hook_specific_output_json(self):
        """Must output hookSpecificOutput JSON on stdout."""
        content = _read_ps1("post-compact-recover")
        assert "hookSpecificOutput" in content
        assert "hookEventName" in content
        assert "SessionStart" in content
        assert "additionalContext" in content

    def test_calls_workflow_state_load(self):
        content = _read_ps1("post-compact-recover")
        assert "workflow_state_load" in content

    def test_optionally_calls_skill_instructions_get(self):
        """Must call skill_instructions_get when active_skill is present."""
        content = _read_ps1("post-compact-recover")
        assert "skill_instructions_get" in content

    def test_extracts_state_fields(self):
        """Must extract active_skill, skill_phase, binding_decisions, etc."""
        content = _read_ps1("post-compact-recover")
        for field in ["active_skill", "skill_phase", "binding_decisions", "next_action"]:
            assert field in content, (
                f"post-compact-recover.ps1 missing extraction of '{field}'"
            )

    def test_logs_to_post_compact_log(self):
        content = _read_ps1("post-compact-recover")
        assert "post-compact" in content

    def test_catch_calls_output_fallback(self):
        """On error, must output fallback directive rather than silently failing."""
        content = _read_ps1("post-compact-recover")
        # The catch block should call Output-Fallback
        assert "Output-Fallback" in content

    def test_reads_cwd_from_stdin(self):
        content = _read_ps1("post-compact-recover")
        assert "cwd" in content


# #############################################################################
# SECTION 6: Cross-hook consistency checks
# #############################################################################


class TestCrossHookConsistency:
    """Verify consistency between .sh and .ps1 hooks."""

    @pytest.mark.parametrize("hook_name", SECURITY_HOOKS)
    def test_security_hook_error_messages_match_sh(self, hook_name):
        """PS1 security hooks must use the same error message strings as .sh."""
        ps1_content = _read_ps1(hook_name)
        sh_path = HOOKS_DIR / f"{hook_name}.sh"
        sh_content = sh_path.read_text(encoding="utf-8")

        # Both should have "Security check unavailable" as default block reason
        assert "Security check unavailable" in ps1_content, (
            f"{hook_name}.ps1 missing default block reason"
        )

    @pytest.mark.parametrize("hook_name", ["spawn-guard", "state-sanitize"])
    def test_normalizing_hooks_match_sh_tool_names(self, hook_name):
        """PS1 normalizing hooks must use same tool_name as .sh."""
        ps1_content = _read_ps1(hook_name)
        sh_path = HOOKS_DIR / f"{hook_name}.sh"
        sh_content = sh_path.read_text(encoding="utf-8")

        expected_names = {
            "spawn-guard": "spawn_claude_session",
            "state-sanitize": "workflow_state_save",
        }
        tool_name = expected_names[hook_name]
        assert tool_name in ps1_content
        assert tool_name in sh_content

    @pytest.mark.parametrize("hook_name", ALL_PS1_HOOKS)
    def test_ps1_and_sh_have_same_failure_policy(self, hook_name):
        """PS1 and SH variants must agree on failure policy."""
        ps1_content = _read_ps1(hook_name)
        sh_path = HOOKS_DIR / f"{hook_name}.sh"
        sh_content = sh_path.read_text(encoding="utf-8")

        ps1_is_fail_closed = "FAIL-CLOSED" in ps1_content
        sh_is_fail_closed = "fail-closed" in sh_content.lower() or "FAIL-CLOSED" in sh_content

        ps1_is_fail_open = "FAIL-OPEN" in ps1_content
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
                            assert ".ps1" in result, (
                                f"String hook not converted to .ps1: {result}"
                            )
                        else:
                            assert ".ps1" in result["command"], (
                                f"Dict hook not converted to .ps1: {result['command']}"
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

        assert len(all_paths) > 0, "No hooks were installed"
        for path in all_paths:
            assert ".ps1" in path, f"Expected .ps1 in path, got: {path}"
            assert ".sh" not in path, f"Unexpected .sh in path: {path}"
