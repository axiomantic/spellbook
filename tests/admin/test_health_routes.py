"""Tests for subsystem health matrix API routes."""

from unittest.mock import AsyncMock, patch

import pytest


class TestHealthMatrix:
    def test_returns_all_databases(self, client):
        with patch(
            "spellbook.admin.routes.health.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock_spellbook, patch(
            "spellbook.admin.routes.health.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock_fractal, patch(
            "spellbook.admin.routes.health.query_forged_db",
            new_callable=AsyncMock,
        ) as mock_forged, patch(
            "spellbook.admin.routes.health.query_coordination_db",
            new_callable=AsyncMock,
        ) as mock_coord, patch(
            "spellbook.admin.routes.health._get_db_paths",
        ) as mock_paths:
            mock_paths.return_value = {
                "spellbook.db": "/tmp/spellbook.db",
                "fractal.db": "/tmp/fractal.db",
                "forged.db": "/tmp/forged.db",
                "coordination.db": "/tmp/coordination.db",
            }

            # spellbook.db: table list, then count+ts for each table
            mock_spellbook.side_effect = [
                [{"name": "memories"}, {"name": "security_events"}],  # table list
                [{"cnt": 100}],  # memories count
                [{"latest": "2026-03-15T10:00:00"}],  # memories last activity
                [{"cnt": 5000}],  # security_events count
                [{"latest": "2026-03-15T10:30:00"}],  # security_events last activity
            ]
            mock_fractal.side_effect = [
                [{"name": "graphs"}, {"name": "nodes"}],
                [{"cnt": 3}],
                [{"latest": "2026-03-15T09:00:00"}],
                [{"cnt": 50}],
                [{"latest": "2026-03-15T09:30:00"}],
            ]
            mock_forged.side_effect = [
                [{"name": "projects"}],
                [{"cnt": 2}],
                [{"latest": "2026-03-14T15:00:00"}],
            ]
            mock_coord.side_effect = [
                [{"name": "swarms"}],
                [{"cnt": 1}],
                [{"latest": None}],
            ]

            with patch("os.path.getsize", return_value=1234567), \
                 patch("os.path.exists", return_value=True):
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
            assert spellbook_db["size_bytes"] == 1234567
            table_names = [t["name"] for t in spellbook_db["tables"]]
            assert table_names == ["memories", "security_events"]
            assert spellbook_db["tables"][0]["row_count"] == 100
            assert spellbook_db["tables"][1]["row_count"] == 5000

    def test_missing_db_returns_missing_status(self, client):
        with patch(
            "spellbook.admin.routes.health._get_db_paths",
        ) as mock_paths, patch(
            "spellbook.admin.routes.health._probe_database",
            new_callable=AsyncMock,
        ) as mock_probe:
            mock_paths.return_value = {
                "spellbook.db": "/tmp/nonexistent.db",
            }
            mock_probe.return_value = {
                "name": "spellbook.db",
                "status": "missing",
                "size_bytes": 0,
                "tables": [],
            }

            response = client.get("/api/health/matrix")
            assert response.status_code == 200
            data = response.json()
            assert data["databases"][0] == {
                "name": "spellbook.db",
                "status": "missing",
                "size_bytes": 0,
                "tables": [],
            }

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/health/matrix")
        assert response.status_code == 401

    def test_db_query_error_returns_error_status(self, client):
        with patch(
            "spellbook.admin.routes.health._get_db_paths",
        ) as mock_paths, patch(
            "spellbook.admin.routes.health._probe_database",
            new_callable=AsyncMock,
        ) as mock_probe:
            mock_paths.return_value = {
                "spellbook.db": "/tmp/spellbook.db",
            }
            mock_probe.return_value = {
                "name": "spellbook.db",
                "status": "error",
                "size_bytes": 0,
                "tables": [],
            }

            response = client.get("/api/health/matrix")
            assert response.status_code == 200
            data = response.json()
            assert data["databases"][0] == {
                "name": "spellbook.db",
                "status": "error",
                "size_bytes": 0,
                "tables": [],
            }

    def test_probe_missing_file(self, client):
        """_probe_database returns missing status when file does not exist."""
        with patch("os.path.exists", return_value=False):
            from spellbook.admin.routes.health import _probe_database

            import asyncio
            result = asyncio.run(
                _probe_database("test.db", "/tmp/no_such_file.db", AsyncMock())
            )
            assert result == {
                "name": "test.db",
                "status": "missing",
                "size_bytes": 0,
                "tables": [],
            }

    def test_probe_exception_returns_error(self, client):
        """_probe_database returns error status when query raises."""
        mock_query = AsyncMock(side_effect=Exception("db locked"))
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=999):
            from spellbook.admin.routes.health import _probe_database

            import asyncio
            result = asyncio.run(
                _probe_database("broken.db", "/tmp/broken.db", mock_query)
            )
            assert result == {
                "name": "broken.db",
                "status": "error",
                "size_bytes": 0,
                "tables": [],
            }
