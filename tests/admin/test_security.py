"""Tests for security event log API routes (SQLAlchemy ORM)."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSecurityEvents:
    def _mock_session_with_events(self, events, total):
        """Create a mock session that simulates SQLAlchemy ORM queries.

        The list_security_events handler executes:
          1. A count query (select func.count())
          2. A data query (select SecurityEvent with filters, order, limit, offset)
        Both go through session.execute(), which returns a result proxy.
        """
        mock_session = AsyncMock()

        # Count query result
        count_result = MagicMock()
        count_result.scalar_one.return_value = total

        # Data query result
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = events

        mock_session.execute = AsyncMock(side_effect=[count_result, data_result])
        return mock_session

    def _make_mock_event(self, **overrides):
        """Create a mock SecurityEvent ORM object with to_dict()."""
        defaults = {
            "id": 1,
            "event_type": "tool_blocked",
            "severity": "warning",
            "source": "test",
            "detail": "blocked tool",
            "session_id": None,
            "tool_name": "rm",
            "action_taken": "blocked",
            "created_at": "2026-03-14T10:00:00Z",
        }
        defaults.update(overrides)
        event = MagicMock()
        event.to_dict.return_value = defaults
        return event

    def test_list_events_returns_paginated(self, client):
        mock_event = self._make_mock_event()
        mock_session = self._mock_session_with_events([mock_event], total=1)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/events")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [
                    {
                        "id": 1,
                        "event_type": "tool_blocked",
                        "severity": "warning",
                        "source": "test",
                        "detail": "blocked tool",
                        "session_id": None,
                        "tool_name": "rm",
                        "action_taken": "blocked",
                        "created_at": "2026-03-14T10:00:00Z",
                    }
                ],
                "total": 1,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_list_events_filters_by_severity(self, client):
        mock_session = self._mock_session_with_events([], total=0)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/events?severity=critical")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
            # Verify that session.execute was called (count + data)
            assert mock_session.execute.call_count == 2
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_list_events_filters_by_event_type(self, client):
        mock_session = self._mock_session_with_events([], total=0)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/events?event_type=tool_blocked")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
            assert mock_session.execute.call_count == 2
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_list_events_filters_by_date_range(self, client):
        mock_session = self._mock_session_with_events([], total=0)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get(
                "/api/security/events?since=2026-03-01&until=2026-03-14"
            )
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
            assert mock_session.execute.call_count == 2
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_list_events_pagination(self, client):
        mock_session = self._mock_session_with_events([], total=75)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/events?page=2&per_page=25")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 75,
                "page": 2,
                "per_page": 25,
                "pages": 3,
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_list_events_sorting(self, client):
        """Verify sort_by and sort_order parameters are accepted."""
        mock_session = self._mock_session_with_events([], total=0)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get(
                "/api/security/events?sort_by=severity&sort_order=asc"
            )
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_list_events_sorting_invalid_column_rejected(self, client):
        """Verify invalid sort_by values are rejected (not in whitelist)."""
        mock_session = self._mock_session_with_events([], total=0)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get(
                "/api/security/events?sort_by=id&sort_order=asc"
            )
            assert response.status_code == 422
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_list_events_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/events")
        assert response.status_code == 401

    def test_list_events_empty(self, client):
        mock_session = self._mock_session_with_events([], total=0)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/events")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)


class TestSecurityEventDetail:
    def test_event_detail_returns_event(self, client):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_event = MagicMock()
        mock_event.to_dict.return_value = {
            "id": 42,
            "event_type": "tool_blocked",
            "severity": "warning",
            "source": "test-agent",
            "detail": "Blocked rm -rf /",
            "session_id": "sess-123",
            "tool_name": "rm",
            "action_taken": "blocked",
            "created_at": "2026-03-14T10:00:00Z",
        }
        mock_result.scalars.return_value.first.return_value = mock_event
        mock_session.execute = AsyncMock(return_value=mock_result)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/events/42")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "id": 42,
                "event_type": "tool_blocked",
                "severity": "warning",
                "source": "test-agent",
                "detail": "Blocked rm -rf /",
                "session_id": "sess-123",
                "tool_name": "rm",
                "action_taken": "blocked",
                "created_at": "2026-03-14T10:00:00Z",
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_event_detail_404_not_found(self, client):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/events/999")
            assert response.status_code == 404
            data = response.json()
            assert data == {
                "error": {
                    "code": "EVENT_NOT_FOUND",
                    "message": "Security event not found",
                }
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_event_detail_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/events/1")
        assert response.status_code == 401


class TestSecuritySummary:
    def test_summary_returns_counts(self, client):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # The ORM query returns rows of (severity, count) tuples
        mock_result.all.return_value = [
            ("warning", 3),
            ("info", 10),
            ("critical", 1),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/summary")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "by_severity": {
                    "warning": 3,
                    "info": 10,
                    "critical": 1,
                }
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_summary_empty_db(self, client):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/summary")
            assert response.status_code == 200
            data = response.json()
            assert data == {"by_severity": {}}
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_summary_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/summary")
        assert response.status_code == 401


class TestSecurityDashboard:
    def _build_dashboard_mock_session(
        self,
        severity_rows,
        top_types_rows,
        canary_count,
        trust_count,
        mode_value,
    ):
        """Build a mock session for the dashboard endpoint.

        The dashboard executes 5 queries via asyncio.gather, each calling
        session.execute(). We mock execute to return the right result for
        each call in sequence.
        """
        mock_session = AsyncMock()

        # 1. Events by severity (24h) - returns (severity, cnt) tuples
        sev_result = MagicMock()
        sev_result.all.return_value = severity_rows

        # 2. Top event types - returns (event_type, cnt) tuples
        top_result = MagicMock()
        top_result.all.return_value = top_types_rows

        # 3. Active canaries count - returns scalar
        canary_result = MagicMock()
        canary_result.scalar_one.return_value = canary_count

        # 4. Trust registry size - returns scalar
        trust_result = MagicMock()
        trust_result.scalar_one.return_value = trust_count

        # 5. Security mode - returns a model or None
        mode_result = MagicMock()
        if mode_value is not None:
            mode_obj = MagicMock()
            mode_obj.mode = mode_value
            mode_result.scalars.return_value.first.return_value = mode_obj
        else:
            mode_result.scalars.return_value.first.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[sev_result, top_result, canary_result, trust_result, mode_result]
        )
        return mock_session

    def test_dashboard_returns_full_aggregation(self, client):
        mock_session = self._build_dashboard_mock_session(
            severity_rows=[("warning", 3), ("info", 10)],
            top_types_rows=[("tool_blocked", 5)],
            canary_count=2,
            trust_count=15,
            mode_value="standard",
        )

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/dashboard")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "mode": "standard",
                "events_24h": {"warning": 3, "info": 10},
                "top_event_types": [
                    {"event_type": "tool_blocked", "cnt": 5},
                ],
                "active_canaries": 2,
                "trust_registry_size": 15,
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_dashboard_missing_mode_defaults_to_standard(self, client):
        mock_session = self._build_dashboard_mock_session(
            severity_rows=[],
            top_types_rows=[],
            canary_count=0,
            trust_count=0,
            mode_value=None,
        )

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            response = client.get("/api/security/dashboard")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "mode": "standard",
                "events_24h": {},
                "top_event_types": [],
                "active_canaries": 0,
                "trust_registry_size": 0,
            }
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)

    def test_dashboard_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/dashboard")
        assert response.status_code == 401
