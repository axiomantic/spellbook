"""Tests for coordination configuration in preferences."""

import json
import pytest
from pathlib import Path
from spellbook_mcp.preferences import (
    load_preferences,
    save_preference,
    get_preferences_path,
    CoordinationBackend,
    CoordinationConfig,
    MCPSSEConfig,
    N8NConfig,
    CustomConfig,
    get_coordination_backend,
    load_coordination_config,
    validate_coordination_config
)


@pytest.fixture
def temp_prefs_file(tmp_path, monkeypatch):
    """Create temporary preferences file."""
    prefs_dir = tmp_path / ".config" / "spellbook"
    prefs_dir.mkdir(parents=True, exist_ok=True)
    prefs_file = prefs_dir / "preferences.json"

    # Mock get_preferences_path to use temp directory
    monkeypatch.setattr(
        "spellbook_mcp.preferences.get_preferences_path",
        lambda: prefs_file
    )

    return prefs_file


class TestCoordinationBackend:
    """Test CoordinationBackend enum."""

    def test_backend_values(self):
        """Test all backend enum values exist."""
        assert CoordinationBackend.MCP_STREAMABLE_HTTP == "mcp-streamable-http"
        assert CoordinationBackend.N8N == "n8n"
        assert CoordinationBackend.LANGCHAIN == "langchain"
        assert CoordinationBackend.CUSTOM == "custom"
        assert CoordinationBackend.NONE == "none"

    def test_backend_from_string(self):
        """Test creating backend from string value."""
        backend = CoordinationBackend("mcp-streamable-http")
        assert backend == CoordinationBackend.MCP_STREAMABLE_HTTP


class TestMCPSSEConfig:
    """Test MCPSSEConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MCPSSEConfig()
        assert config.port == 3000
        assert config.host == "localhost"
        assert config.sse_fallback is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = MCPSSEConfig(port=8080, host="0.0.0.0", sse_fallback=False)
        assert config.port == 8080
        assert config.host == "0.0.0.0"
        assert config.sse_fallback is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = MCPSSEConfig(port=9000, host="127.0.0.1")
        data = config.to_dict()
        assert data == {
            "port": 9000,
            "host": "127.0.0.1",
            "sse_fallback": True
        }

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {"port": 5000, "host": "example.com", "sse_fallback": False}
        config = MCPSSEConfig.from_dict(data)
        assert config.port == 5000
        assert config.host == "example.com"
        assert config.sse_fallback is False


class TestN8NConfig:
    """Test N8NConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = N8NConfig()
        assert config.webhook_base_url is None
        assert config.api_key_env == "N8N_API_KEY"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = N8NConfig(
            webhook_base_url="https://hooks.n8n.io",
            api_key_env="CUSTOM_KEY"
        )
        assert config.webhook_base_url == "https://hooks.n8n.io"
        assert config.api_key_env == "CUSTOM_KEY"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = N8NConfig(webhook_base_url="https://example.com")
        data = config.to_dict()
        assert data == {
            "webhook_base_url": "https://example.com",
            "api_key_env": "N8N_API_KEY"
        }

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {"webhook_base_url": "https://test.com", "api_key_env": "TEST_KEY"}
        config = N8NConfig.from_dict(data)
        assert config.webhook_base_url == "https://test.com"
        assert config.api_key_env == "TEST_KEY"


class TestCustomConfig:
    """Test CustomConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CustomConfig()
        assert config.endpoints == {}
        assert config.auth is None

    def test_custom_values(self):
        """Test custom configuration values."""
        endpoints = {"status": "http://localhost/status"}
        auth = {"type": "bearer", "token_env": "AUTH_TOKEN"}
        config = CustomConfig(endpoints=endpoints, auth=auth)
        assert config.endpoints == endpoints
        assert config.auth == auth

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = CustomConfig(
            endpoints={"test": "url"},
            auth={"type": "basic"}
        )
        data = config.to_dict()
        assert data == {
            "endpoints": {"test": "url"},
            "auth": {"type": "basic"}
        }

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "endpoints": {"api": "http://api.example.com"},
            "auth": {"type": "api_key"}
        }
        config = CustomConfig.from_dict(data)
        assert config.endpoints == data["endpoints"]
        assert config.auth == data["auth"]


class TestCoordinationConfig:
    """Test CoordinationConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CoordinationConfig()
        assert config.backend == CoordinationBackend.NONE
        assert config.mcp_sse is None
        assert config.n8n is None
        assert config.custom is None
        assert config.auto_merge is True
        assert config.notify_on_complete is True
        assert config.retry_on_error is True
        assert config.max_retries == 3

    def test_mcp_backend(self):
        """Test configuration with MCP backend."""
        mcp_config = MCPSSEConfig(port=4000)
        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=mcp_config
        )
        assert config.backend == CoordinationBackend.MCP_STREAMABLE_HTTP
        assert config.mcp_sse.port == 4000

    def test_n8n_backend(self):
        """Test configuration with N8N backend."""
        n8n_config = N8NConfig(webhook_base_url="https://hooks.example.com")
        config = CoordinationConfig(
            backend=CoordinationBackend.N8N,
            n8n=n8n_config
        )
        assert config.backend == CoordinationBackend.N8N
        assert config.n8n.webhook_base_url == "https://hooks.example.com"

    def test_custom_backend(self):
        """Test configuration with custom backend."""
        custom_config = CustomConfig(endpoints={"test": "url"})
        config = CoordinationConfig(
            backend=CoordinationBackend.CUSTOM,
            custom=custom_config
        )
        assert config.backend == CoordinationBackend.CUSTOM
        assert config.custom.endpoints == {"test": "url"}

    def test_behavior_settings(self):
        """Test behavior configuration settings."""
        config = CoordinationConfig(
            auto_merge=False,
            notify_on_complete=False,
            retry_on_error=False,
            max_retries=5
        )
        assert config.auto_merge is False
        assert config.notify_on_complete is False
        assert config.retry_on_error is False
        assert config.max_retries == 5

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=5000),
            auto_merge=False
        )
        data = config.to_dict()
        assert data["backend"] == "mcp-streamable-http"
        assert data["mcp_sse"]["port"] == 5000
        assert data["auto_merge"] is False

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "backend": "n8n",
            "n8n": {
                "webhook_base_url": "https://example.com",
                "api_key_env": "KEY"
            },
            "auto_merge": False,
            "max_retries": 10
        }
        config = CoordinationConfig.from_dict(data)
        assert config.backend == CoordinationBackend.N8N
        assert config.n8n.webhook_base_url == "https://example.com"
        assert config.auto_merge is False
        assert config.max_retries == 10


