"""Tests for diff_symbols and search_serena modules.

Covers: DiffHunk/SymbolChange dataclasses, parse_diff_hunks, extract_symbols_from_hunk
(Python, JS/TS, generic), extract_changed_files, extract_changed_symbols,
and Serena at-risk memory detection (hard-dep; integration tests marked).
"""

import datetime
import os

import pytest
import yaml


# ---------------------------------------------------------------------------
# Sample diff fixtures
# ---------------------------------------------------------------------------

SAMPLE_UNIFIED_DIFF = """\
diff --git a/src/api/client.py b/src/api/client.py
index abc1234..def5678 100644
--- a/src/api/client.py
+++ b/src/api/client.py
@@ -10,7 +10,9 @@ class APIClient:
     def __init__(self, base_url):
         self.base_url = base_url

-    def retry(self, request):
-        return self._send(request)
+    def retry_with_backoff(self, request, max_retries=3):
+        for attempt in range(max_retries):
+            response = self._send(request)
+            if response.ok:
+                return response
+        raise RetryError("max retries exceeded")

     def _send(self, request):
@@ -25,3 +27,6 @@ class APIClient:
         pass

     def close(self):
         pass
+
+def calculate_backoff(attempt, base_delay=1.0):
+    return base_delay * (2 ** attempt)
"""

SAMPLE_PYTHON_ADD_DIFF = """\
diff --git a/src/utils.py b/src/utils.py
new file mode 100644
--- /dev/null
+++ b/src/utils.py
@@ -0,0 +1,12 @@
+import math
+
+def exponential_backoff(attempt, base=1.0):
+    return base * (2 ** attempt)
+
+class RetryPolicy:
+    def __init__(self, max_retries=3):
+        self.max_retries = max_retries
+
+    def should_retry(self, attempt):
+        return attempt < self.max_retries
+
"""

SAMPLE_JS_DIFF = """\
diff --git a/src/client.ts b/src/client.ts
index aaa1111..bbb2222 100644
--- a/src/client.ts
+++ b/src/client.ts
@@ -5,8 +5,12 @@ import { Config } from './config';
 export class HttpClient {
     private baseUrl: string;

-    constructor(baseUrl: string) {
+    constructor(baseUrl: string, private timeout: number = 30000) {
         this.baseUrl = baseUrl;
     }
+
+    async fetchWithRetry(url: string, retries: number = 3): Promise<Response> {
+        return fetch(url);
+    }
 }

-export const DEFAULT_TIMEOUT = 5000;
+export const DEFAULT_TIMEOUT = 30000;
+
+export function createClient(config: Config): HttpClient {
+    return new HttpClient(config.baseUrl, config.timeout);
+}
"""

SAMPLE_GENERIC_DIFF = """\
diff --git a/config.yaml b/config.yaml
index 111aaaa..222bbbb 100644
--- a/config.yaml
+++ b/config.yaml
@@ -1,5 +1,5 @@
 server:
-  port: 8080
+  port: 9090
   host: localhost
"""

SAMPLE_PYTHON_REMOVE_DIFF = """\
diff --git a/src/old_module.py b/src/old_module.py
index aaa1111..bbb2222 100644
--- a/src/old_module.py
+++ b/src/old_module.py
@@ -1,10 +1,4 @@
-def deprecated_function():
-    pass
-
-class OldHandler:
-    def handle(self):
-        pass
-
 def kept_function():
     return True

"""

SAMPLE_MULTI_FILE_DIFF = """\
diff --git a/src/api/client.py b/src/api/client.py
index abc1234..def5678 100644
--- a/src/api/client.py
+++ b/src/api/client.py
@@ -10,4 +10,6 @@ class APIClient:
     def __init__(self, base_url):
         self.base_url = base_url

+    def new_method(self):
+        pass
diff --git a/src/utils.py b/src/utils.py
index 111aaaa..222bbbb 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,3 +1,3 @@
-def old_helper():
+def new_helper():
     pass

"""


