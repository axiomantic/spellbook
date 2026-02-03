# /dead-code-analyze

## Command Content

``````````markdown
# MISSION

Extract code items from scope, present for triage, verify usage, and re-scan until fixed-point.

**Part of the dead-code-* command family.** Run after `/dead-code-setup` completes.

**Prerequisites:** Git safety completed, scope selected.

## Invariant Principles

1. **Assume dead until proven alive** - Start from the premise that code is unused; evidence of usage clears the item
2. **Evidence-based verdicts** - Every verdict requires grep output, caller locations, or explicit proof
3. **Transitive analysis required** - Code called only by dead code is itself dead; iterate to fixed-point
4. **Write-only detection** - Setters without getter usage indicate dead features, not just dead functions

---

## Phase 2: Code Item Extraction

Extract ALL added code items from scoped files.

### What to Extract

| Item Type | Examples | How to Identify |
|-----------|----------|-----------------|
| **Procedures/Functions** | `proc foo()`, `func bar()`, `def baz()` | Declaration lines |
| **Types/Classes** | `type Foo = object`, `class Bar` | Type definitions |
| **Object Fields** | `field: int` in type definitions | Field declarations |
| **Imports/Includes** | `import foo`, `from x import y` | Import statements |
| **Methods** | Procs on objects, class methods | Method definitions |
| **Constants** | `const X = 5`, `#define X` | Constant declarations |
| **Macros/Templates** | `macro foo()`, `template bar()` | Macro/template defs |
| **Global Variables** | Top-level vars | Variable declarations |
| **Getters/Setters** | Accessor procs/methods | Property accessors |
| **Iterators** | `iterator items()`, `for x in y` | Iterator definitions |
| **Convenience Wrappers** | Simple forwarding functions | Thin wrapper procs |

### Language-Specific Patterns

**Nim:**
```nim
proc|func|method|macro|template|iterator NAME
type NAME = (object|enum|distinct|...)
field: TYPE in object definitions
import|from|include MODULE
const|let|var NAME at top level
```

**Python:**
```python
def NAME, class NAME, import/from statements
```

**TypeScript/JavaScript:**
```typescript
function NAME, class NAME, const/let/var at top level
export/import statements
```

### Extraction Strategy

For each added/modified file in scope:

1. Get the diff of added lines: `git diff <base> <file> | grep "^+"`
2. Parse added lines for code item declarations
3. Record: `{type, name, location, signature}`
4. Group symmetric pairs (get/set, create/destroy, etc.)
5. **For each setter/store call**: Record corresponding getter/read pattern to check later
6. **For each field assignment**: Record field read patterns to check later

---

## Phase 3: Initial Triage

<RULE>Present ALL extracted items upfront before verification begins. User must see full scope.</RULE>

Display items grouped by type with counts:

```
## Code Items Found: 47

### Procedures/Functions (23 items)
1. proc getDeferredExpr(t: PType): PNode - compiler/semtypes.nim:342
2. proc setDeferredExpr(t: PType, n: PNode) - compiler/semtypes.nim:349
3. proc clearDeferredExpr(t: PType) - compiler/semtypes.nim:356
...

### Type Fields (12 items)
24. deferredPragmas: seq[PNode] - compiler/ast.nim:234
...

### Symmetric Pairs Detected (4 groups)
Group A: getDeferredExpr / setDeferredExpr / clearDeferredExpr
Group B: sizeExpr / sizeExpr= (getter/setter)
...

Proceed with verification? (yes/no)
```

**Symmetric Pairs**: If you see `getFoo` / `setFoo` / `clearFoo`, or `foo` / `foo=`, group them. They often live or die together.

---

## Phase 4: Verification

<RULE>For EVERY code item, search the ENTIRE codebase for usages. Start from "dead" assumption.</RULE>

### Step 1: Generate "Dead Code" Claim

```
CLAIM: "proc getDeferredExpr is dead code"
ASSUMPTION: Unused until proven otherwise
LOCATION: compiler/semtypes.nim:342
```

### Step 2: Search for Usage Evidence

**Search Strategy:**

