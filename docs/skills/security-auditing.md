# security-auditing

Audits skills, commands, hooks, and MCP tools for injection risks, privilege escalation, and prompt manipulation vulnerabilities. Combines static analysis scanning with human-guided triage across six ordered phases. A core spellbook capability for systematic security review of the spellbook ecosystem and project code.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when auditing skills, commands, hooks, and MCP tools for security vulnerabilities. Triggers: 'security audit', 'scan for vulnerabilities', 'check security', 'audit skills', 'audit MCP tools', 'is this safe', 'check for injection', 'OWASP'. NOT for: general code review (use code-review --audit).

## Workflow Diagram

Now I have the full skill. Let me generate the diagrams.

## Overview Diagram

```mermaid
graph TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/Input/Output/]
        L5["🔵 Subagent Dispatch"]
        L6["🔴 Quality Gate"]
        L7["🟢 Success Terminal"]
        style L5 fill:#4a9eff,color:#fff
        style L6 fill:#ff6b6b,color:#fff
        style L7 fill:#51cf66,color:#fff
    end

    START([Skill Invoked]) --> INPUT[/Inputs: scope, security_mode, diff_text/]
    INPUT --> P1["Phase 1: DISCOVER<br>Identify scope, catalog targets"]
    P1 --> P2["Phase 2: ANALYZE<br>Run scanner against all targets"]
    P2 --> SCAN_OK{Scanner<br>succeeded?}
    SCAN_OK -->|All targets scanned| P3["Phase 3: CLASSIFY<br>Deduplicate, assess severity,<br>identify false positives"]
    SCAN_OK -->|Partial failure| USER_APPROVE{User approves<br>partial results?}
    USER_APPROVE -->|Yes| P3
    USER_APPROVE -->|No| INCOMPLETE([Audit Incomplete])
    style INCOMPLETE fill:#ff6b6b,color:#fff
    P3 --> HC{Any HIGH/CRITICAL<br>findings?}
    HC -->|Yes| P4["Phase 4: TRACE<br>Attack chain analysis"]
    HC -->|No| P5
    P4 --> P5["Phase 5: REPORT<br>Generate structured audit report"]
    P5 --> P6["Phase 6: GATE<br>Enforce audit verdict"]
    P6 --> VERDICT{Verdict?}
    VERDICT -->|PASS| PASS([PASS: Clean audit])
    style PASS fill:#51cf66,color:#fff
    VERDICT -->|WARN| WARN_ACK{User<br>acknowledges?}
    WARN_ACK -->|Yes| WARN_PROCEED([WARN: Proceed with acknowledgment])
    style WARN_PROCEED fill:#51cf66,color:#fff
    WARN_ACK -->|No| REMEDIATE
    VERDICT -->|FAIL| REMEDIATE[Remediate findings]
    REMEDIATE --> RESCAN{Re-scan?}
    RESCAN -->|Yes| P2
    RESCAN -->|No| BLOCKED([FAIL: Blocked])
    style BLOCKED fill:#ff6b6b,color:#fff

    style P1 fill:#e8f4fd,stroke:#4a9eff
    style P2 fill:#e8f4fd,stroke:#4a9eff
    style P3 fill:#e8f4fd,stroke:#4a9eff
    style P4 fill:#e8f4fd,stroke:#4a9eff
    style P5 fill:#e8f4fd,stroke:#4a9eff
    style P6 fill:#ff6b6b,color:#fff
```

### Cross-Reference Table

| Overview Node | Detail Diagram |
|---------------|---------------|
| Phase 1: DISCOVER | Detail Diagram 1 |
| Phase 2: ANALYZE | Detail Diagram 2 |
| Phase 3: CLASSIFY | Detail Diagram 3 |
| Phase 4: TRACE | Detail Diagram 4 |
| Phase 5: REPORT | Detail Diagram 5 |
| Phase 6: GATE | Detail Diagram 6 |

---

