"""Tests for tooling discovery system."""

import pytest
import yaml
from pathlib import Path


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
