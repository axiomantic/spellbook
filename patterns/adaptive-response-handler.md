# Adaptive Response Handler (ARH) Pattern

## Purpose
Intelligent processing of AskUserQuestion responses that transforms answers into actionable intelligence and dispatches research when needed.

## Pattern Structure

### 1. Response Type Detection

**EXACT REGEX PATTERNS:**

```javascript
// Response type detection with exact regular expressions
// Check in ORDER - first match wins

RESPONSE_TYPES = {
  // 1. DIRECT_ANSWER - Check first for multiple choice responses
  DIRECT_ANSWER: {
    pattern: /^[A-D]$/i,
    description: "Single letter A-D (case insensitive)",
    examples: ["A", "b", "C", "d"],
    caseInsensitive: true
  },

  // 2. USER_ABORT - Check early for stop signals
  USER_ABORT: {
    pattern: /^\s*(stop|cancel|exit|abort|nevermind|never mind|quit)\s*$/i,
    description: "Explicit stop/cancel commands",
    examples: ["stop", "cancel", "exit", "nevermind"],
    caseInsensitive: true
  },

  // 3. RESEARCH_REQUEST - Explicit ask to investigate
  RESEARCH_REQUEST: {
    pattern: /\b(research\s+this|look\s+into|find\s+out|investigate|can\s+you\s+(check|look|research|find))\b/i,
    description: "Explicit request to research something",
    examples: ["research this", "can you look into that", "find out more", "investigate the codebase"],
    caseInsensitive: true
  },

  // 4. UNKNOWN - User doesn't know the answer
  UNKNOWN: {
    pattern: /\b(don'?t\s+know|not\s+sure|unsure|i'?m\s+not\s+certain|no\s+idea|need\s+to\s+check|have\s+to\s+look)\b/i,
    description: "User expresses uncertainty or lack of knowledge",
    examples: ["I don't know", "not sure", "I'm unsure", "no idea", "need to check"],
    caseInsensitive: true
  },

  // 5. CLARIFICATION - User needs question rephrased
  CLARIFICATION: {
    pattern: /\b(what\s+do\s+you\s+mean|clarify|explain|rephrase|don'?t\s+understand|what\s+does\s+.+\s+mean|can\s+you\s+explain)\b/i,
    description: "Request for clarification or explanation",
    examples: ["what do you mean", "can you clarify", "please explain", "I don't understand"],
    caseInsensitive: true
  },

  // 6. SKIP - User wants to skip this question
  SKIP: {
    pattern: /^\s*(skip|n\/?a|not\s+applicable|not\s+relevant|pass|move\s+on)\s*$/i,
    description: "Skip this question",
    examples: ["skip", "n/a", "not applicable", "pass", "move on"],
    caseInsensitive: true
  },

  // 7. OPEN_ENDED - Default for anything else
  OPEN_ENDED: {
    pattern: /.*/,  // Matches everything
    description: "Any other response - free-form answer",
    examples: ["[anything that doesn't match above patterns]"],
    caseInsensitive: false
  }
};

// Detection function - returns first matching type
function detectResponseType(userResponse) {
  // Normalize: trim whitespace
  const normalized = userResponse.trim();

  // Empty response defaults to CLARIFICATION
  if (normalized.length === 0) {
    return "CLARIFICATION";
  }

  // Check each pattern IN ORDER
  const checkOrder = [
    "DIRECT_ANSWER",
    "USER_ABORT",
    "RESEARCH_REQUEST",
    "UNKNOWN",
    "CLARIFICATION",
    "SKIP",
    "OPEN_ENDED"
  ];

  for (const typeName of checkOrder) {
    const type = RESPONSE_TYPES[typeName];
    if (type.pattern.test(normalized)) {
      return typeName;
    }
  }

  // Fallback (should never reach here due to OPEN_ENDED catch-all)
  return "OPEN_ENDED";
}

// Testing examples:
detectResponseType("A")                           // → DIRECT_ANSWER
detectResponseType("research this pattern")       // → RESEARCH_REQUEST
detectResponseType("I don't know")                // → UNKNOWN
detectResponseType("what do you mean by that")    // → CLARIFICATION
detectResponseType("skip")                        // → SKIP
detectResponseType("stop")                        // → USER_ABORT
detectResponseType("I think we should use JWT")   // → OPEN_ENDED
```

**IMPORTANT NOTES:**
1. **Order matters**: Check DIRECT_ANSWER before OPEN_ENDED to catch single letters
2. **Case insensitive**: All patterns use /i flag except OPEN_ENDED
3. **Word boundaries**: Use \b to avoid partial matches (e.g., "research" in "researcher")
4. **Trim input**: Always normalize by trimming whitespace first
5. **Empty responses**: Treat as CLARIFICATION request

### 2. Response Handlers

**DIRECT_ANSWER Handler:**
```markdown
ACTION: Update design_context
NEXT: Continue to next question
```

**RESEARCH_REQUEST Handler:**
```markdown
ACTION:
1. Parse research request to extract topic
2. Dispatch Explore/Task subagent with specific instructions:
   "Research: [topic]
   Context: [current understanding]
   Return: Specific findings with evidence"
3. Wait for subagent results
4. Regenerate ALL questions in current category
5. Present updated questions to user

RATIONALE: New research may improve previous questions
```

**UNKNOWN Handler:**
```markdown
ACTION:
1. Recognize this as implicit research request
2. Dispatch subagent to research the question topic
3. Return with findings
4. Rephrase question with research context
5. Re-ask user

EXAMPLE:
User: "I don't know what pattern to use"
→ Dispatch: "Research authentication patterns in codebase"
→ Return: "Found 3 patterns: OAuth (5 files), JWT (8 files), Session (3 files)"
→ Rephrase: "Research shows we use OAuth in [areas] and JWT in [areas]. Which fits better for [feature]?"
```

