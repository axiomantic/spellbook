// OpenCode plugin for Spellbook security
//
// Registers tool.execute.before and tool.execute.after hooks that shell out
// to the spellbook security check module for input validation and output
// audit logging.
//
// Note: subagent tool calls do NOT trigger plugin hooks (OpenCode issue #5894)

import { execSync } from 'child_process';

function getCheckCommand(): string {
  const spellbookDir = process.env.SPELLBOOK_DIR;
  if (!spellbookDir) {
    throw new Error('SPELLBOOK_DIR environment variable is not set');
  }
  return 'python3 -m spellbook_mcp.security.check';
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
    // Non-security errors (timeout, missing module, etc.) are logged but not blocking
    console.error('[spellbook-security] Check error:', err.message || err);
    return { safe: true };
  }
}

export default {
  name: 'spellbook-security',
  setup(app: any) {
    app.hook('tool.execute.before', async (ctx: any) => {
      const toolName = ctx.tool_name || ctx.toolName || '';
      const toolInput = ctx.tool_input || ctx.toolInput || {};

      // Only check Bash and spawn_claude_session tools
      if (toolName !== 'Bash' && toolName !== 'spawn_claude_session') {
        return;
      }

      const payload = JSON.stringify({
        tool_name: toolName,
        tool_input: toolInput,
      });

      const result = runSecurityCheck(payload);

      if (!result.safe) {
        throw new Error(result.error || 'Blocked by spellbook security check');
      }
    });

    app.hook('tool.execute.after', async (ctx: any) => {
      const toolName = ctx.tool_name || ctx.toolName || '';
      const toolOutput = ctx.tool_output || ctx.toolOutput || ctx.output || '';

      const payload = JSON.stringify({
        tool_name: toolName,
        tool_input: {},
        tool_output: typeof toolOutput === 'string' ? toolOutput : JSON.stringify(toolOutput),
      });

      // Audit logging via --check-output; errors are non-blocking
      runSecurityCheck(payload, ['--check-output']);
    });
  },
};
