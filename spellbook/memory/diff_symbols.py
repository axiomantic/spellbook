"""Git diff to symbol-level change information.

Translates unified diff output into structured symbol changes.
Serena cannot do this -- it only queries current state. This component
owns the diff-to-symbol mapping using regex-based heuristics.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class DiffHunk:
    """A single hunk from a unified diff."""

    file_path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str  # raw hunk text
    added_lines: list[str]
    removed_lines: list[str]


@dataclass
class SymbolChange:
    """A symbol affected by a diff."""

    file: str
    symbol_name: str
    change_type: str  # added, removed, modified
    symbol_type: str  # function, class, method, variable, unknown
    context: str = ""  # surrounding code for LLM context


# ---------------------------------------------------------------------------
# Regex patterns for symbol extraction
# ---------------------------------------------------------------------------

# Python patterns
_PY_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")
_PY_CLASS_RE = re.compile(r"^\s*class\s+(\w+)\s*[:(]")

# JS/TS patterns
_JS_FUNCTION_RE = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("
)
_JS_CLASS_RE = re.compile(r"(?:export\s+)?class\s+(\w+)")
_JS_CONST_RE = re.compile(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=")
_JS_METHOD_RE = re.compile(r"^\s+(?:async\s+)?(\w+)\s*\(")

# Hunk header: @@ -old_start,old_count +new_start,new_count @@ optional context
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)"
)

# File path from diff header. Git wraps filenames containing spaces, tabs,
# control characters, or non-ASCII bytes in double quotes (controlled by
# ``core.quotepath``). Both forms must parse: bare ``a/path b/path`` and
# quoted ``"a/path with space" "b/path with space"``. Mixed forms (one
# quoted, one bare) do not occur in practice but are tolerated by the
# alternation. Inside quoted names, git uses C-style escapes for special
# bytes; :func:`_unquote_diff_path` handles the common ones.
_DIFF_FILE_RE = re.compile(
    r'^diff --git (?:"a/(.*?)"|a/(.*?)) (?:"b/(.*?)"|b/(.*?))$'
)

# C-style escapes that git emits inside quoted diff filenames. Higher-order
# octal byte escapes (e.g. ``\303\251`` for UTF-8 ``é``) are NOT decoded
# here -- those paths arrive intact as the literal escape sequence. If that
# matters in practice, switch to ``codecs.escape_decode`` and handle the
# bytes->str conversion explicitly.
_DIFF_QUOTE_ESCAPES = {
    "\\\\": "\\",
    '\\"': '"',
    "\\t": "\t",
    "\\n": "\n",
    "\\r": "\r",
}


def _unquote_diff_path(path: str) -> str:
    """Decode the limited C-style escapes git uses in quoted diff paths."""
    if "\\" not in path:
        return path
    out: list[str] = []
    i = 0
    while i < len(path):
        if path[i] == "\\" and i + 1 < len(path):
            two = path[i : i + 2]
            replacement = _DIFF_QUOTE_ESCAPES.get(two)
            if replacement is not None:
                out.append(replacement)
                i += 2
                continue
        out.append(path[i])
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# parse_diff_hunks
# ---------------------------------------------------------------------------


def parse_diff_hunks(diff_text: str) -> list[DiffHunk]:
    """Parse unified diff format into structured hunks.

    Args:
        diff_text: Raw unified diff output.

    Returns:
        List of DiffHunk, one per hunk in the diff.
    """
    if not diff_text.strip():
        return []

    hunks: list[DiffHunk] = []
    current_file: str | None = None
    current_hunk_lines: list[str] = []
    current_header: re.Match | None = None

    def _flush_hunk():
        nonlocal current_hunk_lines, current_header
        if current_header is None or current_file is None:
            return
        old_start = int(current_header.group(1))
        old_count = int(current_header.group(2)) if current_header.group(2) else 0
        new_start = int(current_header.group(3))
        new_count = int(current_header.group(4)) if current_header.group(4) else 0

        added = []
        removed = []
        for line in current_hunk_lines:
            if line.startswith("+"):
                added.append(line[1:])
            elif line.startswith("-"):
                removed.append(line[1:])

        content_text = current_header.group(0) + "\n" + "\n".join(current_hunk_lines)
        hunks.append(DiffHunk(
            file_path=current_file,
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            content=content_text,
            added_lines=added,
            removed_lines=removed,
        ))
        current_hunk_lines = []
        current_header = None

    for line in diff_text.splitlines():
        file_match = _DIFF_FILE_RE.match(line)
        if file_match:
            _flush_hunk()
            # Pick whichever side-b alternation matched (quoted vs bare).
            b_path = file_match.group(3) or file_match.group(4) or ""
            current_file = _unquote_diff_path(b_path)
            continue

        hunk_match = _HUNK_HEADER_RE.match(line)
        if hunk_match:
            _flush_hunk()
            current_header = hunk_match
            continue

        if current_header is not None:
            if line.startswith("+") or line.startswith("-") or line.startswith(" "):
                current_hunk_lines.append(line)

    _flush_hunk()
    return hunks


# ---------------------------------------------------------------------------
# extract_symbols_from_hunk
# ---------------------------------------------------------------------------


def extract_symbols_from_hunk(hunk: DiffHunk, file_ext: str) -> list[SymbolChange]:
    """Extract symbols touched by changes in a hunk.

    Args:
        hunk: A parsed DiffHunk.
        file_ext: File extension (e.g., ".py", ".ts", ".js").

    Returns:
        List of SymbolChange for symbols found in the hunk.
    """
    if file_ext in (".py",):
        return _extract_python_symbols(hunk)
    elif file_ext in (".js", ".ts", ".jsx", ".tsx"):
        return _extract_js_symbols(hunk)
    else:
        return []


def _extract_python_symbols(hunk: DiffHunk) -> list[SymbolChange]:
    """Extract Python symbols from a hunk."""
    added_syms = _find_python_symbols_in_lines(hunk.added_lines, hunk)
    removed_syms = _find_python_symbols_in_lines(hunk.removed_lines, hunk)

    added_names = {s[0] for s in added_syms}
    removed_names = {s[0] for s in removed_syms}

    # Symbols in both are modified; only added are added; only removed are removed
    modified_names = added_names & removed_names

    results: list[SymbolChange] = []
    seen: set[str] = set()

    for name, stype, context_line in added_syms:
        if name in seen:
            continue
        seen.add(name)
        if name in modified_names:
            change_type = "modified"
        else:
            change_type = "added"
        results.append(SymbolChange(
            file=hunk.file_path,
            symbol_name=name,
            change_type=change_type,
            symbol_type=stype,
            context=context_line,
        ))

    for name, stype, context_line in removed_syms:
        if name in seen:
            continue
        seen.add(name)
        results.append(SymbolChange(
            file=hunk.file_path,
            symbol_name=name,
            change_type="removed",
            symbol_type=stype,
            context=context_line,
        ))

    return results


def _find_python_symbols_in_lines(
    lines: list[str], hunk: DiffHunk
) -> list[tuple[str, str, str]]:
    """Find Python symbol definitions in a list of lines.

    Returns list of (name, symbol_type, context_line).
    """
    results: list[tuple[str, str, str]] = []
    # Determine if we are inside a class context from the hunk header
    class_context = _get_class_context_from_hunk(hunk)
    current_class: str | None = None

    for line in lines:
        stripped = line.rstrip()

        # Check for class definition
        cls_match = _PY_CLASS_RE.match(stripped)
        if cls_match:
            cls_name = cls_match.group(1)
            current_class = cls_name
            results.append((cls_name, "class", stripped.strip()))
            continue

        # Check for function/method definition
        def_match = _PY_DEF_RE.match(stripped)
        if def_match:
            fn_name = def_match.group(1)
            # Determine if it's a method (indented or has self/cls param, or class context)
            is_indented = stripped != stripped.lstrip()
            effective_class = current_class or class_context

            if is_indented and effective_class:
                sym_name = f"{effective_class}.{fn_name}"
                sym_type = "method"
            elif is_indented:
                # Indented but no class context: treat as method
                sym_type = "method"
                sym_name = fn_name
            else:
                sym_type = "function"
                sym_name = fn_name

            results.append((sym_name, sym_type, stripped.strip()))

    return results


def _get_class_context_from_hunk(hunk: DiffHunk) -> str | None:
    """Extract class name from the hunk header context (the @@ ... @@ ClassName line)."""
    # The hunk content often starts with the @@ header which may contain class context
    # e.g., "@@ -10,3 +10,5 @@ class APIClient:"
    match = re.search(r"@@.*@@\s*class\s+(\w+)", hunk.content)
    if match:
        return match.group(1)
    return None


def _extract_js_symbols(hunk: DiffHunk) -> list[SymbolChange]:
    """Extract JS/TS symbols from a hunk."""
    added_syms = _find_js_symbols_in_lines(hunk.added_lines, hunk)
    removed_syms = _find_js_symbols_in_lines(hunk.removed_lines, hunk)

    added_names = {s[0] for s in added_syms}
    removed_names = {s[0] for s in removed_syms}
    modified_names = added_names & removed_names

    results: list[SymbolChange] = []
    seen: set[str] = set()

    for name, stype, context_line in added_syms:
        if name in seen:
            continue
        seen.add(name)
        if name in modified_names:
            change_type = "modified"
        else:
            change_type = "added"
        results.append(SymbolChange(
            file=hunk.file_path,
            symbol_name=name,
            change_type=change_type,
            symbol_type=stype,
            context=context_line,
        ))

    for name, stype, context_line in removed_syms:
        if name in seen:
            continue
        seen.add(name)
        results.append(SymbolChange(
            file=hunk.file_path,
            symbol_name=name,
            change_type="removed",
            symbol_type=stype,
            context=context_line,
        ))

    return results


def _find_js_symbols_in_lines(
    lines: list[str], hunk: DiffHunk
) -> list[tuple[str, str, str]]:
    """Find JS/TS symbol definitions in a list of lines.

    Returns list of (name, symbol_type, context_line).
    """
    results: list[tuple[str, str, str]] = []
    class_context = _get_js_class_context_from_hunk(hunk)

    for line in lines:
        stripped = line.rstrip()

        # Check for class definition
        cls_match = _JS_CLASS_RE.search(stripped)
        if cls_match and "new " not in stripped:
            results.append((cls_match.group(1), "class", stripped.strip()))
            continue

        # Check for function definition (including export, async)
        fn_match = _JS_FUNCTION_RE.search(stripped)
        if fn_match:
            results.append((fn_match.group(1), "function", stripped.strip()))
            continue

        # Check for const/let/var
        const_match = _JS_CONST_RE.search(stripped)
        if const_match:
            results.append((const_match.group(1), "variable", stripped.strip()))
            continue

        # Check for method (indented, inside class)
        is_indented = stripped != stripped.lstrip()
        if is_indented:
            method_match = _JS_METHOD_RE.match(stripped)
            if method_match and class_context:
                name = method_match.group(1)
                # Skip common non-method keywords
                if name not in ("if", "for", "while", "return", "switch", "catch"):
                    results.append((name, "method", stripped.strip()))

    return results


def _get_js_class_context_from_hunk(hunk: DiffHunk) -> str | None:
    """Extract class name from the hunk header for JS/TS."""
    match = re.search(r"@@.*@@\s*(?:export\s+)?class\s+(\w+)", hunk.content)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------
# Git integration
# ---------------------------------------------------------------------------


def extract_changed_files(project_root: str, base_ref: str = "main") -> list[str]:
    """Get list of changed files between merge base and HEAD.

    Args:
        project_root: Root directory of the git repository.
        base_ref: Base branch to diff against.

    Returns:
        List of changed file paths relative to project root.
    """
    merge_base_result = subprocess.run(
        ["git", "merge-base", "HEAD", base_ref],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if merge_base_result.returncode != 0:
        return []

    merge_base = merge_base_result.stdout.strip()

    diff_result = subprocess.run(
        ["git", "diff", "--name-only", f"{merge_base}..HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if diff_result.returncode != 0:
        return []

    files = [f for f in diff_result.stdout.strip().splitlines() if f]
    return files


def extract_changed_symbols(
    project_root: str, base_ref: str = "main"
) -> list[SymbolChange]:
    """Extract symbol-level changes from git diff.

    Args:
        project_root: Root directory of the git repository.
        base_ref: Base branch to diff against.

    Returns:
        List of SymbolChange for all symbols touched by the diff.
    """
    merge_base_result = subprocess.run(
        ["git", "merge-base", "HEAD", base_ref],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if merge_base_result.returncode != 0:
        return []

    merge_base = merge_base_result.stdout.strip()

    diff_result = subprocess.run(
        ["git", "diff", f"{merge_base}..HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if diff_result.returncode != 0:
        return []

    hunks = parse_diff_hunks(diff_result.stdout)

    symbols: list[SymbolChange] = []
    for hunk in hunks:
        _, ext = os.path.splitext(hunk.file_path)
        hunk_symbols = extract_symbols_from_hunk(hunk, ext)
        symbols.extend(hunk_symbols)

    return symbols
