"""Tests for security_check_intent MCP tool."""
import sqlite3

import bigfoot
import pytest
from dirty_equals import IsInstance


def test_security_check_intent_registered():
    """The security_check_intent tool must be in the MCP tools module."""
    from spellbook.mcp.tools import security
    assert hasattr(security, "security_check_intent")


def test_security_check_intent_in_all():
    from spellbook.mcp.tools.security import __all__
    assert "security_check_intent" in __all__


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setenv("SPELLBOOK_DB_PATH", path)
    from spellbook.core.db import init_db
    init_db(path)
    yield path


def _setup_config_mock(fn, count):
    """Set up a config_get mock that delegates to fn for `count` calls."""
    mock = bigfoot.mock("spellbook.mcp.tools.security:config_get")
    for _ in range(count):
        mock.__call__.required(False).calls(fn)
    return mock


def _setup_db_path_mock(db_path, count):
    """Set up a get_db_path mock returning db_path for `count` calls."""
    mock = bigfoot.mock("spellbook.core.db:get_db_path")
    for _ in range(count):
        mock.__call__.required(False).returns(db_path)
    return mock


@pytest.mark.asyncio
async def test_security_check_intent_disabled_returns_unknown():
    """When sleuth is disabled, returns UNKNOWN."""
    from spellbook.mcp.tools.security import security_check_intent

    config_mock = bigfoot.mock("spellbook.mcp.tools.security:config_get")
    config_mock.returns(None)

    async with bigfoot:
        result = await security_check_intent.__wrapped__(
            content="test content",
            source_tool="test",
        )

    assert result["classification"] == "UNKNOWN"
    assert result["evidence"] == "PromptSleuth is disabled"
    config_mock.assert_call(args=("security.sleuth.enabled",), kwargs={})


@pytest.mark.asyncio
async def test_security_check_intent_cache_hit(db_path):
    """When content is cached, returns cached result."""
    from spellbook.mcp.tools.security import security_check_intent
    from spellbook.security.sleuth import write_sleuth_cache, content_hash

    c_hash = content_hash("cached test content")
    await write_sleuth_cache(c_hash, {"classification": "DATA", "confidence": 0.95}, db_path=db_path)

    def mock_config_get(key):
        if key == "security.sleuth.enabled":
            return True
        return None

    # 1 config_get call: security.sleuth.enabled
    config_mock = _setup_config_mock(mock_config_get, 1)
    # 1 get_db_path call: from get_sleuth_cache
    db_mock = _setup_db_path_mock(db_path, 1)

    # bigfoot 0.19.1 intercepts sqlite3.connect inside sandboxes;
    # mock the db lifecycle for get_sleuth_cache: connect -> execute -> close
    db_session = bigfoot.db_mock.new_session()
    db_session.expect("connect", returns=None)
    db_session.expect("execute", returns=[("DATA", 0.95)])
    db_session.expect("close", returns=None)



