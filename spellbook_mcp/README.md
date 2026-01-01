# Spellbook MCP Server

Session management tools for Claude Code via Model Context Protocol.

## Overview

The Spellbook MCP server provides three efficient tools for session discovery and management:

- **find_session**: Find sessions by name (case-insensitive substring match)
- **split_session**: Calculate chunk boundaries for session content
- **list_sessions**: List recent sessions with metadata and content samples

This reduces session discovery from 10+ LLM tool calls to a single MCP invocation.

## Installation

### Quick Install (via spellbook installer)

Run from the spellbook root:

```bash
./install.sh
```

This will install Python dependencies and register the MCP server with Claude Code.

### Manual Installation

#### 1. Install Python Dependencies

```bash
pip install -r spellbook_mcp/requirements.txt
```

#### 2. Add to Claude Code

```bash
claude mcp add spellbook -- python /path/to/spellbook/spellbook_mcp/server.py
```

Replace `/path/to/spellbook` with the absolute path to your spellbook repository.

#### 3. Verify Installation

```bash
claude mcp list
# Should show: spellbook (python .../spellbook_mcp/server.py)
```

## Usage

### find_session

Find sessions by name (searches slug and custom title):

```python
find_session(name="auth", limit=5)
# Returns sessions with "auth" in slug or custom title
```

### split_session

Calculate chunk boundaries for a session:

```python
split_session(
    session_path="/Users/foo/.claude/projects/spellbook/fuzzy-bear.jsonl",
    start_line=100,
    char_limit=100000
)
# Returns: [[100, 245], [245, 389], [389, 450]]
```

### list_sessions

List recent sessions in current project:

```python
list_sessions(limit=10)
# Returns 10 most recent sessions with metadata and samples
```

## Configuration

The server automatically:
- Detects the current project from `os.getcwd()`
- Resolves session directory to `~/.claude/projects/{encoded-cwd}/`
- Supports `CLAUDE_CONFIG_DIR` environment variable

No manual configuration required.

## Development

### Running Tests

```bash
# From spellbook root directory
pytest tests/test_spellbook_mcp/ -v

# Run specific test file
pytest tests/test_spellbook_mcp/test_server_integration.py -v

# Run with coverage
pytest tests/test_spellbook_mcp/ -v --cov=spellbook_mcp
```

### Test Quality

Tests are audited for green mirage patterns. All assertions verify actual values, not just existence. Key invariants verified:

- **load_jsonl**: Full object comparison, not field spot-checks
- **split_session**: Chunk contiguity, boundary correctness, coverage
- **list_sessions**: Exact field values including timestamps and paths
- **find_session**: Correct sessions matched, not just counts

### Project Structure

```
spellbook_mcp/
├── server.py           # FastMCP server with tool registrations
├── session_ops.py      # Session loading, metadata, chunking
├── path_utils.py       # Path encoding and project resolution
├── requirements.txt    # Python dependencies (fastmcp)
└── README.md           # This file

tests/test_spellbook_mcp/
├── test_path_utils.py        # Path encoding tests
├── test_session_ops.py       # Session operations tests (20 tests)
└── test_server_integration.py # End-to-end tool tests
```

## Troubleshooting

### "Module not found" Error

Make sure you're using the absolute path in `claude mcp add`:

```bash
pwd  # Get current directory
claude mcp add spellbook python $(pwd)/spellbook_mcp/server.py
```

### Sessions Not Found

Verify the project directory exists:

```bash
ls ~/.claude/projects/
# Or with custom config:
ls $CLAUDE_CONFIG_DIR/projects/
```

### Python Version

Requires Python 3.8+:

```bash
python3 --version
```

## License

Same as parent spellbook repository.
