from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Optional

from spellbook.sdk.base import AssistantSDK, ChatResponse, SDKConfig

class GeminiSDK(AssistantSDK):
    """SDK for Gemini (Google), wrapping the Gemini CLI."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ChatResponse:
        """Execute a prompt via `gemini --prompt` to leverage CLI-level context."""
        cmd = ["gemini", "--prompt", prompt, "--yolo"]
        
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        
        if self.config.extra_args:
            cmd.extend(self.config.extra_args)

        # Unset GEMINI_CLI to allow nested execution
        env = self.config.env.copy()
        if "GEMINI_CLI" in env:
            del env["GEMINI_CLI"]

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
                raise RuntimeError(f"Gemini CLI failed: {result.stderr}")
                
            return ChatResponse(
                text=result.stdout.strip(),
                raw_response=result
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Gemini CLI timed out after {self.config.timeout}s")

    async def run_command(self, command: str, args: List[str]) -> str:
        """Run a command via Gemini CLI."""
        # For Gemini CLI, we might need different positional handling
        full_prompt = f"{command} " + " ".join(args)
        resp = await self.chat(full_prompt)
        return resp.text

    async def call_mcp(self, server: str, tool: str, arguments: Dict[str, Any]) -> Any:
        """Invoke an MCP tool by instructing Gemini to use it."""
        import json
        args_json = json.dumps(arguments)
        prompt = f"Call the MCP tool '{tool}' from server '{server}' with these arguments: {args_json}. Return only the result."
        resp = await self.chat(prompt)
        return resp.text
