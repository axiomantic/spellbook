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


def split_by_char_limit(session_path: str, start_line: int, char_limit: int) -> List[tuple]:
    """
    Calculate chunk boundaries that fit within char_limit.

    Returns: [(start_line, end_line), ...]

    Always splits at message boundaries (never mid-message).
    """
    messages = load_jsonl(session_path)

    if start_line < 0 or start_line >= len(messages):
        raise ValueError(f"Invalid start_line: {start_line}")

    if char_limit <= 0:
        raise ValueError(f"Invalid char_limit: {char_limit}")

    chunks = []
    current_chunk_start = start_line
    current_chunk_chars = 0

    for i in range(start_line, len(messages)):
        msg = messages[i]
        msg_chars = len(json.dumps(msg))

        # If adding this message would exceed limit, close current chunk
        if current_chunk_chars + msg_chars > char_limit and current_chunk_chars > 0:
            chunks.append((current_chunk_start, i))
            current_chunk_start = i
            current_chunk_chars = 0

        current_chunk_chars += msg_chars

    # Add final chunk if there are remaining messages
    if current_chunk_start < len(messages):
        chunks.append((current_chunk_start, len(messages)))

    return chunks


def extract_chunk(session_path: str, start_line: int, end_line: int) -> str:
    """
    Extract messages from start_line to end_line.
    Returns JSON array of messages.
    """
    messages = load_jsonl(session_path)

    if start_line < 0 or end_line > len(messages) or start_line >= end_line:
        raise ValueError(
            f"Invalid range: start={start_line}, end={end_line}, total={len(messages)}"
        )

    chunk = messages[start_line:end_line]
    return json.dumps(chunk, indent=2)
