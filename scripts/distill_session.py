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


def get_last_compact_summary(session_path: str) -> Optional[Dict[str, Any]]:
    """
    Find the most recent compact summary in a session.

    Returns: {
        'line_number': int,      # Line of compact_boundary
        'summary_content': str,  # The actual summary text
        'timestamp': str,        # When compact happened
    }
    Or None if no compact exists.
    """
    messages = load_jsonl(session_path)

    last_boundary_idx = find_last_compact_boundary(messages)

    if last_boundary_idx is None:
        return None

    # Get the boundary message
    boundary_msg = messages[last_boundary_idx]

    # Find the summary message (should be next)
    summary_content = None
    if last_boundary_idx + 1 < len(messages):
        summary_msg = messages[last_boundary_idx + 1]
        if summary_msg.get('isCompactSummary'):
            summary_content = summary_msg.get('message', {}).get('content', '')

    return {
        'line_number': last_boundary_idx,
        'summary_content': summary_content or '',
        'timestamp': boundary_msg.get('timestamp', '')
    }


def resolve_project_dir(project_dir: str) -> str:
    """
    Resolve project directory, trying alternate encodings if needed.

    Claude Code encodes paths by replacing '/' with '-', keeping the leading dash.
    But older documentation stripped the leading dash, so we try both.

    Examples:
        /Users/alice/dev/proj -> -Users-alice-dev-proj (current Claude Code behavior)
        /Users/alice/dev/proj -> Users-alice-dev-proj (old documentation)
    """
    if os.path.isdir(project_dir):
        return project_dir

    # Get the basename to try alternate encodings
    parent = os.path.dirname(project_dir)
    basename = os.path.basename(project_dir)

    # Try adding leading dash if missing
    if not basename.startswith('-'):
        alt_path = os.path.join(parent, '-' + basename)
        if os.path.isdir(alt_path):
            return alt_path

    # Try removing leading dash if present
    if basename.startswith('-'):
        alt_path = os.path.join(parent, basename[1:])
        if os.path.isdir(alt_path):
            return alt_path

    # Neither worked, return original for error message
    return project_dir


