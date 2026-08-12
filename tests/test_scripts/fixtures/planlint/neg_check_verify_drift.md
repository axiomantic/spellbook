**Schema:** planlint-v1

### Task 1: Drifted verify step

**Files:**
- Create: `a.py`

**Depends:** none

**Check:** `pytest tests/x.py::test_a -v`

**Step 1: Write failing test**
Some test code.

**Step 2: Verify failure**
Run: `pytest tests/x.py::test_a -v`
Expected: FAIL

**Step 3: Minimal implementation**
Some implementation code.

**Step 4: Verify pass**
Run: `pytest tests/x.py::test_a`
Expected: PASS

### Task 2: Matching verify step

**Files:**
- Create: `b.py`

**Depends:** none

**Check:** `pytest tests/y.py::test_b -v`

**Step 4: Verify pass**
Run: `pytest tests/y.py::test_b -v`
Expected: PASS