@pytest.mark.asyncio
async def test_security_check_intent_api_call_mocked(db_path):
    """Full API path with mocked unified SDK client."""
    from spellbook.mcp.tools.security import security_check_intent

    def mock_config_get(key):
        if key == "security.sleuth.enabled":
            return True
        if key == "security.sleuth.max_content_bytes":
            return 50000
        if key == "security.sleuth.timeout_seconds":
            return 5
        return None

    # config_get calls: enabled, calls_per_session, max_content_bytes, timeout_seconds, model
    config_mock = _setup_config_mock(mock_config_get, 5)
    # get_db_path calls: get_session_budget, write_sleuth_cache, write_intent_check, decrement_budget
    db_mock = _setup_db_path_mock(db_path, 4)

    async def mock_run(self, prompt):
        return '{"classification": "DIRECTIVE", "confidence": 0.92, "evidence": "override detected"}'

    client_obj = type("MockClient", (), {"run": mock_run})()

    mock_client_fn = bigfoot.mock("spellbook.sdk.unified:get_agent_client")
    mock_client_fn.__call__.required(False).returns(client_obj)

    # bigfoot 0.19.1 intercepts sqlite3.connect inside sandboxes;
    # mock db lifecycle for each sqlite function call:

    # 1. get_session_budget: connect -> execute(SELECT, no rows) -> execute(INSERT) -> commit -> close
    db_s1 = bigfoot.db_mock.new_session()
    db_s1.expect("connect", returns=None)
    db_s1.expect("execute", returns=[])
    db_s1.expect("execute", returns=[])
    db_s1.expect("commit", returns=None)
    db_s1.expect("close", returns=None)

    # 2. write_sleuth_cache: connect -> execute(DELETE) -> execute(INSERT) -> commit -> close
    db_s2 = bigfoot.db_mock.new_session()
    db_s2.expect("connect", returns=None)
    db_s2.expect("execute", returns=[])
    db_s2.expect("execute", returns=[])
    db_s2.expect("commit", returns=None)
    db_s2.expect("close", returns=None)

    # 3. write_intent_check: connect -> execute(INSERT) -> commit -> close
    db_s3 = bigfoot.db_mock.new_session()
    db_s3.expect("connect", returns=None)
    db_s3.expect("execute", returns=[])
    db_s3.expect("commit", returns=None)
    db_s3.expect("close", returns=None)

    # 4. decrement_budget: connect -> execute(UPDATE) -> commit -> execute(SELECT) -> close
    db_s4 = bigfoot.db_mock.new_session()
    db_s4.expect("connect", returns=None)
    db_s4.expect("execute", returns=[])
    db_s4.expect("commit", returns=None)
    db_s4.expect("execute", returns=[(49,)])
    db_s4.expect("close", returns=None)

    with bigfoot.in_any_order():
        config_mock.assert_call(args=("security.sleuth.enabled",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.calls_per_session",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.max_content_bytes",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.timeout_seconds",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.model",), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        mock_client_fn.assert_call(
            args=(),
            kwargs={"options": IsInstance(object)},
        )
        # get_session_budget db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="SELECT calls_remaining, reset_at FROM sleuth_budget WHERE session_id = ?",
            parameters=("unknown",),
        )
        bigfoot.db_mock.assert_execute(
            sql="INSERT INTO sleuth_budget (session_id, calls_remaining, reset_at) "
                "VALUES (?, ?, datetime('now', '+24 hours'))",
            parameters=("unknown", 50),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_close()
        # write_sleuth_cache db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="DELETE FROM sleuth_cache WHERE expires_at < datetime('now')",
            parameters=(),
        )
        bigfoot.db_mock.assert_execute(
            sql="INSERT OR REPLACE INTO sleuth_cache "
                "(content_hash, classification, confidence) VALUES (?, ?, ?)",
            parameters=(c_hash, "DIRECTIVE", 0.92),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_close()
        # write_intent_check db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="INSERT INTO intent_checks "
                "(session_id, content_hash, source_tool, classification, "
                "confidence, evidence, latency_ms, cached) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            parameters=(
                "unknown", c_hash, "WebFetch", "DIRECTIVE", 0.92,
                "override detected", 0,
            ),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_close()
        # decrement_budget db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="UPDATE sleuth_budget SET calls_remaining = MAX(0, calls_remaining - 1) "
                "WHERE session_id = ?",
            parameters=("unknown",),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_execute(
            sql="SELECT calls_remaining FROM sleuth_budget WHERE session_id = ?",
            parameters=("unknown",),
        )
        bigfoot.db_mock.assert_close()
    async with bigfoot:
        result = await security_check_intent.__wrapped__(
            content="test timeout content",
            source_tool="test",
            force=True,
        )

    assert result["classification"] == "UNKNOWN"
    assert "TimeoutError" in result["evidence"]
    assert result["cached"] is False

    with bigfoot.in_any_order():
        config_mock.assert_call(args=("security.sleuth.enabled",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.calls_per_session",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.max_content_bytes",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.timeout_seconds",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.model",), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        mock_client_fn.assert_call(
            args=(),
            kwargs={"options": IsInstance(object)},
        )
        # get_session_budget db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="SELECT calls_remaining, reset_at FROM sleuth_budget WHERE session_id = ?",
            parameters=("unknown",),
        )
        bigfoot.db_mock.assert_execute(
            sql="INSERT INTO sleuth_budget (session_id, calls_remaining, reset_at) "
                "VALUES (?, ?, datetime('now', '+24 hours'))",
            parameters=("unknown", 50),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_close()
    async with bigfoot:
        result = await security_check_intent.__wrapped__(
            content="test content",
            source_tool="test",
            session_id="test-budget-session",
        )

    assert result["classification"] == "UNKNOWN"
    assert "Budget exhausted" in result["evidence"]
    assert "regex_only" in result["evidence"]
    assert result["budget_remaining"] == 0

    c_hash = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"



@pytest.mark.asyncio
async def test_security_check_intent_budget_decremented(db_path):
    """Successful API call decrements budget."""
    from spellbook.mcp.tools.security import security_check_intent

    def mock_config_get(key):
        if key == "security.sleuth.enabled":
            return True
        if key == "security.sleuth.calls_per_session":
            return 50
        if key == "security.sleuth.timeout_seconds":
            return 5
        return None

    # config_get calls: enabled, calls_per_session, max_content_bytes, timeout_seconds, model
    config_mock = _setup_config_mock(mock_config_get, 5)
    # get_db_path calls: get_session_budget, write_sleuth_cache, write_intent_check, decrement_budget
    db_mock = _setup_db_path_mock(db_path, 4)

    async def mock_run(self, prompt):
        return '{"classification": "DATA", "confidence": 0.99, "evidence": "pure data"}'

    client_obj = type("MockClient", (), {"run": mock_run})()

    mock_client_fn = bigfoot.mock("spellbook.sdk.unified:get_agent_client")
    mock_client_fn.__call__.required(False).returns(client_obj)

    # bigfoot 0.19.1 intercepts sqlite3.connect inside sandboxes;
    # mock db lifecycle for each sqlite function call:

    # 1. get_session_budget: connect -> execute(SELECT, no rows) -> execute(INSERT) -> commit -> close
    db_s1 = bigfoot.db_mock.new_session()
    db_s1.expect("connect", returns=None)
    db_s1.expect("execute", returns=[])
    db_s1.expect("execute", returns=[])
    db_s1.expect("commit", returns=None)
    db_s1.expect("close", returns=None)

    # 2. write_sleuth_cache: connect -> execute(DELETE) -> execute(INSERT) -> commit -> close
    db_s2 = bigfoot.db_mock.new_session()
    db_s2.expect("connect", returns=None)
    db_s2.expect("execute", returns=[])
    db_s2.expect("execute", returns=[])
    db_s2.expect("commit", returns=None)
    db_s2.expect("close", returns=None)

    # 3. write_intent_check: connect -> execute(INSERT) -> commit -> close
    db_s3 = bigfoot.db_mock.new_session()
    db_s3.expect("connect", returns=None)
    db_s3.expect("execute", returns=[])
    db_s3.expect("commit", returns=None)
    db_s3.expect("close", returns=None)

    # 4. decrement_budget: connect -> execute(UPDATE) -> commit -> execute(SELECT) -> close
    db_s4 = bigfoot.db_mock.new_session()
    db_s4.expect("connect", returns=None)
    db_s4.expect("execute", returns=[])
    db_s4.expect("commit", returns=None)
    db_s4.expect("execute", returns=[(49,)])
    db_s4.expect("close", returns=None)

    with bigfoot.in_any_order():
        config_mock.assert_call(args=("security.sleuth.enabled",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.calls_per_session",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.max_content_bytes",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.timeout_seconds",), kwargs={})
        config_mock.assert_call(args=("security.sleuth.model",), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        db_mock.assert_call(args=(), kwargs={})
        mock_client_fn.assert_call(
            args=(),
            kwargs={"options": IsInstance(object)},
        )
        # get_session_budget db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="SELECT calls_remaining, reset_at FROM sleuth_budget WHERE session_id = ?",
            parameters=("budget-test-session",),
        )
        bigfoot.db_mock.assert_execute(
            sql="INSERT INTO sleuth_budget (session_id, calls_remaining, reset_at) "
                "VALUES (?, ?, datetime('now', '+24 hours'))",
            parameters=("budget-test-session", 50),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_close()
        # write_sleuth_cache db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="DELETE FROM sleuth_cache WHERE expires_at < datetime('now')",
            parameters=(),
        )
        bigfoot.db_mock.assert_execute(
            sql="INSERT OR REPLACE INTO sleuth_cache "
                "(content_hash, classification, confidence) VALUES (?, ?, ?)",
            parameters=(c_hash, "DATA", 0.99),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_close()
        # write_intent_check db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="INSERT INTO intent_checks "
                "(session_id, content_hash, source_tool, classification, "
                "confidence, evidence, latency_ms, cached) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            parameters=(
                "budget-test-session", c_hash, "test", "DATA", 0.99,
                "pure data", 0,
            ),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_close()
        # decrement_budget db lifecycle
        bigfoot.db_mock.assert_connect(database=db_path)
        bigfoot.db_mock.assert_execute(
            sql="UPDATE sleuth_budget SET calls_remaining = MAX(0, calls_remaining - 1) "
                "WHERE session_id = ?",
            parameters=("budget-test-session",),
        )
        bigfoot.db_mock.assert_commit()
        bigfoot.db_mock.assert_execute(
            sql="SELECT calls_remaining FROM sleuth_budget WHERE session_id = ?",
            parameters=("budget-test-session",),
        )
        bigfoot.db_mock.assert_close()


def test_security_sleuth_reset_budget_registered():
    """The security_sleuth_reset_budget tool must be in the module."""
    from spellbook.mcp.tools import security
    assert hasattr(security, "security_sleuth_reset_budget")


def test_security_sleuth_reset_budget_in_all():
    from spellbook.mcp.tools.security import __all__
    assert "security_sleuth_reset_budget" in __all__
