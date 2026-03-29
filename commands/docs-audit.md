---
description: "Phase 1 of documenting-projects: Project analysis for documentation planning. Triggers: '/docs-audit', invoked by documenting-projects orchestrator."
---

# MISSION

Analyze the target project to build a complete picture of its language, framework, existing documentation, API surface, and documentation gaps. Produce a structured `DocsAuditResult` that subsequent phases consume. Every field must be populated or explicitly defaulted with user interview fallback.

<ROLE>
Documentation Auditor. Your reputation depends on accurate project analysis. A wrong language detection or missed existing doc causes every downstream phase to produce wrong output. Misidentifying the framework means the build tool recommendation is wrong, the tone assignments are wrong, and the generated docs reference the wrong APIs.
</ROLE>

<analysis>
Before analyzing, determine:
- What package manifests exist in the project root? (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `setup.py`)
- Is there an existing `docs/` or `doc/` directory?
- What is the primary language by source file count?
- Are there existing build configs? (`mkdocs.yml`, `conf.py`, `docusaurus.config.js`)
- Is this a monorepo with multiple packages?
</analysis>

## Invariant Principles

1. **Detect, don't assume**: Scan package manifests and source files. Never guess language from directory names alone.
2. **Every field populated**: A `DocsAuditResult` with null or empty fields causes downstream failures. If detection fails, interview the user via AskUserQuestion.
3. **User chooses existing docs mode**: Present all three options (audit+improve, start fresh, additive only). Never default silently.
4. **Graceful degradation**: Missing manifest means interview the user, not a hard failure. Unsupported language means warn and default to MkDocs, not abort.

## Execution Steps

### Step 0: Create State Directory

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
# Follows the spellbook project-encoded path convention (see managing-artifacts skill):
# strip leading slash, replace remaining slashes with dashes.
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')
mkdir -p ~/.local/spellbook/docs/$PROJECT_ENCODED/doc-state/
```

Store `PROJECT_ROOT` and `PROJECT_ENCODED` for use in all subsequent steps.

### Step 1: Language and Framework Detection

Dispatch an explore subagent to analyze the codebase:

```
Task:
  description: "Analyze project for documentation planning"
  subagent_type: "explore"
  prompt: |
    Analyze this project for documentation planning. Return structured JSON.

    1. Scan for package manifests: pyproject.toml, setup.py, package.json,
       Cargo.toml, go.mod, build.gradle, pom.xml
    2. Detect primary language from file extension frequency
    3. Identify framework from imports/dependencies
    4. Extract project metadata: name, description, license, version
    5. Get repo URL from git remote

    Project root: {PROJECT_ROOT}

  result_schema:
    language: string
    framework: string | null
    project_metadata:
      name: string
      description: string
      license: string | null
      version: string | null
      repo_url: string | null
```

If no package manifest is found, use AskUserQuestion:

```markdown
Header: "Project metadata"
Question: "No package manifest found. Please provide:"

- Primary language:
- Framework (if any):
- Project name:
- Brief description:
```

### Step 2: Existing Docs Inventory

Dispatch an explore subagent to scan for documentation:

```
Task:
  description: "Inventory existing documentation files"
  subagent_type: "explore"
  prompt: |
    Scan this project for existing documentation. Return structured JSON.

    Look for:
    - README* files (root and subdirectories)
    - docs/ or doc/ directories (all files within)
    - *.md files in root
    - CHANGELOG*, CONTRIBUTING*, CODE_OF_CONDUCT*
    - Build configs: mkdocs.yml, conf.py, docusaurus.config.js
    - API doc comments/docstrings density

    For each doc found, assess:
    - path: relative to project root
    - type: Diataxis type ("tutorial", "howto", "reference", "explanation") or "unknown"
    - quality: "good" (complete, current), "stale" (outdated or no longer current), "poor" (incomplete/broken)
    - staleness: human-readable (e.g., "6 months since last update")

    Project root: {PROJECT_ROOT}

  result_schema:
    existing_docs:
      - path: string
        type: string
        quality: string
        staleness: string
    build_configs: string[]
```

### Step 3: API Surface Analysis

Dispatch an explore subagent for public API analysis:

```
Task:
  description: "Analyze public API surface for documentation coverage"
  subagent_type: "explore"
  prompt: |
    Analyze the public API surface of this project. Return structured JSON.

    1. Identify public modules/packages (exported, not internal/private)
    2. Measure docstring/JSDoc coverage as a percentage of public
       functions, classes, and methods that have documentation
    3. List modules by name

    For Python: check __all__, public functions/classes without _ prefix
    For JS/TS: check exports in index files, public methods
    For Rust: check pub items
    For Go: check exported identifiers (capitalized)

    Project root: {PROJECT_ROOT}

  result_schema:
    modules: string[]
    coverage: number  # 0-100 percentage
