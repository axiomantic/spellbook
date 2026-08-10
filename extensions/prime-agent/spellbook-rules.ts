/**
 * Spellbook Rules Extension for Prime Agent
 *
 * Auto-injects every selected spellbook rule module into the system prompt
 * at session start. Prime Agent has no native rules-directory walker
 * (it only auto-loads a single `AGENTS.md` / `CLAUDE.md`), and the
 * documented `SYSTEM.md` / `APPEND_SYSTEM.md` mechanism is not yet
 * implemented in `packages/coding-agent/src/core/system-prompt.ts` on
 * `main` -- so this extension is the working delivery path.
 *
 * Behavior:
 *
 * - On `session_start`: scan `~/.prime/agent/rules/*.md` (or wherever
 *   `$PRIME_AGENT_CONFIG_DIR` points), parse the YAML frontmatter, sort
 *   by `(prefix, id)` to match the canonical delivery order from
 *   `installer.components.rule_modules.load_rule_modules`, and pre-load
 *   the bodies in memory.
 *
 * - On `before_agent_start`: append a `# Spellbook Rules` section to
 *   the system prompt containing every loaded rule body. A small
 *   header per rule (`<id> -- <name>`) keeps the agent oriented if
 *   individual rules are referenced later.
 *
 * - Cap: refuse to inline if the total byte size of selected rules
 *   exceeds `INLINE_CAP_BYTES` (default 80 KiB). When capped, fall back
 *   to listing the rule paths so the agent can fetch them on demand
 *   with `ipython`. The cap is a safety belt, not a normal case; the
 *   shipped ruleset totals ~60 KiB today and stays comfortably under it.
 *
 * - User file safety: this extension never touches `AGENTS.md` or any
 *   other user file. It only reads the rules directory the spellbook
 *   installer populated and writes to the in-memory system prompt.
 *
 * Discovery: drop this file at `~/.prime/agent/extensions/spellbook-rules.ts`
 * and Prime Agent will auto-discover and load it on next session start.
 * The spellbook installer manages that path; you should not need to copy
 * this file by hand.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const INLINE_CAP_BYTES = 80 * 1024;

interface RuleFile {
	/** Stable id from YAML frontmatter (e.g. "core", "develop-discipline"). */
	id: string;
	/** Human-readable name from YAML frontmatter. */
	name: string;
	/** Two-digit numeric prefix from the on-disk filename ("00", "10", ...). */
	prefix: string;
	/** Filename relative to the rules directory, kept for diagnostics. */
	relPath: string;
	/** Post-frontmatter body bytes. */
	sizeBytes: number;
	/** Post-frontmatter body text. */
	body: string;
}

let loadedRules: RuleFile[] = [];
let loadError: string | null = null;
let rulesDir: string = "";

function parseFrontmatter(text: string): { meta: Record<string, string>; body: string } {
	const lines = text.split("\n");
	if (lines[0]?.trim() !== "---") {
		return { meta: {}, body: text };
	}
	const close = lines.slice(1).findIndex((l) => l.trim() === "---");
	if (close < 0) {
		return { meta: {}, body: text };
	}
	const metaLines = lines.slice(1, close + 1);
	const body = lines.slice(close + 2).join("\n").trim();

	const meta: Record<string, string> = {};
	for (const raw of metaLines) {
		const m = raw.match(/^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)$/);
		if (!m) continue;
		let value = m[2].trim();
		// Strip one layer of matching quotes.
		if (
			value.length >= 2 &&
			((value.startsWith('"') && value.endsWith('"')) ||
				(value.startsWith("'") && value.endsWith("'")))
		) {
			value = value.slice(1, -1);
		}
		meta[m[1]] = value;
	}
	return { meta, body };
}

