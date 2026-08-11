**Schema:** planlint-v1

### Task 1: Has an unclosed fence

**Files:**
- Create: `spellbook/x.py`

**Depends:** none

**Check:** `pytest -q`

**Step 1: Write failing test**
```
this fence never closes

### Task 2: A second task below the broken fence

**Files:**
- Create: `spellbook/y.py`

**Depends:** Task 1

**Check:** `pytest -q -k y`

### Task 3: A third task

**Files:**
- Create: `spellbook/z.py`

**Depends:** Task 2

**Check:** `pytest -q -k z`
