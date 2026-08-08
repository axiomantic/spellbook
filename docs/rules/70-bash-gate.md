# Bash Gate Navigation

!!! warning "Mandatory module"
    This module installs on every platform and cannot be declined.

How to read a spellbook bash-gate denial, which layer produced it, and what the correct response is for each block class.

**Related artifacts:**

- `skills/dispatching-parallel-agents`

## Rule Content

``````````markdown
<CRITICAL>
### Navigating the Spellbook Bash Gate

Spellbook's bash gate runs a layered pipeline (L4 bashlex AST → L3 tier classifier → L2 regex → exfil rules). Block messages land on **stderr** (per the Claude Code hook protocol). When a Bash call exits 2, read the stderr JSON to learn which layer denied and why.

**Common block messages and the right response:**

| Stderr message contains | Layer | Right response |
|---|---|---|
| `Tier classifier marked Bash call as T2 (ask)` | L3 | Operator confirmation required. Surface the exact command back to the orchestrator (or the operator) — do NOT retry. From a subagent, the harness permission UI cannot reach the operator; only the main context can prompt. |
| `Tier classifier denied Bash call (tier=T3)` | L3 | Forbidden by policy. Restructure to avoid the denied capability. |
| `bashlex failed to parse command` | L4 | Almost always a complex heredoc / quote / process-substitution issue. Write the payload to a temp file and pass via `--body-file`, `--data @file`, `--input-file`, etc. |
| `High entropy content detected` | L4 | Triggered by long base64-/JWT-/random-looking blobs in the command line. Move the blob to a file and reference it. Do NOT try to obfuscate or further encode. |
| `BASH-PARSER-COMPOUND` | L4 | Compound deny is opt-in (`SPELLBOOK_BASH_DENY_COMPOUND=1` or `security_mode="paranoid"`). If you hit this, the operator has opted in. Split into separate Bash invocations. |
| `Compound command (...) is not allowed` | L4 | Compound deny is opt-in and the operator has opted in. Split into separate Bash invocations. |
| `EXF-...` / `BASH-...` (regex layer) | L2 | Substring match on a dangerous pattern. Restructure to avoid the literal substring (e.g., write a script to disk and run it; use `gh api` instead of `curl https://api.github.com/...`). |

**Interactive incompatibility.** Never use `-i` / interactive flags (`git rebase -i`, `git add -i`, and the like). The CLI environment cannot drive an interactive prompt, so the command either hangs or produces a misleading result. Use the non-interactive form instead.

**Subagent escape hatch:** when dispatched, you cannot trigger the harness's interactive permission prompt — that only happens in the main context. If your Bash call blocks at T2, stop the current work, report the exact command and the verbatim stderr message back to the orchestrator, and let the orchestrator either re-run from main context (where the operator can approve) or surface to the operator directly. Looping the same command will not unblock it.

**What NOT to do when blocked:**

- Do NOT retry the same command verbatim — gates are deterministic.
- Do NOT base64/hex-encode the payload to "smuggle" it past the parser — the entropy detector exists for exactly this.
- Do NOT use `--no-verify`, hook-bypass flags, or environment overrides like `SPELLBOOK_BASH_PARSER_ALLOW=*` to silence the gate.
- Do NOT silently fall back to a no-op or fake success. Surface the block.

**Worked example (heredoc → file workaround):**

A subagent tried to post a PR comment with embedded technical content via:
`gh pr comment 288 --body "$(cat <<'EOF' ... EOF)"`. The L4 bashlex layer returned `bashlex failed to parse command` plus `High entropy content detected`. The fix: `Write` the body to `/tmp/comment.md` and use `gh pr comment 288 --body-file /tmp/comment.md`. One retry, succeeded. The same pattern applies to `git commit -F /tmp/msg.txt`, `gh issue create --body-file ...`, `curl --data @file.json`, and any other tool that accepts file-based input as an alternative to inline strings.
</CRITICAL>
``````````
