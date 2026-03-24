from __future__ import annotations

import abc
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncIterator, Union

@dataclass
class AgentOptions:
    """Unified configuration for an AI Agent."""
    system_prompt: Optional[str] = None
    cwd: Path = field(default_factory=Path.cwd)
    model: Optional[str] = None
    max_turns: int = 10
    permission_mode: str = "dontAsk"  # equivalent to --yolo
    allowed_tools: Optional[List[str]] = None
    disallowed_tools: Optional[List[str]] = None
    extra_args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=lambda: os.environ.copy())

@dataclass
class AgentMessage:
    """A message in the agent conversation."""
    role: str
    content: str
    type: str = "text"
    usage: Dict[str, int] = field(default_factory=dict)

class AgentClient(abc.ABC):
    """Programmatic client for an AI Agent, mirroring claude-agent-sdk-python."""

    def __init__(self, options: Optional[AgentOptions] = None):
        self.options = options or AgentOptions()

    @abc.abstractmethod
    async def query(self, prompt: str) -> AsyncIterator[AgentMessage]:
        """Send a prompt and iterate over streaming response messages."""
        pass

    @abc.abstractmethod
    async def run(self, prompt: str) -> str:
        """Run a single-turn prompt and return the final text result."""
        pass

    @abc.abstractmethod
    def spawn_session(self, prompt: str, terminal: Optional[str] = None) -> Dict[str, Any]:
        """Spawn an interactive terminal session."""
        pass

    @property
    @abc.abstractmethod
    def provider(self) -> str:
        """The provider name (claude or gemini)."""
        pass

class ClaudeAgentClient(AgentClient):
    """Client using the official claude-agent-sdk-python."""

    @property
    def provider(self) -> str:
        return "claude"

    async def query(self, prompt: str) -> AsyncIterator[AgentMessage]:
        try:
            from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        except ImportError:
            raise ImportError(
                "claude-agent-sdk not installed. Install with: uv pip install 'spellbook[claude]'"
            )
        
        # Map unified options to Claude-specific options
        claude_options = ClaudeAgentOptions(
            system_prompt=self.options.system_prompt,
            cwd=str(self.options.options.cwd) if hasattr(self.options, 'options') else str(self.options.cwd),
            model=self.options.model,
            max_turns=self.options.max_turns,
            permission_mode=self.options.permission_mode,
            allowed_tools=self.options.allowed_tools,
            disallowed_tools=self.options.disallowed_tools,
        )
        
        async with ClaudeSDKClient(claude_options) as client:
            async for msg in client.query(prompt):
                # Map SDK message to our unified AgentMessage
                yield AgentMessage(
                    role=getattr(msg, 'role', 'assistant'),
                    content=getattr(msg, 'content', str(msg)),
                    usage=getattr(msg, 'usage', {})
                )

    async def run(self, prompt: str) -> str:
        final_text = ""
        async for msg in self.query(prompt):
            if msg.role == "assistant":
                final_text = msg.content
        return final_text

    def spawn_session(self, prompt: str, terminal: Optional[str] = None) -> Dict[str, Any]:
        from spellbook.daemon.terminal import detect_terminal, spawn_terminal_window
        if terminal is None:
            terminal = detect_terminal()
        return spawn_terminal_window(
            terminal=terminal,
            prompt=prompt,
            working_directory=str(self.options.cwd),
            cli_command="claude"
        )

class GeminiAgentClient(AgentClient):
    """Client for Gemini CLI, emulating the Claude SDK interface via subprocess."""

    @property
    def provider(self) -> str:
        return "gemini"

    async def query(self, prompt: str) -> AsyncIterator[AgentMessage]:
        """Run gemini CLI and yield a single response message."""
        import subprocess
        
        # Build command based on Unified AgentOptions
        cmd = ["gemini", "--prompt", prompt, "-o", "text"]
        
        # Map permission modes
        if self.options.permission_mode == "dontAsk":
            cmd.append("--yolo")
        elif self.options.permission_mode == "acceptEdits":
            cmd.extend(["--approval-mode", "auto_edit"])
        
        if self.options.model:
            cmd.extend(["--model", self.options.model])
            
        # If a system prompt is provided, we prepend it to the prompt 
        # (Gemini CLI doesn't have a direct --system-prompt flag yet)
        if self.options.system_prompt:
            cmd[2] = f"{self.options.system_prompt}\n\n{prompt}"

        if self.options.extra_args:
            cmd.extend(self.options.extra_args)

        # Handle environment and prevent recursive CLI detection
        env = self.options.env.copy()
        if "GEMINI_CLI" in env:
            del env["GEMINI_CLI"]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.options.cwd),
            env=env
        )
        
        if process.returncode != 0:
            raise RuntimeError(f"Gemini CLI failed (code {process.returncode}): {process.stderr}")
            
        yield AgentMessage(
            role="assistant",
            content=process.stdout.strip()
        )

    async def run(self, prompt: str) -> str:
        msg_list = [m async for m in self.query(prompt)]
        return msg_list[0].content if msg_list else ""

    def spawn_session(self, prompt: str, terminal: Optional[str] = None) -> Dict[str, Any]:
        from spellbook.daemon.terminal import detect_terminal, spawn_terminal_window
        if terminal is None:
            terminal = detect_terminal()
        return spawn_terminal_window(
            terminal=terminal,
            prompt=prompt,
            working_directory=str(self.options.cwd),
            cli_command="gemini"
        )

def get_agent_client(provider: Optional[str] = None, options: Optional[AgentOptions] = None) -> AgentClient:
    """Factory to get the right client."""
    if provider is None:
        if os.environ.get("GEMINI_CLI"):
            provider = "gemini"
        else:
            provider = "claude"
            
    if provider == "claude":
        return ClaudeAgentClient(options)
    elif provider == "gemini":
        return GeminiAgentClient(options)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
