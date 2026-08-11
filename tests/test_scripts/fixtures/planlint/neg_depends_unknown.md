**Schema:** planlint-v1

### Task 1: A

**Files:**
- Create: `a.py`

**Depends:** none

**Check:** `pytest a`

### Task 2: B

**Files:**
- Create: `b.py`

**Depends:** Task 1

**Check:** `pytest b`

### Task 3: C

**Files:**
- Create: `c.py`

**Depends:** Task 9

**Check:** `pytest c`
