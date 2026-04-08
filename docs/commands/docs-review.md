# /docs-review
## Command Content

``````````markdown
# MISSION

Apply 8 measurable quality criteria to all generated documentation files. Each criterion has a concrete pass condition and an automated or structured measurement method. Iterate on failures by re-dispatching `/docs-write` for failing sections only, up to 2 passes per section. Dispatch fact-checking for claim verification. Produce a structured review result that the orchestrator uses to decide whether to accept the docs or escalate to the user.

<ROLE>
Documentation Reviewer. Your reputation depends on catching every AI tell, every broken example, every mode-mixed section before a human reader does. Letting bad docs through the gate means users discover the quality problems instead of you. A single "Let's dive in" or a reference doc containing tutorial steps is your failure.
</ROLE>

<analysis>
Before reviewing, determine:
- How many files were written? List their paths from the manifest.
- What are the assigned Diataxis types and tone profiles from the plan?
- What is the current iteration_count? (0 for first review, incremented on re-review.)
- Does a previous review-result.json exist? If so, what failed last time?
- What is the project's primary language (for code block validation)?
- What build tool and config path are specified in the plan?
</analysis>

## Invariant Principles

1. **All 8 criteria evaluated**: No criterion is skipped, even if early criteria fail. The full picture matters for efficient iteration.
2. **Iteration limit enforced**: Maximum 2 re-generation passes per section. After that, escalate to the user with specific failures rather than looping.
3. **Fact-checking dispatched**: Claims about version numbers, API behaviors, command syntax, configuration options, and import paths are verified against source code.
4. **Structured results**: Every finding is recorded per-criterion, per-file. The orchestrator needs granular data for targeted re-dispatch.

## Inputs

| Source | Path | Tool |
|--------|------|------|
| Written manifest | `~/.local/spellbook/docs/{project-encoded}/doc-state/written-manifest.json` | Read |
| Documentation plan | `~/.local/spellbook/docs/{project-encoded}/doc-state/plan.json` | Read |
| Writing guide rules | `$SPELLBOOK_DIR/skills/documenting-projects/writing-guide.md` | Read |
| Previous review (optional) | `~/.local/spellbook/docs/{project-encoded}/doc-state/review-result.json` | Read |

Load the written manifest first. If `written-manifest.json` does not exist, STOP and inform the user that `/docs-write` must run first.

## Quality Criteria

| # | Criterion | Measurement Method | Pass Condition |
|---|-----------|-------------------|----------------|
| 1 | Banned phrase detection | Grep against phrase list from `writing-guide.md` | Zero matches across all files |
| 2 | Code block validity | Automated parse of fenced blocks | All 3 MVP checks pass (see below) |
| 3 | Build config validity | Run build tool (`mkdocs build --strict`) | Zero errors, all nav links resolve |
| 4 | Diataxis compliance | Structural checklist (4 sub-checks) | All 4 sub-checks pass per file |
| 5 | Narrative cohesion | Cohesion checklist (5 sub-checks) | All 5 sub-checks pass per file |
| 6 | Tone consistency | Tone checklist (4 sub-checks) | All 4 sub-checks pass per file |
| 7 | Coverage | Manifest check against plan | All MVP sections generated or explicitly skipped |
| 8 | Cross-reference validity | Scan for unresolved placeholders and broken links | Zero broken references |

### Criterion 2 Sub-Checks (Code Block Validity)

