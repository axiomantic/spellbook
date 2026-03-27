"""Tests for subsystem health matrix API routes."""

from contextlib import asynccontextmanager

import bigfoot
import pytest


class _MockResult:
    """Mimics SQLAlchemy Result with .mappings().all() chain."""

    def __init__(self, data):
        self._data = data

    def mappings(self):
        return self

    def all(self):
        return self._data


class _MockSession:
    """Async mock session that returns results from a side_effects list.

    Each call to session.execute() pops the next item from side_effects
    and returns it wrapped in a _MockResult with .mappings().all() behavior.
    """

    def __init__(self, side_effects):
        self._side_effects = side_effects
        self._call_idx = 0
        self.execute_call_count = 0

    async def execute(self, query, params=None):
        idx = self._call_idx
        self._call_idx += 1
        self.execute_call_count += 1
        if idx >= len(self._side_effects):
            raise RuntimeError(f"Unexpected execute call #{idx}")
        data = self._side_effects[idx]
        if isinstance(data, Exception):
            raise data
        return _MockResult(data)


def _make_mock_session(side_effects):
    """Create a mock async session that returns results from side_effects list."""
    return _MockSession(side_effects)


def _make_session_factory(session):
    """Wrap a mock session in an async context manager factory."""
    @asynccontextmanager
    async def factory():
        yield session
    return factory