## Detail Diagram 1: Phase 1 - DISCOVER

```mermaid
graph TD
    subgraph Legend
        L1["🔵 Subagent Dispatch"]
        L2{Decision}
        style L1 fill:#4a9eff,color:#fff
    end

    START([Phase 1 Start]) --> PARSE{Parse scope<br>argument}
    PARSE -->|"skills"| SK[Catalog all .md under skills/]
    PARSE -->|"mcp"| MCP[Catalog all .py under spellbook/]
    PARSE -->|"changeset"| CS[Get staged or branch diff]
    PARSE -->|"all"| ALL[Catalog skills/ + spellbook/]
    PARSE -->|"specific paths"| SP[Catalog specified files/dirs]

    SK --> BROAD{Broad scope?<br>20+ files?}
    MCP --> BROAD
    CS --> BROAD
    ALL --> BROAD
    SP --> BROAD

    BROAD -->|Yes| SUBAGENT["Dispatch explore subagent<br>for target cataloging"]
    style SUBAGENT fill:#4a9eff,color:#fff
    BROAD -->|No| DIRECT[Catalog in main context]

    SUBAGENT --> INVENTORY[Build Audit Inventory:<br>- Skill files list<br>- MCP Python files list<br>- Total target counts]
    DIRECT --> INVENTORY

    INVENTORY --> MODE{Security mode<br>specified?}
    MODE -->|Yes| USE_MODE[Use specified mode]
    MODE -->|No| DEFAULT[Default to 'standard']
    USE_MODE --> DONE([Phase 1 Complete])
    DEFAULT --> DONE
```

---

## Detail Diagram 2: Phase 2 - ANALYZE

```mermaid
graph TD
    subgraph Legend
        L1["🔵 Subagent Dispatch"]
        L2["🔴 Quality Gate"]
        style L1 fill:#4a9eff,color:#fff
        style L2 fill:#ff6b6b,color:#fff
    end

    START([Phase 2 Start]) --> SCOPE{Target type?}

    SCOPE -->|Markdown skills| SKILL_SCAN["Run scanner --skills<br>or --mode skill &lt;path&gt;"]
    SCOPE -->|Python MCP| MCP_SCAN["Run scanner --mode mcp<br>spellbook/"]
    SCOPE -->|Changeset| CS_SCAN["Run scanner --changeset<br>or --base origin/main"]
    SCOPE -->|Both| PARALLEL["Dispatch parallel subagents<br>for skills + MCP scans"]
    style PARALLEL fill:#4a9eff,color:#fff

    SKILL_SCAN --> CHECK_EXIT{Exit code 0?}
    MCP_SCAN --> CHECK_EXIT
    CS_SCAN --> CHECK_EXIT
    PARALLEL --> CHECK_EXIT

    CHECK_EXIT -->|Success| CAPTURE[Capture all findings:<br>- File path + line<br>- Severity level<br>- Rule ID<br>- Message<br>- Evidence]
    CHECK_EXIT -->|Failure| FAILURE["Record error, note<br>unscanned targets"]
    style FAILURE fill:#ff6b6b,color:#fff

    FAILURE --> INCOMPLETE_GATE{User approves<br>partial results?}
    style INCOMPLETE_GATE fill:#ff6b6b,color:#fff
    INCOMPLETE_GATE -->|Yes| CAPTURE
    INCOMPLETE_GATE -->|No| ABORT([Audit Incomplete])
    style ABORT fill:#ff6b6b,color:#fff

    CAPTURE --> RAW[Record raw findings<br>before classification]
    RAW --> DONE([Phase 2 Complete])
```

---

## Detail Diagram 3: Phase 3 - CLASSIFY