# ---------------------------------------------------------------------------
# Helper: write memory files for at-risk tests
# ---------------------------------------------------------------------------

def _write_memory(directory, type_dir, slug, fm_dict, body):
    """Helper to write a memory file for tests."""
    d = os.path.join(str(directory), type_dir)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{slug}.md")
    fm_yaml = yaml.dump(fm_dict, default_flow_style=False, sort_keys=False)
    with open(p, "w") as f:
        f.write(f"---\n{fm_yaml}---\n\n{body}\n")
    return p


# ---------------------------------------------------------------------------
# DiffHunk / SymbolChange data models
# ---------------------------------------------------------------------------


class TestDiffModels:
    """Test DiffHunk and SymbolChange dataclass construction."""

    def test_diff_hunk_construction(self):
        from spellbook.memory.diff_symbols import DiffHunk

        hunk = DiffHunk(
            file_path="src/api/client.py",
            old_start=10,
            old_count=7,
            new_start=10,
            new_count=9,
            content="@@ -10,7 +10,9 @@\n context\n-old\n+new",
            added_lines=["+new"],
            removed_lines=["-old"],
        )
        assert hunk == DiffHunk(
            file_path="src/api/client.py",
            old_start=10,
            old_count=7,
            new_start=10,
            new_count=9,
            content="@@ -10,7 +10,9 @@\n context\n-old\n+new",
            added_lines=["+new"],
            removed_lines=["-old"],
        )

    def test_symbol_change_construction(self):
        from spellbook.memory.diff_symbols import SymbolChange

        sc = SymbolChange(
            file="src/api/client.py",
            symbol_name="retry_with_backoff",
            change_type="added",
            symbol_type="method",
            context="def retry_with_backoff(self, request):",
        )
        assert sc == SymbolChange(
            file="src/api/client.py",
            symbol_name="retry_with_backoff",
            change_type="added",
            symbol_type="method",
            context="def retry_with_backoff(self, request):",
        )

    def test_symbol_change_default_context(self):
        from spellbook.memory.diff_symbols import SymbolChange

        sc = SymbolChange(
            file="a.py",
            symbol_name="foo",
            change_type="modified",
            symbol_type="function",
        )
        assert sc.context == ""


# ---------------------------------------------------------------------------
# parse_diff_hunks
# ---------------------------------------------------------------------------


class TestParseDiffHunks:
    """Test unified diff parsing into structured DiffHunk objects."""

    def test_parse_single_file_two_hunks(self):
        from spellbook.memory.diff_symbols import DiffHunk, parse_diff_hunks

        hunks = parse_diff_hunks(SAMPLE_UNIFIED_DIFF)

        # The sample diff has 2 hunks, both in src/api/client.py
        assert len(hunks) == 2

        h0 = hunks[0]
        assert h0.file_path == "src/api/client.py"
        assert h0.old_start == 10
        assert h0.old_count == 7
        assert h0.new_start == 10
        assert h0.new_count == 9
        assert h0.removed_lines == [
            "    def retry(self, request):",
            "        return self._send(request)",
        ]
        assert h0.added_lines == [
            "    def retry_with_backoff(self, request, max_retries=3):",
            "        for attempt in range(max_retries):",
            "            response = self._send(request)",
            "            if response.ok:",
            "                return response",
            "        raise RetryError(\"max retries exceeded\")",
        ]

        h1 = hunks[1]
        assert h1.file_path == "src/api/client.py"
        assert h1.old_start == 25
        assert h1.old_count == 3
        assert h1.new_start == 27
        assert h1.new_count == 6
        assert h1.removed_lines == []
        assert h1.added_lines == [
            "",
            "def calculate_backoff(attempt, base_delay=1.0):",
            "    return base_delay * (2 ** attempt)",
        ]

    def test_parse_new_file(self):
        from spellbook.memory.diff_symbols import parse_diff_hunks

        hunks = parse_diff_hunks(SAMPLE_PYTHON_ADD_DIFF)
        assert len(hunks) == 1
        h = hunks[0]
        assert h.file_path == "src/utils.py"
        assert h.old_start == 0
        assert h.old_count == 0
        assert h.new_start == 1
        assert h.new_count == 12
        assert h.removed_lines == []
        assert len(h.added_lines) == 12

    def test_parse_multi_file_diff(self):
        from spellbook.memory.diff_symbols import parse_diff_hunks

        hunks = parse_diff_hunks(SAMPLE_MULTI_FILE_DIFF)
        assert len(hunks) == 2
        assert hunks[0].file_path == "src/api/client.py"
        assert hunks[1].file_path == "src/utils.py"

    def test_parse_empty_diff(self):
        from spellbook.memory.diff_symbols import parse_diff_hunks

        hunks = parse_diff_hunks("")
        assert hunks == []

    def test_parse_generic_diff_no_code(self):
        from spellbook.memory.diff_symbols import parse_diff_hunks

        hunks = parse_diff_hunks(SAMPLE_GENERIC_DIFF)
        assert len(hunks) == 1
        assert hunks[0].file_path == "config.yaml"
        assert hunks[0].removed_lines == ["  port: 8080"]
        assert hunks[0].added_lines == ["  port: 9090"]


