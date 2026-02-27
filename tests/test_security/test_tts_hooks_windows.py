"""Tests for TTS hook Python wrappers (Windows compatibility).

Tests the .py hook scripts' Windows code paths with mocked platform.
On real Windows, these scripts would execute natively.
On Unix, they delegate to .sh scripts via os.execv.
"""

import ast
import json
import os
import py_compile
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = PROJECT_ROOT / "hooks"

TTS_PY_HOOKS = {
    "tts-timer-start": HOOKS_DIR / "tts-timer-start.py",
    "tts-notify": HOOKS_DIR / "tts-notify.py",
}


# #############################################################################
# SECTION 1: Syntax and structure validation (runs on ALL platforms)
# #############################################################################


class TestTtsPythonHookSyntax:
    """Verify that every TTS .py hook file is syntactically valid Python."""

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_file_exists(self, hook_name):
        path = TTS_PY_HOOKS[hook_name]
        assert path.is_file(), f"{hook_name}.py not found at {path}"

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_compiles(self, hook_name):
        path = TTS_PY_HOOKS[hook_name]
        py_compile.compile(str(path), doraise=True)

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_parses_ast(self, hook_name):
        path = TTS_PY_HOOKS[hook_name]
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        assert isinstance(tree, ast.Module)

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_has_python_shebang(self, hook_name):
        path = TTS_PY_HOOKS[hook_name]
        first_line = path.read_text().splitlines()[0]
        assert first_line.strip() == "#!/usr/bin/env python3", (
            f"{hook_name}.py missing Python shebang"
        )

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_has_main_guard(self, hook_name):
        path = TTS_PY_HOOKS[hook_name]
        source = path.read_text()
        assert "__name__" in source and "__main__" in source, (
            f"{hook_name}.py missing if __name__ == '__main__' guard"
        )

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_has_main_function(self, hook_name):
        path = TTS_PY_HOOKS[hook_name]
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        function_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        assert "main" in function_names, (
            f"{hook_name}.py does not define a main() function"
        )

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_contains_platform_check(self, hook_name):
        path = TTS_PY_HOOKS[hook_name]
        source = path.read_text()
        assert "sys.platform" in source, (
            f"{hook_name}.py does not reference sys.platform"
        )

    @pytest.mark.parametrize("hook_name", list(TTS_PY_HOOKS.keys()))
    def test_hook_is_fail_open(self, hook_name):
        """TTS hooks must be fail-open (no block() function)."""
        path = TTS_PY_HOOKS[hook_name]
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        function_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        assert "block" not in function_names, (
            f"{hook_name}.py defines block() but TTS hooks must be fail-open"
        )


# #############################################################################
# SECTION 2: Windows code path tests using import + mocked platform
# #############################################################################


def _load_hook_module(hook_name: str):
    """Import a hook module fresh, bypassing any cached version."""
    import importlib.util

    path = TTS_PY_HOOKS[hook_name]
    # Use a unique module name each time to avoid caching issues
    mod_name = f"tts_hook_{hook_name.replace('-', '_')}_{id(path)}"
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTimerStartPyWindows:
    """tts-timer-start.py Windows code path."""

    def test_writes_timestamp_on_windows(self, tmp_path):
        tool_use_id = f"test-win-{int(time.time())}"
        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {},
        }
        start_file = tmp_path / f"claude-tool-start-{tool_use_id}"

        mod = _load_hook_module("tts-timer-start")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=json.dumps(payload)))), \
             patch("tempfile.gettempdir", return_value=str(tmp_path)):
            # tts-timer-start.py uses a top-level `import tempfile`, so the module
            # holds a direct reference. We must replace mod.tempfile directly rather
            # than patching "tempfile.gettempdir" (which only affects the global module).
            mod.tempfile = types.ModuleType("fake_tempfile")
            mod.tempfile.gettempdir = lambda: str(tmp_path)
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

        assert start_file.exists()
        ts = int(start_file.read_text().strip())
        assert abs(ts - int(time.time())) < 5

    def test_exits_0_on_empty_stdin_windows(self):
        mod = _load_hook_module("tts-timer-start")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=""))):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

    def test_exits_0_on_missing_tool_use_id_windows(self):
        payload = {"tool_name": "Bash", "tool_input": {}}
        mod = _load_hook_module("tts-timer-start")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=json.dumps(payload)))):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

    def test_exits_0_on_invalid_json_windows(self):
        mod = _load_hook_module("tts-timer-start")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value="not json"))):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0


class TestTtsNotifyPyWindows:
    """tts-notify.py Windows code path."""

    def test_skips_blacklisted_tool_on_windows(self):
        payload = {
            "tool_name": "AskUserQuestion",
            "tool_use_id": "test-blacklist",
            "tool_input": {},
        }
        mod = _load_hook_module("tts-notify")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=json.dumps(payload)))):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

    def test_exits_0_on_empty_stdin_windows(self):
        mod = _load_hook_module("tts-notify")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=""))):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

    def test_exits_0_on_missing_tool_use_id_windows(self):
        payload = {"tool_name": "Bash", "tool_input": {}}
        mod = _load_hook_module("tts-notify")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=json.dumps(payload)))):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

    def test_skips_when_no_start_file_windows(self):
        payload = {
            "tool_name": "Bash",
            "tool_use_id": "nonexistent-win-id",
            "tool_input": {},
        }
        mod = _load_hook_module("tts-notify")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=json.dumps(payload)))):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

    def test_skips_when_under_threshold_windows(self, tmp_path):
        tool_use_id = f"test-win-under-{int(time.time())}"
        start_file = tmp_path / f"claude-tool-start-{tool_use_id}"
        start_file.write_text(str(int(time.time())))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
            "cwd": "/tmp/myproject",
        }
        mod = _load_hook_module("tts-notify")

        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=json.dumps(payload)))), \
             patch.dict(os.environ, {"SPELLBOOK_TTS_THRESHOLD": "9999"}), \
             patch("tempfile.gettempdir", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

        # Start file should be cleaned up
        assert not start_file.exists()

    def test_sends_speak_request_when_above_threshold_windows(self, tmp_path):
        tool_use_id = f"test-win-above-{int(time.time())}"
        start_file = tmp_path / f"claude-tool-start-{tool_use_id}"
        # Write a start file with timestamp 60 seconds ago
        start_file.write_text(str(int(time.time()) - 60))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
            "cwd": "/tmp/myproject",
        }
        mod = _load_hook_module("tts-notify")

        mock_urlopen = MagicMock()
        # tts-notify.py uses a function-level `import tempfile` (inside main()),
        # so patching "tempfile.gettempdir" via string path works here, unlike
        # tts-timer-start.py which uses a top-level import.
        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "stdin", MagicMock(read=MagicMock(return_value=json.dumps(payload)))), \
             patch.dict(os.environ, {"SPELLBOOK_TTS_THRESHOLD": "5"}), \
             patch("tempfile.gettempdir", return_value=str(tmp_path)), \
             patch.object(mod.urllib.request, "urlopen", mock_urlopen):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0

        # Start file should have been consumed
        assert not start_file.exists()

        # Verify the correct JSON payload was sent to /api/speak
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        sent_payload = json.loads(req.data.decode())
        assert "text" in sent_payload
        assert "myproject" in sent_payload["text"]
        assert "Bash" in sent_payload["text"]
        assert "finished" in sent_payload["text"]
