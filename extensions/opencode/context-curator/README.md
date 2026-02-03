# Context Curator

OpenCode plugin for intelligent context pruning with spellbook MCP integration.

## Features

- **Automatic Pruning Strategies**
  - Deduplication: Removes older duplicate tool calls
  - Supersede-writes: Prunes write inputs when file is subsequently read
  - Purge-errors: Removes errored tool outputs after N turns

- **LLM-Invoked Tools**
  - `discard`: Remove tool outputs no longer needed
  - `extract`: Summarize and remove tool outputs

- **Commands**
  - `/curator context`: Show token usage breakdown
  - `/curator stats`: Show cumulative statistics

- **Spellbook Integration**
  - Analytics tracking via MCP server
  - Persistent statistics across sessions

## Installation

```bash
# In your OpenCode project
opencode plugin add spellbook-context-curator
```

## Configuration

In `opencode.json`:

```json
{
  "plugins": {
    "spellbook-context-curator": {
      "enabled": true,
      "debug": false,
      "strategies": {
        "deduplication": {
          "enabled": true,
          "protectedTools": ["custom-tool"]
        },
        "supersedeWrites": {
          "enabled": true
        },
        "purgeErrors": {
          "enabled": true,
          "turnThreshold": 3
        }
      },
      "tools": {
        "discard": { "enabled": true },
        "extract": { "enabled": true }
      },
      "commands": { "enabled": true },
      "protectedFilePatterns": [
        "**/CLAUDE.md",
        "**/AGENTS.md",
        "**/.env*"
      ]
    }
  }
}
```

## Environment Variables

- `SPELLBOOK_MCP_PORT`: MCP server port (default: 8765)
- `CURATOR_DEBUG`: Enable debug logging (set to "true")

## How It Works

1. **Message Transform Hook**: On each LLM request, the plugin:
   - Syncs tool invocations to its cache
   - Runs automatic pruning strategies
   - Replaces pruned content with markers
   - Injects `<prunable-tools>` list for LLM awareness

2. **LLM Tools**: The LLM can proactively manage context using:
   - `discard` to remove unneeded tool outputs
   - `extract` to summarize before removal

3. **Analytics**: All pruning events are tracked via spellbook MCP for statistics and monitoring.

## Known Limitations

- **Deduplication**: Compares tool name + parameters only, not output content
- **Supersede-writes**: Assumes reads reflect writes (external modifications not detected)
- **Subagents**: Pruning is disabled for subagent sessions

## License

MIT