# ---------------------------------------------------------------------------
# extract_symbols_from_hunk - Python
# ---------------------------------------------------------------------------


class TestExtractSymbolsFromHunkPython:
    """Test Python symbol extraction from diff hunks."""

    def test_extract_added_function(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/utils.py",
            old_start=0,
            old_count=0,
            new_start=1,
            new_count=5,
            content="@@ -0,0 +1,5 @@\n+def exponential_backoff(attempt, base=1.0):\n+    return base * (2 ** attempt)\n",
            added_lines=[
                "def exponential_backoff(attempt, base=1.0):",
                "    return base * (2 ** attempt)",
            ],
            removed_lines=[],
        )
        symbols = extract_symbols_from_hunk(hunk, ".py")

        assert symbols == [
            SymbolChange(
                file="src/utils.py",
                symbol_name="exponential_backoff",
                change_type="added",
                symbol_type="function",
                context="def exponential_backoff(attempt, base=1.0):",
            ),
        ]

    def test_extract_added_class(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/utils.py",
            old_start=0,
            old_count=0,
            new_start=1,
            new_count=6,
            content="",
            added_lines=[
                "class RetryPolicy:",
                "    def __init__(self, max_retries=3):",
                "        self.max_retries = max_retries",
                "    def should_retry(self, attempt):",
                "        return attempt < self.max_retries",
            ],
            removed_lines=[],
        )
        symbols = extract_symbols_from_hunk(hunk, ".py")

        # Should extract the class and its methods
        symbol_names = {s.symbol_name for s in symbols}
        assert "RetryPolicy" in symbol_names
        # Class-level methods should be extracted as methods
        assert "RetryPolicy.__init__" in symbol_names or "__init__" in symbol_names
        assert "RetryPolicy.should_retry" in symbol_names or "should_retry" in symbol_names

        # Verify types
        class_sym = [s for s in symbols if s.symbol_name == "RetryPolicy"][0]
        assert class_sym.change_type == "added"
        assert class_sym.symbol_type == "class"

    def test_extract_removed_function(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/old_module.py",
            old_start=1,
            old_count=10,
            new_start=1,
            new_count=4,
            content="",
            added_lines=[],
            removed_lines=[
                "def deprecated_function():",
                "    pass",
                "",
                "class OldHandler:",
                "    def handle(self):",
                "        pass",
            ],
        )
        symbols = extract_symbols_from_hunk(hunk, ".py")

        symbol_names = {s.symbol_name for s in symbols}
        assert "deprecated_function" in symbol_names
        assert "OldHandler" in symbol_names

        removed_fn = [s for s in symbols if s.symbol_name == "deprecated_function"][0]
        assert removed_fn.change_type == "removed"
        assert removed_fn.symbol_type == "function"

        removed_cls = [s for s in symbols if s.symbol_name == "OldHandler"][0]
        assert removed_cls.change_type == "removed"
        assert removed_cls.symbol_type == "class"

    def test_extract_modified_function(self):
        """When same symbol appears in both added and removed lines, it's modified."""
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/api/client.py",
            old_start=10,
            old_count=4,
            new_start=10,
            new_count=4,
            content="",
            added_lines=[
                "    def retry_with_backoff(self, request, max_retries=3):",
                "        for attempt in range(max_retries):",
                "            response = self._send(request)",
                "        raise RetryError(\"max retries exceeded\")",
            ],
            removed_lines=[
                "    def retry(self, request):",
                "        return self._send(request)",
            ],
        )
        symbols = extract_symbols_from_hunk(hunk, ".py")

        # retry was removed and retry_with_backoff was added
        symbol_names = {s.symbol_name for s in symbols}
        assert "retry" in symbol_names or "retry_with_backoff" in symbol_names
        # At minimum, we should see both the old and new names
        assert len(symbols) >= 1

    def test_extract_async_def_function(self):
        """`async def` should be recognized as a function symbol."""
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/async_mod.py",
            old_start=0,
            old_count=0,
            new_start=1,
            new_count=2,
            content="",
            added_lines=[
                "async def foo(x):",
                "    return x",
            ],
            removed_lines=[],
        )
        symbols = extract_symbols_from_hunk(hunk, ".py")
        assert {s.symbol_name for s in symbols} == {"foo"}

    def test_extract_method_with_class_context(self):
        """Methods inside a class context should be identified as methods."""
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/api/client.py",
            old_start=10,
            old_count=3,
            new_start=10,
            new_count=5,
            content="@@ -10,3 +10,5 @@ class APIClient:\n     def __init__(self, base_url):\n         self.base_url = base_url\n+\n+    def new_method(self):\n+        pass\n",
            added_lines=[
                "    def new_method(self):",
                "        pass",
            ],
            removed_lines=[],
        )
        symbols = extract_symbols_from_hunk(hunk, ".py")

        assert len(symbols) >= 1
        method_sym = [s for s in symbols if "new_method" in s.symbol_name][0]
        assert method_sym.change_type == "added"
        # Should be method since it's indented (self parameter or context says class)
        assert method_sym.symbol_type == "method"