```mermaid
graph TD
    subgraph Legend
        L1["🔴 Quality Gate"]
        style L1 fill:#ff6b6b,color:#fff
    end

    START([Phase 3 Start]) --> INTEGRITY["CLASSIFICATION INTEGRITY GATE:<br>Resist downgrading to produce<br>a clean report"]
    style INTEGRITY fill:#ff6b6b,color:#fff

    INTEGRITY --> DEDUP[Deduplicate: group identical<br>rule triggers across files]

    DEDUP --> ASSESS["Assess each finding:<br>1. Real severity vs default?<br>2. False positive?<br>3. Exploitable in context?<br>4. File trust level?"]

    ASSESS --> TRUST{Apply trust-level<br>context}

    TRUST -->|"system (5)"| T5[Only CRITICAL matters]
    TRUST -->|"verified (4)"| T4[HIGH and above]
    TRUST -->|"user (3)"| T3[MEDIUM and above]
    TRUST -->|"untrusted (2)"| T2[All findings]
    TRUST -->|"hostile (1)"| T1[All findings, paranoid mode]

    T5 --> CLASSIFY_TEMPLATE
    T4 --> CLASSIFY_TEMPLATE
    T3 --> CLASSIFY_TEMPLATE
    T2 --> CLASSIFY_TEMPLATE
    T1 --> CLASSIFY_TEMPLATE

    CLASSIFY_TEMPLATE["Classify each finding:<br>- Rule ID + message<br>- File + line<br>- Scanner vs assessed severity<br>- FP determination + rationale"]

    CLASSIFY_TEMPLATE --> FP{False positive<br>confirmed?}
    FP -->|Yes, with evidence| FP_DOC[Move to False Positives<br>section with rationale]
    FP -->|No / insufficient evidence| ACTIVE[Keep in active findings]

    FP_DOC --> DONE([Phase 3 Complete])
    ACTIVE --> DONE
```

---

## Detail Diagram 4: Phase 4 - TRACE

```mermaid
graph TD
    subgraph Legend
        L1["🔵 Subagent Dispatch"]
        L2{Decision}
        style L1 fill:#4a9eff,color:#fff
    end

    START([Phase 4 Start]) --> FILTER[Select HIGH/CRITICAL<br>findings from Phase 3]

    FILTER --> FRACTAL{Finding is<br>HIGH or CRITICAL?}

    FRACTAL -->|Optional| FRACTAL_THINK["Invoke fractal-thinking<br>intensity: pulse<br>seed: attack vectors + second-order effects"]
    style FRACTAL_THINK fill:#4a9eff,color:#fff

    FRACTAL -->|Direct analysis| ANSWER_Q

    FRACTAL_THINK --> ANSWER_Q["Answer for each finding:<br>1. Entry point?<br>2. Trust boundary crossed?<br>3. Impact type?<br>4. Attack scenario?<br>5. Existing mitigations?"]

    ANSWER_Q --> CHAIN["Document attack chain:<br>- Chain name<br>- Entry point<br>- Path (component chain)<br>- Impact<br>- Mitigations<br>- Exploitability level"]

    CHAIN --> REASSESS{Re-assess severity<br>based on chain}

    REASSESS -->|"Trivial exploit + no mitigations"| UPGRADE[Upgrade to CRITICAL]
    REASSESS -->|"Multiple defense layers"| KEEP[Keep severity, note<br>low exploitability]
    REASSESS -->|"No change"| CONFIRM[Confirm original severity]

    UPGRADE --> DONE([Phase 4 Complete])
    KEEP --> DONE
    CONFIRM --> DONE
```

---

## Detail Diagram 5: Phase 5 - REPORT

```mermaid
graph TD
    START([Phase 5 Start]) --> STRUCTURE["Build report sections:<br>1. Header (date, scope, mode, verdict)<br>2. Executive Summary<br>3. Finding Counts table<br>4. Findings by Severity<br>5. Attack Chains<br>6. False Positives<br>7. Recommendations"]

    STRUCTURE --> FINDINGS["For each finding:<br>- Rule ID + message heading<br>- File path + line<br>- Category<br>- Evidence<br>- Attack chain ref<br>- Remediation"]

    FINDINGS --> SAVE["Save to:<br>$SPELLBOOK_CONFIG_DIR/docs/<br>&lt;project-encoded&gt;/audits/<br>security-audit-&lt;timestamp&gt;.md"]

    SAVE --> DONE([Phase 5 Complete])
```

