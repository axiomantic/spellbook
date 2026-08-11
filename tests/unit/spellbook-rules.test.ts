import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';


import { loadRules, resolveRulesDir } from '../../extensions/prime-agent/spellbook-rules.ts';

// These cover the resilience contract of the Prime Agent rules loader: the
// rules directory is full of SYMLINKS into a spellbook checkout, so one of
// them going stale (the checkout moved, a module was deselected mid-flight)
// is an ordinary occurrence rather than an exceptional one. It must cost the
// agent that one rule, never the whole ruleset.

let dir: string;

function writeRule(name: string, id: string, body: string): void {
  fs.writeFileSync(
    path.join(dir, name),
    `---\nid: ${id}\nname: ${id} rules\n---\n\n${body}\n`,
    'utf8',
  );
}

function breakSymlink(name: string): void {
  fs.symlinkSync(path.join(dir, 'does-not-exist.md'), path.join(dir, name));
}

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'spellbook-rules-'));
});

afterEach(() => {
  fs.rmSync(dir, { recursive: true, force: true });
});

describe('loadRules', () => {
  it('loads every well-formed rule', () => {
    writeRule('00-spellbook-core.md', 'core', 'core body');
    writeRule('20-spellbook-orchestration.md', 'orchestration', 'orch body');

    const { rules, error } = loadRules(dir);

    expect(error).toBeNull();
    expect(rules.map((r) => r.id).sort()).toEqual(['core', 'orchestration']);
  });

  it('returns empty without error when the directory does not exist', () => {
    const { rules, error } = loadRules(path.join(dir, 'nope'));

    expect(rules).toEqual([]);
    expect(error).toBeNull();
  });

  it('ignores files spellbook did not install', () => {
    writeRule('00-spellbook-core.md', 'core', 'core body');
    fs.writeFileSync(path.join(dir, 'my-own-notes.md'), 'personal', 'utf8');

    const { rules } = loadRules(dir);

    expect(rules.map((r) => r.id)).toEqual(['core']);
  });

  // --- the BOT-B1 regression ------------------------------------------

  it('keeps every readable rule when one symlink is broken', () => {
    writeRule('00-spellbook-core.md', 'core', 'core body');
    breakSymlink('10-spellbook-broken.md');
    writeRule('20-spellbook-orchestration.md', 'orchestration', 'orch body');

    const { rules } = loadRules(dir);

    // Previously this returned [] -- one stale symlink silently stripped
    // ALL behavioural context from the system prompt at session start.
    const ids = rules.map((r) => r.id);
    expect(ids).toContain('core');
    expect(ids).toContain('orchestration');
  });

  it('does not abort rules parsed before the broken one', () => {
    writeRule('00-spellbook-core.md', 'core', 'core body');
    breakSymlink('99-spellbook-zzz.md');

    expect(loadRules(dir).rules.map((r) => r.id)).toContain('core');
  });

  it('surfaces the unreadable rule as a marker rather than dropping it', () => {
    breakSymlink('10-spellbook-broken.md');

    const { rules } = loadRules(dir);
    const marker = rules.find((r) => r.id === 'broken');

    // Skipping quietly would be indistinguishable from the rule never having
    // been installed, and the agent cannot report what it never saw.
    expect(marker).toBeDefined();
    expect(marker!.name).toContain('unreadable');
    expect(marker!.body).toContain('spellbook install');
    expect(marker!.sizeBytes).toBe(0);
  });

  it('warns the agent not to treat an unreadable rule as absent', () => {
    breakSymlink('10-spellbook-broken.md');

    const marker = loadRules(dir).rules.find((r) => r.id === 'broken');

    expect(marker!.body).toContain('NOT loaded');
  });

  it('does not report a directory-level error for a per-file failure', () => {
    writeRule('00-spellbook-core.md', 'core', 'core body');
    breakSymlink('10-spellbook-broken.md');

    // The error channel means "the whole load failed". A single bad file
    // must not claim that, or callers cannot tell the two apart.
    expect(loadRules(dir).error).toBeNull();
  });

  it('survives every rule being broken', () => {
    breakSymlink('00-spellbook-a.md');
    breakSymlink('10-spellbook-b.md');

    const { rules, error } = loadRules(dir);

    expect(error).toBeNull();
    expect(rules).toHaveLength(2);
    expect(rules.every((r) => r.body.includes('Could not read'))).toBe(true);
  });
});

describe('resolveRulesDir', () => {
  const saved = { ...process.env };

  afterEach(() => {
    process.env = { ...saved };
  });

  it('prefers PRIME_AGENT_CONFIG_DIR when set', () => {
    process.env.PRIME_AGENT_CONFIG_DIR = '/tmp/custom';
    expect(resolveRulesDir()).toBe(path.join('/tmp/custom', 'rules'));
  });

  it('ignores a blank PRIME_AGENT_CONFIG_DIR', () => {
    process.env.PRIME_AGENT_CONFIG_DIR = '   ';
    process.env.HOME = '/tmp/home';
    expect(resolveRulesDir()).toBe(
      path.join('/tmp/home', '.prime', 'agent', 'rules'),
    );
  });

  it('falls back to HOME', () => {
    delete process.env.PRIME_AGENT_CONFIG_DIR;
    process.env.HOME = '/tmp/home';
    expect(resolveRulesDir()).toBe(
      path.join('/tmp/home', '.prime', 'agent', 'rules'),
    );
  });

  // The BOT-F1 regression.
  it('returns an absolute path even with no home env vars', () => {
    delete process.env.PRIME_AGENT_CONFIG_DIR;
    delete process.env.HOME;
    delete process.env.USERPROFILE;

    const resolved = resolveRulesDir();

    // Previously this was `~/.prime/agent/rules` -- RELATIVE, because nothing
    // in Node expands a tilde. It would resolve against cwd and scan the
    // wrong place entirely.
    expect(path.isAbsolute(resolved)).toBe(true);
    expect(resolved.startsWith('~')).toBe(false);
    expect(resolved).not.toContain(`${path.sep}~${path.sep}`);
  });

  it('uses the real home directory as the last resort', () => {
    delete process.env.PRIME_AGENT_CONFIG_DIR;
    delete process.env.HOME;
    delete process.env.USERPROFILE;

    expect(resolveRulesDir()).toBe(
      path.join(os.homedir(), '.prime', 'agent', 'rules'),
    );
  });
});