# ---------------------------------------------------------------------------
# extract_symbols_from_hunk - JS/TS
# ---------------------------------------------------------------------------


class TestExtractSymbolsFromHunkJS:
    """Test JS/TS symbol extraction from diff hunks."""

    def test_extract_added_export_function(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/client.ts",
            old_start=15,
            old_count=0,
            new_start=15,
            new_count=3,
            content="",
            added_lines=[
                "export function createClient(config: Config): HttpClient {",
                "    return new HttpClient(config.baseUrl, config.timeout);",
                "}",
            ],
            removed_lines=[],
        )
        symbols = extract_symbols_from_hunk(hunk, ".ts")

        assert len(symbols) >= 1
        fn_sym = [s for s in symbols if s.symbol_name == "createClient"][0]
        assert fn_sym.change_type == "added"
        assert fn_sym.symbol_type == "function"
        assert fn_sym.file == "src/client.ts"

    def test_extract_added_class_method(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/client.ts",
            old_start=8,
            old_count=2,
            new_start=8,
            new_count=6,
            content="@@ -8,2 +8,6 @@ export class HttpClient {\n     }\n+\n+    async fetchWithRetry(url: string, retries: number = 3): Promise<Response> {\n+        return fetch(url);\n+    }\n",
            added_lines=[
                "    async fetchWithRetry(url: string, retries: number = 3): Promise<Response> {",
                "        return fetch(url);",
                "    }",
            ],
            removed_lines=[],
        )
        symbols = extract_symbols_from_hunk(hunk, ".ts")

        assert len(symbols) >= 1
        method_sym = [s for s in symbols if "fetchWithRetry" in s.symbol_name][0]
        assert method_sym.change_type == "added"
        assert method_sym.symbol_type == "method"

    def test_extract_modified_const(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/client.ts",
            old_start=14,
            old_count=1,
            new_start=18,
            new_count=1,
            content="",
            added_lines=[
                "export const DEFAULT_TIMEOUT = 30000;",
            ],
            removed_lines=[
                "export const DEFAULT_TIMEOUT = 5000;",
            ],
        )
        symbols = extract_symbols_from_hunk(hunk, ".ts")

        assert len(symbols) >= 1
        const_sym = [s for s in symbols if s.symbol_name == "DEFAULT_TIMEOUT"][0]
        assert const_sym.change_type == "modified"
        assert const_sym.symbol_type == "variable"

    def test_extract_js_function_keyword(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            SymbolChange,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="src/helpers.js",
            old_start=0,
            old_count=0,
            new_start=1,
            new_count=3,
            content="",
            added_lines=[
                "function parseResponse(data) {",
                "    return JSON.parse(data);",
                "}",
            ],
            removed_lines=[],
        )
        symbols = extract_symbols_from_hunk(hunk, ".js")

        assert len(symbols) == 1
        assert symbols[0] == SymbolChange(
            file="src/helpers.js",
            symbol_name="parseResponse",
            change_type="added",
            symbol_type="function",
            context="function parseResponse(data) {",
        )


