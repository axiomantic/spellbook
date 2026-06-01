"""pytest path bootstrap so `import roundup` resolves from the skill dir.

Task 2, step 2 (impl plan). Adds the skill directory (parent of tests/) to
sys.path so the self-contained `roundup.py` helper can be imported directly.

Also adds the tests directory itself to sys.path so shared test helpers
(e.g. `_matchers`) can be imported across test modules.
"""
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(TESTS_DIR)
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)
