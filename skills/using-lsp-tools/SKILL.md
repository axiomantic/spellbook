---
name: using-lsp-tools
description: Use when mcp-language-server tools are available and you need semantic code intelligence for navigation, refactoring, or type analysis
---

# Using LSP Tools

When `mcp-language-server` tools are available (tools prefixed with the server name, e.g., `definition`, `references`, `hover`), they provide semantic code intelligence that understands types, scopes, and relationships. These tools are almost always superior to text-based alternatives for supported languages.

## Tool Priority: LSP First, Then Fallback

<RULE>
For tasks in the left column, use the LSP tool if available. Fall back to built-in tools only if LSP tool is unavailable or returns no results.
</RULE>

| Task | LSP Tool (Preferred) | Fallback |
|------|---------------------|----------|
| Find where symbol is defined | `definition` | Grep for `func X\|class X\|def X` |
| Find all usages of symbol | `references` | Grep for symbol name |
| Understand what a symbol is/does | `hover` | Read file + infer from context |
| Rename symbol across codebase | `rename_symbol` | Multi-file Edit (error-prone) |
| Get file structure/outline | `document_symbols` | Grep for definitions |
| Find callers of a function | `call_hierarchy` (incoming) | Grep + manual analysis |
| Find what a function calls | `call_hierarchy` (outgoing) | Read function body |
| Get type hierarchy | `type_hierarchy` | Grep for extends/implements |
| Search symbols across workspace | `workspace_symbol_resolve` | Glob + Grep |
| Get available refactorings | `code_actions` | Manual refactoring |
| Get function signature help | `signature_help` | Hover or read definition |
| Get compiler errors/warnings | `diagnostics` | Run build command |
| Format code | `format_document` | Run formatter CLI |
| Apply text edits to file | `edit_file` | Built-in Edit tool |

## Tool Parameters

Most LSP tools require:
- `filePath`: Absolute path to the file
- `line`, `column`: 1-indexed position (use `document_symbols` or `hover` output to find these)
- `symbolName`: For `definition`/`references`, the fully-qualified name (e.g., `mypackage.MyFunction`)

The `edit_file` tool takes line-based edits, useful when you have precise line ranges from LSP output.

## When LSP Tools Excel

**Always prefer LSP tools for:**
- Finding the true definition (not just text matches)
- Refactoring operations (rename, extract, inline)
- Understanding type relationships and inheritance
- Finding semantic usages (not just text occurrences)
- Cross-file navigation following imports/references

**LSP tools understand:**
- Scope (local variable vs. parameter vs. field)
- Overloading (which `foo()` is called)
- Generics and type parameters
- Import/export relationships
- Language-specific semantics

## When Built-in Tools Are Better

**Use Grep/Glob when:**
- Searching for literal strings, comments, or non-code text
- Pattern matching across file contents (regex)
- LSP tool returns empty but you know the code exists
- Working with files the language server doesn't support
- Searching for things that aren't symbols (TODOs, URLs, magic strings)

**Use Read when:**
- You need to see surrounding context
- You want to understand code flow, not just find definitions
- Reading configuration files, READMEs, etc.

## Practical Workflow

1. **Exploring unfamiliar code:**
   - Start with `document_symbols` to see file structure
   - Use `hover` on unknown symbols to understand types
   - Use `definition` to jump to implementations
   - Use `references` to see how things are used

2. **Refactoring:**
   - Use `rename_symbol` for renames (handles all files atomically)
   - Use `code_actions` to discover available refactorings
   - Use `references` before manual changes to understand impact

3. **Debugging type issues:**
   - Use `hover` to see inferred types
   - Use `type_hierarchy` to understand inheritance
   - Use `diagnostics` to see compiler errors

4. **Understanding call patterns:**
   - Use `call_hierarchy` with direction "incoming" for "who calls this?"
   - Use `call_hierarchy` with direction "outgoing" for "what does this call?"

## Fallback Protocol

If an LSP tool returns an error or empty result:
1. Check if the file is saved (LSP works on disk state)
2. Try the fallback tool from the table above
3. For persistent issues, the language server may not support that feature