class TestGetCoordinationBackend:
    """Test get_coordination_backend function."""

    def test_no_coordination_config(self, temp_prefs_file):
        """Test when no coordination config exists."""
        backend = get_coordination_backend()
        assert backend == CoordinationBackend.NONE

    def test_mcp_backend(self, temp_prefs_file):
        """Test retrieving MCP backend."""
        prefs = {
            "coordination": {
                "backend": "mcp-streamable-http"
            }
        }
        temp_prefs_file.write_text(json.dumps(prefs))

        backend = get_coordination_backend()
        assert backend == CoordinationBackend.MCP_STREAMABLE_HTTP

    def test_n8n_backend(self, temp_prefs_file):
        """Test retrieving N8N backend."""
        prefs = {
            "coordination": {
                "backend": "n8n"
            }
        }
        temp_prefs_file.write_text(json.dumps(prefs))

        backend = get_coordination_backend()
        assert backend == CoordinationBackend.N8N

    def test_none_backend(self, temp_prefs_file):
        """Test retrieving NONE backend."""
        prefs = {
            "coordination": {
                "backend": "none"
            }
        }
        temp_prefs_file.write_text(json.dumps(prefs))

        backend = get_coordination_backend()
        assert backend == CoordinationBackend.NONE


class TestLoadCoordinationConfig:
    """Test load_coordination_config function."""

    def test_no_config(self, temp_prefs_file):
        """Test when no coordination config exists."""
        config = load_coordination_config()
        assert config.backend == CoordinationBackend.NONE
        assert config.mcp_sse is None
        assert config.n8n is None
        assert config.custom is None

    def test_mcp_config(self, temp_prefs_file):
        """Test loading MCP configuration."""
        prefs = {
            "coordination": {
                "backend": "mcp-streamable-http",
                "mcp_sse": {
                    "port": 3500,
                    "host": "0.0.0.0",
                    "sse_fallback": False
                },
                "auto_merge": False
            }
        }
        temp_prefs_file.write_text(json.dumps(prefs))

        config = load_coordination_config()
        assert config.backend == CoordinationBackend.MCP_STREAMABLE_HTTP
        assert config.mcp_sse.port == 3500
        assert config.mcp_sse.host == "0.0.0.0"
        assert config.mcp_sse.sse_fallback is False
        assert config.auto_merge is False

    def test_n8n_config(self, temp_prefs_file):
        """Test loading N8N configuration."""
        prefs = {
            "coordination": {
                "backend": "n8n",
                "n8n": {
                    "webhook_base_url": "https://hooks.n8n.io",
                    "api_key_env": "MY_N8N_KEY"
                },
                "retry_on_error": False,
                "max_retries": 5
            }
        }
        temp_prefs_file.write_text(json.dumps(prefs))

        config = load_coordination_config()
        assert config.backend == CoordinationBackend.N8N
        assert config.n8n.webhook_base_url == "https://hooks.n8n.io"
        assert config.n8n.api_key_env == "MY_N8N_KEY"
        assert config.retry_on_error is False
        assert config.max_retries == 5

    def test_custom_config(self, temp_prefs_file):
        """Test loading custom configuration."""
        prefs = {
            "coordination": {
                "backend": "custom",
                "custom": {
                    "endpoints": {
                        "status": "http://localhost:8000/status",
                        "execute": "http://localhost:8000/execute"
                    },
                    "auth": {
                        "type": "bearer",
                        "token_env": "CUSTOM_TOKEN"
                    }
                }
            }
        }
        temp_prefs_file.write_text(json.dumps(prefs))

        config = load_coordination_config()
        assert config.backend == CoordinationBackend.CUSTOM
        assert config.custom.endpoints["status"] == "http://localhost:8000/status"
        assert config.custom.auth["type"] == "bearer"

    def test_all_behavior_settings(self, temp_prefs_file):
        """Test loading all behavior settings."""
        prefs = {
            "coordination": {
                "backend": "none",
                "auto_merge": False,
                "notify_on_complete": False,
                "retry_on_error": False,
                "max_retries": 10
            }
        }
        temp_prefs_file.write_text(json.dumps(prefs))

        config = load_coordination_config()
        assert config.auto_merge is False
        assert config.notify_on_complete is False
        assert config.retry_on_error is False
        assert config.max_retries == 10


