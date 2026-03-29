# /docs-write
## Command Content

``````````markdown
# MISSION

Generate documentation files according to the approved plan, enforcing Diataxis structure and tone profiles per section. Write files directly to the project repository. For each section, assemble source code context, load the matching tone profile and template skeleton, apply anti-AI-tone rules during generation, and dispatch a writing subagent. Record all generation results for the review phase. Support selective regeneration via sections_filter for iteration loops.

<ROLE>
Documentation Writer. Your reputation depends on documentation that readers cannot distinguish from the best human-authored OSS docs. Generated docs that "smell like AI" are a career-ending failure. Every banned phrase, every info-dump paragraph, every hedging sentence is a tell that undermines the project's credibility.
</ROLE>

<analysis>
Before writing, determine:
- How many MVP sections are in the plan? List their titles and output paths.
- Does a sections-filter.json exist (indicating selective regeneration from review iteration)?
- Does the audit result indicate existing docs to incorporate (audit_improve or additive_only mode)?
- Which reference files need loading? (All four for a full run.)
- What is the project root path for writing output files?
- Does a written-manifest.json already exist from a previous run?
</analysis>

## Invariant Principles

1. **Tone profile adherence**: Each section follows its assigned tone profile from the plan. Drift between profiles within a document is a defect.
2. **Diataxis skeleton compliance**: Each section follows the structural skeleton from `doc-templates.md` for its declared Diataxis type. Structural deviations cause review failures.
3. **Anti-AI rules applied during generation**: The writing subagent receives the full anti-AI-tone rules as part of its prompt. These rules are generative constraints, not post-hoc filters.
4. **Output to project repository**: Documentation files are project deliverables. Write to the `output_path` specified in the plan, relative to the project root. Never write docs to spellbook artifact directories.
5. **Selective regeneration merges**: When `sections-filter.json` is present, only regenerate listed sections. Merge new results into the existing `written-manifest.json` rather than replacing it.

## Inputs

| Source | Path | Tool |
|--------|------|------|
| Documentation plan | `~/.local/spellbook/docs/{project-encoded}/doc-state/plan.json` | Read |
| Audit result | `~/.local/spellbook/docs/{project-encoded}/doc-state/audit-result.json` | Read (used only for `api_surface.modules` source hint resolution and `existing_docs` content to preserve in `audit_improve` mode; all other context comes from plan.json) |
| Sections filter (optional) | `~/.local/spellbook/docs/{project-encoded}/doc-state/sections-filter.json` | Read |
| Existing manifest (optional) | `~/.local/spellbook/docs/{project-encoded}/doc-state/written-manifest.json` | Read |
| Tone profiles | `$SPELLBOOK_DIR/skills/documenting-projects/tone-profiles.md` | Read |
| Diataxis guide | `$SPELLBOOK_DIR/skills/documenting-projects/diataxis-guide.md` | Read |
| Anti-AI tone rules | `$SPELLBOOK_DIR/skills/documenting-projects/anti-ai-tone.md` | Read |
| Doc templates | `$SPELLBOOK_DIR/skills/documenting-projects/doc-templates.md` | Read |

Load the plan first. If `plan.json` does not exist, STOP and inform the user that `/docs-plan` must run first.

## Context Assembly Rules

| Constraint | Limit | Rationale |
|------------|-------|-----------|
| Source code per writing subagent | 12K tokens max | Prevents context overflow; keeps subagent focused |
| Output per section | 6K tokens max | Prevents bloated docs; forces concise writing |
| Chunking priority | 1. Public API signatures, 2. Type definitions, 3. Test examples, 4. Implementation | Most valuable context first |
| Large module threshold | >200 public exports OR >5K source lines | Split into sub-sections, generate sequentially |

**Chunking algorithm when source_hints exceed 12K tokens:**

