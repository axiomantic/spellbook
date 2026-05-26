<!-- diagram-meta: {"source": "skills/code-review/SKILL.md", "source_hash": "sha256:b4367a566b65f993d44610f1f92d94128c16a3aa88911cdab8f38f226e44233f", "generated_at": "2026-05-25T23:20:15Z", "generator": "generate_diagrams.py"} -->
# Diagram: code-review

The existing diagram is complete and verified against the source `SKILL.md` and all three referenced command files (`code-review-give`, `code-review-feedback`, `code-review-tarot`). Below is the verified diagram content.

# Diagram: code-review

Workflow diagrams for the `code-review` skill: mode routing, self/audit inline modes, give/feedback/tarot command workflows, and cross-reference index.

## Overview

High-level mode routing, modifiers, and terminal outputs for all four modes.

```mermaid
flowchart TD
    classDef dispatch fill:#4a9eff,color:#000
    classDef gate fill:#ff6b6b,color:#000
    classDef success fill:#51cf66,color:#000

    INVOKE["code-review invoked"]

    INVOKE --> MODCHECK{"Modifier flags?"}

    MODCHECK -->|"--tarot"| TAROT["code-review-tarot\n(wraps active mode)"]:::dispatch
    MODCHECK -->|"--pr &lt;num&gt;"| PRFETCH["pr_fetch / pr_diff\n(MCP tools; fallback:\ngh CLI → local diff → paste)"]:::dispatch
    MODCHECK -->|"none"| MODECHECK{"Mode flag?"}

    TAROT --> MODECHECK{"Mode flag?"}
    PRFETCH --> MODECHECK

    MODECHECK -->|"--self / -s\nor no flag"| SELF["Self Mode\n(inline)"]:::dispatch
    MODECHECK -->|"--feedback / -f"| FEEDBACK["code-review-feedback\ncommand"]:::dispatch
    MODECHECK -->|"--give &lt;target&gt;"| GIVE["code-review-give\ncommand"]:::dispatch
    MODECHECK -->|"--audit [scope]"| AUDIT["Audit Mode\n(inline)"]:::dispatch

    SELF --> SELFOUT(["PASS / WARN / FAIL\n(severity gate)"]):::success
    FEEDBACK --> FBOUT(["All items addressed\n+ self-review clean"]):::success
    GIVE --> GIVEOUT(["APPROVE /\nREQUEST_CHANGES /\nCOMMENT"]):::success
    AUDIT --> AUDITOUT(["Executive Summary\n+ Risk Assessment\nLOW / MEDIUM / HIGH / CRITICAL"]):::success

    subgraph LEGEND["Legend"]
        LL1["Process"]
        LL2{"Decision"}
        LL3(["Terminal"]):::success
        LL4["Dispatch node"]:::dispatch
        LL5["Quality gate"]:::gate
    end
```

---

## Detail A — Self Mode and Audit Mode

Both inline modes: Self on the left, Audit on the right.

```mermaid
flowchart TD
    classDef dispatch fill:#4a9eff,color:#000
    classDef gate fill:#ff6b6b,color:#000
    classDef success fill:#51cf66,color:#000

    subgraph SELF["Self Mode (--self / -s / default)"]
        S1["git diff\n$(git merge-base origin/main HEAD)..HEAD"]
        S2["Pass 1: Logic"]
        S3["Pass 2: Integration"]
        S4["Pass 3: Security"]
        S5["Pass 4: Style"]
        S6["Generate findings\n(severity + file:line)"]
        SGATE{"Highest severity?"}:::gate
        SFAIL(["FAIL\n(Critical finding)"]):::success
        SWARN(["WARN\n(Important finding)"]):::success
        SPASS(["PASS\n(Minor only)"]):::success

        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> SGATE
        SGATE -->|"Critical"| SFAIL
        SGATE -->|"Important"| SWARN
        SGATE -->|"Minor only"| SPASS
    end

    subgraph AUDIT["Audit Mode (--audit [scope])"]
        ASCOPE{"Scope\nresolution"}:::gate
        ANONE["none → branch changes"]
        AFILE["file.py → single file"]
        ADIR["dir/ → directory"]
        ASEC["security → security-only"]
        AALL["all → full codebase"]

        AP1["Pass 1: Correctness\n+ API Hallucination Detection\nchecklist"]
        AP2["Pass 2: Security"]
        AP3["Pass 3: Performance"]
        AP4["Pass 4: Maintainability"]
        AP5["Pass 5: Edge Cases"]

        AOUT(["Executive Summary\n+ findings by category\n+ Risk Assessment\nLOW / MEDIUM / HIGH / CRITICAL"]):::success

        ASCOPE -->|"none"| ANONE
        ASCOPE -->|"file.py"| AFILE
        ASCOPE -->|"dir/"| ADIR
        ASCOPE -->|"security"| ASEC
        ASCOPE -->|"all"| AALL

        ANONE --> AP1
        AFILE --> AP1
        ADIR --> AP1
        ASEC --> AP2
        AALL --> AP1

        AP1 --> AP2 --> AP3 --> AP4 --> AP5 --> AOUT
    end

    subgraph LEGEND["Legend"]
        LL1["Process"]
        LL2{"Decision"}
        LL3(["Terminal"]):::success
        LL4["Dispatch node"]:::dispatch
        LL5["Quality gate"]:::gate
    end
```

