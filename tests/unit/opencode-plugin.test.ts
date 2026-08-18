import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

import { runSecurityCheck, getCheckCommand } from '../../hooks/opencode-plugin.ts';

// Spellbook ships no gate. The check command comes from SPELLBOOK_GATE_CMD:
//
//   - unset     -> allow, without spawning a process. There is no policy to
//     enforce and nothing to fail closed on behalf of.
//   - set       -> the gate must produce a verdict. Missing, crashed, or timed
//     out all mean no verdict, and no verdict blocks.

let dir: string;

function script(body: string): string {
  const p = path.join(dir, `gate-${Math.random().toString(36).slice(2)}.py`);
  fs.writeFileSync(p, body, 'utf8');
  return `python3 ${p}`;
}

const PAYLOAD = JSON.stringify({ tool_name: 'Bash', tool_input: { command: 'ls' } });

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'spellbook-gate-'));
});

afterEach(() => {
  fs.rmSync(dir, { recursive: true, force: true });
});

describe('getCheckCommand', () => {
  it('reports no gate when SPELLBOOK_GATE_CMD is unset', () => {
    delete process.env.SPELLBOOK_GATE_CMD;

    expect(getCheckCommand()).toBeNull();
  });

  it('returns the operator-supplied command', () => {
    process.env.SPELLBOOK_GATE_CMD = 'python3 -m my_gate';

    expect(getCheckCommand()).toBe('python3 -m my_gate');

    delete process.env.SPELLBOOK_GATE_CMD;
  });
});

describe('runSecurityCheck', () => {
  it('allows without spawning anything when no gate is configured', () => {
    delete process.env.SPELLBOOK_GATE_CMD;

    expect(runSecurityCheck(PAYLOAD).safe).toBe(true);
  });

  it('blocks when a configured gate is not installed', () => {
    const cmd = 'python3 -m spellbook_gate_that_is_not_installed_xyz';

    expect(runSecurityCheck(PAYLOAD, [], cmd).safe).toBe(false);
  });

  it('blocks when the gate ran and crashed', () => {
    const cmd = script('import sys\nraise RuntimeError("gate exploded")\n');

    expect(runSecurityCheck(PAYLOAD, [], cmd).safe).toBe(false);
  });

  it('blocks when the gate loads but its dependency is missing', () => {
    const cmd = script('import spellbook_gate_missing_dependency_xyz\n');

    expect(runSecurityCheck(PAYLOAD, [], cmd).safe).toBe(false);
  });

  it('blocks with the gate message on a deliberate deny (exit 2)', () => {
    const cmd = script(
      'import json, sys\n'
      + 'sys.stdout.write(json.dumps({"error": "BASH-001 denied"}))\n'
      + 'sys.exit(2)\n',
    );

    const result = runSecurityCheck(PAYLOAD, [], cmd);

    expect(result.safe).toBe(false);
    expect(result.error).toBe('BASH-001 denied');
  });

  it('allows when the gate ran and approved', () => {
    expect(runSecurityCheck(PAYLOAD, [], script('pass\n')).safe).toBe(true);
  });
});