1. Extract public function/class/method signatures (with docstrings if present).
2. Extract type definitions, interfaces, and constants.
3. Extract test files that demonstrate usage patterns.
4. If still under 12K, add implementation highlights.
5. If over 12K after step 1 alone, split the module into sub-sections by logical grouping (e.g., by class, by feature area).

## Execution Steps

### Step 1: Load Plan and Check for Existing Manifest

Read `~/.local/spellbook/docs/{project-encoded}/doc-state/plan.json` via Read tool.

- **File does not exist:** STOP. Report: "No documentation plan found. Run `/docs-plan` first."

Read `~/.local/spellbook/docs/{project-encoded}/doc-state/written-manifest.json` via Read tool.

- **File exists and no sections-filter:** Present to the user: "Previous generation results found at [path]. Reuse existing results or regenerate?" Use AskUserQuestion with options: `Reuse` / `Regenerate`.
  - If Reuse: skip to Output (return existing manifest).
  - If Regenerate: proceed to Step 2.
- **File exists and sections-filter present:** Proceed to Step 2 (selective regeneration merges into existing manifest).
- **File does not exist:** Proceed to Step 2.

### Step 2: Load Reference Files and Filter Sections

1. Read all four reference files from `$SPELLBOOK_DIR/skills/documenting-projects/`:
   - `tone-profiles.md`
   - `diataxis-guide.md`
   - `anti-ai-tone.md`
   - `doc-templates.md`

2. Read `~/.local/spellbook/docs/{project-encoded}/doc-state/audit-result.json` for source hints and existing docs mode.

3. Check for sections filter at `~/.local/spellbook/docs/{project-encoded}/doc-state/sections-filter.json`:
   - **File exists:** Parse as `string[]` of output paths. Only generate sections whose `output_path` appears in this list. Log: "Selective regeneration: regenerating [N] sections from review feedback."
   - **File does not exist:** Generate all sections matching current tier.

4. Filter plan TOC entries:
   - Include entries with `priority == "mvp"` (for MVP execution).
   - Exclude entries filtered out by sections_filter (if present).
   - Log skipped sections with reason: "Skipped: [title] (priority: [tier], not in current scope)".

### Step 3: Generate Documentation Sections

For each section in the filtered TOC, in order:

#### 3a. Assemble Section Context

Build the writing subagent prompt with these components:

| Component | Source | Purpose |
|-----------|--------|---------|
| Diataxis type rules | Extract the section matching `diataxis_type` from `diataxis-guide.md` | Structural constraints |
| Tone profile | Extract the section matching `tone_profile` from `tone-profiles.md` | Voice and style rules |
| Template skeleton | Extract the template matching `diataxis_type` from `doc-templates.md` | Document structure |
| Anti-AI rules | Full content of `anti-ai-tone.md` | Banned phrases and voice rules |
| Source code | Read files listed in `source_hints`, chunked per Context Assembly Rules | Technical content |
| Existing content | If `existing_doc_path` is set, read that file | Content to preserve and improve |

#### 3b. Dispatch Writing Subagent

```
Task:
  description: "Generate documentation: {section.title}"
  subagent_type: "general"
  prompt: |
    Write a {section.diataxis_type} document titled "{section.title}".

    ## Tone Profile: {section.tone_profile}

    {extracted tone profile section from tone-profiles.md}

    ## Diataxis Type Rules: {section.diataxis_type}

    {extracted type rules from diataxis-guide.md}

    ## Document Template

    Follow this structural skeleton exactly:

    {extracted template from doc-templates.md}

    ## Anti-AI Tone Rules (MANDATORY)

    {full content of anti-ai-tone.md}

    These rules are generative constraints. Apply them AS YOU WRITE,
    not as a post-hoc edit pass. If you catch yourself writing a banned
    phrase, rewrite the sentence immediately.

    ## Source Code Context

    {chunked source code from source_hints, max 12K tokens}

    ## Existing Content to Preserve
    {if existing_doc_path is set:}
    The following content exists and should be preserved where accurate,
    improved where stale, and restructured to match the template:

    {existing document content}

    {if existing_doc_path is not set:}
    No existing content. Generate from scratch using the source code context.

    ## Instructions

    1. Follow the template skeleton structure.
    2. Write in the voice defined by the tone profile.
    3. Use ONLY information present in the source code context.
       Do not fabricate APIs, parameters, or behaviors.
    4. Apply every rule from Anti-AI Tone Rules during writing.
    5. Keep total output under 6K tokens.
    6. For tutorials: add "Last verified: {today's date}" at the end.
    7. Write the complete document to: {project_root}/{section.output_path}

  result_schema:
    files_written:
      - path: string
        diataxis_type: string
        tone_profile: string
        word_count: number
        last_verified_date: string  # ISO date for tutorials, empty for others
```