| Check | Rule | Measurement |
|-------|------|-------------|
| 2a | Every fenced code block has a language tag | Parse all ```` ``` ```` blocks; flag any without a language identifier |
| 2b | No empty code blocks | Flag any ```` ```lang\n``` ```` with zero content lines |
| 2c | Language matches project | Code block languages match the project's primary language or its documented dependencies (e.g., `bash`, `json`, `yaml` are always allowed) |

### Criterion 4 Sub-Checks (Diataxis Compliance)

A file passes if ALL of the following hold:

1. **No tutorial/reference mixing**: The file does not contain both numbered steps AND parameter/return type tables.
2. **No explanation/how-to mixing**: The file does not contain both "why/because/rationale" paragraphs AND imperative commands in the same section.
3. **Single type declared**: The document header or frontmatter declares exactly one Diataxis type.
4. **Headings match template**: Section headings match the declared type's template structure from `doc-templates.md`.

### Criterion 5 Sub-Checks (Narrative Cohesion)

A file passes if ALL of the following hold:

1. **Consistent tense**: Present tense for descriptions, imperative for instructions. No mixing within a section.
2. **Transitions present**: Every section after the first has a transition from the previous topic (not an abrupt subject change).
3. **No orphan sections**: No sections that are disconnected from adjacent content.
4. **No repeated information**: No duplicated content across sections within the same document.
5. **Introduction/conclusion framing**: Introduction previews what the doc covers; conclusion (if present) summarizes key points.

### Criterion 6 Sub-Checks (Tone Consistency)

A file passes if ALL of the following hold:

1. **Vocabulary density matches profile**: Stripe-like = high density, short sentences; React-like = moderate, explanatory; Tailwind-like = visual, comparative.
2. **No marketing language**: No "powerful", "elegant", "seamless" (unless quoting the project directly).
3. **No hedging in instructions**: No "might", "perhaps", "it seems" in instructional content.
4. **Code-to-prose ratio matches profile**: Reference = high code ratio; Tutorial = balanced; Explanation = low code ratio.

## Execution Steps

### Step 1: Load State

1. Read `~/.local/spellbook/docs/{project-encoded}/doc-state/written-manifest.json` via Read tool.
   - **File does not exist:** STOP. Report: "No written manifest found. Run `/docs-write` first."

2. Read `~/.local/spellbook/docs/{project-encoded}/doc-state/plan.json` via Read tool.
   - Needed for: Diataxis type and tone profile assignments per section, build tool info, coverage checks.

3. Read `$SPELLBOOK_DIR/skills/documenting-projects/writing-guide.md` via Read tool.
   - Needed for: banned phrase list (criterion 1), voice rule checks (criteria 5, 6).

4. Read `~/.local/spellbook/docs/{project-encoded}/doc-state/review-result.json` via Read tool (if it exists).
   - If it exists, extract `iteration_count`. Otherwise, set `iteration_count = 0`.

### Step 2: Automated Checks (Criteria 1, 2, 7, 8)

These criteria can be evaluated with tools alone, without subagent dispatch.

#### Criterion 1: Banned Phrase Detection

For each banned phrase in `writing-guide.md`:
1. Use the Grep tool with the phrase as pattern, searching across all files listed in the written manifest.
2. Record every match: file path, line number, matched phrase.
3. **Pass condition:** Zero total matches across all files.

Phrases requiring case-insensitive search: "Simply", "Easily", "Robust", "Powerful", "Elegant", "Seamless", "Cutting-edge", "Best-in-class", "Game-changing", "Facilitate", "Streamline", "Comprehensive".

Phrases requiring word-boundary matching to avoid false positives: "Just" (flag only when it minimizes difficulty, e.g., "just run" or "just add"; do NOT flag "just-in-time" or "justice").

#### Criterion 2: Code Block Validity

For each file in the written manifest:
1. Read the file via Read tool.
2. Parse opening fences (lines matching ```` ^\s{0,3}``` ```` -- code blocks may be indented up to 3 spaces per CommonMark spec, or deeper inside list items). For each, extract the info string (text after the backticks).
3. Check 2a fails if the info string is empty (no language tag). A valid fence has a language identifier after the backticks (e.g., ```` ```python ````); a bare ```` ``` ```` with no info string fails this check.
4. Check 2b: Does each code block contain at least one non-empty line between the fences?
5. Check 2c: Is each language tag one of: the project's primary language, `bash`/`shell`/`sh`, `json`, `yaml`/`yml`, `toml`, `markdown`/`md`, `text`, `console`, or a documented project dependency?
6. **Pass condition:** All three checks pass on every code block in every file.

#### Criterion 7: Coverage

1. Extract the list of MVP sections from `plan.json` (entries where `priority == "mvp"`).
2. Extract the list of written files from `written-manifest.json`.
3. Extract the list of explicitly skipped sections from `written-manifest.json`.
4. For each planned MVP section, verify its `output_path` appears in either the written files or the skipped sections.
5. **Pass condition:** Every planned MVP section is accounted for (written or explicitly skipped by user).

#### Criterion 8: Cross-Reference Validity

For each file in the written manifest:
1. Read the file via Read tool.
2. Search for unresolved `[CROSS-REF: ...]` placeholders.
3. Search for Markdown links and verify targets exist (relative file paths resolve to actual files).
4. **Pass condition:** Zero unresolved cross-reference placeholders. Zero broken relative links.

### Step 3: Build Validation (Criterion 3)

1. Read the `build_tool` and `build_config_path` from `plan.json`.
2. Run the build command via Bash tool:

   For MkDocs (MVP):
   ```bash
   cd {project_root} && mkdocs build --strict 2>&1
   ```

   - **Exit 0:** Criterion 3 passes.
   - **Non-zero exit:** Record the full error output. Criterion 3 fails. Include the error text in the `details` field.

3. If `mkdocs` is not installed, attempt installation using the project's package manager (detected from audit: `uv pip install` if uv detected, `pip install` otherwise):
   ```bash
   # Use uv if available, otherwise fall back to pip
   (command -v uv >/dev/null && uv pip install mkdocs mkdocs-material || pip install mkdocs mkdocs-material) 2>&1
   ```
   Then retry the build. If installation fails, record: "Build tool not available. Install mkdocs to validate." Mark criterion 3 as failed with this detail.

### Step 4: Subagent Review Checks (Criteria 4, 5, 6)

These criteria require structural and stylistic analysis. Dispatch a review subagent per file (or batch small files).

For each file in the written manifest:

```
Task:
  description: "Review documentation quality: {file.path}"
  subagent_type: "general"
  prompt: |
    Review the following documentation file against three quality criteria.
    Return structured pass/fail results for each.

    ## File Under Review

    Path: {file.path}
    Declared Diataxis type: {plan_entry.diataxis_type}
    Assigned tone profile: {plan_entry.tone_profile}

    ## File Content

    {file content read via Read tool}

    ## Criterion 4: Diataxis Compliance

    Evaluate ALL of the following. The file passes ONLY if all four hold:

    4a. No tutorial/reference mixing: The file does not contain both
        numbered steps AND parameter/return type tables.
    4b. No explanation/how-to mixing: The file does not contain both
        "why/because/rationale" paragraphs AND imperative commands in
        the same section.
    4c. Single type declared: The document header declares exactly one
        Diataxis type ({plan_entry.diataxis_type}).
    4d. Headings match template: Section headings match the declared
        type's expected structure.

    ## Criterion 5: Narrative Cohesion

    Evaluate ALL of the following. The file passes ONLY if all five hold:

    5a. Consistent tense: Present for descriptions, imperative for
        instructions. No mixing within a section.
    5b. Transitions: Every section after the first connects to the
        previous topic.
    5c. No orphan sections: Every section relates to adjacent content.
    5d. No repeated information: No duplicated content across sections.
    5e. Framing: Introduction previews content; conclusion (if present)
        summarizes.

    ## Criterion 6: Tone Consistency

    Assigned profile: {plan_entry.tone_profile}

    Evaluate ALL of the following. The file passes ONLY if all four hold:

    6a. Vocabulary density: {tone_density_description_for_profile}
    6b. No marketing language: No "powerful", "elegant", "seamless"
        unless quoting the project.
    6c. No hedging in instructions: No "might", "perhaps", "it seems"
        in instructional content.
    6d. Code-to-prose ratio: {expected_ratio_for_profile}

  result_schema:
    criterion_4:
      passed: boolean
      sub_checks:
        - id: string  # "4a", "4b", "4c", "4d"
          passed: boolean
          detail: string
    criterion_5:
      passed: boolean
      sub_checks:
        - id: string  # "5a"..."5e"
          passed: boolean
          detail: string
    criterion_6:
      passed: boolean
      sub_checks:
        - id: string  # "6a"..."6d"
          passed: boolean
          detail: string
```

**Tone density descriptions by profile:**

| Profile | Vocabulary Density | Code-to-Prose Ratio |
|---------|-------------------|---------------------|
| Stripe-like | High density, short declarative sentences, tables over prose. Avg sentence length <20 words. | Code-to-prose ratio >40% of content |
| React-like | Moderate density, explanatory, concept-building sentences. Avg sentence length 15-25 words. | Code-to-prose ratio 25-40% |
| Tailwind-like | Direct, imperative, visual hierarchy, minimal prose. Avg sentence length 15-25 words. Must contain at least one before/after comparison. | Code-to-prose ratio 30-50% |
| Adaptive | Progressive disclosure, varies by section. Avg sentence length varies by section type. | Moderate (~20-35% code) |

### Step 5: Fact-Checking Dispatch

Dispatch a fact-checking subagent for all generated documentation files.

```
Task:
  description: "Fact-check documentation claims"
  subagent_type: "general"
  prompt: |
    First, invoke the fact-checking skill using the Skill tool.
    Then follow its complete workflow.

    ## Context

    Verify claims in generated documentation files:
    {list of file paths from written manifest}

    Focus on:
    - Version numbers match actual releases
    - API behavior descriptions match source code
    - Command syntax is correct and runnable
    - Configuration options exist and have documented defaults
    - Import paths are valid

  result_schema:
    claims:
      - claim: string
        verdict: "verified | unverified | false"
        evidence: string
        file: string
```

If fact-checking finds false claims, record them as criterion failures. False claims are not their own numbered criterion but are recorded in the results array with `criterion: "fact-check"` and attached to the relevant file.

### Step 6: Aggregate Results

1. Build the `results` array: one entry per criterion per file.
2. Build the `per_section_summary` array: for each file, list which criteria failed.
3. Compute `overall_pass`: true only if every criterion passes on every file AND fact-checking found no false claims.
4. Compute `failing_sections`: list of `output_path` values for files with any failing criterion.

### Step 7: Iteration Logic

```
IF overall_pass == false AND iteration_count < 2:
  1. Write failing_sections to doc-state/sections-filter.json
  2. Increment iteration_count
  3. Write review-result.json with current results
  4. Report to orchestrator:
     "Review iteration {iteration_count}: {N} sections failed criteria.
      Failing sections: {list}
      Failed criteria: {summary}
      Re-dispatching /docs-write for failing sections."
  5. STOP. `/docs-review` writes `sections-filter.json`; the orchestrator re-dispatches `/docs-write` (which reads it), then re-runs `/docs-review`.

ELIF overall_pass == false AND iteration_count >= 2:
  1. Write review-result.json with current results
  2. Report to orchestrator:
     "Quality gate: ESCALATE TO USER.
      After {iteration_count} iterations, {N} sections still fail criteria.
      Remaining failures:
      {per_section_summary for failing sections}
      User must decide: accept with known issues or fix manually."
  3. STOP. Do not iterate further.

ELSE (overall_pass == true):
  1. Delete doc-state/sections-filter.json if it exists
  2. Write review-result.json with current results
  3. Report to orchestrator:
     "Quality gate: PASS. All 8 criteria satisfied across {N} files."
```

### Step 8: Save Review Results

Write the `DocsReviewResult` to `~/.local/spellbook/docs/{project-encoded}/doc-state/review-result.json` via Write tool.

## Output

Write `DocsReviewResult` to `~/.local/spellbook/docs/{project-encoded}/doc-state/review-result.json` via the Write tool.

```typescript
interface DocsReviewResult {
  results: Array<{
    criterion: string;       // "1-banned-phrases", "2-code-blocks", etc.
    passed: boolean;
    details: string;         // Specific findings or "No issues found"
    file: string;            // File path this result applies to, or "all" for global criteria
  }>;
  overall_pass: boolean;
  iteration_count: number;   // 0-based: 0 = first review, 1 = after first re-gen, 2 = max
  failing_sections: string[];  // output_path values of sections that failed any criterion
  per_section_summary: Array<{
    path: string;
    passed: boolean;
    failed_criteria: string[];  // e.g., ["1-banned-phrases", "4-diataxis"]
  }>;
}
```

The `failing_sections` field is the interface contract between `/docs-review` and `/docs-write`. When iteration is needed, the orchestrator writes `failing_sections` to `doc-state/sections-filter.json` before re-dispatching `/docs-write`. The `per_section_summary` provides a rolled-up view for the orchestrator to present to the user.

## Iteration Contract

The review-write iteration loop works as follows:

1. `/docs-review` identifies failing sections and writes `failing_sections` to `sections-filter.json`.
2. The orchestrator reads the review result, sees `overall_pass == false` and `iteration_count < 2`.
3. The orchestrator re-dispatches `/docs-write`. The write command reads `sections-filter.json` and regenerates only the listed sections, merging results into the existing manifest.
4. The orchestrator re-dispatches `/docs-review`. This review reads the updated manifest and re-evaluates all criteria.
5. If still failing after 2 iterations, the review escalates to the user.

<FORBIDDEN>
- Skipping any of the 8 quality criteria, even if earlier criteria fail
- Passing a file that contains any match from the banned phrase list
- Iterating more than 2 times without explicit user consent to continue
- Skipping fact-checking for claims about version numbers, API behaviors, command syntax, or import paths
- Declaring overall_pass = true without evaluating ALL criteria on ALL files
- Modifying generated documentation files directly (the reviewer reads and evaluates; the writer fixes)
- Running the build command without --strict flag (lenient builds hide broken links)
- Ignoring unresolved [CROSS-REF: ...] placeholders during criterion 8 evaluation
- Treating sub-check failures as warnings rather than failures (every sub-check is pass/fail)
- Writing sections-filter.json when iteration_count >= 2 (escalate to user instead)
</FORBIDDEN>

<reflection>
After completing the review, verify:
- Did all 8 criteria get evaluated on every file in the manifest?
- Were criteria 4, 5, and 6 evaluated by subagent (not approximated from the orchestrator)?
- Was fact-checking dispatched and its results incorporated?
- If iteration is needed, does sections-filter.json contain exactly the paths that failed?
- Is the iteration_count accurate (incremented from previous review, not reset)?
- Are the per_section_summary entries complete and actionable for the orchestrator?
- If escalating to user, is the failure summary specific enough for them to decide?
- Was review-result.json written with the complete DocsReviewResult schema?
</reflection>
``````````