class TestHealthMatrix:
    def test_returns_all_databases(self, client, monkeypatch):
        mock_spellbook_session = _make_mock_session([
            [{"name": "memories"}, {"name": "security_events"}],  # table list
            [{"cnt": 100}],  # memories count
            [{"latest": "2026-03-15T10:00:00"}],  # memories last activity
            [{"cnt": 5000}],  # security_events count
            [{"latest": "2026-03-15T10:30:00"}],  # security_events last activity
        ])
        mock_fractal_session = _make_mock_session([
            [{"name": "graphs"}, {"name": "nodes"}],
            [{"cnt": 3}],
            [{"latest": "2026-03-15T09:00:00"}],
            [{"cnt": 50}],
            [{"latest": "2026-03-15T09:30:00"}],
        ])
        mock_forged_session = _make_mock_session([
            [{"name": "projects"}],
            [{"cnt": 2}],
            [{"latest": "2026-03-14T15:00:00"}],
        ])
        mock_coord_session = _make_mock_session([
            [{"name": "swarms"}],
            [{"cnt": 1}],
            [{"latest": None}],
        ])

        mock_get_spellbook = bigfoot.mock(
            "spellbook.admin.routes.health:get_spellbook_session"
        )
        mock_get_spellbook.calls(
            lambda: _make_session_factory(mock_spellbook_session)()
        )

        mock_get_fractal = bigfoot.mock(
            "spellbook.admin.routes.health:get_fractal_session"
        )
        mock_get_fractal.calls(
            lambda: _make_session_factory(mock_fractal_session)()
        )

        mock_get_forged = bigfoot.mock(
            "spellbook.admin.routes.health:get_forged_session"
        )
        mock_get_forged.calls(
            lambda: _make_session_factory(mock_forged_session)()
        )

        mock_get_coord = bigfoot.mock(
            "spellbook.admin.routes.health:get_coordination_session"
        )
        mock_get_coord.calls(
            lambda: _make_session_factory(mock_coord_session)()
        )

        mock_paths = bigfoot.mock(
            "spellbook.admin.routes.health:_get_db_paths"
        )
        mock_paths.returns({
            "spellbook.db": "/tmp/spellbook.db",
            "fractal.db": "/tmp/fractal.db",
            "forged.db": "/tmp/forged.db",
            "coordination.db": "/tmp/coordination.db",
        })

        monkeypatch.setattr("os.path.getsize", lambda path: 1234567)
        monkeypatch.setattr("os.path.exists", lambda path: True)

        with bigfoot:
            response = client.get("/api/health/matrix")

        assert response.status_code == 200
        data = response.json()
        assert "databases" in data
        assert "generated_at" in data
        db_names = [db["name"] for db in data["databases"]]
        assert db_names == ["spellbook.db", "fractal.db", "forged.db", "coordination.db"]
        assert len(data["databases"]) == 4

        # Verify spellbook.db details
        spellbook_db = data["databases"][0]
        assert spellbook_db["name"] == "spellbook.db"
        assert spellbook_db["status"] in ("healthy", "idle")
        assert spellbook_db["size_bytes"] == 1234567
        table_names = [t["name"] for t in spellbook_db["tables"]]
        assert table_names == ["memories", "security_events"]
        assert spellbook_db["tables"][0]["row_count"] == 100
        assert spellbook_db["tables"][0]["last_activity"] == "2026-03-15T10:00:00"
        assert spellbook_db["tables"][1]["row_count"] == 5000
        assert spellbook_db["tables"][1]["last_activity"] == "2026-03-15T10:30:00"

        # Verify fractal.db details
        fractal_db = data["databases"][1]
        assert fractal_db["name"] == "fractal.db"
        assert fractal_db["size_bytes"] == 1234567
        fractal_tables = [t["name"] for t in fractal_db["tables"]]
        assert fractal_tables == ["graphs", "nodes"]
        assert fractal_db["tables"][0]["row_count"] == 3
        assert fractal_db["tables"][1]["row_count"] == 50

        # Verify forged.db details
        forged_db = data["databases"][2]
        assert forged_db["name"] == "forged.db"
        assert forged_db["tables"][0]["name"] == "projects"
        assert forged_db["tables"][0]["row_count"] == 2

        # Verify coordination.db details
        coord_db = data["databases"][3]
        assert coord_db["name"] == "coordination.db"
        assert coord_db["tables"][0]["name"] == "swarms"
        assert coord_db["tables"][0]["row_count"] == 1
        assert coord_db["tables"][0]["last_activity"] is None

        # Verify session.execute was called the expected number of times:
        # 1 table list + (1 count + 1 timestamp) * 2 tables = 5 calls
        assert mock_spellbook_session.execute_call_count == 5

        # Assert all mocked interactions
        mock_paths.assert_call(args=(), kwargs={})
        mock_get_spellbook.assert_call()
        mock_get_fractal.assert_call()
        mock_get_forged.assert_call()
        mock_get_coord.assert_call()

    def test_missing_db_returns_missing_status(self, client, monkeypatch):
        mock_paths = bigfoot.mock(
            "spellbook.admin.routes.health:_get_db_paths"
        )
        mock_paths.returns({
            "spellbook.db": "/tmp/nonexistent.db",
        })

        mock_get_factory = bigfoot.mock(
            "spellbook.admin.routes.health:_get_session_factory"
        )
        mock_get_factory.returns(
            _make_session_factory(_make_mock_session([]))
        )

        monkeypatch.setattr("os.path.exists", lambda path: False)

        with bigfoot:
            response = client.get("/api/health/matrix")

        assert response.status_code == 200
        data = response.json()
        assert data["databases"][0] == {
            "name": "spellbook.db",
            "status": "missing",
            "size_bytes": 0,
            "tables": [],
        }

        mock_paths.assert_call(args=(), kwargs={})
        mock_get_factory.assert_call(args=("spellbook.db",), kwargs={})

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/health/matrix")
        assert response.status_code == 401

    def test_db_query_error_returns_error_status(self, client, monkeypatch):
        error_session = _make_mock_session([Exception("db locked")])

        mock_paths = bigfoot.mock(
            "spellbook.admin.routes.health:_get_db_paths"
        )
        mock_paths.returns({
            "spellbook.db": "/tmp/spellbook.db",
        })

        mock_get_factory = bigfoot.mock(
            "spellbook.admin.routes.health:_get_session_factory"
        )
        mock_get_factory.returns(
            _make_session_factory(error_session)
        )

        monkeypatch.setattr("os.path.exists", lambda path: True)
        monkeypatch.setattr("os.path.getsize", lambda path: 999)

        with bigfoot:
            response = client.get("/api/health/matrix")

        assert response.status_code == 200
        data = response.json()
        assert data["databases"][0] == {
            "name": "spellbook.db",
            "status": "error",
            "size_bytes": 0,
            "tables": [],
        }

        mock_paths.assert_call(args=(), kwargs={})
        mock_get_factory.assert_call(args=("spellbook.db",), kwargs={})
        bigfoot.log_mock.assert_log(
            "ERROR",
            "Error probing spellbook.db: db locked",
            "spellbook.admin.routes.health",
        )

    def test_probe_missing_file(self, client, monkeypatch):
        """_probe_database returns missing status when file does not exist."""
        monkeypatch.setattr("os.path.exists", lambda path: False)

        from spellbook.admin.routes.health import _probe_database

        import asyncio
        mock_factory = _make_session_factory(_make_mock_session([]))
        result = asyncio.run(
            _probe_database("test.db", "/tmp/no_such_file.db", mock_factory)
        )
        assert result == {
            "name": "test.db",
            "status": "missing",
            "size_bytes": 0,
            "tables": [],
        }

    def test_probe_exception_returns_error(self, client, monkeypatch):
        """_probe_database returns error status when query raises."""
        error_session = _make_mock_session([Exception("db locked")])

        monkeypatch.setattr("os.path.exists", lambda path: True)
        monkeypatch.setattr("os.path.getsize", lambda path: 999)

        from spellbook.admin.routes.health import _probe_database

        import asyncio
        result = asyncio.run(
            _probe_database(
                "broken.db",
                "/tmp/broken.db",
                _make_session_factory(error_session),
            )
        )
        assert result == {
            "name": "broken.db",
            "status": "error",
            "size_bytes": 0,
            "tables": [],
        }

    def test_probe_table_count_error_returns_negative_one(self, client, monkeypatch):
        """When COUNT(*) fails for a table, row_count is -1."""
        session = _make_mock_session([
            [{"name": "broken_table"}],  # table list
            Exception("table corrupted"),  # count fails
            # no timestamp queries attempted after count fails
        ])

        monkeypatch.setattr("os.path.exists", lambda path: True)
        monkeypatch.setattr("os.path.getsize", lambda path: 500)

        from spellbook.admin.routes.health import _probe_database

        import asyncio
        result = asyncio.run(
            _probe_database(
                "test.db",
                "/tmp/test.db",
                _make_session_factory(session),
            )
        )
        assert result["tables"][0]["row_count"] == -1

    def test_probe_no_recent_activity_returns_idle(self, client, monkeypatch):
        """When no table has activity within 24h, status is idle."""
        session = _make_mock_session([
            [{"name": "old_table"}],  # table list
            [{"cnt": 10}],  # count
            [{"latest": "2020-01-01T00:00:00"}],  # very old activity
        ])

        monkeypatch.setattr("os.path.exists", lambda path: True)
        monkeypatch.setattr("os.path.getsize", lambda path: 1000)

        from spellbook.admin.routes.health import _probe_database

        import asyncio
        result = asyncio.run(
            _probe_database(
                "test.db",
                "/tmp/test.db",
                _make_session_factory(session),
            )
        )
        assert result["status"] == "idle"
        assert result["tables"][0]["row_count"] == 10
        assert result["tables"][0]["last_activity"] == "2020-01-01T00:00:00"

    def test_probe_no_timestamp_columns(self, client, monkeypatch):
        """When no timestamp column exists, last_activity is None."""
        # Session returns table list, count, then errors for all 4 timestamp columns
        session = _make_mock_session([
            [{"name": "data_table"}],  # table list
            [{"cnt": 42}],  # count
            Exception("no such column: created_at"),
            Exception("no such column: updated_at"),
            Exception("no such column: timestamp"),
            Exception("no such column: last_activity"),
        ])

        monkeypatch.setattr("os.path.exists", lambda path: True)
        monkeypatch.setattr("os.path.getsize", lambda path: 2000)

        from spellbook.admin.routes.health import _probe_database

        import asyncio
        result = asyncio.run(
            _probe_database(
                "test.db",
                "/tmp/test.db",
                _make_session_factory(session),
            )
        )
        assert result["tables"][0]["row_count"] == 42
        assert result["tables"][0]["last_activity"] is None
