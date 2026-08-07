# AGENTS.spellbook.md Changes — Prime Agent Adaptation

## Overview
Updated `AGENTS.spellbook.md` to add Prime Agent as a supported platform and remove references to features unavailable or inapplicable in Prime Agent (stints, MCP tools, admin URLs).

## Changes Made

### 1. "What Spellbook Is (And Isn't)" Section (lines 9, 14)
- Added "Prime Agent" to the list of harnesses
- Changed "shared MCP server (focus stints, session resume)" to "shared state layer (session resume)"
- Added explanation: MCP-capable platforms use the MCP server; Prime Agent uses the continual harness (memories, skills, prompt notes)
- Updated MCP server bullet to scope `spellbook_*` tools to MCP-capable platforms only, with Prime Agent using the continual harness

### 2. Platform Identification Table — Step 0 (line 41)
- Added Prime Agent row: signal = "Your system prompt mentions Prime Agent, RLM, or IPython kernel", platform value = `prime_agent`, assistant name = "Prime Agent"

### 3. Session Init — Step 1 (lines 64-68)
- Split platform initialization into two paths: MCP-capable platforms call `spellbook_session_init` MCP tool; Prime Agent checks `rlm.harness.overview()`
- Removed `admin_url` reference from the greeting line (Prime Agent has no admin URL concept)

### 4. Focus Tracking (Stints) Section — REMOVED (was lines 115-126)
- Entire section removed: "Focus Tracking (Stints)" with stint_push, stint_pop, stint_check, stint_replace references
- Document now flows directly from Project Knowledge into Inviolable Rules

### 5. MCP Tools Section — REMOVED (was lines 548-557)
- Entire section removed: MCP tool usage rule, platform-specific MCP configuration paths
- Document now flows directly from Testing into File Reading

### Sections Preserved
- Session Mode, Session Resume, Notification Configuration
- Project Knowledge, Inviolable Rules, Core Philosophy
- Code Quality, Communication, Testing, File Reading
- Context Minimization, Opportunity Awareness, Worktrees
- Language-Specific, Pull Request Conventions
- Key Skill References, Glossary

## Net Effect
- **Lines removed**: ~25 (Focus Tracking + MCP Tools sections + admin_url)
- **Lines added**: ~8 (Prime Agent platform row + platform-conditional instructions)
- **File**: 643 → 622 lines (21 fewer), 40,616 → 40,090 chars