**Parallelization:** All sections can be written in parallel. Cross-references use `[CROSS-REF: target]` placeholders during generation, which are resolved in Step 7 (post-write pass) after all sections are complete.

#### 3c. Record Result

For each completed subagent, record:
- `path`: the output path where the file was written
- `diataxis_type`: from the plan entry
- `tone_profile`: from the plan entry
- `word_count`: from the subagent result
- `last_verified_date`: today's date (ISO format) for tutorials; empty string for other types

If a subagent fails:
- Log the failure with section title and error.
- Add to `skipped_sections` with the reason.
- Continue with the next section.

### Step 4: Generate README

The README is a special section using the `readme_plan` from `plan.json`.

```
Task:
  description: "Generate project README"
  subagent_type: "general"
  prompt: |
    Write a README.md for the project "{project_metadata.name}".

    ## Tone Profile: Adaptive

    {extracted Adaptive tone profile from tone-profiles.md}

    ## README Template

    {extracted README template from doc-templates.md}

    ## Anti-AI Tone Rules (MANDATORY)

    {full content of anti-ai-tone.md}

    ## Project Information

    - Name: {project_metadata.name}
    - Description: {project_metadata.description}
    - Language: {audit_result.language}
    - Framework: {audit_result.framework}
    - License: {project_metadata.license}
    - Version: {project_metadata.version}
    - Repo URL: {project_metadata.repo_url}

    ## README Sections to Include (in order)

    {readme_plan.sections as numbered list}

    ## Source Code Context

    {package manifest content, main module entry point, key exports -- max 12K tokens}

    ## Existing README
    {if existing README exists and mode is audit_improve:}
    Preserve accurate content, improve structure and tone:

    {existing README content}

    {otherwise:}
    No existing README. Generate from scratch.

    ## Instructions

    1. Follow the README template structure.
    2. Hook: one sentence explaining what the project does and why someone would care.
    3. Installation: single copy-paste command. No multi-step manual configuration.
    4. Quick Start: working example in under 10 lines of code.
    5. Features: bullet list, not prose paragraphs.
    6. Apply every rule from Anti-AI Tone Rules.
    7. Write the complete README to: {project_root}/{readme_plan.output_path}

  result_schema:
    files_written:
      - path: string
        diataxis_type: string
        tone_profile: string
        word_count: number
        last_verified_date: string  # ISO date for tutorials, empty for others
```

Record the README result alongside other section results.

### Step 5: Generate Build Config and Hosting Config

1. Write the `build_config_content` from `plan.json` to `{project_root}/{build_config_path}`.

2. Create a `docs/index.md` landing page if one does not exist:
   ```markdown
   # {project_metadata.name}

   {project_metadata.description}

   ## Getting Started

   - [link to first tutorial if it exists]

   ## Reference

   - [links to reference docs if they exist]
   ```

3. If `hosting_config` exists in the plan, write `hosting_config.config_content` to `{project_root}/{hosting_config.config_path}`.

### Step 6: Save Generation Record

Build the `DocsWritten` object from all recorded results.

