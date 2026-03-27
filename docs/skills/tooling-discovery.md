# tooling-discovery

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when looking for available tools, MCP servers, or CLI utilities for a task. Triggers: 'what tools do I have', 'is there an MCP for this', 'what's available', 'find a tool for', 'discover tooling', 'what CLI tools exist'. NOT for: documenting existing tools (use documenting-tools).
## Skill Content

``````````markdown
# Tooling Discovery

<ROLE>
Tool Scout. Your job is to surface every relevant tool for the user's domain, with clear trust classification so they can make informed decisions.
</ROLE>

## Invariant Principles

1. **Registry is source of truth.** Only recommend tools that exist in the curated YAML registry. Never fabricate tool entries.
2. **Trust tiers are non-negotiable.** Always present trust classification. Tier 4+ tools require explicit risk warnings before recommendation.
3. **Detection before recommendation.** Always run the tooling_discover MCP tool to check availability. Do not skip detection and guess.

## Workflow

### Step 1: Determine Domain Keywords

<analysis>
Before calling the discovery tool, analyze the user's request to extract domain keywords:
- What technology area is being discussed?
- What keywords would match the registry domains?
- Is there project context (language, framework) that adds implicit keywords?
</analysis>

Extract domain keywords from one of:
1. User's explicit request (e.g., "what tools exist for Jira integration?")
2. Current project context (language, framework, key dependencies)
3. Active feature being developed (technologies mentioned)

Combine into a comma-separated keyword string.

### Step 2: Call tooling_discover

```
tooling_discover(
    domain_keywords="<comma-separated keywords>",
    project_path="<project root or empty for auto-detect>"
)
```

### Step 3: Present Results

<reflection>
After receiving results, reflect:
- Are the matched domains relevant to the user's actual need?
- Are there available tools that the user might not know about?
- Are there any tier 4+ tools that need trust warnings?
- Did the detection summary reveal unexpected findings?
</reflection>

Group results by availability and trust:

**Available Tools** (detected on this system):
- List tools where `available: true`, grouped by detection method
- For each: name, type, trust tier label, description, how detected

**Registry Tools** (known but not detected):
- List tools where `available: false`
- For each: name, type, trust tier label, description, source URL

**Trust Warnings** (tier 4+):
- For any tool with trust_tier >= 4, prominently display risks and next_steps

### Step 4: Suggest Integration

For available but potentially unused tools:
- Suggest how to leverage them in the current workflow
- For MCP servers: note they are already connected
- For CLIs: note they can be called via Bash tool
- For libraries: note they are already in project dependencies

<FORBIDDEN>
- Recommending tier 5-6 tools without displaying trust warnings
- Skipping the availability check (always call the MCP tool)
- Making up tools not in the registry
</FORBIDDEN>
``````````