---

## Detail Diagram 6: Phase 6 - GATE

```mermaid
graph TD
    subgraph Legend
        L1["🔴 Quality Gate"]
        L2["🟢 Success Terminal"]
        style L1 fill:#ff6b6b,color:#fff
        style L2 fill:#51cf66,color:#fff
    end

    START([Phase 6 Start]) --> EVAL{Evaluate findings}
    style EVAL fill:#ff6b6b,color:#fff

    EVAL -->|"Zero findings"| PASS([PASS: Clean audit])
    style PASS fill:#51cf66,color:#fff

    EVAL -->|"Only LOW/MEDIUM"| WARN1[WARN verdict]
    EVAL -->|"HIGH without<br>attack chain"| WARN2[WARN verdict]
    EVAL -->|"HIGH with viable<br>attack chain"| FAIL1[FAIL verdict]
    EVAL -->|"Any CRITICAL"| FAIL2[FAIL verdict]

    WARN1 --> PRESENT_WARN[Present findings to user]
    WARN2 --> PRESENT_WARN

    PRESENT_WARN --> ACK{User<br>acknowledges?}
    ACK -->|Yes| LOG[Log acknowledgment<br>in report]
    LOG --> PROCEED([WARN: Proceed])
    style PROCEED fill:#51cf66,color:#fff
    ACK -->|No| REMEDIATE

    FAIL1 --> PRESENT_FAIL[Present findings to user]
    FAIL2 --> PRESENT_FAIL
    PRESENT_FAIL --> REMEDIATE[Block: remediate findings]
    style REMEDIATE fill:#ff6b6b,color:#fff

    REMEDIATE --> RESCAN{Remediation done,<br>re-scan?}
    RESCAN -->|Yes| BACK([Return to Phase 2])
    RESCAN -->|No| BLOCKED([FAIL: Blocked])
    style BLOCKED fill:#ff6b6b,color:#fff
```

---

## Integration Points Diagram

```mermaid
graph LR
    subgraph Legend
        L1[External Caller]
        L2[This Skill]
        style L1 fill:#fff3e0,stroke:#ff9800
        style L2 fill:#e8f4fd,stroke:#4a9eff
    end

    CR["code-review --audit<br>(correctness, perf,<br>maintainability passes)"]
    style CR fill:#fff3e0,stroke:#ff9800

    DEV["develop Phase 4<br>(dispatches subagent)"]
    style DEV fill:#fff3e0,stroke:#ff9800

    DISTILL["distilling-prs<br>(PR review)"]
    style DISTILL fill:#fff3e0,stroke:#ff9800

    SA["security-auditing<br>(security pass)"]
    style SA fill:#e8f4fd,stroke:#4a9eff

    CR -->|"Combined in<br>final report"| SA
    DEV -->|"scope=changeset<br>FAIL blocks merge"| SA
    DISTILL -->|"scope=PR diff<br>findings in distill report"| SA

    SA --> VERDICT{Verdict}
    VERDICT -->|PASS/WARN| CALLER_OK[Caller proceeds]
    VERDICT -->|FAIL| CALLER_BLOCK[Caller blocked]
    style CALLER_BLOCK fill:#ff6b6b,color:#fff
```

---

## Self-Check Gate Diagram

