from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from spellbook.sdk.base import AssistantSDK, ChatResponse, SDKConfig

class ClaudeSDK(AssistantSDK):
    """SDK for Claude (Anthropic), wrapping the Claude Code CLI."""

    @property
    def provider_name(self) -> str:
        return "claude"

    async def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ChatResponse:
        """Execute a prompt via `claude --print` to leverage CLI-level context."""
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]
        
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        
        if self.config.extra_args:
            cmd.extend(self.config.extra_args)
            
        cmd.append(prompt)

        # Unset CLAUDECODE to allow nested execution
        env = self.config.env.copy()
        if "CLAUDECODE" in env:
            del env["CLAUDECODE"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=self.config.project_root,
                env=env,
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Claude CLI failed: {result.stderr}")
                
            return ChatResponse(
                text=result.stdout.strip(),
                raw_response=result
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Claude CLI timed out after {self.config.timeout}s")

    async def run_command(self, command: str, args: List[str]) -> str:
        """Run a slash command or other CLI command."""
        full_prompt = f"{command} " + " ".join(args)
        resp = await self.chat(full_prompt)
        return resp.text

    async def call_mcp(self, server: str, tool: str, arguments: Dict[str, Any]) -> Any:
        """Invoke an MCP tool by instructing Claude to use it."""
        # We instruct Claude to use the specific tool. 
        # Claude Code will look up the tool in its configured MCP servers.
        args_json = json.dumps(arguments)
        prompt = f"Call the MCP tool '{tool}' from server '{server}' with these arguments: {args_json}. Return only the result."
        resp = await self.chat(prompt)
        return resp.text
