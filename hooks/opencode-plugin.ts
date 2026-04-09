// OpenCode plugin for Spellbook security
//
// Registers tool.execute.before and tool.execute.after hooks that shell out
// to the spellbook security check module for input validation and output
// audit logging.
//
// Note: subagent tool calls do NOT trigger plugin hooks (OpenCode issue #5894)

import { execSync } from 'child_process';

function getCheckCommand(): string {
  return 'python3 -m spellbook.gates.check';
}

function runSecurityCheck(payload: string, extraArgs: string[] = []): { safe: boolean; error?: string } {
  try {
    const cmd = getCheckCommand();
    const args = extraArgs.length > 0 ? ' ' + extraArgs.join(' ') : '';
    execSync(`${cmd}${args}`, {
      input: payload,
      encoding: 'utf-8',
      timeout: 5000,
      env: { ...process.env },
    });
    return { safe: true };
  } catch (err: any) {
    if (err.status === 2) {
      // Security check blocked the tool
      try {
        const result = JSON.parse(err.stdout || '{}');
        return { safe: false, error: result.error || 'Security check failed' };
      } catch {
        return { safe: false, error: 'Security check failed' };
      }
    }
    // Non-security errors (timeout, missing module, etc.) fail closed
    console.error('[spellbook-security] Check error:', err.message || err);
    return { safe: false };
  }
}

export default function spellbookSecurityPlugin(context: {
  project: { name: string; path: string };
  directory: string;
  worktree: string;
}): Record<string, (...args: any[]) => Promise<void>> {
  return {
    'tool.execute.before': async (toolName: string, input: any) => {
      if (toolName !== 'Bash' && toolName !== 'spawn_claude_session') {
        return;
      }

      const payload = JSON.stringify({
        tool_name: toolName,
        tool_input: input,
      });

      const result = runSecurityCheck(payload);

      if (!result.safe) {
        throw new Error(result.error || 'Blocked by spellbook security check');
      }
    },

    'tool.execute.after': async (toolName: string, _input: any, output: any) => {
      const payload = JSON.stringify({
        tool_name: toolName,
        tool_input: {},
        tool_output: typeof output === 'string' ? output : JSON.stringify(output),
      });

      runSecurityCheck(payload, ['--check-output']);
    },
  };
}