def list_sessions_with_samples(project_dir: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    List recent sessions with metadata and content samples.

    Returns: [{
        'slug': str,
        'path': str,
        'created': str,           # ISO timestamp
        'last_activity': str,     # ISO timestamp
        'message_count': int,
        'char_count': int,
        'compact_count': int,
        'last_compact_line': int | None,

        # Content samples for AI interpretation
        'first_user_message': str,      # First 500 chars
        'last_compact_summary': str | None,  # Full text if exists
        'recent_messages': list[str],   # Last 5 messages, each truncated to 500 chars
    }]

    Sorted by last_activity descending (most recent first).
    """
    # Try to resolve alternate path encodings
    project_dir = resolve_project_dir(project_dir)

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

            # Extract first user message
            first_user_msg = None
            for msg in messages:
                if msg.get('type') == 'user':
                    content = msg.get('message', {}).get('content', '')
                    first_user_msg = content[:500]
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
            # Skip files that can't be parsed
            continue

    # Sort by last activity (most recent first)
    sessions.sort(key=lambda x: x.get('last_activity') or '', reverse=True)

    # Limit results
    return sessions[:limit]


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


def get_content_after_line(session_path: str, start_line: int) -> str:
    """
    Extract all message content after a given line number.
    Returns JSON array of messages.
    """
    messages = load_jsonl(session_path)

    if start_line < 0 or start_line >= len(messages):
        raise ValueError(f"Invalid start_line: {start_line} (total messages: {len(messages)})")

    # Extract messages after start_line (start_line is 0-indexed)
    # start_line + 1 because we want content AFTER that line
    content = messages[start_line + 1:]

    return json.dumps(content, indent=2)


def get_content_from_start(session_path: str) -> str:
    """
    Extract all message content from session start.
    Returns JSON array of messages.
    """
    messages = load_jsonl(session_path)
    return json.dumps(messages, indent=2)


def get_agent_output(project_dir: str, agent_id: str) -> Dict[str, Any]:
    """
    Extract agent's final output from persisted session file.

    Agent session files are stored at:
        $CLAUDE_CONFIG_DIR/projects/<project-encoded>/agent-<id>.jsonl
    Where CLAUDE_CONFIG_DIR defaults to ~/.claude if not set.

    Returns: {
        'agent_id': str,
        'found': bool,
        'output': str | None,       # The agent's final response text
        'prompt': str | None,       # The original prompt sent to agent
        'session_id': str | None,   # Parent session ID
        'file_path': str,
    }
    """
    # Try to resolve alternate path encodings
    project_dir = resolve_project_dir(project_dir)

    agent_file = os.path.join(project_dir, f"agent-{agent_id}.jsonl")

    result = {
        'agent_id': agent_id,
        'found': False,
        'output': None,
        'prompt': None,
        'session_id': None,
        'file_path': agent_file,
    }

    if not os.path.exists(agent_file):
        return result

    try:
        messages = load_jsonl(agent_file)
        result['found'] = True

        # Extract session ID from first message
        if messages:
            result['session_id'] = messages[0].get('sessionId')

        # Find the prompt (first user message)
        for msg in messages:
            if msg.get('type') == 'user' or msg.get('message', {}).get('role') == 'user':
                content = msg.get('message', {}).get('content', '')
                result['prompt'] = content[:1000] if content else None
                break

        # Find the final output (last assistant message)
        for msg in reversed(messages):
            msg_data = msg.get('message', {})
            if msg_data.get('role') == 'assistant':
                content = msg_data.get('content', [])
                if isinstance(content, list) and content:
                    # Handle content array format
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            text_parts.append(part.get('text', ''))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    result['output'] = '\n'.join(text_parts)
                elif isinstance(content, str):
                    result['output'] = content
                break

    except Exception as e:
        result['error'] = str(e)

    return result


def list_agents_for_session(project_dir: str, session_id: str) -> List[Dict[str, Any]]:
    """
    List all agent session files that belong to a parent session.

    Returns: [{
        'agent_id': str,
        'file_path': str,
        'timestamp': str | None,
        'prompt_preview': str | None,  # First 200 chars of prompt
    }]
    """
    # Try to resolve alternate path encodings
    project_dir = resolve_project_dir(project_dir)

    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    agents = []

    for agent_file in glob.glob(f"{project_dir}/agent-*.jsonl"):
        try:
            # Extract agent ID from filename
            basename = os.path.basename(agent_file)
            agent_id = basename.replace('agent-', '').replace('.jsonl', '')

            messages = load_jsonl(agent_file)
            if not messages:
                continue

            # Check if this agent belongs to the target session
            agent_session_id = messages[0].get('sessionId')
            if agent_session_id != session_id:
                continue

            # Extract metadata
            timestamp = messages[0].get('timestamp')
            prompt_preview = None

            for msg in messages:
                if msg.get('type') == 'user' or msg.get('message', {}).get('role') == 'user':
                    content = msg.get('message', {}).get('content', '')
                    prompt_preview = content[:200] if content else None
                    break

            agents.append({
                'agent_id': agent_id,
                'file_path': agent_file,
                'timestamp': timestamp,
                'prompt_preview': prompt_preview,
            })

        except Exception:
            continue

    # Sort by timestamp
    agents.sort(key=lambda x: x.get('timestamp') or '', reverse=False)
    return agents


def main():
    """Main entry point with command dispatcher."""
    parser = argparse.ArgumentParser(
        description='Distill session helper for Claude Code sessions',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    subparsers.required = True

    # list-sessions
    list_cmd = subparsers.add_parser('list-sessions', help='List sessions with samples')
    list_cmd.add_argument('project_dir', help='Project directory path')
    list_cmd.add_argument('--limit', type=int, default=5, help='Max sessions to return')

    # get-last-compact
    compact_cmd = subparsers.add_parser('get-last-compact', help='Get last compact summary')
    compact_cmd.add_argument('session_file', help='Session file path')

    # get-content-after
    after_cmd = subparsers.add_parser('get-content-after', help='Get content after line')
    after_cmd.add_argument('session_file', help='Session file path')
    after_cmd.add_argument('--start-line', type=int, required=True, help='Start line number')

    # get-content-from-start
    start_cmd = subparsers.add_parser('get-content-from-start', help='Get all content')
    start_cmd.add_argument('session_file', help='Session file path')

    # split-by-char-limit
    split_cmd = subparsers.add_parser('split-by-char-limit', help='Calculate chunk boundaries')
    split_cmd.add_argument('session_file', help='Session file path')
    split_cmd.add_argument('--start-line', type=int, required=True, help='Start line')
    split_cmd.add_argument('--char-limit', type=int, required=True, help='Character limit per chunk')

    # extract-chunk
    extract_cmd = subparsers.add_parser('extract-chunk', help='Extract chunk by range')
    extract_cmd.add_argument('session_file', help='Session file path')
    extract_cmd.add_argument('--start-line', type=int, required=True, help='Start line')
    extract_cmd.add_argument('--end-line', type=int, required=True, help='End line')

    # get-agent-output
    agent_cmd = subparsers.add_parser('get-agent-output', help='Get agent output from persisted session file')
    agent_cmd.add_argument('project_dir', help='Project directory path (e.g., $CLAUDE_CONFIG_DIR/projects/-Users-...)')
    agent_cmd.add_argument('--agent-id', required=True, help='Agent ID (e.g., a1b2c3d)')

    # list-agents
    list_agents_cmd = subparsers.add_parser('list-agents', help='List agents belonging to a session')
    list_agents_cmd.add_argument('project_dir', help='Project directory path')
    list_agents_cmd.add_argument('--session-id', required=True, help='Parent session UUID')

    args = parser.parse_args()

    # Dispatch to command handler
    try:
        if args.command == 'list-sessions':
            result = list_sessions_with_samples(args.project_dir, args.limit)
            print(json.dumps(result, indent=2))
        elif args.command == 'get-last-compact':
            result = get_last_compact_summary(args.session_file)
            print(json.dumps(result, indent=2))
        elif args.command == 'get-content-after':
            result = get_content_after_line(args.session_file, args.start_line)
            print(result)
        elif args.command == 'get-content-from-start':
            result = get_content_from_start(args.session_file)
            print(result)
        elif args.command == 'split-by-char-limit':
            result = split_by_char_limit(args.session_file, args.start_line, args.char_limit)
            print(json.dumps(result, indent=2))
        elif args.command == 'extract-chunk':
            result = extract_chunk(args.session_file, args.start_line, args.end_line)
            print(result)
        elif args.command == 'get-agent-output':
            result = get_agent_output(args.project_dir, args.agent_id)
            print(json.dumps(result, indent=2))
        elif args.command == 'list-agents':
            result = list_agents_for_session(args.project_dir, args.session_id)
            print(json.dumps(result, indent=2))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(3)
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(4)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
