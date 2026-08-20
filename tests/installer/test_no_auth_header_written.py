"""Guard: no installer-written config may carry an Authorization header.

The population is derived from EVERY primitive file write in the platform
installers via AST -- not from calls to a designated safe helper. Deriving from
a helper self-blinds: a site reverted to a plain ``write_text`` would silently
*leave* the derived set instead of failing the guard.

One unit = one AST Call node that writes file contents (``write_text``,
``write_bytes``, ``open(..., "w")``, or a file handle's ``.write``) located in
``installer/platforms/*.py``.
"""

import ast
from pathlib import Path

import pytest

PLATFORM_DIR = Path(__file__).resolve().parents[2] / "installer" / "platforms"

# base.py bundles rule modules, not MCP config, and is not a credential surface.
EXCLUDED_MODULES = {"base.py", "__init__.py"}

FORBIDDEN_SUBSTRINGS = ("authorization", "bearer")


def _primitive_write_calls(tree):
    """Yield Call nodes that write file contents."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {
            "write_text",
            "write_bytes",
            "write",
            "writelines",
        }:
            yield node, func.attr
        elif isinstance(func, ast.Name) and func.id == "open":
            modes = [a.value for a in node.args[1:] if isinstance(a, ast.Constant)]
            modes += [
                kw.value.value
                for kw in node.keywords
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant)
            ]
            if any(isinstance(m, str) and ("w" in m or "a" in m) for m in modes):
                yield node, "open"


def _enclosing_function(node, parents):
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
    return "<module>"


def _census():
    """Return list of (module, lineno, function, kind) for every write site."""
    rows = []
    for path in sorted(PLATFORM_DIR.glob("*.py")):
        if path.name in EXCLUDED_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node, kind in _primitive_write_calls(tree):
            rows.append((path.name, node.lineno, _enclosing_function(node, parents), kind))
    return rows


def test_census_covers_every_platform_module():
    """Every platform installer that writes config is in the population."""
    modules = {row[0] for row in _census()}
    assert modules == {
        "antigravity.py",
        "codex.py",
        "forgecode.py",
        "goose.py",
        "opencode.py",
        "pi.py",
    }


def test_census_is_non_trivial():
    """A census that collapsed to zero would pass every content check vacuously."""
    rows = _census()
    assert len(rows) >= 15, f"write-site census shrank to {len(rows)}; verify detector"
    assert len({(r[0], r[2]) for r in rows}) >= 13


@pytest.mark.parametrize("module", sorted(p.name for p in PLATFORM_DIR.glob("*.py")))
def test_no_platform_module_mentions_an_auth_header(module):
    """Content-based: no auth-header string survives anywhere in an installer.

    Content-based rather than call-based, so there is no allowlist of 'known
    safe' sites for a real leak to hide in.
    """
    source = (PLATFORM_DIR / module).read_text(encoding="utf-8").lower()
    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle not in source, f"{module} still references {needle!r}"


def test_mcp_component_has_no_token_reader():
    """installer/components/mcp.py must not read or forward a bearer token."""
    source = (
        PLATFORM_DIR.parent / "components" / "mcp.py"
    ).read_text(encoding="utf-8").lower()
    for needle in (*FORBIDDEN_SUBSTRINGS, "get_mcp_auth_token", "mcp-token"):
        assert needle not in source, f"mcp.py still references {needle!r}"
