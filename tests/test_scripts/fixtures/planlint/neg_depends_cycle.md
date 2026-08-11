**Schema:** planlint-v1

### Task 1: A

**Files:**
- Create: `a.py`

**Depends:** Task 2

**Check:** `pytest a`

### Task 2: B

**Files:**
- Create: `b.py`

**Depends:** Task 3

**Check:** `pytest b`

### Task 3: C

**Files:**
- Create: `c.py`

**Depends:** Task 1

**Check:** `pytest c`
