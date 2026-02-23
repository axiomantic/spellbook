"""User preferences management."""

import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from .command_utils import atomic_write_json, read_json_safe


class CoordinationBackend(str, Enum):
    """Coordination backend types."""
    MCP_STREAMABLE_HTTP = "mcp-streamable-http"
    N8N = "n8n"
    LANGCHAIN = "langchain"
    CUSTOM = "custom"
    NONE = "none"


@dataclass
class MCPSSEConfig:
    """Configuration for MCP SSE backend."""
    port: int = 3000
    host: str = "localhost"
    sse_fallback: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MCPSSEConfig":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class N8NConfig:
    """Configuration for N8N backend."""
    webhook_base_url: Optional[str] = None
    api_key_env: str = "N8N_API_KEY"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "N8NConfig":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class CustomConfig:
    """Configuration for custom backend."""
    endpoints: dict = field(default_factory=dict)
    auth: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CustomConfig":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class CoordinationConfig:
    """Complete coordination configuration."""
    backend: CoordinationBackend = CoordinationBackend.NONE
    mcp_sse: Optional[MCPSSEConfig] = None
    n8n: Optional[N8NConfig] = None
    custom: Optional[CustomConfig] = None
    auto_merge: bool = True
    notify_on_complete: bool = True
    retry_on_error: bool = True
    max_retries: int = 3

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "backend": self.backend.value if isinstance(self.backend, CoordinationBackend) else self.backend,
            "auto_merge": self.auto_merge,
            "notify_on_complete": self.notify_on_complete,
            "retry_on_error": self.retry_on_error,
            "max_retries": self.max_retries
        }
        if self.mcp_sse is not None:
            result["mcp_sse"] = self.mcp_sse.to_dict()
        if self.n8n is not None:
            result["n8n"] = self.n8n.to_dict()
        if self.custom is not None:
            result["custom"] = self.custom.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "CoordinationConfig":
        """Create from dictionary."""
        backend = CoordinationBackend(data.get("backend", "none"))
        mcp_sse = MCPSSEConfig.from_dict(data["mcp_sse"]) if "mcp_sse" in data else None
        n8n = N8NConfig.from_dict(data["n8n"]) if "n8n" in data else None
        custom = CustomConfig.from_dict(data["custom"]) if "custom" in data else None

        return cls(
            backend=backend,
            mcp_sse=mcp_sse,
            n8n=n8n,
            custom=custom,
            auto_merge=data.get("auto_merge", True),
            notify_on_complete=data.get("notify_on_complete", True),
            retry_on_error=data.get("retry_on_error", True),
            max_retries=data.get("max_retries", 3)
        )


def get_preferences_path() -> Path:
    """Get path to preferences file."""
    from installer.compat import get_config_dir
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "preferences.json"

def load_preferences() -> dict:
    """Load user preferences."""
    prefs_path = get_preferences_path()

    if not prefs_path.exists():
        return {
            "terminal": {
                "program": None,
                "detected": False
            },
            "execution_mode": {
                "default": None,
                "always_ask": True
            }
        }

    return read_json_safe(str(prefs_path))

def save_preference(key: str, value: Any):
    """
    Save a preference value.

    Args:
        key: Dot-separated key path (e.g., "terminal.program")
        value: Value to save
    """
    prefs = load_preferences()

    keys = key.split('.')
    current = prefs
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]

    current[keys[-1]] = value

    prefs_path = get_preferences_path()
    atomic_write_json(str(prefs_path), prefs)

def get_coordination_backend() -> CoordinationBackend:
    """
    Get the configured coordination backend.

    Returns:
        CoordinationBackend enum value
    """
    prefs = load_preferences()
    coordination = prefs.get("coordination", {})
    backend_str = coordination.get("backend", "none")
    return CoordinationBackend(backend_str)

def load_coordination_config() -> CoordinationConfig:
    """
    Load coordination configuration from preferences.

    Returns:
        CoordinationConfig with all settings
    """
    prefs = load_preferences()
    coordination = prefs.get("coordination", {})

    if not coordination:
        return CoordinationConfig()

    return CoordinationConfig.from_dict(coordination)

def validate_coordination_config(config: CoordinationConfig) -> list[str]:
    """
    Validate coordination configuration.

    Args:
        config: Configuration to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Validate backend-specific config
    if config.backend == CoordinationBackend.MCP_STREAMABLE_HTTP:
        if config.mcp_sse is None:
            errors.append("MCP backend requires mcp_sse configuration")
        elif config.mcp_sse.port < 1 or config.mcp_sse.port > 65535:
            errors.append("MCP port must be between 1 and 65535")

    elif config.backend == CoordinationBackend.N8N:
        if config.n8n is None:
            errors.append("N8N backend requires n8n configuration")
        elif config.n8n.webhook_base_url is None:
            errors.append("N8N backend requires webhook_base_url")

    elif config.backend == CoordinationBackend.CUSTOM:
        if config.custom is None:
            errors.append("Custom backend requires custom configuration")
        elif not config.custom.endpoints:
            errors.append("Custom backend requires endpoints configuration")

    # Validate behavior settings
    if config.max_retries < 0:
        errors.append("max_retries must be non-negative")

    return errors
