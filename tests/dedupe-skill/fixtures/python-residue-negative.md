# Python Residue Negative Control Fixture

This file deliberately contains Python residue patterns that the D2 gate
(`verify-no-python.sh`) must catch. If any of these patterns slip through
the gate, D2 has a false-negative bug.

Each paragraph below contains exactly one pattern.

---

NEGATIVE CONTROL — D2 must catch this:

    import os

NEGATIVE CONTROL — D2 must catch this:

    from pathlib import Path

NEGATIVE CONTROL — D2 must catch this: install via setup.py if needed.

NEGATIVE CONTROL — D2 must catch this:

    #!/usr/bin/env python3

NEGATIVE CONTROL — D2 must catch this:

    python3 script.py --flag

NEGATIVE CONTROL — D2 must catch this:

    pip install foo

NEGATIVE CONTROL — D2 must catch this:

    python -m pytest tests/
