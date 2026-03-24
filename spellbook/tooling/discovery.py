"""Core tooling discovery logic.

Searches a curated YAML registry, introspects active MCP tools,
scans project dependencies, and checks CLI availability.
"""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Set

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


TRUST_LABELS = {
    1: "First-party official",
    2: "Established ecosystem",
    3: "Community standard",
    4: "Niche/specialized",
    5: "Experimental",
    6: "Unknown provenance",
}


def _tokenize(s: str) -> Set[str]:
    """Split on spaces and hyphens, lowercase."""
    return set(re.split(r"[\s\-]+", s.lower())) - {""}


def _parse_dep_names(project_path: str) -> Set[str]:
    """Extract package names from supported dependency files."""
    names: Set[str] = set()
    root = Path(project_path)

    # package.json
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            for key in ("dependencies", "devDependencies"):
                if key in data and isinstance(data[key], dict):
                    names.update(k.lower() for k in data[key].keys())
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            pass

    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text())
            deps = data.get("project", {}).get("dependencies", [])
            for dep in deps:
                name = re.split(r"[><=!~;\s\[]", dep)[0].strip()
                if name:
                    names.add(name.lower())
        except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError):
            pass

    # requirements.txt
    req_txt = root / "requirements.txt"
    if req_txt.exists():
        try:
            for line in req_txt.read_text().splitlines():
                line = line.split("#")[0].strip()
                if not line or line.startswith("-"):
                    continue
                name = re.split(r"[><=!~;\s\[]", line)[0].strip()
                if name:
                    names.add(name.lower())
        except OSError:
            pass

    # Cargo.toml
    cargo = root / "Cargo.toml"
    if cargo.exists():
        try:
            import tomllib

            data = tomllib.loads(cargo.read_text())
            deps = data.get("dependencies", {})
            if isinstance(deps, dict):
                names.update(k.lower() for k in deps.keys())
        except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError):
            pass

    # Gemfile
    gemfile = root / "Gemfile"
    if gemfile.exists():
        try:
            for line in gemfile.read_text().splitlines():
                m = re.match(r"""gem\s+['"]([^'"]+)['"]""", line.strip())
                if m:
                    names.add(m.group(1).lower())
        except OSError:
            pass

    return names


def discover_tools(
    domain_keywords: List[str],
    project_path: str = "",
    registry_path: str = "",
) -> Dict[str, Any]:
    """Discover available tools for given domain keywords.

    Searches the YAML registry, checks MCP tool availability,
    scans project dependencies, and checks CLI availability.
    """
    registry = _load_registry(registry_path)
    domains = registry.get("domains", {})

    # Tokenize user keywords
    user_tokens: Set[str] = set()
    for kw in domain_keywords:
        user_tokens.update(_tokenize(kw))

    # Match domains by keyword overlap
    matched_domains: Dict[str, Any] = {}
    for domain_name, domain_data in domains.items():
        domain_tokens: Set[str] = set()
        # Include the domain name itself as a token
        domain_tokens.update(_tokenize(domain_name))
        for kw in domain_data.get("keywords", []):
            domain_tokens.update(_tokenize(kw))
        if user_tokens & domain_tokens:
            matched_domains[domain_name] = domain_data

    # Check MCP tool availability
    available_mcp_tools: Set[str] = set()
    try:
        from spellbook.mcp.tools.health import get_tool_names

        available_mcp_tools = set(get_tool_names())
    except (ImportError, RuntimeError, AttributeError):
        pass

    dep_names = _parse_dep_names(project_path) if project_path else set()

    tools_out: List[Dict[str, Any]] = []
    summary = {
        "registry_matches": 0,
        "mcp_available": 0,
        "cli_available": 0,
        "dep_detected": 0,
    }

    for domain_name, domain_data in matched_domains.items():
        for tool in domain_data.get("tools", []):
            summary["registry_matches"] += 1
            detection_methods = ["registry_keyword"]
            available = False

            # MCP prefix matching
            mcp_prefix = tool.get("mcp_tool_prefix", "")
            if mcp_prefix and any(
                t.startswith(mcp_prefix) for t in available_mcp_tools
            ):
                detection_methods.append("mcp_available")
                summary["mcp_available"] += 1
                available = True

            # CLI availability
            for cli_name in tool.get("cli_names", []):
                if shutil.which(cli_name):
                    detection_methods.append("cli_available")
                    summary["cli_available"] += 1
                    available = True
                    break

            # Dependency signals
            for _pkg_type, pkg_names in tool.get("dep_signals", {}).items():
                if isinstance(pkg_names, list) and any(
                    p.lower() in dep_names for p in pkg_names
                ):
                    detection_methods.append("dep_detected")
                    summary["dep_detected"] += 1
                    available = True
                    break

            tools_out.append(
                {
                    "name": tool["name"],
                    "type": tool["type"],
                    "trust_tier": tool["trust_tier"],
                    "trust_label": TRUST_LABELS.get(
                        tool["trust_tier"], "Unknown"
                    ),
                    "source": tool["source"],
                    "description": tool["description"],
                    "available": available,
                    "detection_methods": detection_methods,
                    "risks": tool.get("risks")
                    if tool.get("trust_tier", 1) >= 4
                    else None,
                    "next_steps": tool.get("next_steps")
                    if tool.get("trust_tier", 1) >= 4
                    else None,
                }
            )

    tools_out.sort(key=lambda t: t["trust_tier"])

    return {
        "domain_keywords": domain_keywords,
        "tools": tools_out,
        "detection_summary": summary,
    }
