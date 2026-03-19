"""Session operations: loading, metadata extraction, and chunking."""

import json
import os
import glob
from typing import Dict, List, Any, Optional


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """
    Load JSONL file into list of message objects.

    Args:
        file_path: Absolute path to .jsonl session file

    Returns:
        List of message dictionaries

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON is malformed (includes line number)
    """
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
    """
    Find line number of last compact_boundary, or None if none exists.

    Args:
        messages: List of message dictionaries

    Returns:
        Index of last compact boundary message, or None
    """
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get('type') == 'system' and msg.get('subtype') == 'compact_boundary':
            return i
    return None


def extract_custom_title(messages: List[Dict[str, Any]]) -> Optional[str]:
    """
    Extract custom title from session messages (last one wins).

    Custom titles are stored as messages with type='custom-title' and
    a 'customTitle' field. If multiple exist, the last one takes precedence.

    Args:
        messages: List of message dictionaries

    Returns:
        Custom title string, or None if no custom title exists
    """
    custom_title = None
    for msg in messages:
        if msg.get('type') == 'custom-title':
            custom_title = msg.get('customTitle')
    return custom_title


def split_by_char_limit(session_path: str, start_line: int, char_limit: int) -> List[List[int]]:
    """
    Calculate chunk boundaries that fit within char_limit.

    Always splits at message boundaries (never mid-message). Returns list of
    [start_line, end_line] pairs. Note: end_line is exclusive.

    Args:
        session_path: Absolute path to .jsonl file
        start_line: Starting line number (0-indexed)
        char_limit: Maximum characters per chunk

    Returns:
        List of [start, end] chunk boundaries

    Raises:
        ValueError: If start_line out of bounds or char_limit invalid
        FileNotFoundError: If session file doesn't exist
    """
    messages = load_jsonl(session_path)

    if start_line < 0 or start_line >= len(messages):
        raise ValueError(
            f"Invalid start_line: {start_line} "
            f"(must be 0 <= start_line < {len(messages)})"
        )

    if char_limit <= 0:
        raise ValueError(f"Invalid char_limit: {char_limit} (must be > 0)")

    chunks = []
    current_chunk_start = start_line
    current_chunk_chars = 0

    for i in range(start_line, len(messages)):
        msg = messages[i]
        msg_chars = len(json.dumps(msg))

        # If adding this message would exceed limit, close current chunk
        if current_chunk_chars + msg_chars > char_limit and current_chunk_chars > 0:
            chunks.append([current_chunk_start, i])
            current_chunk_start = i
            current_chunk_chars = 0

        current_chunk_chars += msg_chars

    # Add final chunk if there are remaining messages
    if current_chunk_start < len(messages):
        chunks.append([current_chunk_start, len(messages)])

    return chunks


def list_sessions_with_samples(project_dir: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    List recent sessions with metadata and content samples.

    Returns rich metadata including custom titles, timestamps, message counts,
    and content samples for AI interpretation.

    Args:
        project_dir: Path to project's session directory
        limit: Maximum sessions to return (default 5)

    Returns:
        List of session metadata dictionaries, sorted by last_activity descending

    Raises:
        FileNotFoundError: If project_dir doesn't exist
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    sessions = []

    for jsonl_file in glob.glob(f"{project_dir}/*.jsonl"):
        try:
            messages = load_jsonl(jsonl_file)
            if not messages:
                continue

            # Extract metadata
            slug = None
            first_timestamp = None
            last_timestamp = None

            for msg in messages:
                if msg.get('slug'):
                    slug = msg['slug']
                if msg.get('timestamp'):
                    if first_timestamp is None:
                        first_timestamp = msg['timestamp']
                    last_timestamp = msg['timestamp']

            # Calculate statistics
            total_chars = sum(len(json.dumps(msg)) for msg in messages)

            # Count compact boundaries
            compact_count = sum(
                1 for msg in messages
                if msg.get('type') == 'system' and msg.get('subtype') == 'compact_boundary'
            )

            last_compact_line = find_last_compact_boundary(messages)

            # Extract custom title
            custom_title = extract_custom_title(messages)

            # Extract first user message
            first_user_msg = None
            for msg in messages:
                if msg.get('type') == 'user':
                    content = msg.get('message', {}).get('content', '')
                    first_user_msg = content[:500] if isinstance(content, str) else str(content)[:500]
                    break

            # Extract last compact summary if exists
            last_compact_summary = None
            if last_compact_line is not None and last_compact_line + 1 < len(messages):
                next_msg = messages[last_compact_line + 1]
                if next_msg.get('isCompactSummary'):
                    last_compact_summary = next_msg.get('message', {}).get('content', '')

            # Extract recent messages (last 5)
            recent_messages = []
            for msg in messages[-5:]:
                if msg.get('type') in ['user', 'assistant']:
                    content = msg.get('message', {}).get('content', '')
                    if isinstance(content, list):
                        content = json.dumps(content)
                    recent_messages.append(str(content)[:500])

            sessions.append({
                'slug': slug,
                'custom_title': custom_title,
                'path': jsonl_file,
                'created': first_timestamp,
                'last_activity': last_timestamp,
                'message_count': len(messages),
                'char_count': total_chars,
                'compact_count': compact_count,
                'last_compact_line': last_compact_line,
                'first_user_message': first_user_msg,
                'last_compact_summary': last_compact_summary,
                'recent_messages': recent_messages
            })
        except Exception:
            # Skip files that can't be parsed (graceful degradation)
            continue

    # Sort by last activity (most recent first)
    sessions.sort(key=lambda x: x.get('last_activity') or '', reverse=True)

    # Limit results
    return sessions[:limit]
