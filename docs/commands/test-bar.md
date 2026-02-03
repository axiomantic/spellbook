# /test-bar

## Command Content

``````````markdown
# MISSION

Analyze the current branch's code changes against its merge base, identify every conditional rendering path and its data triggers, then generate a self-contained floating React overlay component with one-click scenario buttons. Each button transforms client-side state (store, entitlements, feature flags, API responses) and navigates to the correct page so the developer can visually QA each scenario without manual data setup.

<ROLE>
QA Test Apparatus Engineer. You build temporary, throwaway UI test harnesses that let developers click through every visual state a feature introduces. You are thorough about scenario identification and surgical about code injection. Your test bars catch visual regressions that automated tests miss.
</ROLE>

## Invariant Principles

1. **Throwaway code** - Everything you create will be reverted via `/test-bar-remove`. Optimize for "works correctly" over "production quality." But it MUST work.
2. **No test file changes** - Only modify source/component files. Never touch `__tests__/`, `*.test.*`, or `*.spec.*` files.
3. **Track all changes** - Write a manifest so `/test-bar-remove` can cleanly revert. No untracked modifications.
4. **Dev-only guard** - Wrap ALL injected code in `__DEV__` or `process.env.NODE_ENV !== 'production'` checks.
5. **Minimal footprint** - Inject at the highest possible level. One overlay component, one injection point. Scattered changes are forbidden.
6. **Reversible state** - Every scenario button must be reversible. Capture original state before overriding. "Reset" restores it.

---

## Phase 1: Branch Analysis

### Step 1: Determine merge base and changed files

```bash
# Detect target branch (PR base or default)
TARGET=$(git rev-parse --abbrev-ref HEAD@{upstream} 2>/dev/null | sed 's|origin/||' || echo "master")
MERGE_BASE=$(git merge-base HEAD "origin/$TARGET" 2>/dev/null || git merge-base HEAD origin/master 2>/dev/null || git merge-base HEAD origin/main)

# Detect source directory (src/ is most common, but verify)
if [ -d "src" ]; then
  SRC_DIR="src"
elif [ -d "app" ]; then
  SRC_DIR="app"
elif [ -d "lib" ]; then
  SRC_DIR="lib"
else
  echo "ERROR: No src/, app/, or lib/ directory found. Identify the source directory manually."
  exit 1
fi

# Changed source files only (exclude tests, configs, assets)
git diff "$MERGE_BASE"...HEAD --name-only --diff-filter=ACMR \
  | grep -E '\.(tsx?|jsx?)$' \
  | grep -v -E '(__tests__|\.test\.|\.spec\.|\.stories\.|\.mock\.)' \
  | sort
```

If no changed source files are found, report "No source file changes detected on this branch" and exit.

### Step 2: Read and analyze each changed file

For each changed file, read the FULL file (not just the diff) and identify:

| Category | What to Look For | Examples |
|----------|-----------------|---------|
| **Conditional rendering** | `if/else`, ternaries, `&&` guards, `switch` that produce different UI | `{isPro && <ProBadge/>}`, `isLoading ? <Spinner/> : <Content/>` |
| **Data triggers** | Store selectors, props, hooks, API response fields that control rendering | `useSelector(state => state.user.plan)`, `data?.subscription?.status` |
| **Feature flags** | Any gating mechanism | `useFeatureFlag('new_checkout')`, `isEnabled('beta_ui')` |
| **Entitlements / plans** | User tier, plan type, permission checks | `provider.plan === 'pro'`, `hasEntitlement('custom_website')` |
| **Navigation targets** | Routes where affected components render | `<Route path="/settings" />`, `navigation.navigate('Profile')` |
| **Error/empty states** | Fallback UI for missing data, errors, empty lists | `{items.length === 0 && <EmptyState/>}`, `{error && <ErrorBanner/>}` |
| **Loading states** | Skeleton screens, spinners, placeholders | `{isLoading && <Skeleton/>}` |

### Step 3: Detect project framework

Identify the state management and routing used by the project:

```bash
# Use SRC_DIR detected in Phase 1 (defaults to src/)

# State management
grep -rl "configureStore\|createStore\|@rematch\|createModel" "$SRC_DIR"/ --include="*.ts" --include="*.tsx" | head -3
grep -rl "zustand\|create(" "$SRC_DIR"/ --include="*.ts" --include="*.tsx" | head -3
grep -rl "useContext\|createContext" "$SRC_DIR"/ --include="*.ts" --include="*.tsx" | head -3

# Routing
grep -rl "react-router\|BrowserRouter\|useNavigate\|useHistory" "$SRC_DIR"/ --include="*.ts" --include="*.tsx" | head -3
grep -rl "next/router\|next/navigation\|useRouter" "$SRC_DIR"/ --include="*.ts" --include="*.tsx" | head -3
grep -rl "@react-navigation" "$SRC_DIR"/ --include="*.ts" --include="*.tsx" | head -3

# Store location (for dispatch/state override)
find "$SRC_DIR"/ -name "store.ts" -o -name "store.tsx" -o -name "store.js" -o -name "store/index.*" 2>/dev/null | head -5
```

Record the detected framework for use in Phase 3.

---

## Phase 2: Scenario Matrix

Build a scenario matrix from the analysis. Each scenario must be specific and testable.

**Required columns:**

| Scenario Name | Data Overrides | Navigation Target | Expected Visual Result |
|---------------|---------------|-------------------|----------------------|
| Short, descriptive label (e.g., "Pro plan active") | Exact state/prop changes (e.g., `store.user.plan = 'pro'`) | Route path or screen name | What the developer should see |

**Scenario categories to cover (check all that apply):**

- [ ] Happy path (primary feature working correctly)
- [ ] Each conditional branch (every if/else, every ternary arm)
- [ ] Empty state (no data, zero items)
- [ ] Error state (API failure, invalid data)
- [ ] Loading state (in-progress fetch)
- [ ] Permission/entitlement variants (free vs pro vs enterprise)
- [ ] Feature flag on vs off
- [ ] Edge cases (long text, missing optional fields, boundary values)

<CRITICAL>
Present the scenario matrix to the user for confirmation before proceeding to Phase 3.
Include: "Should I add, remove, or modify any scenarios?"
</CRITICAL>

---

## Phase 3: Implementation

### Step 1: Create the overlay component

Create a single self-contained file: `src/components/TestScenarioBar.tsx` (or `.jsx` if project uses JS).

The component MUST include:

**Visual design:**
- Fixed position, bottom-right corner
- `z-index: 99999`
- Bright orange/yellow border (2px solid #ff6b00) to be visually obvious as test apparatus
- Semi-transparent dark background (`rgba(0, 0, 0, 0.85)`)
- Small monospace font (11px)
- Max height 50vh with scroll for many scenarios
- Draggable via a drag handle at the top (use mouse events, no external deps)
- Collapsed/expanded toggle (starts expanded)
- Width: 280px

**Required UI elements:**
- Header: "Test Scenarios" with drag handle and collapse toggle
- Active scenario indicator (green highlight on active button)
- One button per scenario, with short label
- "Reset" button that restores original state (always visible)
- "Close" button that unmounts the bar entirely

**State management integration (adapt to detected framework):**

For Redux/Rematch:
```tsx
// Capture original state on mount
const originalState = useRef(store.getState());

// Override for a scenario
const applyScenario = (overrides: Record<string, any>) => {
  Object.entries(overrides).forEach(([path, value]) => {
    // Use store.dispatch for Rematch models or Redux actions
    // path format: "modelName/setState" or action type
    store.dispatch({ type: path, payload: value });
  });
};

// Reset
const resetState = () => {
  // Dispatch original values back
};
```

For Zustand:
```tsx
const applyScenario = (overrides: Record<string, any>) => {
  useStore.setState(overrides);
};
```

For Context/props: Create a wrapper provider that overrides context values.

**Navigation integration (adapt to detected framework):**

For React Router: `useNavigate()` or `useHistory().push()`
For Next.js: `useRouter().push()`
For React Navigation: `navigation.navigate()`

### Step 2: Create scenario data file

Create `src/components/testScenarioData.ts` with the scenario definitions:

```typescript
interface TestScenario {
  id: string;
  label: string;
  description: string;
  stateOverrides: Record<string, any>;
  navigationTarget?: string;
  setupFn?: () => void; // For scenarios needing imperative setup
  teardownFn?: () => void;
}

export const scenarios: TestScenario[] = [
  // ... generated from the matrix
];
```

### Step 3: Inject the overlay

1. Find the app's root component or top-level layout file
2. Add a dev-only import and render:

```tsx
// DEV-ONLY: Test scenario bar (remove with /test-bar-remove)
const TestScenarioBar = __DEV__
  ? require('./components/TestScenarioBar').default
  : null;

// Inside the component's return:
{__DEV__ && TestScenarioBar && <TestScenarioBar />}
```

Prefer `__DEV__` for React Native projects. Use `process.env.NODE_ENV !== 'production'` for web projects. Check which pattern the project already uses.

<CRITICAL>
The injection point MUST be a SINGLE location. Do not scatter test bar code across multiple files beyond the overlay component file, the scenario data file, and the one injection point.
</CRITICAL>

---

## Phase 4: Write Manifest

Write the manifest to `~/.local/spellbook/test-bar-manifest.json`:

```json
{
  "version": 1,
  "created_at": "<ISO timestamp>",
  "branch": "<current branch name>",
  "project_root": "<absolute path to project root>",
  "merge_base": "<merge base commit hash>",
  "files_created": [
    "src/components/TestScenarioBar.tsx",
    "src/components/testScenarioData.ts"
  ],
  "files_modified": [
    {
      "path": "src/App.tsx",
      "injection_type": "import_and_render",
      "description": "Added TestScenarioBar import and render"
    }
  ],
  "scenarios": ["scenario-id-1", "scenario-id-2"],
  "framework": {
    "state": "redux|zustand|context",
    "routing": "react-router|next|react-navigation",
    "dev_guard": "__DEV__|process.env.NODE_ENV"
  }
}
```

<CRITICAL>
The manifest MUST be written BEFORE any verification step. If verification fails and the user runs `/test-bar-remove`, the manifest must already exist to enable clean removal.
</CRITICAL>

---

## Phase 5: Verification

1. **Compile check:** Run the project's type-check or build command to confirm no type errors were introduced

```bash
# Try in order, use first that exists
npx tsc --noEmit 2>&1 | tail -20 || npm run typecheck 2>&1 | tail -20 || echo "No typecheck command found"
```

2. **Import check:** Verify all new imports resolve

```bash
grep -n "import.*TestScenarioBar\|require.*TestScenarioBar" src/ -r
grep -n "import.*testScenarioData\|require.*testScenarioData" src/ -r
```

3. **Dev guard check:** Verify all injected code is behind dev guards

```bash
# Every file we modified or created should have a dev guard
grep -n "__DEV__\|NODE_ENV" <each file from manifest>
```

If any check fails:
1. Attempt to fix the issue (missing import, type error, missing guard)
2. Re-run the failing check
3. If the issue cannot be fixed programmatically, report it in the Output section under "Known Issues" and inform the user what manual action is needed

---

## Output

After completion, display:

```
Test Bar Injected

Branch: <branch-name>
Merge Base: <short-hash>
Framework: <state-mgmt> + <router>

Scenarios:
  [1] Scenario Name - Brief description
  [2] Scenario Name - Brief description
  ...

Files created:
  - src/components/TestScenarioBar.tsx
  - src/components/testScenarioData.ts

Files modified:
  - src/App.tsx (injected TestScenarioBar import + render)

Manifest: ~/.local/spellbook/test-bar-manifest.json

To remove all test apparatus: /test-bar-remove
```

---

<FORBIDDEN>
- Modifying test files (`__tests__/`, `*.test.*`, `*.spec.*`)
- Injecting code without dev-only guards
- Creating scenarios without presenting the matrix for user confirmation
- Skipping the manifest write
- Modifying more than ONE existing file for injection (the overlay itself is new files)
- Using external npm dependencies not already in the project
- Leaving any injected code without a cleanup path
- Hardcoding store paths without reading the actual store structure
- Assuming Redux when the project might use Zustand, Context, or something else
</FORBIDDEN>

<analysis>
This command must adapt to each project's specific framework, store shape, and routing. The Phase 1 framework detection is critical for generating working code. The scenario matrix in Phase 2 is the intellectual core: identifying every visual state the branch introduces. Phase 3 translates that into working throwaway UI.
</analysis>

<reflection>
Before reporting completion, verify:
- Did I read the FULL changed files or just the diff? (Must be full files for context)
- Does every scenario in the matrix have a corresponding button in the overlay?
- Is every piece of injected code behind a dev guard?
- Does the manifest accurately list ALL created and modified files?
- Can `/test-bar-remove` cleanly revert everything using only the manifest?
</reflection>
``````````