// Exported for tests. A broken symlink in the rules directory must degrade to
// one unreadable rule, never to an empty ruleset, and that is only assertable
// from outside.
export function loadRules(dir: string): { rules: RuleFile[]; error: string | null } {
	if (!fs.existsSync(dir)) {
		return { rules: [], error: null };
	}

	let entries: string[];
	try {
		entries = fs.readdirSync(dir).filter((n) => n.endsWith(".md"));
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		return { rules: [], error: `cannot read ${dir}: ${msg}` };
	}

	const rules: RuleFile[] = [];
	for (const name of entries) {
		const fullPath = path.join(dir, name);
		// Skip anything spellbook did not symlink in. The installer's
		// install_module_symlinks uses the XX-spellbook-<id>.md pattern;
		// a user's own rule file would not match that.
		if (!/^\d{2}-spellbook-[a-z][a-z0-9-]*\.md$/.test(name)) {
			continue;
		}

		let text: string;
		try {
			text = fs.readFileSync(fullPath, "utf8");
		} catch (err) {
			// Skip THIS rule; never abort the whole load. These are symlinks
			// into a spellbook checkout, so one going stale (the checkout
			// moved, a module was deselected mid-flight) is an ordinary
			// occurrence. Returning early here dropped every rule -- including
			// every rule already parsed -- and the agent started with no
			// behavioural context at all, silently.
			//
			// A marker rule is pushed rather than skipping quietly: a missing
			// rule that says nothing is indistinguishable from a rule that
			// was never installed, and the agent cannot report what it never
			// saw.
			const msg = err instanceof Error ? err.message : String(err);
			const markerId = name.replace(/^\d{2}-spellbook-/, "").replace(/\.md$/, "");
			rules.push({
				id: markerId,
				name: `${markerId} (unreadable)`,
				prefix: name.slice(0, 2),
				relPath: name,
				sizeBytes: 0,
				body:
					`[spellbook-rules] Could not read this rule file: ${msg}\n` +
					"Its guidance is NOT loaded. Run `spellbook install` to repair " +
					"the symlink, and do not assume this rule's constraints are absent " +
					"-- they are merely unreadable.",
			});
			continue;
		}

		const { meta, body } = parseFrontmatter(text);
		const prefix = name.slice(0, 2);
		const id = meta.id ?? name.replace(/^\d{2}-spellbook-/, "").replace(/\.md$/, "");
		const ruleName = meta.name ?? id;

		rules.push({
			id,
			name: ruleName,
			prefix,
			relPath: name,
			sizeBytes: Buffer.byteLength(body, "utf8"),
			body,
		});
	}

	rules.sort((a, b) => {
		if (a.prefix !== b.prefix) return a.prefix < b.prefix ? -1 : 1;
		return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
	});

	return { rules, error: null };
}

function resolveRulesDir(): string {
	const envDir = process.env.PRIME_AGENT_CONFIG_DIR;
	const home = process.env.HOME ?? process.env.USERPROFILE ?? "~";
	const base =
		envDir && envDir.trim().length > 0 ? envDir : path.join(home, ".prime", "agent");
	return path.join(base, "rules");
}

function buildInlinedPrompt(
	rules: RuleFile[],
	cap: number,
): { content: string; truncated: boolean } {
	const sections: string[] = [];
	let totalBytes = 0;
	let truncated = false;

	for (const rule of rules) {
		const header = `## ${rule.id} -- ${rule.name}\n\n`;
		const sectionBytes =
			Buffer.byteLength(header, "utf8") + rule.sizeBytes + 2;
		if (totalBytes + sectionBytes > cap) {
			truncated = true;
			break;
		}
		sections.push(header + rule.body);
		totalBytes += sectionBytes;
	}

	if (truncated) {
		// Capped: surface a short listing instead of the full bodies, and
		// instruct the agent to fetch specific files with ipython.
		const items = rules
			.map((r) => `- \`${r.relPath}\` (${r.id}: ${r.name})`)
			.join("\n");
		const content =
			`# Spellbook Rules (listing only -- total size exceeds the ${cap}-byte inline cap)\n\n` +
			`The following spellbook rule modules are available at \`${rulesDir}\`:\n\n` +
			`${items}\n\n` +
			`Use ipython to read the body of any rule you need to apply. ` +
			`Reading one rule does not require reading the others.\n`;
		return { content, truncated: true };
	}

	return {
		content:
			`# Spellbook Rules\n\n` +
			`Auto-injected by the spellbook-rules extension. ` +
			`Each section is one rule module from \`${rulesDir}\`.\n\n` +
			sections.join("\n\n") +
			"\n",
		truncated: false,
	};
}

export default function spellbookRulesExtension(pi: ExtensionAPI) {
	pi.on("session_start", async (_event, _ctx) => {
		rulesDir = resolveRulesDir();
		const { rules, error } = loadRules(rulesDir);
		loadedRules = rules;
		loadError = error;
	});

	pi.on("before_agent_start", async (event) => {
		if (loadError) {
			return {
				systemPrompt:
					event.systemPrompt +
					`\n\n# Spellbook Rules (load error)\n\n` +
					`Failed to read ${rulesDir}: ${loadError}. ` +
					`Run \`/reload\` after fixing the directory, or check ` +
					`that the spellbook installer completed successfully.\n`,
			};
		}
		if (loadedRules.length === 0) {
			return undefined;
		}
		const { content, truncated } = buildInlinedPrompt(loadedRules, INLINE_CAP_BYTES);
		return {
			systemPrompt: event.systemPrompt + "\n\n" + content,
		};
	});
}
