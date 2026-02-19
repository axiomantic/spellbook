"""Tests for MCP tool scanning mode.

Validates:
- MCP_RULES list exists with 9 rules (MCP-001 through MCP-009)
- Each MCP rule pattern compiles and matches crafted Python snippets
- Clean Python code passes MCP scanning without findings
- scan_python_file() scans a single Python file against MCP_RULES
- scan_mcp_directory() recursively scans Python files in a directory
- CLI --mode mcp flag triggers MCP directory scanning
- Category.MCP_TOOL enum member exists for MCP findings
"""

import re
import subprocess
import sys
import textwrap

import pytest


# ---------------------------------------------------------------------------
# MCP_RULES existence and structure tests
# ---------------------------------------------------------------------------


class TestMCPRulesExist:
    """MCP_RULES list exists with correct structure."""

    def test_mcp_rules_exist(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES is not None

    def test_mcp_rules_count(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert len(MCP_RULES) == 9

    def test_all_patterns_compile(self):
        from spellbook_mcp.security.rules import MCP_RULES

        for pattern, severity, rule_id, message in MCP_RULES:
            compiled = re.compile(pattern)
            assert compiled is not None, f"Pattern for {rule_id} failed to compile"

    def test_rule_ids_sequential(self):
        from spellbook_mcp.security.rules import MCP_RULES

        expected_ids = [f"MCP-{i:03d}" for i in range(1, 10)]
        actual_ids = [rule_id for _, _, rule_id, _ in MCP_RULES]
        assert actual_ids == expected_ids

    def test_all_severities_are_enum_members(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        for _, severity, rule_id, _ in MCP_RULES:
            assert isinstance(severity, Severity), (
                f"Rule {rule_id} has invalid severity: {severity}"
            )

    def test_no_duplicate_ids_with_other_rules(self):
        from spellbook_mcp.security.rules import (
            ESCALATION_RULES,
            EXFILTRATION_RULES,
            INJECTION_RULES,
            MCP_RULES,
            OBFUSCATION_RULES,
        )

        all_rules = (
            INJECTION_RULES
            + EXFILTRATION_RULES
            + ESCALATION_RULES
            + OBFUSCATION_RULES
            + MCP_RULES
        )
        ids = [rule_id for _, _, rule_id, _ in all_rules]
        assert len(ids) == len(set(ids)), (
            f"Duplicate rule IDs found: {[x for x in ids if ids.count(x) > 1]}"
        )


class TestMCPToolCategory:
    """Category.MCP_TOOL enum exists."""

    def test_category_has_mcp_tool(self):
        from spellbook_mcp.security.rules import Category

        assert Category.MCP_TOOL is not None

    def test_mcp_tool_value(self):
        from spellbook_mcp.security.rules import Category

        assert Category.MCP_TOOL.value == "mcp_tool"


# ---------------------------------------------------------------------------
# Individual MCP rule pattern tests
# ---------------------------------------------------------------------------


class TestMCPRule001ShellExecution:
    """MCP-001: Shell execution in MCP tool."""

    def test_matches_subprocess_run_shell_true(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[0][0]
        assert re.search(pattern, 'subprocess.run(cmd, shell=True)')

    def test_matches_subprocess_call_shell_true(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[0][0]
        assert re.search(pattern, 'subprocess.call(cmd, shell=True)')

    def test_matches_subprocess_popen_shell_true(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[0][0]
        assert re.search(pattern, 'subprocess.Popen(cmd, shell = True)')

    def test_severity_is_critical(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[0][1] == Severity.CRITICAL

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[0][2] == "MCP-001"


class TestMCPRule002DynamicCodeExecution:
    """MCP-002: Dynamic code execution (eval/exec)."""

    def test_matches_eval(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[1][0]
        assert re.search(pattern, 'eval(user_input)')

    def test_matches_exec(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[1][0]
        assert re.search(pattern, 'exec(code_string)')

    def test_no_false_positive_on_evaluate(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[1][0]
        assert not re.search(pattern, 'evaluate(x)')

    def test_no_false_positive_on_execute_method(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[1][0]
        assert not re.search(pattern, 'cursor.execute(query)')

    def test_severity_is_high(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[1][1] == Severity.HIGH

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[1][2] == "MCP-002"


class TestMCPRule003UnsanitizedPath:
    """MCP-003: Unsanitized path construction."""

    def test_matches_os_path_join_with_concatenation(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[2][0]
        assert re.search(pattern, 'os.path.join(base + user_input)')

    def test_matches_os_path_join_with_plus(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[2][0]
        assert re.search(pattern, 'os.path.join(dir, prefix + name)')

    def test_severity_is_high(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[2][1] == Severity.HIGH

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[2][2] == "MCP-003"


class TestMCPRule004MissingValidation:
    """MCP-004: Missing input validation marker."""

    def test_matches_todo_valid(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[3][0]
        assert re.search(pattern, '# TODO validate input')

    def test_matches_fixme_check(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[3][0]
        assert re.search(pattern, '# FIXME add check here')

    def test_matches_hack(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[3][0]
        assert re.search(pattern, '# HACK workaround')

    def test_severity_is_medium(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[3][1] == Severity.MEDIUM

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[3][2] == "MCP-004"


class TestMCPRule005UnboundedRead:
    """MCP-005: Unbounded file read."""

    def test_matches_read_no_size(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[4][0]
        assert re.search(pattern, 'f.read()')

    def test_matches_file_read_no_size(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[4][0]
        assert re.search(pattern, 'content = file.read()')

    def test_severity_is_medium(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[4][1] == Severity.MEDIUM

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[4][2] == "MCP-005"


class TestMCPRule006EnvironmentAccess:
    """MCP-006: Direct environment access."""

    def test_matches_os_environ_bracket(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[5][0]
        assert re.search(pattern, 'os.environ["SECRET_KEY"]')

    def test_matches_os_getenv(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[5][0]
        assert re.search(pattern, 'os.getenv("API_KEY")')

    def test_severity_is_medium(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[5][1] == Severity.MEDIUM

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[5][2] == "MCP-006"


class TestMCPRule007SQLFormatting:
    """MCP-007: SQL string formatting."""

    def test_matches_fstring_execute(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[6][0]
        assert re.search(pattern, 'cursor.execute(f"SELECT * FROM {table}")')

    def test_matches_fstring_with_execute(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[6][0]
        assert re.search(pattern, 'f"SELECT {col} FROM users" execute')

    def test_severity_is_high(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[6][1] == Severity.HIGH

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[6][2] == "MCP-007"


class TestMCPRule008URLConstruction:
    """MCP-008: Unvalidated URL construction."""

    def test_matches_fstring_url(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[7][0]
        assert re.search(pattern, 'f"https://api.example.com/{endpoint}"')

    def test_matches_http_string_concat(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[7][0]
        assert re.search(pattern, '"http://" + host + "/api"')

    def test_severity_is_medium(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[7][1] == Severity.MEDIUM

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[7][2] == "MCP-008"


class TestMCPRule009OSSystem:
    """MCP-009: OS system call."""

    def test_matches_os_system(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[8][0]
        assert re.search(pattern, 'os.system("ls -la")')

    def test_matches_os_system_variable(self):
        from spellbook_mcp.security.rules import MCP_RULES

        pattern = MCP_RULES[8][0]
        assert re.search(pattern, 'os.system(cmd)')

    def test_severity_is_critical(self):
        from spellbook_mcp.security.rules import MCP_RULES, Severity

        assert MCP_RULES[8][1] == Severity.CRITICAL

    def test_rule_id(self):
        from spellbook_mcp.security.rules import MCP_RULES

        assert MCP_RULES[8][2] == "MCP-009"


# ---------------------------------------------------------------------------
# scan_python_file tests
# ---------------------------------------------------------------------------


class TestScanPythonFileClean:
    """scan_python_file returns PASS for clean Python files."""

    def test_clean_python_passes(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "clean.py"
        py_file.write_text(
            textwrap.dedent("""\
            import json
            from pathlib import Path

            def read_config(path: str) -> dict:
                with open(path) as f:
                    return json.load(f)

            def main():
                config = read_config("config.json")
                print(config)

            if __name__ == "__main__":
                main()
            """)
        )
        result = scan_python_file(str(py_file))
        assert result.verdict == "PASS"
        assert result.findings == []

    def test_empty_python_passes(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "empty.py"
        py_file.write_text("")
        result = scan_python_file(str(py_file))
        assert result.verdict == "PASS"
        assert result.findings == []

    def test_nonexistent_file(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        result = scan_python_file(str(tmp_path / "nonexistent.py"))
        assert result.verdict == "FAIL"
        assert len(result.findings) > 0


class TestScanPythonFileDetection:
    """scan_python_file detects MCP rule violations."""

    def test_detects_shell_execution(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "shell.py"
        py_file.write_text('import subprocess\nsubprocess.run(cmd, shell=True)\n')
        result = scan_python_file(str(py_file))
        assert result.verdict == "FAIL"
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-001" in rule_ids

    def test_detects_eval(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "evalcode.py"
        py_file.write_text('result = eval(user_input)\n')
        result = scan_python_file(str(py_file))
        assert result.verdict == "FAIL"
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-002" in rule_ids

    def test_detects_os_system(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "ossystem.py"
        py_file.write_text('import os\nos.system("rm -rf /")\n')
        result = scan_python_file(str(py_file))
        assert result.verdict == "FAIL"
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-009" in rule_ids

    def test_detects_sql_injection(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "sql.py"
        py_file.write_text('cursor.execute(f"SELECT * FROM {table}")\n')
        result = scan_python_file(str(py_file))
        assert result.verdict == "FAIL"
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-007" in rule_ids

    def test_detects_environment_access(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "envaccess.py"
        py_file.write_text('secret = os.environ["SECRET_KEY"]\n')
        result = scan_python_file(str(py_file), security_mode="paranoid")
        assert result.verdict == "FAIL"
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-006" in rule_ids

    def test_finding_has_correct_line_number(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "lines.py"
        py_file.write_text(
            'import os\n# comment\n# another\nos.system("bad")\n'
        )
        result = scan_python_file(str(py_file))
        assert len(result.findings) > 0
        mcp009_finding = next(
            f for f in result.findings if f.rule_id == "MCP-009"
        )
        assert mcp009_finding.line == 4

    def test_finding_has_mcp_tool_category(self, tmp_path):
        from spellbook_mcp.security.rules import Category
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "cat.py"
        py_file.write_text('os.system("ls")\n')
        result = scan_python_file(str(py_file))
        assert len(result.findings) > 0
        assert result.findings[0].category == Category.MCP_TOOL

    def test_multiple_findings(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "multi.py"
        py_file.write_text(
            textwrap.dedent("""\
            import os
            import subprocess
            os.system("ls")
            subprocess.run(cmd, shell=True)
            """)
        )
        result = scan_python_file(str(py_file))
        assert result.verdict == "FAIL"
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-009" in rule_ids
        assert "MCP-001" in rule_ids

    def test_respects_security_mode_standard(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "medium.py"
        # MCP-006 is MEDIUM severity - should NOT be caught in standard mode
        py_file.write_text('secret = os.environ["KEY"]\n')
        result = scan_python_file(str(py_file), security_mode="standard")
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-006" not in rule_ids

    def test_respects_security_mode_paranoid(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_python_file

        py_file = tmp_path / "medium_paranoid.py"
        # MCP-006 is MEDIUM severity - should be caught in paranoid mode
        py_file.write_text('secret = os.environ["KEY"]\n')
        result = scan_python_file(str(py_file), security_mode="paranoid")
        rule_ids = [f.rule_id for f in result.findings]
        assert "MCP-006" in rule_ids


# ---------------------------------------------------------------------------
# scan_mcp_directory tests
# ---------------------------------------------------------------------------


class TestScanMCPDirectory:
    """scan_mcp_directory recursively scans Python files."""

    def test_scans_python_files(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_mcp_directory

        py_file = tmp_path / "tool.py"
        py_file.write_text('print("clean")\n')
        results = scan_mcp_directory(str(tmp_path))
        assert len(results) == 1
        assert results[0].verdict == "PASS"

    def test_scans_nested_python_files(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_mcp_directory

        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (tmp_path / "top.py").write_text('print("top")\n')
        (sub / "nested.py").write_text('print("nested")\n')
        results = scan_mcp_directory(str(tmp_path))
        assert len(results) == 2

    def test_detects_issues_in_nested_files(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_mcp_directory

        sub = tmp_path / "tools"
        sub.mkdir()
        (sub / "bad_tool.py").write_text('os.system("rm -rf /")\n')
        results = scan_mcp_directory(str(tmp_path))
        assert len(results) == 1
        assert results[0].verdict == "FAIL"
        rule_ids = [f.rule_id for f in results[0].findings]
        assert "MCP-009" in rule_ids

    def test_ignores_non_python_files(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_mcp_directory

        (tmp_path / "readme.md").write_text("# Readme")
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "tool.py").write_text('print("ok")\n')
        results = scan_mcp_directory(str(tmp_path))
        assert len(results) == 1
        files = [r.file for r in results]
        assert str(tmp_path / "tool.py") in files

    def test_nonexistent_directory(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_mcp_directory

        results = scan_mcp_directory(str(tmp_path / "nonexistent"))
        assert results == []

    def test_empty_directory(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_mcp_directory

        results = scan_mcp_directory(str(tmp_path))
        assert results == []

    def test_passes_security_mode(self, tmp_path):
        from spellbook_mcp.security.scanner import scan_mcp_directory

        py_file = tmp_path / "env.py"
        # MCP-006 is MEDIUM severity
        py_file.write_text('secret = os.environ["KEY"]\n')

        results_standard = scan_mcp_directory(str(tmp_path), security_mode="standard")
        results_paranoid = scan_mcp_directory(str(tmp_path), security_mode="paranoid")

        standard_ids = [f.rule_id for r in results_standard for f in r.findings]
        paranoid_ids = [f.rule_id for r in results_paranoid for f in r.findings]

        assert "MCP-006" not in standard_ids
        assert "MCP-006" in paranoid_ids


# ---------------------------------------------------------------------------
# CLI --mode mcp tests
# ---------------------------------------------------------------------------


class TestCLIModeMCP:
    """CLI --mode mcp flag triggers MCP directory scanning."""

    def test_cli_mode_mcp_clean_exits_zero(self, tmp_path):
        py_file = tmp_path / "clean.py"
        py_file.write_text('print("hello")\n')

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "spellbook_mcp.security.scanner",
                "--mode",
                "mcp",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_mode_mcp_findings_exits_one(self, tmp_path):
        py_file = tmp_path / "bad.py"
        py_file.write_text('os.system("rm -rf /")\n')

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "spellbook_mcp.security.scanner",
                "--mode",
                "mcp",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "MCP-009" in result.stderr

    def test_cli_mode_mcp_empty_dir_exits_zero(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "spellbook_mcp.security.scanner",
                "--mode",
                "mcp",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_mode_mcp_nested_detection(self, tmp_path):
        sub = tmp_path / "tools" / "handlers"
        sub.mkdir(parents=True)
        (sub / "handler.py").write_text(
            'subprocess.run(cmd, shell=True)\n'
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "spellbook_mcp.security.scanner",
                "--mode",
                "mcp",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "MCP-001" in result.stderr

    def test_cli_usage_updated(self):
        """Usage message mentions --mode with mcp option."""
        result = subprocess.run(
            [sys.executable, "-m", "spellbook_mcp.security.scanner"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "--mode" in result.stderr
        assert "mcp" in result.stderr
