// OpenCode plugin for Spellbook security
//
// Registers tool.execute.before and tool.execute.after hooks that shell out
// to a security check command for input validation and output audit logging.
//
// Spellbook itself ships no gate. The command is supplied by the operator
// through SPELLBOOK_GATE_CMD; with it unset there is no gate to consult and
// the hooks are a pass-through. Naming a built-in default here would name a
// module that does not exist and spawn an interpreter per tool call to
// rediscover that on every call.
//
// Note: subagent tool calls do NOT trigger plugin hooks (OpenCode issue #5894)

import { execSync } from 'child_process';

export function getCheckCommand(): string | null {
  return process.env.SPELLBOOK_GATE_CMD || null;
}

export function runSecurityCheck(
  payload: string,
  extraArgs: string[] = [],
  cmd: string | null = getCheckCommand(),
): { safe: boolean; error?: string } {
  if (!cmd) {
    // No gate is configured, so there is no policy to enforce and nothing to
    // fail closed on behalf of.
    return { safe: true };
  }
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
    // A gate was configured and did not finish -- missing, crashed, or timed
    // out. A check that cannot complete is not a check that passed: fail
    // closed. The no-gate case never reaches here; it returns above without
    // spawning anything.
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
