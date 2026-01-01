"""Pytest configuration for spellbook tests."""

import sys
from pathlib import Path

# Add project root to path so spellbook_mcp can be imported
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
