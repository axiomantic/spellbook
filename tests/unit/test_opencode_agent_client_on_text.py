"""Tests for OpencodeAgentClient.query() on_text callback handling.

Verifies that:
1. self.options.on_text is used for streaming text callbacks
2. query() works correctly when on_text is None (no callback)
3. The OPENCODE env var is stripped from subprocess calls
4. Custom model selection works
5. Non-zero exit raises RuntimeError
"""

import pytest
import asyncio
import tripwire

from spellbook.sdk.unified import AgentOptions, OpencodeAgentClient


# Deterministic env for all tests - avoids environment-dependent test failures
_FIXED_ENV = {
    "HOME": "/tmp/test-home",
    "PATH": "/usr/bin:/bin",
    "USER": "testuser",
}


@pytest.mark.asyncio
async def test_opencode_client_query_uses_options_on_text():
    """Test that OpencodeAgentClient.query() uses self.options.on_text for streaming callbacks."""
    callback_calls = []

    def on_text_callback(text: str):
        callback_calls.append(text)

    options = AgentOptions(on_text=on_text_callback, env=_FIXED_ENV.copy())
    client = OpencodeAgentClient(options)

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeProcess:
            returncode = 0
            async def communicate(self):
                return (
                    b'{"message": {"delta": {"content": {"text": "hello "}}}}\n'
                    b'{"message": {"delta": {"content": {"text": "world"}}}}',
                    b"",
                )
        return FakeProcess()

    mock_exec = tripwire.mock.object(asyncio, "create_subprocess_exec")
    mock_exec.calls(fake_create_subprocess_exec)

    async with tripwire:
        messages = []
        async for msg in client.query("test prompt"):
            messages.append(msg)

    # Verify the subprocess call
    mock_exec.assert_call(
        args=('opencode', 'run', '--format', 'json', '-m', 'zai-coding-plan/glm-4.7', 'test prompt'),
        kwargs={
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE,
            'cwd': str(options.cwd),
            'env': _FIXED_ENV.copy(),
        },
    )

    # Verify on_text callback was invoked with extracted text
    assert callback_calls == ["hello ", "world"]

    # Verify message content
    assert len(messages) == 1
    assert messages[0].content == "hello world"
    assert messages[0].role == "assistant"


@pytest.mark.asyncio
async def test_opencode_client_query_no_on_text():
    """Test that OpencodeAgentClient.query() works when no on_text callback is provided."""
    options = AgentOptions(env=_FIXED_ENV.copy())
    client = OpencodeAgentClient(options)

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeProcess:
            returncode = 0
            async def communicate(self):
                return (b'{"message": {"delta": {"content": {"text": "response text"}}}}', b"")
        return FakeProcess()

    mock_exec = tripwire.mock.object(asyncio, "create_subprocess_exec")
    mock_exec.calls(fake_create_subprocess_exec)

    async with tripwire:
        messages = []
        async for msg in client.query("test prompt"):
            messages.append(msg)

    mock_exec.assert_call(
        args=('opencode', 'run', '--format', 'json', '-m', 'zai-coding-plan/glm-4.7', 'test prompt'),
        kwargs={
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE,
            'cwd': str(options.cwd),
            'env': _FIXED_ENV.copy(),
        },
    )

    assert len(messages) == 1
    assert messages[0].content == "response text"
    assert messages[0].role == "assistant"


@pytest.mark.asyncio
async def test_opencode_client_query_strips_opencode_env():
    """Test that the OPENCODE env var is stripped from subprocess calls."""
    # Start with OPENCODE in the env
    env_with_opencode = _FIXED_ENV.copy()
    env_with_opencode["OPENCODE"] = "1"

    # Expected env after stripping OPENCODE
    expected_env = _FIXED_ENV.copy()  # OPENCODE removed

    options = AgentOptions(env=env_with_opencode)
    client = OpencodeAgentClient(options)

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeProcess:
            returncode = 0
            async def communicate(self):
                return (b'{"message": {"delta": {"content": {"text": "ok"}}}}', b"")
        return FakeProcess()

    mock_exec = tripwire.mock.object(asyncio, "create_subprocess_exec")
    mock_exec.calls(fake_create_subprocess_exec)

    async with tripwire:
        async for msg in client.query("test"):
            pass

    # Assert subprocess was called with env that does NOT contain OPENCODE
    mock_exec.assert_call(
        args=('opencode', 'run', '--format', 'json', '-m', 'zai-coding-plan/glm-4.7', 'test'),
        kwargs={
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE,
            'cwd': str(options.cwd),
            'env': expected_env,
        },
    )


@pytest.mark.asyncio
async def test_opencode_client_query_custom_model():
    """Test that OpencodeAgentClient.query() uses the model from options."""
    options = AgentOptions(model="zai-coding-plan/glm-5", env=_FIXED_ENV.copy())
    client = OpencodeAgentClient(options)

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeProcess:
            returncode = 0
            async def communicate(self):
                return (b'{"message": {"delta": {"content": {"text": "result"}}}}', b"")
        return FakeProcess()

    mock_exec = tripwire.mock.object(asyncio, "create_subprocess_exec")
    mock_exec.calls(fake_create_subprocess_exec)

    async with tripwire:
        async for msg in client.query("test"):
            pass

    # Verify the custom model was used in the command
    mock_exec.assert_call(
        args=('opencode', 'run', '--format', 'json', '-m', 'zai-coding-plan/glm-5', 'test'),
        kwargs={
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE,
            'cwd': str(options.cwd),
            'env': _FIXED_ENV.copy(),
        },
    )


@pytest.mark.asyncio
async def test_opencode_client_query_nonzero_exit():
    """Test that OpencodeAgentClient.query() raises RuntimeError on non-zero exit code."""
    options = AgentOptions(env=_FIXED_ENV.copy())
    client = OpencodeAgentClient(options)

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeProcess:
            returncode = 1
            async def communicate(self):
                return (b"", b"Error: something failed")
        return FakeProcess()

    mock_exec = tripwire.mock.object(asyncio, "create_subprocess_exec")
    mock_exec.calls(fake_create_subprocess_exec)

    async with tripwire:
        with pytest.raises(RuntimeError, match="OpenCode CLI failed"):
            async for msg in client.query("test"):
                pass

    # Must assert the mock call even though the test expects an error
    mock_exec.assert_call(
        args=('opencode', 'run', '--format', 'json', '-m', 'zai-coding-plan/glm-4.7', 'test'),
        kwargs={
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE,
            'cwd': str(options.cwd),
            'env': _FIXED_ENV.copy(),
        },
    )
