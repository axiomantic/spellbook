from __future__ import annotations

import abc
import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, AsyncIterator, Union

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
    # Callback invoked with each text chunk as it streams from the model.
    # Useful for showing progress in scripts. Receives plain text (not JSON).
    on_text: Optional[Callable[[str], None]] = None
    # Timeout in seconds for the entire run() call. None = no timeout.
    timeout: Optional[float] = 120.0

@dataclass
class AgentMessage:
    """A message in the agent conversation."""
    role: str
    content: str
    type: str = "text"
    usage: Dict[str, int] = field(default_factory=dict)


def _extract_text(content: Any) -> str:
    """Extract plain text from an AssistantMessage's content blocks.

    AssistantMessage.content is list[ContentBlock] where ContentBlock
    can be TextBlock(text=str), ToolUseBlock, ThinkingBlock, etc.
    We only care about TextBlock.text for output.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content) if content else ""
    parts: list[str] = []
    for block in content:
        # TextBlock has a .text attribute
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _stderr_printer(line: str) -> None:
    """Default stderr callback: print to stderr."""
    print(line, file=sys.stderr, flush=True)


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

    @abc.abstractmethod
    async def run_subprocess(self, prompt: str) -> Dict[str, Any]:
        """Run the CLI as a headless subprocess, returning output."""
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

    def _make_claude_options(self):
        from claude_agent_sdk import ClaudeAgentOptions
        return ClaudeAgentOptions(
            system_prompt=self.options.system_prompt,
            cwd=str(self.options.cwd),
            model=self.options.model,
            max_turns=self.options.max_turns,
            permission_mode=self.options.permission_mode,
            allowed_tools=self.options.allowed_tools,
            disallowed_tools=self.options.disallowed_tools,
            # Pass stderr through so CLI errors are visible
            stderr=_stderr_printer,
        )

    async def query(self, prompt: str) -> AsyncIterator[AgentMessage]:
        """Send a prompt and stream response messages.

        Collects all messages inside the async-with block to avoid yielding
        through anyio cancel scopes (which breaks on cross-task finalization).
        Streams text to on_text callback as it arrives.
        """
        try:
            from claude_agent_sdk import ClaudeSDKClient
        except ImportError:
            raise ImportError(
                "claude-agent-sdk not installed. Install with: uv pip install 'spellbook[claude]'"
            )

        on_text = self.options.on_text
        messages: list[AgentMessage] = []

        async with ClaudeSDKClient(self._make_claude_options()) as client:
            await client.query(prompt)
            async for msg in client.receive_messages():
                msg_type = type(msg).__name__
                if msg_type == "AssistantMessage":
                    text = _extract_text(getattr(msg, "content", ""))
                    if on_text and text:
                        on_text(text)
                    messages.append(AgentMessage(
                        role="assistant",
                        content=text,
                        usage=getattr(msg, "usage", {}) or {},
                    ))
                elif msg_type == "ResultMessage":
                    result = getattr(msg, "result", "") or ""
                    if result:
                        messages.append(AgentMessage(
                            role="result",
                            content=result,
                            usage=getattr(msg, "usage", {}) or {},
                        ))

        for msg in messages:
            yield msg

    async def run(self, prompt: str) -> str:
        """Run a single-turn prompt and return the final text.

        Respects self.options.timeout (seconds). Raises asyncio.TimeoutError
        if the timeout is exceeded.
        """
        async def _inner() -> str:
            final_text = ""
            async for msg in self.query(prompt):
                if msg.role == "result":
                    return msg.content
                if msg.role == "assistant":
                    final_text = msg.content
            return final_text

        timeout = self.options.timeout
        if timeout is not None:
            return await asyncio.wait_for(_inner(), timeout=timeout)
        return await _inner()

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

    async def run_subprocess(self, prompt: str) -> Dict[str, Any]:
        """Run Claude CLI as a headless subprocess with -p flag.

        Uses the same permission_mode and allowed_tools from AgentOptions.
        Returns {"status": "completed", "output": str} or raises on failure.
        """
        cmd = ["claude", "-p", prompt, "--output-format", "text"]

        if self.options.permission_mode:
            cmd.extend(["--permission-mode", self.options.permission_mode])

        if self.options.allowed_tools:
            cmd.extend(["--allowedTools"] + self.options.allowed_tools)

        if self.options.disallowed_tools:
            cmd.extend(["--disallowedTools"] + self.options.disallowed_tools)

        if self.options.model:
            cmd.extend(["--model", self.options.model])

        if self.options.system_prompt:
            cmd.extend(["--system-prompt", self.options.system_prompt])

        if self.options.extra_args:
            cmd.extend(self.options.extra_args)

        env = self.options.env.copy()
        # Prevent the subprocess from detecting it's inside Claude Code,
        # which would cause recursive session detection issues.
        for key in ("CLAUDE_CODE", "CLAUDE_PROJECT_DIR", "CLAUDE_ENV_FILE"):
            env.pop(key, None)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.options.cwd),
            env=env,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            err_text = stderr.decode().strip()
            raise RuntimeError(f"Claude CLI failed (code {process.returncode}): {err_text}")

        return {
            "status": "completed",
            "output": stdout.decode().strip(),
            "pid": process.pid,
        }

class GeminiAgentClient(AgentClient):
    """Client for Gemini CLI, emulating the Claude SDK interface via async subprocess."""

    @property
    def provider(self) -> str:
        return "gemini"

    async def query(self, prompt: str) -> AsyncIterator[AgentMessage]:
        """Run gemini CLI asynchronously and yield a single response message."""
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
        if self.options.system_prompt:
            cmd[2] = f"{self.options.system_prompt}\n\n{prompt}"

        if self.options.extra_args:
            cmd.extend(self.options.extra_args)

        # Handle environment and prevent recursive CLI detection
        env = self.options.env.copy()
        if "GEMINI_CLI" in env:
            del env["GEMINI_CLI"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.options.cwd),
            env=env
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            err_text = stderr.decode().strip()
            raise RuntimeError(f"Gemini CLI failed (code {process.returncode}): {err_text}")

        content = stdout.decode().strip()
        on_text = self.options.on_text
        if on_text and content:
            on_text(content)

        yield AgentMessage(
            role="assistant",
            content=content
        )

    async def run(self, prompt: str) -> str:
        async def _inner() -> str:
            msg_list = [m async for m in self.query(prompt)]
            return msg_list[0].content if msg_list else ""

        timeout = self.options.timeout
        if timeout is not None:
            return await asyncio.wait_for(_inner(), timeout=timeout)
        return await _inner()

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

    async def run_subprocess(self, prompt: str) -> Dict[str, Any]:
        """Run Gemini CLI as a headless subprocess."""
        # Reuse the existing query() method which already runs as a subprocess
        result = await self.run(prompt)
        return {"status": "completed", "output": result, "pid": None}


class OpencodeAgentClient(AgentClient):
    """Client for OpenCode CLI via z.AI Coding Plan, emulating the Claude SDK interface via async subprocess.

    Routes all model invocations through opencode run (headless one-shot mode).
    No direct API calls to z.AI — everything goes through OpenCode.
    """

    @property
    def provider(self) -> str:
        return "opencode"

    async def query(self, prompt: str) -> AsyncIterator[AgentMessage]:
        """Run opencode run asynchronously and yield a single response message.
        
        Uses --format json for machine-parseable output.
        """
        # Set up on_text callback
        on_text = self.options.on_text
        
        # Build command based on Unified AgentOptions
        cmd = ["opencode", "run", "--format", "json"]
        
        # Model selection
        if self.options.model:
            cmd.extend(["-m", self.options.model])
        else:
            cmd.extend(["-m", "zai-coding-plan/glm-4.7"])
        
        # If a system prompt is provided, prepend it to the prompt
        if self.options.system_prompt:
            prompt = f"{self.options.system_prompt}\n\n{prompt}"
        
        cmd.append(prompt)
        
        # Permission mode is config-based in OpenCode, not CLI flag
        # Just pass through extra_args for any custom flags
        
        if self.options.extra_args:
            cmd.extend(self.options.extra_args)
        
        # Handle environment and prevent recursive CLI detection
        env = self.options.env.copy()
        if "OPENCODE" in env:
            del env["OPENCODE"]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.options.cwd),
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_text = stderr.decode().strip()
            raise RuntimeError(f"OpenCode CLI failed (code {process.returncode}): {err_text}")
        
        # Parse JSONL output
        content = ""
        lines = stdout.decode().strip().split("\n")
        
        for line in lines:
            if not line.strip():
                continue
            try:
                import json
                event = json.loads(line)
                # OpenCode JSONL events: "message.delta.content.text.value" or similar
                # We extract the final text content
                if "message" in event and "delta" in event["message"]:
                    delta = event["message"]["delta"]
                    if "content" in delta and "text" in delta["content"]:
                        text = delta["content"]["text"]
                        if on_text:
                            on_text(text)
                        content += text
            except json.JSONDecodeError:
                # Skip non-JSON lines (shouldn't happen with --format json)
                continue
        
        yield AgentMessage(
            role="assistant",
            content=content
        )

    async def run(self, prompt: str) -> str:
        """Run a single-turn prompt and return the final text.
        
        Respects self.options.timeout (seconds). Raises asyncio.TimeoutError
        if the timeout is exceeded.
        """
        async def _inner() -> str:
            final_text = ""
            async for msg in self.query(prompt):
                final_text = msg.content
            return final_text

        timeout = self.options.timeout
        if timeout is not None:
            return await asyncio.wait_for(_inner(), timeout=timeout)
        return await _inner()

    def spawn_session(self, prompt: str, terminal: Optional[str] = None) -> Dict[str, Any]:
        """Spawn an interactive terminal session with OpenCode."""
        from spellbook.daemon.terminal import detect_terminal, spawn_terminal_window
        if terminal is None:
            terminal = detect_terminal()
        return spawn_terminal_window(
            terminal=terminal,
            prompt=prompt,
            working_directory=str(self.options.cwd),
            cli_command="opencode"
        )

    async def run_subprocess(self, prompt: str) -> Dict[str, Any]:
        """Run OpenCode CLI as a headless subprocess."""
        # Reuse the existing query() method which already runs as a subprocess
        result = await self.run(prompt)
        return {"status": "completed", "output": result, "pid": None}


def get_agent_client(provider: Optional[str] = None, options: Optional[AgentOptions] = None) -> AgentClient:
    """Factory to get the right client."""
    if provider is None:
        # Check for OpenCode environment variable
        if os.environ.get("OPENCODE"):
            provider = "opencode"
        elif os.environ.get("GEMINI_CLI"):
            provider = "gemini"
        else:
            provider = "claude"

    if provider == "claude":
        return ClaudeAgentClient(options)
    elif provider == "gemini":
        return GeminiAgentClient(options)
    elif provider == "opencode":
        return OpencodeAgentClient(options)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
