from __future__ import annotations

import os
from typing import Optional, Type

from spellbook.sdk.base import AssistantSDK, SDKConfig
from spellbook.sdk.claude import ClaudeSDK
from spellbook.sdk.gemini import GeminiSDK

def detect_provider() -> str:
    """Detect the current assistant provider based on environment variables."""
    if os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("CLAUDECODE"):
        return "claude"
    if os.environ.get("GEMINI_CLI"):
        return "gemini"
    # Default to claude if unsure, or read from a config file
    return os.environ.get("SPELLBOOK_DEFAULT_PROVIDER", "claude")

def get_sdk(provider: Optional[str] = None, config: Optional[SDKConfig] = None) -> AssistantSDK:
    """Factory function to get the appropriate SDK instance."""
    if provider is None:
        provider = detect_provider()
        
    if provider == "claude":
        return ClaudeSDK(config)
    if provider == "gemini":
        return GeminiSDK(config)
        
    raise ValueError(f"Unknown or unsupported provider: {provider}")

class UnifiedSDK:
    """A high-level wrapper that routes calls to the appropriate provider SDK."""
    
    def __init__(self, provider: Optional[str] = None, config: Optional[SDKConfig] = None):
        self.sdk = get_sdk(provider, config)
        
    async def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ChatResponse:
        return await self.sdk.chat(prompt, context=context)
        
    async def run_command(self, command: str, args: List[str]) -> str:
        return await self.sdk.run_command(command, args)

    async def call_mcp(self, server: str, tool: str, arguments: Dict[str, Any]) -> Any:
        return await self.sdk.call_mcp(server, tool, arguments)
        
    @property
    def provider(self) -> str:
        return self.sdk.provider_name