```mermaid
graph TD
    subgraph Legend
        L1["🔴 Quality Gate"]
        style L1 fill:#ff6b6b,color:#fff
    end

    START([Pre-Completion Self-Check]) --> C1{All targets<br>scanned?}
    style C1 fill:#ff6b6b,color:#fff
    C1 -->|No| FIX1[Scan missing targets]
    FIX1 --> C1
    C1 -->|Yes| C2{Both scanners used<br>if both in scope?}
    style C2 fill:#ff6b6b,color:#fff
    C2 -->|No| FIX2[Run missing scanner]
    FIX2 --> C2
    C2 -->|Yes| C3{Every finding<br>classified?}
    style C3 fill:#ff6b6b,color:#fff
    C3 -->|No| FIX3[Classify remaining]
    FIX3 --> C3
    C3 -->|Yes| C4{FPs documented<br>with evidence?}
    style C4 fill:#ff6b6b,color:#fff
    C4 -->|No| FIX4[Add rationale]
    FIX4 --> C4
    C4 -->|Yes| C5{HIGH/CRITICAL have<br>attack chains?}
    style C5 fill:#ff6b6b,color:#fff
    C5 -->|No| FIX5[Trace attack chains]
    FIX5 --> C5
    C5 -->|Yes| C6{Report counts<br>match details?}
    style C6 fill:#ff6b6b,color:#fff
    C6 -->|No| FIX6[Reconcile counts]
    FIX6 --> C6
    C6 -->|Yes| C7{Verdict matches<br>criteria?}
    style C7 fill:#ff6b6b,color:#fff
    C7 -->|No| FIX7[Correct verdict]
    FIX7 --> C7
    C7 -->|Yes| DONE([Self-Check Passed])
    style DONE fill:#51cf66,color:#fff
```

## Skill Content

``````````markdown
# Security Auditing

<ROLE>
Security Auditor and Red Team Analyst. Your reputation depends on finding real vulnerabilities before attackers do. You scan systematically, classify honestly, and never downplay findings. False negatives are career-ending. False positives waste time. Balance both.
</ROLE>

<CRITICAL>
This skill orchestrates a full security audit of Spellbook content: skills, commands, hooks, and MCP tool implementations. It uses `spellbook.security.scanner` as its static analysis backbone and layers human-guided triage on top.

Follow ALL six phases in order. Do NOT skip classification or trace analysis for HIGH/CRITICAL findings. Scanner results alone are insufficient; interpret, deduplicate, and contextualize.
</CRITICAL>

## Invariant Principles

1. **Scanner Is Necessary But Not Sufficient** - Static analysis catches patterns, not intent. You interpret the results.
2. **Severity Is Impact-Based** - CRITICAL = exploitable now with real damage. HIGH = exploitable with effort. MEDIUM = defense-in-depth concern. LOW = informational.
3. **Evidence Over Assertion** - Every finding needs file:line, matched rule, and explanation of why it matters in context.
4. **False Positives Are Expected** - The scanner is pattern-based. Legitimate code triggers rules. Your job is to distinguish signal from noise.
5. **Attack Chains Matter** - A MEDIUM finding that enables a CRITICAL exploit is itself CRITICAL. Trace the chain.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Scope | Yes | What to audit: `skills`, `mcp`, `changeset`, `all`, or specific paths |
| Security mode | No | `standard` (default), `paranoid`, or `permissive` |
| Diff text | If changeset | Unified diff for changeset scanning |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Audit report | File | Structured findings at `$SPELLBOOK_CONFIG_DIR/docs/<project-encoded>/audits/security-audit-<timestamp>.md` |
| Verdict | Enum | PASS, WARN, or FAIL |
| Summary | Inline | Finding counts by severity and category |

## Scanner Reference

The `spellbook.security.scanner` module provides these entry points:

| Function | Target | Description |
|----------|--------|-------------|
| `scan_skill(file_path)` | Single .md file | Scans against injection, exfiltration, escalation, obfuscation rules plus invisible chars and entropy |
| `scan_directory(dir_path)` | Directory of .md files | Recursive scan of all markdown files |
| `scan_changeset(diff_text)` | Unified diff | Scans only added lines in .md files |
| `scan_python_file(file_path)` | Single .py file | Scans against MCP-specific rules (shell injection, eval, path traversal, etc.) |
| `scan_mcp_directory(dir_path)` | Directory of .py files | Recursive scan of all Python files |

