#!/usr/bin/env python3
"""
Distill Session Helper Script

Provides CLI commands for session discovery, chunking, and content extraction
for the /distill-session command.
"""

import sys
import json
import argparse
import os
import glob
from typing import Dict, List, Any, Optional
from datetime import datetime

__version__ = '1.0.0'

# Python 3.8+ version check
if sys.version_info < (3, 8):
    print("Error: Python 3.8+ required", file=sys.stderr)
    sys.exit(5)


# Shared helper functions (used by multiple tasks in parallel)
def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """Load JSONL file into list of message objects."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Session file not found: {file_path}")

    messages = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Invalid JSON at line {line_num}",
                    e.doc, e.pos
                )
    return messages


def find_last_compact_boundary(messages: List[Dict[str, Any]]) -> Optional[int]:
    """Find line number of last compact_boundary, or None if none exists."""
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get('type') == 'system' and msg.get('subtype') == 'compact_boundary':
            return i
    return None