The API Hallucination Detection checklist (method existence, signature match, real config keys, resolvable imports, return-type contracts) runs inside the Correctness pass and is elevated to HIGH severity for AI-generated code.

---

## Detail B — Give Mode (code-review-give)

Full step 0–3 workflow with all quality gates.

```mermaid
flowchart TD
    classDef dispatch fill:#4a9eff,color:#000
    classDef gate fill:#ff6b6b,color:#000
    classDef success fill:#51cf66,color:#000

    subgraph STEP0["Step 0: Load Project Conventions (BEFORE any review)"]
        C1["Read CLAUDE.md /\n.claude/CLAUDE.md"]
        C2["Read style config\n(pyproject.toml / .eslintrc /\nbiome.json / setup.cfg)"]
        C3["Check docs/code-review-instructions.md\nor .github/code-review-instructions.md"]
        C4["Sample 1-2 adjacent files\nNOT in PR changed file set"]
        CNOTE["CRITICAL: NEVER read local versions\nof files in the PR changed file set\n(local version is old code)"]:::gate

        C1 --> C2 --> C3 --> C4 --> CNOTE
    end

    subgraph STEP1["Step 1: Fetch and Inventory"]
        SRC{"Source type?"}
        SRCPR["PR# / URL\npr_fetch + pr_diff MCP\n+ gh pr diff"]:::dispatch
        SRCBR["Branch name\ngit diff merge-base..HEAD"]:::dispatch
        MANIFEST["Build coverage manifest\nfrom ALL changed files\n(quality gate — must complete\nBEFORE beginning review)"]:::gate
        PRIOR["Fetch prior review comments\ngh api pulls/number/comments\ngh api pulls/number/reviews"]:::dispatch
        CLASSIFY["Classify each prior item:\nADDRESSED or STILL_OPEN"]

        SRC -->|"PR# or URL"| SRCPR
        SRC -->|"branch name"| SRCBR
        SRCPR --> MANIFEST
        SRCBR --> MANIFEST
        MANIFEST --> PRIOR --> CLASSIFY
    end

    subgraph STEP2["Step 2: Multi-Pass Review"]
        MANDATORY["Mandatory dimensions — every changed file\n(skip any = coverage failure)"]:::gate
        D1["1. Correctness\n(logic errors, off-by-ones,\nnull handling, return types)"]
        D2["2. Security\n(injection, auth, secrets,\nSSRF, input length)"]
        D3["3. Error Handling\n(missing catches, swallowed errors,\nnull safety, interrupt handling)"]
        D4["4. Data Integrity\n(race conditions, non-atomic writes,\nstate mutations)"]
        D5["5. API Contracts\n(breaking changes, validation,\nschema drift)"]
        D6["6. Test Coverage\n(changes tested, edge cases,\nmeaningful assertions)"]

        CONDCHECK{"Conditional\ndimensions\ntriggered?"}
        PERF["Performance pass\n(N+1 queries, missing indexes,\nallocations)"]:::dispatch
        CONC["Concurrency/Async pass\n(REQUIRED when triggered)\nevent loop blocking, thread safety,\nrace conditions, lock ordering"]:::dispatch
        A11Y["Accessibility pass\n(ARIA, keyboard nav,\nscreen readers)"]:::dispatch

        SECPASS["Security Pass — runs for every review\nInput validation, path traversal,\nhardcoded secrets, auth/authz,\ninjection, SSRF"]:::gate

        MANDATORY --> D1 --> D2 --> D3 --> D4 --> D5 --> D6 --> CONDCHECK
        CONDCHECK -->|"hot paths / DB ops"| PERF
        CONDCHECK -->|"async / threading present"| CONC
        CONDCHECK -->|"UI / HTML / templates"| A11Y
        CONDCHECK -->|"none triggered"| SECPASS
        PERF --> SECPASS
        CONC --> SECPASS
        A11Y --> SECPASS
    end

    subgraph STEP3["Step 3: Output and Post-Review Reflection Gate"]
        FORMAT["Format output:\nSummary\n→ Coverage Manifest (N/N files, gaps)\n→ Prior Feedback Reconciliation\n→ Findings (CRITICAL/IMPORTANT/MINOR/QUESTION\nwith file:line + dimension)\n→ Recommendation"]

        REFLECT{"Post-review\nreflection gate"}:::gate
        RCHECK["Self-check:\nAll files in manifest evaluated?\nAll 6 mandatory dimensions checked?\nSecurity pass (all 6 checks)?\nIf async/threading: concurrency pass?\nAll prior items reconciled?\nSeverity ratings honest (impact-based)?"]

        RFIX["Address gaps\nbefore output"]
        TERMINAL(["APPROVE /\nREQUEST_CHANGES /\nCOMMENT"]):::success

        FORMAT --> REFLECT
        REFLECT -->|"gaps found"| RCHECK --> RFIX --> REFLECT
        REFLECT -->|"all checks pass"| TERMINAL
    end

    STEP0 --> STEP1 --> STEP2 --> STEP3

    subgraph LEGEND["Legend"]
        LL1["Process"]
        LL2{"Decision"}
        LL3(["Terminal"]):::success
        LL4["Dispatch node"]:::dispatch
        LL5["Quality gate"]:::gate
    end
```