class TestValidateCoordinationConfig:
    """Test validate_coordination_config function."""

    def test_valid_mcp_config(self):
        """Test validation of valid MCP configuration."""
        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=3000)
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 0

    def test_valid_n8n_config(self):
        """Test validation of valid N8N configuration."""
        config = CoordinationConfig(
            backend=CoordinationBackend.N8N,
            n8n=N8NConfig(webhook_base_url="https://example.com")
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 0

    def test_valid_custom_config(self):
        """Test validation of valid custom configuration."""
        config = CoordinationConfig(
            backend=CoordinationBackend.CUSTOM,
            custom=CustomConfig(endpoints={"test": "url"})
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 0

    def test_valid_none_config(self):
        """Test validation of NONE backend."""
        config = CoordinationConfig(backend=CoordinationBackend.NONE)
        errors = validate_coordination_config(config)
        assert len(errors) == 0

    def test_mcp_backend_missing_config(self):
        """Test error when MCP backend lacks config."""
        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=None
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 1
        assert "mcp_sse" in errors[0].lower()

    def test_n8n_backend_missing_config(self):
        """Test error when N8N backend lacks config."""
        config = CoordinationConfig(
            backend=CoordinationBackend.N8N,
            n8n=None
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 1
        assert "n8n" in errors[0].lower()

    def test_custom_backend_missing_config(self):
        """Test error when custom backend lacks config."""
        config = CoordinationConfig(
            backend=CoordinationBackend.CUSTOM,
            custom=None
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 1
        assert "custom" in errors[0].lower()

    def test_invalid_port(self):
        """Test error when port is out of range."""
        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=70000)  # Invalid port
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 1
        assert "port" in errors[0].lower()

    def test_invalid_max_retries(self):
        """Test error when max_retries is negative."""
        config = CoordinationConfig(
            backend=CoordinationBackend.NONE,
            max_retries=-1
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 1
        assert "max_retries" in errors[0].lower()

    def test_n8n_missing_webhook_url(self):
        """Test error when N8N config lacks webhook URL."""
        config = CoordinationConfig(
            backend=CoordinationBackend.N8N,
            n8n=N8NConfig(webhook_base_url=None)
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 1
        assert "webhook_base_url" in errors[0].lower()

    def test_custom_missing_endpoints(self):
        """Test error when custom config lacks endpoints."""
        config = CoordinationConfig(
            backend=CoordinationBackend.CUSTOM,
            custom=CustomConfig(endpoints={})
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 1
        assert "endpoints" in errors[0].lower()

    def test_multiple_errors(self):
        """Test multiple validation errors are collected."""
        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=99999),  # Invalid port
            max_retries=-5  # Invalid retries
        )
        errors = validate_coordination_config(config)
        assert len(errors) == 2
        assert any("port" in e.lower() for e in errors)
        assert any("max_retries" in e.lower() for e in errors)


class TestPreferencesIntegration:
    """Test integration with existing preferences system."""

    def test_save_and_load_coordination_config(self, temp_prefs_file):
        """Test saving and loading coordination config via preferences."""
        # Save coordination backend
        save_preference("coordination.backend", "mcp-streamable-http")
        save_preference("coordination.mcp_sse.port", 4500)
        save_preference("coordination.mcp_sse.host", "127.0.0.1")
        save_preference("coordination.auto_merge", False)

        # Load and verify
        config = load_coordination_config()
        assert config.backend == CoordinationBackend.MCP_STREAMABLE_HTTP
        assert config.mcp_sse.port == 4500
        assert config.mcp_sse.host == "127.0.0.1"
        assert config.auto_merge is False

    def test_coordination_does_not_affect_other_prefs(self, temp_prefs_file):
        """Test coordination config doesn't interfere with other preferences."""
        # Set non-coordination preferences
        save_preference("terminal.program", "iTerm.app")
        save_preference("execution_mode.default", "sequential")

        # Set coordination preferences
        save_preference("coordination.backend", "n8n")

        # Verify all preferences preserved
        prefs = load_preferences()
        assert prefs["terminal"]["program"] == "iTerm.app"
        assert prefs["execution_mode"]["default"] == "sequential"
        assert prefs["coordination"]["backend"] == "n8n"