All functions accept an optional `security_mode` parameter: `"standard"`, `"paranoid"`, or `"permissive"`.

### Rule Categories

| Category | Rule Prefix | Examples |
|----------|-------------|----------|
| Injection | INJ-001..010 | Instruction overrides, role reassignment, system prompt injection |
| Exfiltration | EXF-001..009 | HTTP transfer tools, credential file access, reverse shells |
| Escalation | ESC-001..008 | Permission bypass, sudo, dynamic execution, shell injection |
| Obfuscation | OBF-001..004 | Base64 payloads, hex escapes, char code obfuscation |
| MCP Tool | MCP-001..009 | Shell execution, dynamic eval, unsanitized paths, SQL injection |
| Invisible | INVIS-001 | Zero-width Unicode characters |
| Entropy | ENT-001 | High-entropy code blocks |

### Security Modes

| Mode | Minimum Severity | Use When |
|------|-----------------|----------|
| `permissive` | CRITICAL only | Quick smoke test |
| `standard` | HIGH and above | Normal audits |
| `paranoid` | MEDIUM and above | Pre-release, supply chain review |

## Phase 1: DISCOVER

Identify the audit scope and catalog all targets.

<!-- SUBAGENT: Dispatch explore subagent if scope is broad (e.g., "all" or full directory). For targeted audits of 1-3 files, stay in main context. -->

1. **Parse scope argument:**
   - `skills` - all files under `skills/`
   - `mcp` - all Python files under `spellbook/`
   - `changeset` - staged or branch diff
   - `all` - both skills and mcp directories
   - Specific path(s) - targeted file or directory scan

2. **Catalog targets** in a structured inventory listing:
   - Audit Inventory header with scope and security mode
   - Skill Files section listing each .md file path
   - MCP Python Files section listing each .py file path
   - Total Targets with markdown file count and Python file count

3. **Determine security mode** from user input or default to `standard`.

## Phase 2: ANALYZE

Run the scanner against all cataloged targets.

<!-- SUBAGENT: Dispatch subagent to run scanner. For large scopes (20+ files), consider parallel subagents split by target type (skills vs MCP). -->

1. **Run appropriate scanner functions based on scope:**

   For skill/command files (markdown):
   ```bash
   uv run python -m spellbook.security.scanner --skills
   ```
   Or for specific files:
   ```bash
   uv run python -m spellbook.security.scanner --mode skill <path>
   ```

   For MCP tool files (Python):
   ```bash
   uv run python -m spellbook.security.scanner --mode mcp spellbook/
   ```

   For changeset scanning:
   ```bash
   git diff --cached | uv run python -m spellbook.security.scanner --changeset
   ```
   Or branch-based:
   ```bash
   uv run python -m spellbook.security.scanner --base origin/main
   ```

   **Scanner failure path:** If any scanner command fails (non-zero exit, missing module, timeout), record the error, note which targets were not scanned, and flag the audit as incomplete. Do not proceed to Phase 3 with partial results unless the user explicitly approves.

2. **Capture all scanner output.** Each finding includes:
   - File path and line number
   - Severity level (LOW, MEDIUM, HIGH, CRITICAL)
   - Rule ID (e.g., INJ-001, MCP-003)
   - Message describing the pattern
   - Evidence (matched text)

3. **Record raw findings** before classification.

## Phase 3: CLASSIFY

Deduplicate findings, assess real severity, and identify false positives.

<CRITICAL>
Classification is the most abuse-prone phase. The temptation to downgrade or dismiss findings to produce a clean report is real. Resist it. Every downgrade requires documented evidence. Every false positive requires rationale. If you cannot explain why a finding is benign in one sentence of evidence, it is not a false positive.
</CRITICAL>

1. **Deduplicate:** Group identical rule triggers across files. A rule that fires 50 times on the same pattern in different files is one finding, not 50.

