# AI Attribution Suppression

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.ai-attribution`.

Suppresses AI attribution in commits, pull requests, issues, and comments.

**Why keep it:** Strips Co-Authored-By trailers and "Generated with" footers from commits and pull requests.

**If you decline:** The harness default stands, so commits and pull requests may carry AI attribution trailers, footers, or bot signatures.

**Related artifacts:**

- `agents/git-committer`
- `skills/creating-issues-and-pull-requests`

## Rule Content

```markdown
<CRITICAL>
### AI Attribution

- NEVER add AI attribution of any kind: no `Co-Authored-By` trailers, no "Generated with Claude Code" footers, no bot signatures in commit messages, PR titles, PR descriptions, issues, or comments
</CRITICAL>

<FORBIDDEN>
- Putting co-authorship footers or "generated with Claude" in commits
</FORBIDDEN>
```