---

## Detail C — Feedback Mode (code-review-feedback)

Full categorize/decide/execute workflow.

```mermaid
flowchart TD
    classDef dispatch fill:#4a9eff,color:#000
    classDef gate fill:#ff6b6b,color:#000
    classDef success fill:#51cf66,color:#000

    GATHER["Gather ALL feedback holistically\nacross related PRs\nbefore responding to any item"]:::gate

    CATEGORIZE["Categorize each item:\nbug / style / question / suggestion / nit"]

    DECIDE{"Decision\nper item"}

    ACCEPT["Accept:\nmake the change"]
    PUSHBACK["Push back:\ndisagree with evidence"]
    CLARIFY["Clarify:\nask specific question"]
    DEFER["Defer:\nacknowledge + scope reason"]

    RATIONALE["Document rationale\n(WHY for each decision\nbefore responding)"]:::gate

    FACTCHECK["Fact-check technical claims\nbefore accepting or disputing"]:::gate

    EXECUTE["Execute accepted fixes"]:::dispatch

    SELFREV["Re-run self-review\n(--self mode)"]:::dispatch

    SELFGATE{"Self-review\nclean?"}:::gate
    FIXMORE["Address new findings"]

    subgraph TEMPLATES["Response Templates"]
        T1["Accept: Fixed in &lt;SHA&gt;"]
        T2["Push back: tradeoff + evidence"]
        T3["Clarify: specific question"]
        T4["Defer: scope + reason"]
    end

    RESPOND["Respond using templates"]

    DONE(["All items addressed\n+ self-review clean"]):::success

    GATHER --> CATEGORIZE --> DECIDE
    DECIDE -->|"correct, improves code"| ACCEPT
    DECIDE -->|"incorrect or harmful"| PUSHBACK
    DECIDE -->|"ambiguous"| CLARIFY
    DECIDE -->|"valid but out of scope"| DEFER

    ACCEPT --> RATIONALE
    PUSHBACK --> RATIONALE
    CLARIFY --> RATIONALE
    DEFER --> RATIONALE

    RATIONALE --> FACTCHECK --> EXECUTE --> SELFREV --> SELFGATE
    SELFGATE -->|"findings"| FIXMORE --> SELFREV
    SELFGATE -->|"clean"| RESPOND --> TEMPLATES --> DONE

    subgraph LEGEND["Legend"]
        LL1["Process"]
        LL2{"Decision"}
        LL3(["Terminal"]):::success
        LL4["Dispatch node"]:::dispatch
        LL5["Quality gate"]:::gate
    end
```

