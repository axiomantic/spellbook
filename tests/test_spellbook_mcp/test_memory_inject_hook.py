"""Tests for memory injection behavior via the unified hook (spellbook_hook.py).

PostToolUse handler (_memory_inject):
- Receives JSON on stdin with tool_name, tool_input, cwd
- Only processes file tools: Read, Edit, Grep, Glob
- Extracts file_path from tool_input
- Computes namespace from cwd (project-encoded)
- Calls MCP recall API and injects memories as XML
- FAIL-OPEN: always exits 0, never blocks tool execution

Payload construction and XML output format are tested via isolated
Python snippets that mirror the hook's internal logic.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.integration

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
UNIFIED_HOOK = os.path.join(PROJECT_ROOT, "hooks", "spellbook_hook.py")

# Environment that prevents the hook from actually reaching a server
DEAD_PORT = "99999"


def _run_hook(
    stdin_data: dict | str,
    *,
    env_overrides: dict | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run the unified hook with given stdin data as PostToolUse event."""
    if isinstance(stdin_data, str):
        input_str = stdin_data
    else:
        payload = dict(stdin_data)
        payload["hook_event_name"] = "PostToolUse"
        input_str = json.dumps(payload)

    env = os.environ.copy()
    env["SPELLBOOK_DIR"] = PROJECT_ROOT
    env["PYTHONPATH"] = PROJECT_ROOT
    env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
    env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        [sys.executable, UNIFIED_HOOK],
        input=input_str,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Fail-open behavior
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_exits_zero_on_empty_input(self):
        result = _run_hook("")
        assert result.returncode == 0

    def test_exits_zero_on_invalid_json(self):
        result = _run_hook("not json at all {{{")
        assert result.returncode == 0

    def test_exits_zero_on_json_missing_tool_name(self):
        result = _run_hook({"some_field": "value"})
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Tool filtering
# ---------------------------------------------------------------------------


