# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public issue.** Instead, use [GitHub's private vulnerability reporting](https://github.com/axiomantic/spellbook/security/advisories/new) or email the maintainer directly.

Please include:

- Description of the vulnerability
- Steps to reproduce
- Impact assessment (if known)

We will acknowledge receipt within 48 hours and aim to provide an initial
assessment within 5 business days.

## Scope

Security issues for spellbook include but are not limited to:

- **Prompt injection** in skills, commands, or agent definitions
- **MCP tool vulnerabilities** that could leak data or escalate privileges
- **Credential exposure** through hooks, scripts, or configuration
- **Path traversal** in file-handling operations
- **Arbitrary code execution** through skill or hook injection

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | Yes       |
| < latest | Best effort |