# ---------------------------------------------------------------------------
# extract_symbols_from_hunk - Generic
# ---------------------------------------------------------------------------


class TestExtractSymbolsFromHunkGeneric:
    """Test generic/unknown language symbol extraction."""

    def test_generic_returns_empty_for_config_files(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="config.yaml",
            old_start=1,
            old_count=5,
            new_start=1,
            new_count=5,
            content="",
            added_lines=["  port: 9090"],
            removed_lines=["  port: 8080"],
        )
        symbols = extract_symbols_from_hunk(hunk, ".yaml")

        # YAML has no recognizable symbol patterns
        assert symbols == []

    def test_generic_handles_unknown_extension(self):
        from spellbook.memory.diff_symbols import (
            DiffHunk,
            extract_symbols_from_hunk,
        )

        hunk = DiffHunk(
            file_path="data.xyz",
            old_start=1,
            old_count=1,
            new_start=1,
            new_count=1,
            content="",
            added_lines=["some data line"],
            removed_lines=["old data line"],
        )
        symbols = extract_symbols_from_hunk(hunk, ".xyz")

        # Unknown extension: should return empty, not crash
        assert symbols == []


# ---------------------------------------------------------------------------
# extract_changed_files (git integration)
# ---------------------------------------------------------------------------


class TestExtractChangedFiles:
    """Test git diff file extraction."""

    @pytest.mark.allow("subprocess")
    def test_extract_changed_files_in_git_repo(self, tmp_path):
        """Test in a real git repo with actual changes."""
        import subprocess

        from spellbook.memory.diff_symbols import extract_changed_files

        repo = str(tmp_path)
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            capture_output=True,
        )

        # Initial commit on main
        (tmp_path / "existing.py").write_text("# existing\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=repo,
            capture_output=True,
        )

        # Create feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=repo,
            capture_output=True,
        )
        (tmp_path / "new_file.py").write_text("def new_func(): pass\n")
        (tmp_path / "existing.py").write_text("# modified\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature changes"],
            cwd=repo,
            capture_output=True,
        )

        changed = extract_changed_files(repo, base_ref="main")
        assert sorted(changed) == ["existing.py", "new_file.py"]

    @pytest.mark.allow("subprocess")
    def test_extract_changed_files_empty_diff(self, tmp_path):
        """When no files changed, return empty list."""
        import subprocess

        from spellbook.memory.diff_symbols import extract_changed_files

        repo = str(tmp_path)
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            capture_output=True,
        )
        (tmp_path / "file.py").write_text("# content\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=repo,
            capture_output=True,
        )

        # Still on main, no branch diff
        changed = extract_changed_files(repo, base_ref="main")
        assert changed == []


