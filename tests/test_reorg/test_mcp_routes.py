"""Tests for spellbook.mcp.routes module.

Verifies that the routes module is importable and contains the expected
custom route handler functions.
"""



class TestMcpRoutesImportable:
    """Test that spellbook.mcp.routes is importable with expected exports."""

    def test_module_importable(self):
        import spellbook.mcp.routes  # noqa: F401

    def test_api_health_exists(self):
        from spellbook.mcp.routes import api_health

        assert callable(api_health)
