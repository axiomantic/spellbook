"""Check that spellbook package follows core -> domains -> interfaces layering.

Walks all .py files in spellbook/ and parses imports using the ast module.
Each file is classified into one of three layers:
  - core: spellbook/core/
  - domain: spellbook/{memory,health,sessions,notifications,updates,experiments}/
  - interface: spellbook/{mcp,daemon,cli}/

The dependency rules are:
  - core/ must NOT import from domains/ or interfaces/
  - domains/ must NOT import from interfaces/
  - interfaces/ can import from anything within spellbook/

Exits 0 if clean, exits 1 if violations found.
"""

import ast
import sys
from pathlib import Path

# Layer classification
CORE_PACKAGES = {"core"}
DOMAIN_PACKAGES = {"memory", "health", "sessions", "notifications", "updates", "experiments"}
INTERFACE_PACKAGES = {"mcp", "daemon", "cli"}

# Layer ordering (lower number = lower layer)
LAYER_RANK = {
    "core": 0,
    "domain": 1,
    "interface": 2,
}


def classify_layer(file_path: Path, spellbook_root: Path) -> str | None:
    """Classify a file into its architectural layer.

    Args:
        file_path: Absolute path to a .py file inside spellbook/.
        spellbook_root: Path to the spellbook/ package directory.

    Returns:
        "core", "domain", "interface", or None if the file is at the
        top level of spellbook/ (e.g., __init__.py, __main__.py).
    """
    try:
        relative = file_path.relative_to(spellbook_root)
    except ValueError:
        return None

    parts = relative.parts
    if len(parts) < 2:
        # Top-level files like __init__.py, __main__.py
        return None

    top_package = parts[0]
    if top_package in CORE_PACKAGES:
        return "core"
    elif top_package in DOMAIN_PACKAGES:
        return "domain"
    elif top_package in INTERFACE_PACKAGES:
        return "interface"
    return None


def get_spellbook_imports(source: str) -> list[str]:
    """Parse a Python source file and extract module-level spellbook.* import targets.

    Only checks top-level imports (not imports inside functions, methods, or
    conditional blocks). Function-level imports are a common pattern for
    avoiding circular dependencies and should not trigger layer violations.

    Returns a list of fully-qualified module paths that start with "spellbook.".
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports = []
    # Only check top-level statements (direct children of Module)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("spellbook."):
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("spellbook."):
                    imports.append(alias.name)
    return imports


def classify_import_target(module_path: str) -> str | None:
    """Classify an import target module path into its layer.

    Args:
        module_path: A dotted module path like "spellbook.core.config".

    Returns:
        "core", "domain", "interface", or None if unclassifiable.
    """
    parts = module_path.split(".")
    if len(parts) < 2:
        return None

    # parts[0] is "spellbook", parts[1] is the sub-package
    sub_package = parts[1]
    if sub_package in CORE_PACKAGES:
        return "core"
    elif sub_package in DOMAIN_PACKAGES:
        return "domain"
    elif sub_package in INTERFACE_PACKAGES:
        return "interface"
    return None


def check_violation(source_layer: str, target_layer: str) -> bool:
    """Check if an import from source_layer to target_layer violates layering.

    Returns True if the import is a violation.
    """
    source_rank = LAYER_RANK.get(source_layer)
    target_rank = LAYER_RANK.get(target_layer)
    if source_rank is None or target_rank is None:
        return False
    # A lower layer importing from a higher layer is a violation
    return source_rank < target_rank


def main() -> int:
    """Walk spellbook/ and check for layer violations.

    Returns:
        0 if no violations, 1 if violations found.
    """
    # Find the spellbook package directory relative to this script
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    spellbook_root = project_root / "spellbook"

    if not spellbook_root.is_dir():
        print(f"ERROR: spellbook/ directory not found at {spellbook_root}")
        return 1

    violations = []
    file_counts = {"core": 0, "domain": 0, "interface": 0}

    for py_file in sorted(spellbook_root.rglob("*.py")):
        # Skip __pycache__
        if "__pycache__" in py_file.parts:
            continue

        source_layer = classify_layer(py_file, spellbook_root)
        if source_layer is None:
            continue

        file_counts[source_layer] += 1

        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        spellbook_imports = get_spellbook_imports(source)
        for imp in spellbook_imports:
            target_layer = classify_import_target(imp)
            if target_layer is None:
                continue
            if check_violation(source_layer, target_layer):
                relative_path = py_file.relative_to(project_root)
                violations.append(
                    f"  {relative_path} ({source_layer}) -> {imp} ({target_layer})"
                )

    # Report
    print("Layer analysis of spellbook/ package:")
    print(f"  Core files:      {file_counts['core']}")
    print(f"  Domain files:    {file_counts['domain']}")
    print(f"  Interface files: {file_counts['interface']}")
    print()

    if violations:
        print(f"Found {len(violations)} layer violation(s):")
        for v in violations:
            print(v)
        return 1
    else:
        print("No layer violations found. All imports follow core -> domain -> interface ordering.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
