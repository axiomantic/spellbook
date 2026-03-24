from __future__ import annotations

import abc
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union

@dataclass
class SDKConfig:
    """Configuration for an Assistant SDK."""
    project_root: Path = field(default_factory=Path.cwd)
    model: Optional[str] = None
    timeout: int = 300
    extra_args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=lambda: os.environ.copy())

@dataclass
class ChatResponse:
    """Response from an assistant."""
    text: str
    usage: Dict[str, int] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    raw_response: Any = None

class AssistantSDK(abc.ABC):
    """Abstract base class for Assistant SDKs."""

    def __init__(self, config: Optional[SDKConfig] = None):
        self.config = config or SDKConfig()

    @abc.abstractmethod
    async def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ChatResponse:
        """Send a prompt to the assistant and get a response."""
        pass

    @abc.abstractmethod
    async def run_command(self, command: str, args: List[str]) -> str:
        """Invoke a CLI-style command (e.g. '/help', '/skill')."""
        pass

    @abc.abstractmethod
    async def call_mcp(self, server: str, tool: str, arguments: Dict[str, Any]) -> Any:
        """Invoke an MCP tool through the provider's CLI infrastructure."""
        pass

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """The name of the provider (e.g. 'claude', 'gemini')."""
        pass

    def _resolve_project_file(self, filename: str) -> Optional[Path]:
        """Look for a project file (like CLAUDE.md) in the project root."""
        path = self.config.project_root / filename
        return path if path.exists() else None