# ---------------------------------------------------------------------------
# extract_changed_symbols (integration of diff + extraction)
# ---------------------------------------------------------------------------


class TestExtractChangedSymbols:
    """Test extract_changed_symbols orchestration."""

    @pytest.mark.allow("subprocess")
    def test_extract_changed_symbols_from_git(self, tmp_path):
        """End-to-end: git repo with Python changes produces SymbolChange objects."""
        import subprocess

        from spellbook.memory.diff_symbols import SymbolChange, extract_changed_symbols

        repo = str(tmp_path)
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            capture_output=True,
        )

        # Initial commit
        (tmp_path / "module.py").write_text(
            "def old_function():\n    pass\n"
        )
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=repo,
            capture_output=True,
        )

        # Feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature/new"],
            cwd=repo,
            capture_output=True,
        )
        (tmp_path / "module.py").write_text(
            "def new_function():\n    return 42\n"
        )
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "replace function"],
            cwd=repo,
            capture_output=True,
        )

        symbols = extract_changed_symbols(repo, base_ref="main")
        assert len(symbols) >= 1

        symbol_names = {s.symbol_name for s in symbols}
        # Should find old_function (removed) and/or new_function (added)
        assert "old_function" in symbol_names or "new_function" in symbol_names

        # All should reference module.py
        for s in symbols:
            assert s.file == "module.py"


# ---------------------------------------------------------------------------
# search_serena data models
# ---------------------------------------------------------------------------


class TestSerenaModels:
    """Test search_serena data models."""

    def test_symbol_reference_construction(self):
        from spellbook.memory.search_serena import SymbolReference

        ref = SymbolReference(file="src/main.py", symbol="main", line=10)
        assert ref == SymbolReference(file="src/main.py", symbol="main", line=10)

    def test_at_risk_memory_construction(self):
        from spellbook.memory.models import Citation, MemoryFile, MemoryFrontmatter
        from spellbook.memory.search_serena import AtRiskMemory

        fm = MemoryFrontmatter(
            type="project",
            created=datetime.date(2026, 4, 14),
        )
        mf = MemoryFile(path="/tmp/test.md", frontmatter=fm, content="body")
        cit = Citation(file="src/main.py", symbol="main", symbol_type="function")

        arm = AtRiskMemory(
            memory=mf,
            at_risk_citations=[cit],
            reason="cited_file_changed",
            relevant_diff="diff text here",
        )
        assert arm.memory is mf
        assert arm.at_risk_citations == [cit]
        assert arm.reason == "cited_file_changed"
        assert arm.relevant_diff == "diff text here"

    def test_at_risk_memory_default_diff(self):
        from spellbook.memory.models import MemoryFile, MemoryFrontmatter
        from spellbook.memory.search_serena import AtRiskMemory

        fm = MemoryFrontmatter(
            type="project",
            created=datetime.date(2026, 4, 14),
        )
        mf = MemoryFile(path="/tmp/test.md", frontmatter=fm, content="body")

        arm = AtRiskMemory(
            memory=mf,
            at_risk_citations=[],
            reason="cited_file_changed",
        )
        assert arm.relevant_diff == ""


# ---------------------------------------------------------------------------
# find_at_risk_memories (file-citation matching)
# ---------------------------------------------------------------------------


def _symbol_changes_for_files(files):
    """Build file-only SymbolChange entries for at-risk detection."""
    from spellbook.memory.diff_symbols import SymbolChange

    return [
        SymbolChange(
            file=f,
            symbol_name="",
            symbol_type="",
            change_type="modified",
            context="",
        )
        for f in files
    ]


