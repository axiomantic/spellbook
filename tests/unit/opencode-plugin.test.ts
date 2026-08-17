import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

import { runSecurityCheck, getCheckCommand } from '../../hooks/opencode-plugin.ts';

// The plugin shells out to a gate module. Two failure shapes reach the same
// catch block and must NOT be treated the same way:
//
//   - the gate RAN and errored  -> block. A security check that cannot finish
//     is not a security check that passed.
//   - the gate IS NOT INSTALLED -> allow. Blocking here bricks every Bash call
//     on OpenCode for a policy that does not exist to have an opinion.
//
// Python reports the second as ModuleNotFoundError naming the gate package
// itself. A ModuleNotFoundError naming anything ELSE means the gate is present
// and its dependencies are broken -- that is the first case, and it blocks.

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

describe('runSecurityCheck', () => {
  it('allows when the gate module is not installed', () => {
    // The real, default command. This repo ships no spellbook.gates package,
    // so this is the exact condition every OpenCode user hits today.
    const result = runSecurityCheck(PAYLOAD, [], getCheckCommand());

    expect(result.safe).toBe(true);
  });

  it('blocks when the gate ran and crashed', () => {
    const cmd = script('import sys\nraise RuntimeError("gate exploded")\n');

    expect(runSecurityCheck(PAYLOAD, [], cmd).safe).toBe(false);
  });

  it('blocks when the gate is present but its dependency is missing', () => {
    // Not the same as an absent gate: a policy exists, it just cannot load.
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
