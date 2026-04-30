import os
import asyncio
import tripwire
import pytest
from spellbook.sdk.unified import (
    AgentOptions,
    AgentMessage,
    ClaudeAgentClient,
    GeminiAgentClient,
    OpencodeAgentClient,
    get_agent_client,
)


@pytest.mark.asyncio
async def test_claude_agent_client_query():
    options = AgentOptions(system_prompt="test prompt", model="sonnet")
    client = ClaudeAgentClient(options)

    # Create a mock message whose type().__name__ == "AssistantMessage"
    class AssistantMessage:
        def __init__(self):
            self.content = "hello from claude"
            self.usage = {"input_tokens": 10}

    mock_msg = AssistantMessage()

    # Async iterator helper for receive_messages
    class AsyncIter:
        def __init__(self, items):
            self.items = items
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)

    # Build a fake SDK client object with the methods ClaudeAgentClient.query() uses
    class FakeSDKClient:
        async def query(self, prompt):
            pass
        def receive_messages(self):
            return AsyncIter([mock_msg])
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    fake_client = FakeSDKClient()

    # Use a sentinel so we can assert the exact constructor arg
    sentinel_options = object()
    mock_make_opts = tripwire.mock.object(client, "_make_claude_options")
    mock_make_opts.returns(sentinel_options)

    # Mock the constructor to return our fake client
    mock_sdk = tripwire.mock("claude_agent_sdk:ClaudeSDKClient")
    mock_sdk.returns(fake_client)

    async with tripwire:
        messages = []
        async for msg in client.query("hi"):
            messages.append(msg)

    mock_make_opts.assert_call(args=(), kwargs={})
    mock_sdk.assert_call(args=(sentinel_options,), kwargs={})

    assert len(messages) == 1
    assert messages[0].content == "hello from claude"
    assert messages[0].role == "assistant"
    assert messages[0].usage == {"input_tokens": 10}


@pytest.mark.asyncio
async def test_claude_agent_client_run():
    client = ClaudeAgentClient()

    # Create an async generator that yields the expected message
    async def fake_query(prompt):
        yield AgentMessage(role="assistant", content="final result")

    mock_query = tripwire.mock.object(client, "query")
    mock_query.calls(fake_query)

    async with tripwire:
        result = await client.run("do something")

    mock_query.assert_call(args=("do something",), kwargs={})
    assert result == "final result"


@pytest.mark.asyncio
@pytest.mark.allow("subprocess")
async def test_gemini_agent_client_run():
    # Use a minimal fixed env so assertion is deterministic
    fixed_env = {"PATH": "/usr/bin", "HOME": "/tmp"}
    options = AgentOptions(
        model="gemini-2.5-flash",
        system_prompt="be concise",
        permission_mode="dontAsk",
        env=fixed_env,
    )
    client = GeminiAgentClient(options)

    # Track the args passed to create_subprocess_exec for content assertions
    captured_args = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args["args"] = args
        captured_args["kwargs"] = kwargs

        class FakeProcess:
            returncode = 0
            async def communicate(self):
                return (b"hello from gemini", b"")

        return FakeProcess()

    mock_exec = tripwire.mock.object(asyncio, "create_subprocess_exec")
    mock_exec.calls(fake_create_subprocess_exec)

    async with tripwire:
        result = await client.run("hi")

    # The expected command line built by GeminiAgentClient.query()
    expected_cmd = (
        "gemini", "--prompt", "be concise\n\nhi", "-o", "text",
        "--yolo", "--model", "gemini-2.5-flash",
    )
    mock_exec.assert_call(
        args=expected_cmd,
        kwargs={
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": str(options.cwd),
            "env": fixed_env,  # GEMINI_CLI not in env, so no deletion
        },
    )

    assert result == "hello from gemini"

    # Additional content assertions on the command
    cmd = list(captured_args["args"])
    assert "gemini" in cmd
    assert "--prompt" in cmd
    assert "be concise\n\nhi" in cmd
    assert "--model" in cmd
    assert "gemini-2.5-flash" in cmd
    assert "--yolo" in cmd


def test_get_agent_client_factory(monkeypatch):
    # Clear all platform env vars to ensure isolation
    monkeypatch.delenv("OPENCODE", raising=False)
    monkeypatch.delenv("GEMINI_CLI", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)

    # Test auto-detection: with GEMINI_CLI set (and no OPENCODE)
    monkeypatch.setenv("GEMINI_CLI", "1")
    client = get_agent_client()
    assert isinstance(client, GeminiAgentClient)

    # Test auto-detection: without GEMINI_CLI (falls through to claude)
    monkeypatch.delenv("GEMINI_CLI", raising=False)
    client = get_agent_client()
    assert isinstance(client, ClaudeAgentClient)

    # Test auto-detection: with OPENCODE set
    monkeypatch.setenv("OPENCODE", "1")
    client = get_agent_client()
    assert isinstance(client, OpencodeAgentClient)

    # Test explicit provider overrides auto-detection
    monkeypatch.delenv("OPENCODE", raising=False)
    client = get_agent_client(provider="gemini")
    assert isinstance(client, GeminiAgentClient)

    client = get_agent_client(provider="claude")
    assert isinstance(client, ClaudeAgentClient)

    client = get_agent_client(provider="opencode")
    assert isinstance(client, OpencodeAgentClient)


def test_gemini_spawn_session():
    client = GeminiAgentClient()

    mock_spawn = tripwire.mock("spellbook.daemon.terminal:spawn_terminal_window")
    mock_spawn.returns({"status": "spawned"})

    # spawn_session also calls detect_terminal when terminal=None
    mock_detect = tripwire.mock("spellbook.daemon.terminal:detect_terminal")
    mock_detect.returns("iterm2")

    with tripwire:
        result = client.spawn_session("start shell")

    mock_detect.assert_call()
    mock_spawn.assert_call(
        args=(),
        kwargs={
            "terminal": "iterm2",
            "prompt": "start shell",
            "working_directory": str(client.options.cwd),
            "cli_command": "gemini",
        },
    )

    assert result["status"] == "spawned"
