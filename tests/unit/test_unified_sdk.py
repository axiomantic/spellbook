import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from spellbook.sdk.unified import (
    AgentOptions, 
    AgentMessage, 
    ClaudeAgentClient, 
    GeminiAgentClient, 
    get_agent_client
)

@pytest.mark.asyncio
async def test_claude_agent_client_query():
    options = AgentOptions(system_prompt="test prompt", model="sonnet")
    client = ClaudeAgentClient(options)
    
    mock_msg = MagicMock()
    mock_msg.role = "assistant"
    mock_msg.content = "hello from claude"
    mock_msg.usage = {"input_tokens": 10}
    
    # Mock the ClaudeSDKClient and its query method
    mock_sdk_client_instance = MagicMock()
    # Create an async iterator helper
    class AsyncIter:
        def __init__(self, items):
            self.items = items
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)
            
    mock_sdk_client_instance.query.return_value = AsyncIter([mock_msg])
    mock_sdk_client_instance.__aenter__.return_value = mock_sdk_client_instance
    mock_sdk_client_instance.__aexit__ = AsyncMock()
    
    with patch("claude_agent_sdk.ClaudeSDKClient", return_value=mock_sdk_client_instance):
        messages = []
        async for msg in client.query("hi"):
            messages.append(msg)
            
        assert len(messages) == 1
        assert messages[0].content == "hello from claude"
        assert messages[0].role == "assistant"
        assert messages[0].usage == {"input_tokens": 10}

@pytest.mark.asyncio
async def test_claude_agent_client_run():
    client = ClaudeAgentClient()
    
    with patch.object(ClaudeAgentClient, "query") as mock_query:
        mock_query.return_value.__aiter__.return_value = [
            AgentMessage(role="assistant", content="final result")
        ]
        
        result = await client.run("do something")
        assert result == "final result"

@pytest.mark.asyncio
async def test_gemini_agent_client_run():
    options = AgentOptions(model="gemini-2.5-flash")
    client = GeminiAgentClient(options)
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello from gemini"
    
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = await client.run("hi")
        
        assert result == "hello from gemini"
        # Check if correct command was built
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert "gemini" in cmd
        assert "--prompt" in cmd
        assert "hi" in cmd
        assert "gemini-2.5-flash" in cmd

def test_get_agent_client_factory():
    # Test auto-detection
    with patch.dict(os.environ, {"GEMINI_CLI": "1"}):
        client = get_agent_client()
        assert isinstance(client, GeminiAgentClient)
        
    with patch.dict(os.environ, {}, clear=True):
        client = get_agent_client()
        assert isinstance(client, ClaudeAgentClient)
        
    # Test explicit provider
    client = get_agent_client(provider="gemini")
    assert isinstance(client, GeminiAgentClient)
    
    client = get_agent_client(provider="claude")
    assert isinstance(client, ClaudeAgentClient)

@pytest.mark.asyncio
async def test_gemini_spawn_session():
    client = GeminiAgentClient()
    
    with patch("spellbook.daemon.terminal.spawn_terminal_window") as mock_spawn:
        mock_spawn.return_value = {"status": "spawned"}
        
        result = client.spawn_session("start shell")
        assert result["status"] == "spawned"
        
        args, kwargs = mock_spawn.call_args
        assert kwargs["cli_command"] == "gemini"
        assert kwargs["prompt"] == "start shell"
