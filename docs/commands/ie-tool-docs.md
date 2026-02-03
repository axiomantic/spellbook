# /ie-tool-docs

## Command Content

``````````markdown
# Instruction Engineering: Tool Documentation

This command provides guidance for writing effective tool and function documentation, based on Anthropic's "Building Effective Agents" guide.

## Invariant Principles

1. **Equal effort to prompts** - Tool definitions deserve as much attention as prompt engineering (Anthropic guidance)
2. **Document the unhappy path** - Error cases and edge conditions matter more than the happy path
3. **Show, don't tell** - Every parameter needs a concrete example value
4. **Prevent misuse explicitly** - "When NOT to use" is as important as "when to use"

<CRITICAL>
Anthropic recommends: "Spend as much effort on tool definitions as you do on prompts."

Tool documentation is not an afterthought. Poor tool docs cause the model to misuse tools, guess parameters, or avoid tools entirely.
</CRITICAL>

---

## Why Tool Documentation Matters

From Anthropic's experience building agents:

1. **Models read tool descriptions** to decide when and how to use tools
2. **Ambiguous descriptions** cause incorrect tool selection or parameter values
3. **Missing edge cases** lead to runtime errors the model can't recover from
4. **Real example**: For SWE-bench, Anthropic spent MORE time optimizing tool definitions than the overall prompt

---

## Tool Documentation Checklist

For every tool/function, document:

| Element | Required | Description |
|---------|----------|-------------|
| **Purpose** | Yes | What the tool does in one sentence |
| **When to use** | Yes | Conditions that make this tool appropriate |
| **When NOT to use** | Recommended | Common misuse cases |
| **Parameters** | Yes | Each parameter with type, constraints, examples |
| **Return value** | Yes | What the tool returns on success |
| **Error cases** | Yes | What errors can occur and what they mean |
| **Side effects** | If any | What state changes the tool causes |
| **Examples** | Recommended | 1-2 usage examples |

---

## Parameter Documentation

For each parameter:

```
name (type, required/optional): Description.
  - Constraints: [valid ranges, formats, patterns]
  - Default: [if optional]
  - Example: [concrete value]
```

**Good Example:**
```
path (string, required): Absolute path to the file to read.
  - Must start with "/"
  - Must not contain ".." or symbolic links
  - Example: "/Users/alice/project/src/main.ts"
```

**Bad Example:**
```
path: The file path
```

---

## Edge Case Documentation

Document what happens with:

| Edge Case | Document |
|-----------|----------|
| Empty input | What happens if required field is empty string/null? |
| Invalid type | What if string passed where number expected? |
| Out of bounds | What if index exceeds array length? |
| Missing resource | What if file/URL/ID doesn't exist? |
| Permission denied | What if access is restricted? |
| Timeout | What if operation takes too long? |

---

## Good vs Bad Tool Descriptions

### File Reading Tool

**Bad:**
```json
{
  "name": "read_file",
  "description": "Reads a file"
}
```

**Good:**
```json
{
  "name": "read_file",
  "description": "Reads the contents of a file and returns it as a string. Use when you need to examine file contents. Fails if file doesn't exist or is binary. For large files (>1MB), consider using read_file_chunk instead.",
  "parameters": {
    "path": {
      "type": "string",
      "description": "Path to the file. Can be absolute (/Users/...) or relative to current working directory (./src/...).",
      "examples": ["/Users/alice/project/README.md", "./src/index.ts"]
    }
  },
  "returns": "File contents as UTF-8 string. Returns error object if file not found or not readable.",
  "errors": [
    "FILE_NOT_FOUND: Path does not exist",
    "PERMISSION_DENIED: Cannot read file",
    "BINARY_FILE: File appears to be binary, use read_file_binary instead"
  ]
}
```

### API Call Tool

**Bad:**
```json
{
  "name": "api_request",
  "description": "Makes an API request"
}
```

**Good:**
```json
{
  "name": "api_request",
  "description": "Makes an HTTP request to an external API. Use for fetching data from REST APIs. NOT for internal service calls (use internal_rpc instead). Automatically retries on 5xx errors up to 3 times.",
  "parameters": {
    "method": {
      "type": "string",
      "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
      "description": "HTTP method"
    },
    "url": {
      "type": "string", 
      "description": "Full URL including protocol. Must be HTTPS for external APIs.",
      "examples": ["https://api.github.com/repos/owner/repo"]
    },
    "headers": {
      "type": "object",
      "description": "HTTP headers. Authorization headers are added automatically from config.",
      "optional": true
    },
    "body": {
      "type": "object",
      "description": "Request body for POST/PUT/PATCH. Automatically serialized to JSON.",
      "optional": true
    },
    "timeout_ms": {
      "type": "number",
      "description": "Request timeout in milliseconds",
      "default": 30000,
      "optional": true
    }
  },
  "returns": "Response object with status, headers, and body (parsed as JSON if Content-Type is application/json)",
  "errors": [
    "TIMEOUT: Request exceeded timeout_ms",
    "NETWORK_ERROR: Could not connect to host",
    "INVALID_URL: URL is malformed or uses disallowed protocol",
    "AUTH_REQUIRED: API returned 401, check credentials"
  ],
  "side_effects": "POST/PUT/DELETE/PATCH may modify remote state"
}
```

---

## Anti-Patterns

<FORBIDDEN>
- One-word descriptions ("Reads file", "Makes request")
- Missing parameter types
- No error documentation
- No examples
- Assuming the model knows your conventions
- Documenting only the happy path
</FORBIDDEN>

---

## Self-Check

Before finalizing tool documentation:

- [ ] Can a developer who's never seen this tool understand when to use it?
- [ ] Are ALL parameters documented with types and constraints?
- [ ] Are error cases documented with what they mean?
- [ ] Is there at least one usage example?
- [ ] Are side effects clearly stated?
- [ ] Is "when NOT to use" documented for commonly confused tools?

If ANY unchecked: improve documentation before shipping.
``````````
