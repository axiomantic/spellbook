"""Tests for security event log API routes (SQLAlchemy ORM)."""

from types import SimpleNamespace

import pytest


class _ScalarsResult:
    """Stub for SQLAlchemy result.scalars() chain."""

    def __init__(self, items):
        self._items = items

    def first(self):
        if isinstance(self._items, list):
            return self._items[0] if self._items else None
        return self._items

    def all(self):
        if isinstance(self._items, list):
            return self._items
        return [self._items] if self._items is not None else []


class _ExecuteResult:
    """Stub for SQLAlchemy session.execute() result."""

    def __init__(self, items=None, scalar_one_value=None, all_value=None):
        self._items = items
        self._scalar_one_value = scalar_one_value
        self._all_value = all_value

    def scalars(self):
        return _ScalarsResult(self._items)

    def scalar_one(self):
        return self._scalar_one_value

    def all(self):
        return self._all_value if self._all_value is not None else []


class _MockAsyncSession:
    """Stub async session that returns pre-configured results from execute()."""

    def __init__(self, results):
        self._results = list(results)
        self._call_count = 0

    async def execute(self, *args, **kwargs):
        idx = self._call_count
        self._call_count += 1
        if idx < len(self._results):
            return self._results[idx]
        raise IndexError(f"MockAsyncSession: no result for call #{idx}")


def _mock_session_with_events(events, total):
    """Create a mock session that simulates SQLAlchemy ORM queries.

    The list_security_events handler executes:
      1. A count query (select func.count())
      2. A data query (select SecurityEvent with filters, order, limit, offset)
    Both go through session.execute(), which returns a result proxy.
    """
    count_result = _ExecuteResult(scalar_one_value=total)
    data_result = _ExecuteResult(items=events)
    return _MockAsyncSession([count_result, data_result])


def _make_mock_event(**overrides):
    """Create a stub SecurityEvent ORM object with to_dict()."""
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
    obj = SimpleNamespace(**defaults)
    obj.to_dict = lambda: dict(defaults)
    return obj


def _override_spellbook_db(client, mock_session):
    """Override the spellbook_db FastAPI dependency to use a mock session."""
    from spellbook.db import spellbook_db

    client.app.dependency_overrides[spellbook_db] = lambda: mock_session
    return spellbook_db


def _cleanup_overrides(client, dep):
    """Remove dependency override after test."""
    client.app.dependency_overrides.pop(dep, None)


class TestSecurityEvents:
    def test_list_events_returns_paginated(self, client):
        mock_event = _make_mock_event()
        mock_session = _mock_session_with_events([mock_event], total=1)

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_list_events_filters_by_severity(self, client):
        mock_session = _mock_session_with_events([], total=0)

        dep = _override_spellbook_db(client, mock_session)
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
            assert mock_session._call_count == 2
        finally:
            _cleanup_overrides(client, dep)

    def test_list_events_filters_by_event_type(self, client):
        mock_session = _mock_session_with_events([], total=0)

        dep = _override_spellbook_db(client, mock_session)
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
            assert mock_session._call_count == 2
        finally:
            _cleanup_overrides(client, dep)

    def test_list_events_filters_by_date_range(self, client):
        mock_session = _mock_session_with_events([], total=0)

        dep = _override_spellbook_db(client, mock_session)
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
            assert mock_session._call_count == 2
        finally:
            _cleanup_overrides(client, dep)

    def test_list_events_pagination(self, client):
        mock_session = _mock_session_with_events([], total=75)

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_list_events_sorting(self, client):
        """Verify sort_by and sort_order parameters are accepted."""
        mock_session = _mock_session_with_events([], total=0)

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_list_events_sorting_invalid_column_rejected(self, client):
        """Verify invalid sort_by values are rejected (not in whitelist)."""
        mock_session = _mock_session_with_events([], total=0)

        dep = _override_spellbook_db(client, mock_session)
        try:
            response = client.get(
                "/api/security/events?sort_by=id&sort_order=asc"
            )
            assert response.status_code == 422
        finally:
            _cleanup_overrides(client, dep)

    def test_list_events_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/events")
        assert response.status_code == 401

    def test_list_events_empty(self, client):
        mock_session = _mock_session_with_events([], total=0)

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)


class TestSecurityEventDetail:
    def test_event_detail_returns_event(self, client):
        event_data = {
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
        mock_event = SimpleNamespace(**event_data)
        mock_event.to_dict = lambda: dict(event_data)

        result = _ExecuteResult(items=mock_event)
        mock_session = _MockAsyncSession([result])

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_event_detail_404_not_found(self, client):
        result = _ExecuteResult(items=None)
        mock_session = _MockAsyncSession([result])

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_event_detail_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/events/1")
        assert response.status_code == 401


class TestSecuritySummary:
    def test_summary_returns_counts(self, client):
        # The ORM query returns rows of (severity, count) tuples
        result = _ExecuteResult(
            all_value=[("warning", 3), ("info", 10), ("critical", 1)]
        )
        mock_session = _MockAsyncSession([result])

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_summary_empty_db(self, client):
        result = _ExecuteResult(all_value=[])
        mock_session = _MockAsyncSession([result])

        dep = _override_spellbook_db(client, mock_session)
        try:
            response = client.get("/api/security/summary")
            assert response.status_code == 200
            data = response.json()
            assert data == {"by_severity": {}}
        finally:
            _cleanup_overrides(client, dep)

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
        # 1. Events by severity (24h) - returns (severity, cnt) tuples
        sev_result = _ExecuteResult(all_value=severity_rows)

        # 2. Top event types - returns (event_type, cnt) tuples
        top_result = _ExecuteResult(all_value=top_types_rows)

        # 3. Active canaries count - returns scalar
        canary_result = _ExecuteResult(scalar_one_value=canary_count)

        # 4. Trust registry size - returns scalar
        trust_result = _ExecuteResult(scalar_one_value=trust_count)

        # 5. Security mode - returns a model or None
        if mode_value is not None:
            mode_obj = SimpleNamespace(mode=mode_value)
            mode_result = _ExecuteResult(items=mode_obj)
        else:
            mode_result = _ExecuteResult(items=None)

        return _MockAsyncSession(
            [sev_result, top_result, canary_result, trust_result, mode_result]
        )

    def test_dashboard_returns_full_aggregation(self, client):
        mock_session = self._build_dashboard_mock_session(
            severity_rows=[("warning", 3), ("info", 10)],
            top_types_rows=[("tool_blocked", 5)],
            canary_count=2,
            trust_count=15,
            mode_value="standard",
        )

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_dashboard_missing_mode_defaults_to_standard(self, client):
        mock_session = self._build_dashboard_mock_session(
            severity_rows=[],
            top_types_rows=[],
            canary_count=0,
            trust_count=0,
            mode_value=None,
        )

        dep = _override_spellbook_db(client, mock_session)
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
            _cleanup_overrides(client, dep)

    def test_dashboard_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/dashboard")
        assert response.status_code == 401
