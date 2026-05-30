"""pytest path bootstrap so `import roundup` resolves from the skill dir.

Task 2, step 2 (impl plan). Adds the skill directory (parent of tests/) to
sys.path so the self-contained `roundup.py` helper can be imported directly.
"""
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
