"""Tests for server startup optimizations.

Verifies:
1. init_curator_tables no-op has been removed from startup()
2. Timing instrumentation is present in startup()
"""

import inspect


class TestStartupNoCuratorInit:
    def test_init_curator_tables_not_referenced_in_startup(self):
        """After removal, startup() should not reference init_curator_tables.

        Uses source inspection to verify the removal without needing to
        instantiate the full server stack.
        """
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        # The string "init_curator_tables" must not appear anywhere in startup's source
        assert "init_curator_tables" not in source, (
            "startup() still references init_curator_tables after removal"
        )

    def test_init_curator_tables_not_in_module_level_imports(self):
        """init_curator_tables should not be imported at module level in server.py."""
        import spellbook.mcp.server as server_module

        source = inspect.getsource(server_module)
        # Module-level imports are outside any function; check that no top-level
        # import line references init_curator_tables. Function-level imports inside
        # startup() are already checked by the test above; this checks the rest.
        # We verify by checking that the only function referencing it (startup)
        # no longer does, AND there's no top-level import.
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip lines inside function/class bodies (indented)
            if stripped.startswith("from") or stripped.startswith("import"):
                assert "init_curator_tables" not in stripped, (
                    f"init_curator_tables still imported at line {i + 1}: {stripped}"
                )


class TestStartupProfiling:
    def test_startup_has_timed_helper(self):
        """startup() should define a _timed helper for timing phases."""
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        assert "def _timed(" in source, (
            "startup() does not define a _timed timing helper"
        )

    def test_startup_uses_time_monotonic(self):
        """startup() timing should use time.monotonic() for measurements."""
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        assert "time.monotonic()" in source, (
            "startup() does not use time.monotonic() for timing"
        )

    def test_startup_collects_timings_dict(self):
        """startup() should collect timings into a dict."""
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        assert "timings: dict[str, float] = {}" in source, (
            "startup() does not define timings dict"
        )

    def test_startup_logs_timings(self):
        """startup() should log timing data with 'startup timings' message."""
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        assert 'logger.info("startup timings:' in source, (
            "startup() does not log startup timings via logger.info"
        )

    def test_startup_times_db_init_phases(self):
        """startup() should time each database initialization phase."""
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        # Each DB init should be wrapped in _timed
        assert '_timed("init_db"' in source, (
            "startup() does not time init_db"
        )
        assert '_timed("init_forged_schema"' in source, (
            "startup() does not time init_forged_schema"
        )
        assert '_timed("init_fractal_schema"' in source, (
            "startup() does not time init_fractal_schema"
        )

    def test_startup_times_watcher_phases(self):
        """startup() should time watcher initialization and start."""
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        assert '_timed("session_watcher' in source, (
            "startup() does not time session watcher"
        )

    def test_startup_times_mount_phases(self):
        """startup() should time admin app mount."""
        from spellbook.mcp.server import startup

        source = inspect.getsource(startup)
        assert '_timed("mount_admin"' in source, (
            "startup() does not time admin mount"
        )
