"""Verify SQLAlchemy models for injection defense tables."""
import pytest


def test_intent_check_model_exists():
    from spellbook.db.spellbook_models import IntentCheck
    assert IntentCheck.__tablename__ == "intent_checks"


def test_intent_check_has_required_columns():
    from spellbook.db.spellbook_models import IntentCheck
    mapper = IntentCheck.__mapper__
    col_names = {c.key for c in mapper.column_attrs}
    required = {"id", "session_id", "content_hash", "source_tool",
                "classification", "confidence", "evidence",
                "checked_at", "latency_ms", "cached"}
    missing = required - col_names
    assert not missing, f"Missing columns: {missing}"


def test_session_content_accumulator_model_exists():
    from spellbook.db.spellbook_models import SessionContentAccumulator
    assert SessionContentAccumulator.__tablename__ == "session_content_accumulator"


def test_sleuth_budget_model_exists():
    from spellbook.db.spellbook_models import SleuthBudget
    assert SleuthBudget.__tablename__ == "sleuth_budget"


def test_sleuth_cache_model_exists():
    from spellbook.db.spellbook_models import SleuthCache
    assert SleuthCache.__tablename__ == "sleuth_cache"


def test_trust_registry_has_signature_columns():
    from spellbook.db.spellbook_models import TrustRegistry
    mapper = TrustRegistry.__mapper__
    col_names = {c.key for c in mapper.column_attrs}
    required = {"signature", "signing_key_id", "analysis_status", "analysis_at"}
    missing = required - col_names
    assert not missing, f"Missing signature columns: {missing}"


def test_intent_check_to_dict():
    from spellbook.db.spellbook_models import IntentCheck
    obj = IntentCheck(
        session_id="sess-1", content_hash="abc", source_tool="WebFetch",
        classification="DATA", confidence=0.95, evidence="benign",
        checked_at="2026-01-01 00:00:00", latency_ms=50, cached=0,
    )
    d = obj.to_dict()
    assert d["classification"] == "DATA"
    assert d["confidence"] == 0.95


def test_trust_registry_to_dict_includes_signature():
    from spellbook.db.spellbook_models import TrustRegistry
    obj = TrustRegistry(
        content_hash="abc", source="test", trust_level="signed",
        signature="base64sig", signing_key_id="key-fp",
        analysis_status="passed", analysis_at="2026-01-01",
    )
    d = obj.to_dict()
    assert d["signature"] == "base64sig"
    assert d["signing_key_id"] == "key-fp"
    assert d["analysis_status"] == "passed"