1. **Direct calls**: `grep -rn "getDeferredExpr" --include="*.nim" <repo_root>`
2. **Exclude definition**: Filter out the line where it's defined
3. **Check callers**: Are there calls outside the definition?
4. **Check exports**: Is it exported and could be used externally?
5. **Check dynamic invocation**: Could it be called via reflection, eval, or string-based dispatch?

**Evidence Categories:**

| Evidence Type | Verdict | What to Check |
|---------------|---------|---------------|
| **Zero callers** | DEAD | No grep results except definition |
| **Self-call only** | DEAD | Only calls itself (recursion) |
| **Write-only** | DEAD | Setter/store called but getter/read never called |
| **Dead caller only** | TRANSITIVE DEAD | Only called by other dead code |
| **Test-only** | MAYBE DEAD | Only called in tests (ask user) |
| **One+ live callers** | ALIVE | Real usage found |
| **Exported API** | MAYBE ALIVE | Public API, might be used externally |
| **Dynamic possible** | INVESTIGATE | Check for reflection/eval patterns |

### Step 3: Write-Only Dead Code Detection

Check for code that STORES values but stored values are NEVER READ:

**Patterns:**
1. **Setter without getter**: `setFoo()` has callers but `getFoo()` has zero callers
2. **Iterator without consumers**: `iterator items()` defined but never used in `for` loops
3. **Field assigned but never read**: Field appears on LHS of `=` but never on RHS
4. **Collection stored but never accessed**: `seq.add(x)` called but seq never iterated

**Algorithm:**
```
FOR each setter/store found:
  Search for corresponding getter/read
  IF setter has callers BUT getter has zero:
    → WRITE-ONLY DEAD
    Mark BOTH setter and getter as dead (entire feature unused)
```

### Step 4: Transitive Dead Code Detection

If item only called by other items, check if ALL callers are dead:

```
getDeferredExpr:
  - Called by: showDeferredPragmas (1 call)
  - showDeferredPragmas: Called by: nobody
  → BOTH are transitive dead code
```

**Algorithm:**
```
WHILE changes detected:
  FOR each item with callers:
    IF ALL callers are marked dead:
      Mark item as TRANSITIVE DEAD
  Repeat until no new transitive dead code found (fixed point)
```

### Step 5: Remove and Test Verification (Optional)

For high-confidence dead code, offer experimental verification:

**Protocol:**
1. Ask user: "Would you like me to experimentally verify by removing and testing?"
2. If yes, create temporary git worktree or branch
3. Remove the suspected dead code
4. Run the test suite
5. If tests pass → definitive proof code was dead
6. If tests fail → code was used (or tests are incomplete)
7. Restore original state

**When to offer:**
- User uncertain about grep-based verdict
- Code looks "important" but has zero callers
- High-value cleanup (large amount of code)

### Step 6: Symmetric Pair Analysis

For detected symmetric pairs:

```
IF ANY of {getFoo, setFoo, clearFoo} is ALIVE → all potentially alive
IF ALL are dead → entire group is dead
IF SOME alive, SOME dead → flag asymmetry for user review
```

---

## Phase 5: Iterative Re-scanning

<RULE>After identifying dead code, re-scan for newly orphaned code. Removal may cascade.</RULE>

**Why Re-scan:**
```
Round 1: evaluateDeferredFieldPragmas → 0 callers → DEAD
Round 2: iterator deferredPragmas → only called by above → NOW TRANSITIVE DEAD
Round 3: setDeferredExpr → stores to iterator that's dead → NOW WRITE-ONLY DEAD
```

**Re-scan Algorithm:**
1. Mark initial dead code (zero callers)
2. Re-extract remaining items, excluding already-marked-dead
3. Re-run verification on remaining items
4. Check for newly transitive dead code
5. Check for newly write-only dead code (getter removed → setter orphaned)
6. Repeat until no new dead code found (fixed point)

**Cascade Detection:**
- If removal of A makes B dead → note "B depends on A" in report
- Present cascade chains: "Removing X enables removing Y, Z"

---

## Output

This command produces:
1. List of all code items with verdicts
2. Evidence for each verdict (grep output, caller locations)
3. Cascade chains documented
4. Fixed-point reached

**Next:** Run `/dead-code-report` to generate the findings report.
``````````