---

## Detail D — Tarot Overlay (code-review-tarot)

Persona mapping, roundtable format, and audit integration.

```mermaid
flowchart TD
    classDef dispatch fill:#4a9eff,color:#000
    classDef gate fill:#ff6b6b,color:#000
    classDef success fill:#51cf66,color:#000

    OPTIN["Opt-in: --tarot modifier\n(compatible with all modes)"]

    subgraph PERSONAS["Persona Mapping"]
        PH["Hermit\nRole: Security reviewer\nFocus: Input validation, injection\nStakes: Do NOT trust inputs"]
        PP["Priestess\nRole: Architecture reviewer\nFocus: Design patterns, coupling\nStakes: Do NOT commit early"]
        PF["Fool\nRole: Assumption challenger\nFocus: Hidden assumptions, edge cases\nStakes: Do NOT accept hidden complexity"]
        PM["Magician\nRole: Synthesis / verdict\nFocus: Final assessment\nStakes: Clarity determines everything"]
    end

    subgraph ROUNDTABLE["Roundtable Format"]
        RT1["Magician opens"]
        RT2["Hermit speaks\n(security findings)"]
        RT3["Priestess speaks\n(architecture findings)"]
        RT4["Fool speaks\n(assumption challenges)"]
        RT5["Magician synthesizes\nby evidence weight\nNOT majority vote"]:::gate

        RT1 --> RT2 --> RT3 --> RT4 --> RT5
    end

    subgraph AUDITINT["Audit + Tarot Integration\n(parallel subagent prompts)"]
        AI1["Security pass\n→ Hermit persona"]:::dispatch
        AI2["Architecture pass\n→ Priestess persona"]:::dispatch
        AI3["Assumption pass\n→ Fool persona"]:::dispatch
        AI4["Synthesis\n→ Magician persona"]:::dispatch

        AI1 --> AI4
        AI2 --> AI4
        AI3 --> AI4
    end

    RULES["Critical rules:\nPersona dialogue appears ONLY in dialogue sections\nNEVER in code suggestions or formal findings\nSynthesis by evidence weight (NOT majority vote)\nfile:line citations required even in persona dialogue"]:::gate

    TOUT(["Tarot-annotated\nreview output"]):::success

    OPTIN --> PERSONAS
    OPTIN --> ROUNDTABLE
    OPTIN --> AUDITINT
    PERSONAS --> RULES
    ROUNDTABLE --> RULES
    AUDITINT --> RULES
    RULES --> TOUT

    subgraph LEGEND["Legend"]
        LL1["Process"]
        LL2{"Decision"}
        LL3(["Terminal"]):::success
        LL4["Dispatch node"]:::dispatch
        LL5["Quality gate"]:::gate
    end
```

---

## Cross-Reference Table

| Overview node | Detail diagram | Section |
|---|---|---|
| Self Mode (inline) | Detail A | Self Mode subgraph |
| Audit Mode (inline) | Detail A | Audit Mode subgraph |
| code-review-give command | Detail B | Steps 0–3 |
| code-review-feedback command | Detail C | Full workflow |
| code-review-tarot command | Detail D | Personas + Roundtable + Audit integration |
| pr_fetch / pr_diff modifier | Detail B | Step 1: Fetch and Inventory |
| Severity gate | Detail A | Self Mode — highest severity decision node |
| Coverage manifest gate | Detail B | Step 1: Build coverage manifest |
| Post-review reflection gate | Detail B | Step 3: Reflection gate |
| Synthesis by evidence weight | Detail D | Roundtable — Magician synthesizes node |