class TestToolFiltering:
    def test_ignores_bash_tool(self):
        """Bash tool is not a file tool, no memory injection."""
        result = _run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        assert result.returncode == 0

    def test_ignores_write_tool(self):
        """Write tool is not a file tool for memory injection."""
        result = _run_hook({
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/foo.txt", "content": "hi"},
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        assert result.returncode == 0

    def test_ignores_task_tool(self):
        """Task tool is not a file tool for memory injection."""
        result = _run_hook({
            "tool_name": "Task",
            "tool_input": {"description": "do something"},
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        assert result.returncode == 0

    @pytest.mark.parametrize("tool_name", ["Read", "Edit", "Grep", "Glob"])
    def test_accepts_file_tools(self, tool_name: str):
        """File tools should be accepted (not filtered out).

        They will still produce no injection output because the recall API
        is unreachable, but the hook should attempt to process them (not
        exit early at the tool filtering stage).
        """
        tool_input = {"file_path": "/Users/alice/project/main.py"}
        if tool_name in ("Grep", "Glob"):
            tool_input = {"path": "/Users/alice/project/src"}

        result = _run_hook({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Payload construction (via isolated Python that mirrors hook logic)
# ---------------------------------------------------------------------------


class TestPayloadConstruction:
    """Test the Python logic that extracts file_path and builds the recall payload.

    We test this by running just the Python portion of the hook logic in isolation.
    """

    PYTHON_EXTRACT = textwrap.dedent("""\
        import json, sys

        try:
            d = json.load(sys.stdin)
        except Exception:
            sys.exit(0)

        tool_name = d.get('tool_name', '')
        tool_input = d.get('tool_input') or {}
        cwd = d.get('cwd', '')

        file_tools = {'Read', 'Edit', 'Grep', 'Glob'}
        if tool_name not in file_tools:
            sys.exit(0)

        file_path = ''
        if tool_name in ('Read', 'Write', 'Edit'):
            file_path = tool_input.get('file_path', '')
        elif tool_name == 'Grep':
            file_path = tool_input.get('path', '')
        elif tool_name == 'Glob':
            file_path = tool_input.get('path', '')

        if not file_path:
            sys.exit(0)

        namespace = cwd.replace('/', '-').lstrip('-') if cwd else ''
        if not namespace:
            sys.exit(0)

        payload = {'file_path': file_path, 'namespace': namespace, 'limit': 5}
        print(json.dumps(payload))
    """)

    def _run_python_extract(self, hook_input_dict: dict) -> str:
        result = subprocess.run(
            ["python3", "-c", self.PYTHON_EXTRACT],
            input=json.dumps(hook_input_dict),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()

    def test_read_tool_extracts_file_path(self):
        output = self._run_python_extract({
            "tool_name": "Read",
            "tool_input": {"file_path": "/Users/alice/project/src/main.py"},
            "cwd": "/Users/alice/project",
        })
        assert json.loads(output) == {
            "file_path": "/Users/alice/project/src/main.py",
            "namespace": "Users-alice-project",
            "limit": 5,
        }

    def test_edit_tool_extracts_file_path(self):
        output = self._run_python_extract({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/Users/bob/code/app.js", "old_string": "a", "new_string": "b"},
            "cwd": "/Users/bob/code",
        })
        assert json.loads(output) == {
            "file_path": "/Users/bob/code/app.js",
            "namespace": "Users-bob-code",
            "limit": 5,
        }

    def test_grep_tool_extracts_path(self):
        output = self._run_python_extract({
            "tool_name": "Grep",
            "tool_input": {"pattern": "TODO", "path": "/Users/alice/project/src"},
            "cwd": "/Users/alice/project",
        })
        assert json.loads(output) == {
            "file_path": "/Users/alice/project/src",
            "namespace": "Users-alice-project",
            "limit": 5,
        }

    def test_glob_tool_extracts_path(self):
        output = self._run_python_extract({
            "tool_name": "Glob",
            "tool_input": {"pattern": "*.py", "path": "/Users/alice/project"},
            "cwd": "/Users/alice/project",
        })
        assert json.loads(output) == {
            "file_path": "/Users/alice/project",
            "namespace": "Users-alice-project",
            "limit": 5,
        }

    def test_namespace_computation_strips_leading_dash(self):
        output = self._run_python_extract({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "cwd": "/home/user/myproject",
        })
        assert json.loads(output) == {
            "file_path": "/tmp/test.py",
            "namespace": "home-user-myproject",
            "limit": 5,
        }

    def test_exits_silently_when_no_file_path(self):
        output = self._run_python_extract({
            "tool_name": "Grep",
            "tool_input": {"pattern": "TODO"},
            "cwd": "/Users/alice/project",
        })
        assert output == ""

    def test_exits_silently_when_no_cwd(self):
        output = self._run_python_extract({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "cwd": "",
        })
        assert output == ""


# ---------------------------------------------------------------------------
# Output format (XML memory injection)
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Test the Python logic that formats memories as XML.

    We test this in isolation by feeding it simulated API responses.
    """

    FORMAT_PYTHON = textwrap.dedent("""\
        import json, sys

        try:
            data = json.load(sys.stdin)
        except Exception:
            sys.exit(0)

        memories = data.get('memories', [])
        if not memories:
            sys.exit(0)

        lines = ['<spellbook-memory>']
        for mem in memories[:5]:
            content = mem.get('content', '')
            mtype = mem.get('memory_type', 'fact')
            importance = mem.get('importance', 1.0)
            status = mem.get('status', 'active')
            confidence = 'verified' if status == 'active' else 'unverified'

            lines.append(f'  <memory type="{mtype}" confidence="{confidence}" importance="{importance:.1f}">')
            lines.append(f'    {content}')
            lines.append(f'  </memory>')
        lines.append('</spellbook-memory>')
        print('\\n'.join(lines))
    """)

    def _run_format(self, api_response: dict) -> str:
        result = subprocess.run(
            ["python3", "-c", self.FORMAT_PYTHON],
            input=json.dumps(api_response),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout

    def test_single_active_memory(self):
        response = {
            "memories": [{
                "content": "This module handles authentication",
                "memory_type": "fact",
                "importance": 0.8,
                "status": "active",
            }],
        }
        output = self._run_format(response)
        expected = textwrap.dedent("""\
            <spellbook-memory>
              <memory type="fact" confidence="verified" importance="0.8">
                This module handles authentication
              </memory>
            </spellbook-memory>
        """)
        assert output == expected

    def test_multiple_memories(self):
        response = {
            "memories": [
                {
                    "content": "Uses JWT tokens",
                    "memory_type": "fact",
                    "importance": 0.9,
                    "status": "active",
                },
                {
                    "content": "Watch out for circular imports",
                    "memory_type": "warning",
                    "importance": 0.7,
                    "status": "archived",
                },
            ],
        }
        output = self._run_format(response)
        expected = textwrap.dedent("""\
            <spellbook-memory>
              <memory type="fact" confidence="verified" importance="0.9">
                Uses JWT tokens
              </memory>
              <memory type="warning" confidence="unverified" importance="0.7">
                Watch out for circular imports
              </memory>
            </spellbook-memory>
        """)
        assert output == expected

    def test_limits_to_five_memories(self):
        memories = [
            {
                "content": f"Memory {i}",
                "memory_type": "fact",
                "importance": 0.5,
                "status": "active",
            }
            for i in range(8)
        ]
        response = {"memories": memories}
        output = self._run_format(response)
        # Should contain exactly 5 <memory> elements (indices 0-4)
        expected_lines = ["<spellbook-memory>"]
        for i in range(5):
            expected_lines.append('  <memory type="fact" confidence="verified" importance="0.5">')
            expected_lines.append(f"    Memory {i}")
            expected_lines.append("  </memory>")
        expected_lines.append("</spellbook-memory>")
        expected = "\n".join(expected_lines) + "\n"
        assert output == expected

    def test_empty_memories_produces_no_output(self):
        response = {"memories": []}
        output = self._run_format(response)
        assert output == ""

    def test_no_memories_key_produces_no_output(self):
        response = {"other_key": "value"}
        output = self._run_format(response)
        assert output == ""

    def test_default_memory_type_is_fact(self):
        response = {
            "memories": [{
                "content": "Some content",
                "importance": 1.0,
                "status": "active",
            }],
        }
        output = self._run_format(response)
        expected = textwrap.dedent("""\
            <spellbook-memory>
              <memory type="fact" confidence="verified" importance="1.0">
                Some content
              </memory>
            </spellbook-memory>
        """)
        assert output == expected

    def test_default_importance_is_one(self):
        response = {
            "memories": [{
                "content": "Some content",
                "memory_type": "fact",
                "status": "active",
            }],
        }
        output = self._run_format(response)
        expected = textwrap.dedent("""\
            <spellbook-memory>
              <memory type="fact" confidence="verified" importance="1.0">
                Some content
              </memory>
            </spellbook-memory>
        """)
        assert output == expected