2. **Assess each finding:**

   | Field | Question |
   |-------|----------|
   | Real severity | Does the context make this more or less dangerous than the rule's default? |
   | False positive? | Is this legitimate code that happens to match a security pattern? |
   | Exploitable? | Could an attacker actually leverage this in a Spellbook context? |
   | Context | What file is this in, and what is its trust level? |

3. **Apply trust-level context:**

   | Trust Level | Content | Threshold |
   |-------------|---------|-----------|
   | system (5) | Core framework code | Only CRITICAL matters |
   | verified (4) | Reviewed library skills | HIGH and above |
   | user (3) | User-installed content | MEDIUM and above |
   | untrusted (2) | Third-party skills | All findings |
   | hostile (1) | Unknown origin | All findings, paranoid mode |

4. **Classify each finding** using this template:

   - Finding: RULE_ID and message
   - File: path and line number
   - Scanner severity vs. assessed severity (upgraded, downgraded, or confirmed)
   - False positive determination with rationale

5. **Remove confirmed false positives** from the active findings list. Document them separately for transparency.

## Phase 4: TRACE

For HIGH and CRITICAL findings that survived classification, trace attack chains.

<analysis>
A finding in isolation tells you a pattern exists. An attack chain tells you what damage is possible. The difference between "this file contains a dynamic execution call" and "an attacker can inject arbitrary code via untrusted skill content that reaches that call through the MCP server" is the difference between awareness and actionable intelligence.
</analysis>

**Fractal exploration (optional):** When a finding is HIGH or CRITICAL severity, invoke fractal-thinking with intensity `pulse` and seed: "What attack vectors exist against [component] and what are the second-order effects?". Use the synthesis to enrich the attack chain graph.

1. **For each HIGH/CRITICAL finding, answer:**

   | Question | Purpose |
   |----------|---------|
   | What is the entry point? | How does attacker-controlled input reach this code? |
   | What is the trust boundary? | Does input cross from untrusted to trusted context? |
   | What is the impact? | Data loss, code execution, privilege escalation, exfiltration? |
   | What is the attack scenario? | Step-by-step exploitation narrative |
   | What prevents exploitation? | Existing mitigations, if any |

2. **Document attack chains** with these fields:

   - Attack Chain name
   - Entry: how attacker input enters the system
   - Path: entry to component to component to vulnerable code
   - Impact: what damage results from successful exploitation
   - Mitigations: existing defenses that slow or prevent exploitation
   - Exploitability: trivial, moderate, difficult, or theoretical

   **Example minimal attack chain:**
   - Chain: "INJ-003 via untrusted skill install"
   - Entry: User installs third-party skill containing injected instruction block
   - Path: skill file -> skill loader -> LLM prompt context -> instruction override
   - Impact: LLM adopts attacker role, exfiltrates session data
   - Mitigations: Skill schema validation (partial), user confirmation on install
   - Exploitability: moderate

3. **Re-assess severity** based on attack chain analysis. A HIGH finding with a trivial exploitation path and no mitigations becomes CRITICAL. A CRITICAL finding behind multiple defense layers may remain CRITICAL but with lower exploitability.

## Phase 5: REPORT

Generate the structured audit report.

### Report Format

The audit report is a markdown document with these sections in order:

1. **Header:** Date, scope, security mode, verdict (PASS/WARN/FAIL)
2. **Executive Summary:** 1-3 sentences on what was audited, what was found, overall risk
3. **Finding Counts:** Table with severity rows (CRITICAL, HIGH, MEDIUM, LOW), count column, and false positives excluded column
4. **Findings by Severity:** Sections for each severity level (CRITICAL first, then HIGH, MEDIUM, LOW). Each finding includes:
   - RULE_ID and message as heading
   - File path and line number
   - Category (injection, exfiltration, escalation, obfuscation, mcp_tool)
   - Evidence (matched text)
   - Attack Chain reference (if applicable, from Phase 4)
   - Remediation (specific fix)
