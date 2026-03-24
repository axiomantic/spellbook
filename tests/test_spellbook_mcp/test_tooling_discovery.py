"""Tests for tooling discovery system."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch


REGISTRY_PATH = str(
    Path(__file__).parent.parent.parent / "spellbook" / "data" / "tooling-registry.yaml"
)


class TestRegistryLoads:
    def test_registry_yaml_loads_without_error(self):
        """YAML registry file loads and parses successfully."""
        with open(REGISTRY_PATH) as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "version" in data
        assert "domains" in data

    def test_registry_has_minimum_domains(self):
        """Registry contains at least 15 fully-vetted domains."""
        with open(REGISTRY_PATH) as f:
            data = yaml.safe_load(f)
        domains = data.get("domains", {})
        assert len(domains) >= 15, f"Expected >= 15 domains, got {len(domains)}"

    def test_registry_schema_validation(self):
        """Every tool entry has required fields."""
        with open(REGISTRY_PATH) as f:
            data = yaml.safe_load(f)
        required_fields = {"name", "type", "trust_tier", "source", "description"}
        valid_types = {"mcp_server", "cli", "api", "library", "service"}

        for domain_name, domain_data in data.get("domains", {}).items():
            assert "keywords" in domain_data, f"Domain '{domain_name}' missing keywords"
            assert "tools" in domain_data, f"Domain '{domain_name}' missing tools"
            for tool in domain_data["tools"]:
                missing = required_fields - set(tool.keys())
                assert not missing, (
                    f"Domain '{domain_name}', tool '{tool.get('name', '?')}' "
                    f"missing fields: {missing}"
                )
                assert tool["type"] in valid_types, (
                    f"Tool '{tool['name']}' has invalid type '{tool['type']}'"
                )
                assert 1 <= tool["trust_tier"] <= 6, (
                    f"Tool '{tool['name']}' trust_tier {tool['trust_tier']} out of range"
                )


class TestRegistryLoader:
    def test_load_registry(self):
        """_load_registry returns parsed YAML data."""
        from spellbook.tooling.discovery import _load_registry

        data = _load_registry(REGISTRY_PATH)
        assert "domains" in data
        assert "version" in data

    def test_load_registry_caches_by_mtime(self):
        """Second call returns cached data (same mtime)."""
        from spellbook.tooling.discovery import _load_registry, _registry_cache

        _registry_cache.clear()
        data1 = _load_registry(REGISTRY_PATH)
        data2 = _load_registry(REGISTRY_PATH)
        assert data1 is data2  # Same object = cached


class TestKeywordMatching:
    def test_exact_domain_match(self):
        """'jira' matches the jira domain."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["jira"], registry_path=REGISTRY_PATH)
        assert result["detection_summary"]["registry_matches"] > 0
        tool_names = [t["name"] for t in result["tools"]]
        assert "Atlassian MCP Server" in tool_names

    def test_partial_keyword_match(self):
        """'project-management' matches domains with that keyword."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["project-management"], registry_path=REGISTRY_PATH)
        assert result["detection_summary"]["registry_matches"] > 0

    def test_no_match(self):
        """'nonexistent-thing-xyz' returns empty results."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["nonexistent-thing-xyz"], registry_path=REGISTRY_PATH)
        assert result["detection_summary"]["registry_matches"] == 0
        assert len(result["tools"]) == 0

    def test_trust_tier_sorting(self):
        """Results are sorted by trust tier (lowest first)."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["github"], registry_path=REGISTRY_PATH)
        tiers = [t["trust_tier"] for t in result["tools"]]
        assert tiers == sorted(tiers)

    def test_trust_label_included(self):
        """Each tool has a trust_label field."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["docker"], registry_path=REGISTRY_PATH)
        for tool in result["tools"]:
            assert "trust_label" in tool
            assert isinstance(tool["trust_label"], str)


class TestCLIDetection:
    @patch("shutil.which")
    def test_cli_detected_when_available(self, mock_which):
        """CLI tool marked available when shutil.which returns a path."""
        from spellbook.tooling.discovery import discover_tools

        mock_which.side_effect = lambda name: "/usr/bin/gh" if name == "gh" else None
        result = discover_tools(["github"], registry_path=REGISTRY_PATH)
        gh_tools = [t for t in result["tools"] if "GitHub CLI" in t["name"]]
        assert len(gh_tools) == 1
        assert gh_tools[0]["available"] is True
        assert "cli_available" in gh_tools[0]["detection_methods"]

    @patch("shutil.which", return_value=None)
    def test_cli_not_detected_when_missing(self, mock_which):
        """CLI tool not marked available when binary not found."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["docker"], registry_path=REGISTRY_PATH)
        docker_tools = [t for t in result["tools"] if "Docker CLI" in t["name"]]
        assert len(docker_tools) == 1
        assert docker_tools[0]["available"] is False


class TestDepScanning:
    def test_dep_scanning_pyproject_toml(self, tmp_path):
        """Detects Python deps from pyproject.toml."""
        from spellbook.tooling.discovery import discover_tools

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\ndependencies = ["boto3>=1.26", "requests"]\n'
        )

        with patch("shutil.which", return_value=None):
            result = discover_tools(
                ["aws"], project_path=str(tmp_path), registry_path=REGISTRY_PATH,
            )

        aws_tools = [t for t in result["tools"] if "AWS CLI" in t["name"]]
        assert len(aws_tools) == 1
        assert aws_tools[0]["available"] is True
        assert "dep_detected" in aws_tools[0]["detection_methods"]

    def test_dep_scanning_package_json(self, tmp_path):
        """Detects npm deps from package.json."""
        import json as json_mod

        from spellbook.tooling.discovery import discover_tools

        pkg = tmp_path / "package.json"
        pkg.write_text(json_mod.dumps({
            "dependencies": {"stripe": "^12.0.0"},
            "devDependencies": {},
        }))

        with patch("shutil.which", return_value=None):
            result = discover_tools(
                ["stripe"], project_path=str(tmp_path), registry_path=REGISTRY_PATH,
            )

        stripe_tools = [t for t in result["tools"] if "Stripe CLI" in t["name"]]
        assert len(stripe_tools) == 1
        assert stripe_tools[0]["available"] is True
        assert "dep_detected" in stripe_tools[0]["detection_methods"]


class TestMCPToolWrapper:
    def test_tooling_discover_function_importable(self):
        """The tooling_discover MCP tool function is importable."""
        from spellbook.mcp.tools.tooling import tooling_discover

        assert callable(tooling_discover)

    def test_tooling_module_has_all_export(self):
        """The tooling module defines __all__ with tooling_discover."""
        from spellbook.mcp.tools import tooling

        assert hasattr(tooling, "__all__")
        assert "tooling_discover" in tooling.__all__

    def test_tooling_registered_in_init(self):
        """The tooling module is imported in spellbook.mcp.tools.__init__."""
        import spellbook.mcp.tools as tools_pkg
        import spellbook.mcp.tools.tooling as tooling_mod

        # Verify the tooling submodule is accessible via the package
        assert hasattr(tools_pkg, "tooling")
        assert tools_pkg.tooling is tooling_mod