```

### Step 4: Project Metadata Fallback

Fill in any metadata fields the Step 1 subagent could not populate (e.g., license from LICENSE file, repo URL from git remote):

1. Check git remote for repo URL: `git -C {PROJECT_ROOT} remote get-url origin 2>/dev/null`
2. Check license file: `ls {PROJECT_ROOT}/LICENSE* 2>/dev/null`
3. For remaining gaps, use AskUserQuestion with specific fields listed.

### Step 5: Gap Analysis

Compare found docs against Diataxis coverage:

| Diataxis Type | Expected | Check |
|---------------|----------|-------|
| Tutorial | At least one getting-started guide | Scan existing_docs for type="tutorial" |
| How-To Guide | Task-oriented guides for common operations | Scan for type="howto" |
| Reference | API/module documentation | Compare against api_surface.modules |
| Explanation | Architecture/design docs | Scan for type="explanation" |

Build the `gaps` array from missing types. Also flag:
- Modules with 0% docstring coverage
- Stale docs (quality="stale" or quality="poor")
- Missing README

### Step 6: Existing Docs Mode Selection

Present via AskUserQuestion:

```markdown
Header: "Existing documentation handling"
Question: "How should I handle your existing documentation?"

Options:
- Audit and improve: Preserve good content, update stale sections, fill gaps
- Start fresh: Build new structure from scratch, migrate salvageable content
- Additive only: Keep all existing docs as-is, only add what's missing
```

If no existing docs were found, default to "start_fresh" and inform the user:

```markdown
No existing documentation found. Defaulting to "start fresh" mode.
```

### Step 7: Build Tool Recommendation

Apply detection logic based on primary language:

| Language | Recommendation | Rationale |
|----------|---------------|-----------|
| Python | `sphinx` | Native autodoc, RST/MyST support |
| JavaScript/TypeScript | `docusaurus` | MDX support, React ecosystem |
| Other/polyglot/unknown | `mkdocs` | Language-agnostic, Material theme, low config |

If an existing build config was found in Step 2 (e.g., `mkdocs.yml`, `conf.py`), note it and recommend keeping the existing tool unless the user prefers otherwise.

## Output

Write `DocsAuditResult` to `~/.local/spellbook/docs/{project-encoded}/doc-state/audit-result.json` via the Write tool.

```typescript
interface DocsAuditResult {
  language: string;                    // Primary language detected
  framework: string | null;            // Framework if detected
  build_tool_recommendation: "mkdocs" | "sphinx" | "docusaurus";
  build_configs: string[];                // Existing build configs found (e.g., "mkdocs.yml", "conf.py")
  existing_docs: Array<{
    path: string;
    type: "tutorial" | "howto" | "reference" | "explanation" | "unknown";
    quality: "good" | "stale" | "poor";
    staleness: string;                 // e.g., "6 months since last update"
  }>;
  api_surface: {
    modules: string[];
    coverage: number;                  // 0-100, percentage with docstrings
  };
  gaps: string[];                      // Missing doc types
  existing_docs_mode: "audit_improve" | "start_fresh" | "additive_only";
  project_metadata: {
    name: string;
    description: string;
    license: string | null;
    version: string | null;
    repo_url: string | null;
  };
}
```

## Failure Handling

| Scenario | Response |
|----------|----------|
| No package manifest | Interview user for project metadata via AskUserQuestion |
| Unsupported language | Warn user, default to MkDocs + generic Markdown structure |
| No existing docs | Default to "start_fresh" mode, inform user |
| Monorepo detected | Ask user which package(s) to document via AskUserQuestion; scope per-package |
| Non-English codebase | Warn user, proceed with English docs, note limitation in audit result |

<FORBIDDEN>
- Guessing language without scanning package manifests or source file extensions
- Leaving audit result fields as null or empty without falling back to user interview
- Skipping the existing docs mode choice (user must choose unless no docs exist)
- Hardcoding build tool recommendation without language-based detection logic
- Proceeding with incomplete project metadata without flagging gaps to the user
- Writing audit results to the project repository (output goes to doc-state/ only)
- Assuming framework from directory structure alone (scan dependencies)
- Skipping the state directory creation in Step 0
</FORBIDDEN>

<reflection>
After completing the audit, verify:
- Are all DocsAuditResult fields populated with detected or user-provided values?
- Did I present the existing docs mode choice to the user (or default with notification if no docs)?
- Is the build tool recommendation consistent with the detected primary language?
- Does the gaps array reflect actual missing Diataxis coverage, not just missing files?
- Was the audit-result.json written to the correct doc-state/ path?
</reflection>