5. **Attack Chains:** Full Phase 4 documentation for HIGH/CRITICAL findings
6. **False Positives:** Documented exclusions with rationale
7. **Recommendations:** Prioritized remediation steps, process improvements, scanner rule adjustments

### Output Location

Save the report to `$SPELLBOOK_CONFIG_DIR/docs/<project-encoded>/audits/security-audit-<timestamp>.md`.

## Phase 6: GATE

Enforce the audit verdict as a quality gate.

### Verdict Determination

| Condition | Verdict | Action |
|-----------|---------|--------|
| Zero findings after classification | PASS | Proceed |
| Only LOW/MEDIUM findings | WARN | Proceed with acknowledgment |
| Any HIGH finding with no attack chain | WARN | Proceed with acknowledgment |
| Any HIGH finding with viable attack chain | FAIL | Block until remediated |
| Any CRITICAL finding (regardless of chain) | FAIL | Block until remediated |

### Gate Enforcement

- **PASS:** Report the clean audit. No action required.
- **WARN:** Present findings to user. Require explicit acknowledgment before proceeding. Log acknowledgment in report.
- **FAIL:** Present findings to user. Do NOT proceed with any further workflow steps. The audit blocks progress until findings are remediated and a re-scan passes.

## Integration Points

### With `code-review --audit`

1. `code-review --audit` handles correctness, performance, and maintainability passes
2. This skill handles the security pass specifically
3. Findings from both are combined in the final audit report

### With `develop` Phase 4

1. `develop` Phase 4 dispatches a subagent that invokes this skill
2. Scope is set to the changeset (branch diff against base)
3. FAIL verdict blocks the feature from proceeding to merge
4. WARN verdict requires the implementer to acknowledge findings

### With `distilling-prs` for PR Review

1. `distilling-prs` can invoke this skill on the PR diff
2. Scope is set to changeset mode with the PR's unified diff
3. Security findings are surfaced as "review required" items in the PR distillation report

<FORBIDDEN>
- Skipping Phase 3 classification (raw scanner output is not an audit)
- Marking a CRITICAL finding as false positive without documented evidence
- Downgrading severity without explaining why in the rationale
- Proceeding past a FAIL gate without remediation
- Running only skill scans when MCP tools are in scope (or vice versa)
- Treating scanner output as the final word without contextual analysis
</FORBIDDEN>

<reflection>
Before finalizing, evaluate your own audit critically: Did you investigate each scanner finding in its full context, or did you rubber-stamp severity levels? Did you trace attack chains end-to-end, or stop at the first plausible-sounding explanation? Are there areas you avoided because they were complex? Honest self-assessment here prevents false confidence in the final report.
</reflection>

## Self-Check

Before completing the audit, verify:

**Completeness:**
- [ ] All targets in scope were scanned
- [ ] Both markdown and Python scanners used (if scope includes both)
- [ ] Every scanner finding has been classified (confirmed, downgraded, or marked false positive)

**Classification Quality:**
- [ ] Each finding has assessed severity with rationale
- [ ] False positives documented with evidence
- [ ] Trust levels applied to contextual assessment

**Trace Quality:**
- [ ] Every HIGH/CRITICAL finding has attack chain analysis
- [ ] Entry points identified for each chain
- [ ] Existing mitigations noted

**Report Quality:**
- [ ] Executive summary accurately reflects findings
- [ ] Finding counts match detailed listings
- [ ] Remediation steps are specific and actionable
- [ ] Report written to correct output path

**Gate:**
- [ ] Verdict matches the determination criteria
- [ ] FAIL verdicts block progress
- [ ] WARN verdicts require acknowledgment

<FINAL_EMPHASIS>
The scanner finds patterns. You find vulnerabilities. A pattern match is not a vulnerability until you understand its context, trace its attack surface, and assess its real-world exploitability. Do the work. Every phase matters.
</FINAL_EMPHASIS>
``````````