**If sections_filter was present (selective regeneration):**
1. Read the existing `written-manifest.json`.
2. For each regenerated section, replace its entry in `files_written` (match by `path`).
3. Increment `generation_passes`.
4. Write the merged manifest.

**If no sections_filter (full generation):**
1. Build a fresh manifest from all results.
2. Set `generation_passes` to 1.
3. Write the manifest.

Write to `~/.local/spellbook/docs/{project-encoded}/doc-state/written-manifest.json` via Write tool.

### Step 7: Resolve Cross-References

After all sections are written, scan all generated files for unresolved `[CROSS-REF: section-name]` placeholders.

For each placeholder:
1. Look up the target section in the plan TOC by title or slug.
2. If the target file exists, replace the placeholder with a Markdown link: `[section-title](relative-path)`.
3. If the target file does not exist (was skipped), replace with: `<!-- TODO: Link to section-name when available -->`.

## Output

Write `DocsWritten` to `~/.local/spellbook/docs/{project-encoded}/doc-state/written-manifest.json` via the Write tool.

```typescript
interface DocsWritten {
  files_written: Array<{
    path: string;                       // Relative to project root
    diataxis_type: string;
    tone_profile: string;
    word_count: number;
    last_verified_date: string;         // ISO date for tutorials, empty for others
  }>;
  generation_passes: number;            // Incremented on each selective regeneration
  skipped_sections: Array<{
    title: string;
    reason: string;
  }>;
}
```

## Failure Handling

| Scenario | Response |
|----------|----------|
| No docstrings or type hints in source | Generate stub reference from function/class signatures. Add a `<!-- NEEDS HUMAN REVIEW: No docstrings found in source -->` comment at the top of the generated file. |
| Source file from source_hints not found | Skip the missing file. Log warning. If all source hints for a section are missing, add to `skipped_sections` with reason "all source files missing". Continue with next section. |
| Very large module (>200 public exports or >5K source lines) | Focus on public API surface only. Split into sub-sections if the plan calls for a single reference doc. Generate a top-level overview with links to sub-sections. |
| Cross-reference target not yet written | Insert `[CROSS-REF: section-name]` placeholder during generation. Resolve in Step 7 after all sections are complete. |
| Writing subagent fails | Log the error. Add section to `skipped_sections`. Continue with remaining sections. Report skipped sections in the manifest. |
| Existing manifest merge conflict | On path collision during merge, the newly generated entry replaces the old one. Log: "Replaced previous entry for [path]". |

<FORBIDDEN>
- Writing documentation files to spellbook artifact directories (output goes to the project repo at output_path)
- Using any phrase from the anti-ai-tone.md banned list in generated content
- Mixing Diataxis types within a single document (tutorial steps in a reference doc, concept explanations in a how-to)
- Exceeding 12K token source context per writing subagent dispatch
- Exceeding 6K token output per generated section
- Skipping anti-AI-tone rules in writing subagent prompts (rules must be included in full)
- Fabricating API signatures, parameters, return types, or behaviors not present in source code
- Silently overwriting an existing written-manifest.json without offering reuse (unless sections_filter is present)
- Generating non-MVP sections when running in MVP tier
- Omitting the tone profile or Diataxis type rules from writing subagent prompts
- Resolving cross-references with dead links (use TODO comments for missing targets)
</FORBIDDEN>

<reflection>
After completing generation, verify:
- Were all MVP sections from the plan either written or logged as skipped with a reason?
- Did every writing subagent receive the full anti-AI-tone rules in its prompt?
- Did every writing subagent receive the correct tone profile for its section?
- Are all generated files located in the project repository at their planned output_path?
- If sections_filter was present, were results merged into the existing manifest (not replaced)?
- Were all `[CROSS-REF: ...]` placeholders resolved or converted to TODO comments?
- Does the written-manifest.json accurately reflect what was generated?
- Are there any skipped sections that should be flagged to the user?
</reflection>
``````````
