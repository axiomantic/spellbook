# Sample Feature Implementation Plan

**Schema:** planlint-v1

---

### Task 1: First component

**Files:**
- Create: `spellbook/sample/first.py`
- Test: `tests/test_scripts/test_sample_first.py`

**Depends:** none

**Check:** `pytest tests/test_scripts/test_sample_first.py -v`

**Step 1: Write failing test**
Some test code here.

**Step 2: Verify failure**
Run: `pytest tests/test_scripts/test_sample_first.py -v`
Expected: FAIL

**Step 3: Minimal implementation**
Some implementation code here.

**Step 4: Verify pass**
Run: `pytest tests/test_scripts/test_sample_first.py -v`
Expected: PASS

**Step 5: Commit**
`git add . && git commit -m "feat: first component"`

### Task 2: Second component

**Files:**
- Create: `spellbook/sample/second.py`
- Modify: `spellbook/sample/first.py`
- Test: `tests/test_scripts/test_sample_second.py`

**Depends:** Task 1

**Check:** `pytest tests/test_scripts/test_sample_second.py -v`

**Step 1: Write failing test**
More test code.

**Step 4: Verify pass**
Run: `pytest tests/test_scripts/test_sample_second.py -v`
Expected: PASS
