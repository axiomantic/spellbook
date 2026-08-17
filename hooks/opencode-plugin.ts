// OpenCode plugin for Spellbook security
//
// Registers tool.execute.before and tool.execute.after hooks that shell out
// to the spellbook security check module for input validation and output
// audit logging.
//
// Note: subagent tool calls do NOT trigger plugin hooks (OpenCode issue #5894)

import { execSync } from 'child_process';

export function getCheckCommand(): string {
  return 'python3 -m spellbook.gates.check';
}

// Matches ONLY the gate package itself failing to import. Python names the
// deepest package it could resolve, so an uninstalled gate reports either
// `spellbook` or `spellbook.gates` depending on what is on the path. A
// ModuleNotFoundError naming any other module means the gate is installed and
// something it imports is broken -- a gate error, which must block.
const GATE_MISSING = /No module named ['"]spellbook(\.gates)?['"]/;

function isGateAbsent(err: { stderr?: string | Buffer | null }): boolean {
  return GATE_MISSING.test(String(err.stderr ?? ''));
}

export function runSecurityCheck(
  payload: string,
  extraArgs: string[] = [],
  cmd: string = getCheckCommand(),
): { safe: boolean; error?: string } {
  try {
    const args = extraArgs.length > 0 ? ' ' + extraArgs.join(' ') : '';
    execSync(`${cmd}${args}`, {
      input: payload,
      encoding: 'utf-8',
      timeout: 5000,
      env: { ...process.env },
      stdio: ['pipe', 'pipe', 'pipe'],
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
    if (isGateAbsent(err)) {
      // No gate is installed, so there is no policy to enforce and nothing to
      // fail closed on behalf of. Failing closed here blocks every Bash call
      // for a check that does not exist. Note this is strictly the interpreter
      // failing to find the gate package itself -- a gate that loads and then
      // errors is handled below, and blocks.
      return { safe: true };
    }
    // The gate ran and did not finish. A check that cannot complete is not a
    // check that passed: fail closed.
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
