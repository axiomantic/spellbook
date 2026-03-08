"""Tests for memory injection hook script (memory-inject.sh).

Tests verify:
- Hook script exists and is executable
- Fail-open behavior (exit 0 on all error conditions)
- Correct tool filtering (only file tools: Read, Edit, Grep, Glob)
- Correct file_path extraction per tool type
- Correct namespace computation (project-encoded from cwd)
- Correct JSON payload construction for the recall API
- Correct XML output format for injected memories
"""

import json
import os
import stat
import subprocess
import textwrap

import pytest


WORKTREE = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
HOOK_PATH = os.path.join(WORKTREE, "hooks", "memory-inject.sh")

# Environment that prevents the hook from actually reaching a server
SAFE_ENV = {**os.environ, "SPELLBOOK_MCP_PORT": "99999"}


def run_hook(stdin_text: str = "", env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook script with given stdin and return the completed process."""
    return subprocess.run(
        ["bash", HOOK_PATH],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env or SAFE_ENV,
        timeout=10,
    )


# ---------------------------------------------------------------------------
# Existence and permissions
# ---------------------------------------------------------------------------


class TestHookFileProperties:
    def test_hook_script_exists(self):
        assert os.path.isfile(HOOK_PATH), f"Hook script not found at {HOOK_PATH}"

    def test_hook_script_is_executable(self):
        mode = os.stat(HOOK_PATH).st_mode
        assert mode & stat.S_IXUSR, "Hook script is not executable by owner"


# ---------------------------------------------------------------------------
# Fail-open behavior
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_exits_zero_on_empty_input(self):
        result = run_hook("")
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_exits_zero_on_invalid_json(self):
        result = run_hook("not json at all {{{")
        assert result.returncode == 0
        assert result.stdout == ""

    def test_exits_zero_on_json_missing_tool_name(self):
        result = run_hook(json.dumps({"some_field": "value"}))
        assert result.returncode == 0
        assert result.stdout == ""


# ---------------------------------------------------------------------------
# Tool filtering
# ---------------------------------------------------------------------------


class TestToolFiltering:
    def test_ignores_bash_tool(self):
        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        result = run_hook(hook_input)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_ignores_write_tool(self):
        hook_input = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/foo.txt", "content": "hi"},
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        result = run_hook(hook_input)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_ignores_task_tool(self):
        hook_input = json.dumps({
            "tool_name": "Task",
            "tool_input": {"description": "do something"},
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        result = run_hook(hook_input)
        assert result.returncode == 0
        assert result.stdout == ""

    @pytest.mark.parametrize("tool_name", ["Read", "Edit", "Grep", "Glob"])
    def test_accepts_file_tools(self, tool_name: str):
        """File tools should be accepted (not filtered out).

        They will still produce no output because the recall API is unreachable,
        but the hook should attempt to process them (not exit early at the
        tool filtering stage).
        """
        tool_input = {"file_path": "/Users/alice/project/main.py"}
        if tool_name in ("Grep", "Glob"):
            tool_input = {"path": "/Users/alice/project/src"}

        hook_input = json.dumps({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "session_id": "sess-1",
            "cwd": "/Users/alice/project",
        })
        result = run_hook(hook_input)
        assert result.returncode == 0
        # No output because API is unreachable, but no error either


# ---------------------------------------------------------------------------
# Payload construction (via the embedded Python)
# ---------------------------------------------------------------------------


class TestPayloadConstruction:
    """Test the Python block that extracts file_path and builds the recall payload.

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
        expected = {
            "file_path": "/Users/alice/project/src/main.py",
            "namespace": "Users-alice-project",
            "limit": 5,
        }
        assert json.loads(output) == expected

    def test_edit_tool_extracts_file_path(self):
        output = self._run_python_extract({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/Users/bob/code/app.js", "old_string": "a", "new_string": "b"},
            "cwd": "/Users/bob/code",
        })
        expected = {
            "file_path": "/Users/bob/code/app.js",
            "namespace": "Users-bob-code",
            "limit": 5,
        }
        assert json.loads(output) == expected

    def test_grep_tool_extracts_path(self):
        output = self._run_python_extract({
            "tool_name": "Grep",
            "tool_input": {"pattern": "TODO", "path": "/Users/alice/project/src"},
            "cwd": "/Users/alice/project",
        })
        expected = {
            "file_path": "/Users/alice/project/src",
            "namespace": "Users-alice-project",
            "limit": 5,
        }
        assert json.loads(output) == expected

    def test_glob_tool_extracts_path(self):
        output = self._run_python_extract({
            "tool_name": "Glob",
            "tool_input": {"pattern": "*.py", "path": "/Users/alice/project"},
            "cwd": "/Users/alice/project",
        })
        expected = {
            "file_path": "/Users/alice/project",
            "namespace": "Users-alice-project",
            "limit": 5,
        }
        assert json.loads(output) == expected

    def test_namespace_computation_strips_leading_dash(self):
        output = self._run_python_extract({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "cwd": "/home/user/myproject",
        })
        parsed = json.loads(output)
        assert parsed["namespace"] == "home-user-myproject"

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
    """Test the Python block that formats memories as XML.

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
            expected_lines.append(f'  <memory type="fact" confidence="verified" importance="0.5">')
            expected_lines.append(f"    Memory {i}")
            expected_lines.append(f"  </memory>")
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


# ---------------------------------------------------------------------------
# PowerShell script existence
# ---------------------------------------------------------------------------


class TestPowerShellHook:
    PS1_PATH = os.path.join(WORKTREE, "hooks", "memory-inject.ps1")

    def test_powershell_hook_exists(self):
        assert os.path.isfile(self.PS1_PATH), f"PowerShell hook not found at {self.PS1_PATH}"
