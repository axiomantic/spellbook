"""Core tooling discovery logic.

Searches a curated YAML registry, introspects active MCP tools,
scans project dependencies, and checks CLI availability.
"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml

# Module-level cache: keyed by registry file mtime to avoid re-parsing
_registry_cache: Dict[float, Dict[str, Any]] = {}


def _load_registry(registry_path: str = "") -> Dict[str, Any]:
    """Load and cache the YAML registry. Cache invalidates on file mtime change."""
    if not registry_path:
        registry_path = str(Path(__file__).parent.parent / "data" / "tooling-registry.yaml")
    mtime = os.path.getmtime(registry_path)
    if mtime in _registry_cache:
        return _registry_cache[mtime]
    with open(registry_path) as f:
        data = yaml.safe_load(f)
    _registry_cache.clear()
    _registry_cache[mtime] = data
    return data