class TestFindAtRiskMemories:
    """Test citation-based at-risk memory detection."""

    def test_finds_memories_citing_changed_files(self, tmp_path):
        from spellbook.memory.search_serena import find_at_risk_memories

        _write_memory(
            tmp_path,
            "project",
            "client-retry",
            {
                "type": "project",
                "created": "2026-04-14",
                "content_hash": "sha256:abc",
                "citations": [
                    {"file": "src/api/client.py", "symbol": "APIClient.retry"},
                ],
            },
            "We use retry backoff in the API client.",
        )
        _write_memory(
            tmp_path,
            "project",
            "deploy-process",
            {
                "type": "project",
                "created": "2026-04-14",
                "content_hash": "sha256:def",
                "citations": [
                    {"file": "scripts/deploy.sh"},
                ],
            },
            "Deploy process requires staging first.",
        )

        changes = _symbol_changes_for_files(["src/api/client.py"])
        at_risk = find_at_risk_memories(
            changes, str(tmp_path), "/fake/project/root"
        )

        assert len(at_risk) == 1
        assert "client-retry" in at_risk[0].memory.path
        assert at_risk[0].reason == "cited_file_changed"
        assert len(at_risk[0].at_risk_citations) == 1
        assert at_risk[0].at_risk_citations[0].file == "src/api/client.py"

    def test_no_at_risk_when_no_citations_match(self, tmp_path):
        from spellbook.memory.search_serena import find_at_risk_memories

        _write_memory(
            tmp_path,
            "project",
            "unrelated-memory",
            {
                "type": "project",
                "created": "2026-04-14",
                "content_hash": "sha256:xyz",
                "citations": [
                    {"file": "src/unrelated.py"},
                ],
            },
            "Unrelated memory.",
        )

        changes = _symbol_changes_for_files(["src/api/client.py"])
        at_risk = find_at_risk_memories(
            changes, str(tmp_path), "/fake/project/root"
        )
        assert at_risk == []

    def test_memory_with_no_citations_not_at_risk(self, tmp_path):
        from spellbook.memory.search_serena import find_at_risk_memories

        _write_memory(
            tmp_path,
            "project",
            "no-citations",
            {
                "type": "project",
                "created": "2026-04-14",
                "content_hash": "sha256:nocit",
            },
            "Memory without any citations.",
        )

        changes = _symbol_changes_for_files(["src/api/client.py"])
        at_risk = find_at_risk_memories(
            changes, str(tmp_path), "/fake/project/root"
        )
        assert at_risk == []

    def test_multiple_changed_files_match_one_memory(self, tmp_path):
        from spellbook.memory.search_serena import find_at_risk_memories

        _write_memory(
            tmp_path,
            "project",
            "multi-cite",
            {
                "type": "project",
                "created": "2026-04-14",
                "content_hash": "sha256:multi",
                "citations": [
                    {"file": "src/api/client.py"},
                    {"file": "src/utils.py"},
                ],
            },
            "Memory citing multiple files.",
        )

        changes = _symbol_changes_for_files(["src/api/client.py", "src/utils.py"])
        at_risk = find_at_risk_memories(
            changes, str(tmp_path), "/fake/project/root"
        )
        assert len(at_risk) == 1
        at_risk_files = {c.file for c in at_risk[0].at_risk_citations}
        assert at_risk_files == {"src/api/client.py", "src/utils.py"}

    def test_skips_archive_directory(self, tmp_path):
        from spellbook.memory.search_serena import find_at_risk_memories

        _write_memory(
            tmp_path,
            ".archive/project",
            "archived-memory",
            {
                "type": "project",
                "created": "2026-04-14",
                "content_hash": "sha256:arc",
                "citations": [
                    {"file": "src/api/client.py"},
                ],
            },
            "Archived memory.",
        )

        changes = _symbol_changes_for_files(["src/api/client.py"])
        at_risk = find_at_risk_memories(
            changes, str(tmp_path), "/fake/project/root"
        )
        assert at_risk == []