**CLARIFICATION Handler:**
```markdown
ACTION:
1. Rephrase question with more context from research
2. Provide examples from codebase
3. Re-ask

EXAMPLE:
User: "What do you mean by 'integration point'?"
→ Rephrase: "By integration point, I mean where [feature] connects to existing code.
   Research shows similar features integrate via:
   A) Event emitters (src/events/*.ts)
   B) Direct function calls (src/core/*.ts)
   C) Message queues (src/queue/*.ts)
   Which pattern fits [feature]?"
```

**SKIP Handler:**
```markdown
ACTION:
1. Mark question as out-of-scope
2. Document in design_context.explicit_exclusions
3. Continue to next question
```

**OPEN_ENDED Handler:**
```markdown
ACTION:
1. Parse for intent
2. Update design_context with interpretation
3. Confirm interpretation: "I understand this as [interpretation]. Correct?"
4. If confirmed, continue. If not, clarify.
```

### 3. Regeneration Logic

```markdown
WHEN TO REGENERATE QUESTIONS:
- After any research dispatch completes
- After disambiguation of related ambiguity
- After user provides context that changes understanding

HOW TO REGENERATE:
1. Take updated design_context
2. Re-run question generation logic for current category
3. Compare old questions to new questions
4. Present new questions if meaningfully different
5. Otherwise, continue with original questions

EXAMPLE:
Original: "Should this feature use authentication?"
After research: "Should this feature use JWT (found in 8 files) or OAuth (found in 5 files)?"
```

### 4. Loop Control

```markdown
MAX_ITERATIONS: None (user controls)
TERMINATION CONDITIONS:
- User provides direct answer
- User skips question
- User requests to move on

PROGRESS TRACKING:
- Track questions answered vs total
- Show progress after each answer: "[Category]: 3/5 questions answered"
```

### 5. Integration Points

**Skills Using ARH:**
- implementing-features (Phase 1.5.0, 1.5.2)
- fact-checking (evidence validation questions)
- finding-dead-code (usage confirmation questions)
- scientific-debugging (hypothesis validation questions)
- worktree-merge (conflict resolution questions)

**How to Reference:**
```markdown
<!-- In skill SKILL.md -->
RESPONSE PROCESSING:
See patterns/adaptive-response-handler.md for full ARH pattern.

IMPLEMENTATION:
[Specific ARH usage for this skill]
```

### 6. Example Flow

```markdown
USER REQUEST: "Build authentication feature"

PHASE 1: Research
→ Subagent finds: JWT in 8 files, OAuth in 5 files, session in 3 files

PHASE 1.5.0: Disambiguation
Question: "Research found 3 auth patterns. Which should we use?"
User: "What's the difference? I don't know which is better."

ARH PROCESSING:
- Detect: UNKNOWN type
- Action: Dispatch research subagent
  "Research: Compare JWT vs OAuth vs session auth
   Context: User unsure of differences
   Return: Pros/cons of each pattern in our codebase"

→ Subagent returns comparison

ARH REGENERATES QUESTION:
"Research shows:
- JWT: Stateless, used in API endpoints (src/api/*), supports mobile clients
- OAuth: Third-party integration (src/integrations/*), complex setup
- Session: Simple, used in admin panel (src/admin/*), server-side state

For [feature], which approach fits best?
A) JWT (stateless, mobile-friendly)
B) OAuth (third-party logins)
C) Session (simple, server-side)
D) Something else

Your choice: ___"

User: "A - JWT makes sense for our mobile app"

ARH PROCESSING:
- Detect: DIRECT_ANSWER
- Action: Update design_context.architecture.auth_pattern = "JWT"
- Next: Continue to next question
```

## Usage Guidelines

1. **Always detect response type first** - Don't assume user will follow multiple choice
2. **Dispatch research liberally** - "I don't know" should trigger research, not guessing
3. **Regenerate after new information** - Don't keep stale questions
4. **Confirm interpretations** - For open-ended answers, verify understanding
5. **Track progress** - Show users where they are in the process
6. **No iteration limits** - Let user control when to proceed

## ARH Implementation Model

**CRITICAL CLARIFICATION:** The Adaptive Response Handler (ARH) is NOT executable code. It is a set of LLM instructions that Claude follows during execution.

### What ARH Is

ARH is a **prompt pattern** - a structured set of instructions stored in `patterns/adaptive-response-handler.md` that tells Claude how to process user responses intelligently.

**How Skills "Use" ARH:**
1. Skill SKILL.md includes reference: "See patterns/adaptive-response-handler.md for ARH pattern"
2. Claude reads ARH pattern document as part of skill execution
3. Claude follows the instructions in ARH to process user responses
4. No code execution - Claude interprets and applies the pattern

**Skill Execution Model:**
```
User invokes skill → Claude reads SKILL.md → Skill references ARH pattern →
Claude reads patterns/adaptive-response-handler.md → Claude follows instructions →
Claude detects response type → Claude applies appropriate handler →
Claude dispatches subagent if needed → Claude regenerates questions based on new info
```

**Example:**
- User responds: "I don't know which pattern to use"
- Claude reads ARH instructions: "If response matches UNKNOWN type, dispatch research subagent"
- Claude follows instruction: Creates Task/Explore subagent to research patterns
- Subagent returns findings
- Claude reads ARH: "After research, regenerate questions with new context"
- Claude generates new question incorporating research findings

**Key Point:** ARH is documentation of how Claude should behave, not executable code. Skills reference it so Claude knows the correct behavior pattern to follow.
