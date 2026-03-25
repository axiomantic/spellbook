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
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "version" in data
        assert "domains" in data

    def test_registry_has_minimum_domains(self):
        """Registry contains at least 15 fully-vetted domains."""
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        domains = data.get("domains", {})
        assert len(domains) >= 15, f"Expected >= 15 domains, got {len(domains)}"

    def test_registry_schema_validation(self):
        """Every tool entry has required fields."""
        with open(REGISTRY_PATH, encoding="utf-8") as f:
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
    def test_ensure_indexed_creates_db(self):
        """_ensure_indexed creates the SQLite database from the YAML registry."""
        from spellbook.tooling.discovery import _ensure_indexed

        _ensure_indexed()
        # After indexing, _query_registry should work
        from spellbook.tooling.discovery import _query_registry

        results = _query_registry(["github"])
        assert len(results) >= 1

    def test_query_registry_returns_tool_dicts(self):
        """_query_registry returns a list of tool dicts with expected fields."""
        from spellbook.tooling.discovery import _ensure_indexed, _query_registry

        _ensure_indexed()
        results = _query_registry(["jira"])
        assert len(results) >= 1
        tool = results[0]
        assert "name" in tool
        assert "type" in tool
        assert "trust_tier" in tool


class TestKeywordMatching:
    def test_exact_domain_match(self):
        """'jira' matches the jira domain."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["jira"], registry_path=REGISTRY_PATH)
        assert result["detection_summary"]["registry_matches"] == 2
        tool_names = [t["name"] for t in result["tools"]]
        assert "Atlassian MCP Server" in tool_names

    def test_partial_keyword_match(self):
        """'project-management' matches domains with that keyword."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["project-management"], registry_path=REGISTRY_PATH)
        assert result["detection_summary"]["registry_matches"] == 2

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
        assert len(tiers) >= 1
        assert tiers == sorted(tiers)

    def test_trust_label_included(self):
        """Each tool has a trust_label field."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["docker"], registry_path=REGISTRY_PATH)
        for tool in result["tools"]:
            assert "trust_label" in tool
            expected_label = {
                1: "First-party official",
                2: "Established ecosystem",
                3: "Community standard",
                4: "Niche/specialized",
                5: "Experimental",
                6: "Unknown provenance",
            }[tool["trust_tier"]]
            assert tool["trust_label"] == expected_label


class TestCLIDetection:
    @patch("shutil.which")
    def test_cli_detected_when_available(self, mock_which):
        """CLI tool marked available when shutil.which returns a path."""
        from spellbook.tooling.discovery import discover_tools

        mock_which.side_effect = lambda name: "/usr/bin/gh" if name == "gh" else None
        result = discover_tools(["github"], registry_path=REGISTRY_PATH)
        gh_tools = [t for t in result["tools"] if t["name"] == "GitHub CLI"]
        assert len(gh_tools) == 1
        assert gh_tools[0]["available"] is True
        assert "cli_available" in gh_tools[0]["detection_methods"]

    @patch("shutil.which", return_value=None)
    def test_cli_not_detected_when_missing(self, mock_which):
        """CLI tool not marked available when binary not found."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["docker"], registry_path=REGISTRY_PATH)
        docker_tools = [t for t in result["tools"] if t["name"] == "Docker CLI"]
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

        aws_tools = [t for t in result["tools"] if t["name"] == "AWS CLI"]
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

        stripe_tools = [t for t in result["tools"] if t["name"] == "Stripe CLI"]
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


class TestToolingDiscoverIntegration:
    def test_tooling_discover_jira_returns_tier_1(self):
        """tooling_discover('jira') returns Atlassian MCP with Tier 1."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["jira"], registry_path=REGISTRY_PATH)
        tier_1 = [t for t in result["tools"] if t["trust_tier"] == 1]
        tier_1_names = {t["name"] for t in tier_1}
        assert "Atlassian MCP Server" in tier_1_names

    def test_tooling_discover_multiple_keywords(self):
        """Multiple keywords match across domains."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["docker", "kubernetes"], registry_path=REGISTRY_PATH)
        tool_names = {t["name"] for t in result["tools"]}
        assert "Docker CLI" in tool_names
        assert "kubectl" in tool_names

    def test_detection_summary_counts(self):
        """Detection summary has correct count fields."""
        from spellbook.tooling.discovery import discover_tools

        result = discover_tools(["github"], registry_path=REGISTRY_PATH)
        summary = result["detection_summary"]
        assert "registry_matches" in summary
        assert "mcp_available" in summary
        assert "cli_available" in summary
        assert "dep_detected" in summary
        assert summary["registry_matches"] == 2

    def test_feature_research_file_exists(self):
        """feature-research.md exists as a command file."""
        feature_research_path = (
            Path(__file__).parent.parent.parent / "commands" / "feature-research.md"
        )
        assert feature_research_path.exists(), "commands/feature-research.md should exist"
