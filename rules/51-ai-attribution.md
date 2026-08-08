---
id: ai-attribution
name: AI Attribution Suppression
class: preference
default: "on"
description: >
  Suppresses AI attribution in commits, pull requests, issues, and comments.
benefit: >
  Strips Co-Authored-By trailers and "Generated with" footers from commits and pull requests.
declining_means: >
  The harness default stands, so commits and pull requests may carry AI attribution
  trailers, footers, or bot signatures.
related:
  - agents/git-committer
  - skills/creating-issues-and-pull-requests
renamed_from: []
superseded_by: null
paths: []
---

<CRITICAL>
### AI Attribution

- NEVER add AI attribution of any kind: no `Co-Authored-By` trailers, no "Generated with Claude Code" footers, no bot signatures in commit messages, PR titles, PR descriptions, issues, or comments
</CRITICAL>

<FORBIDDEN>
- Putting co-authorship footers or "generated with Claude" in commits
</FORBIDDEN>
