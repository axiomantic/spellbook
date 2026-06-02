import pytest
import roundup


def test_within_lookback_hours_inclusive():
    now = "2026-05-29T00:00:00Z"
    assert roundup.within_lookback("2026-05-28T00:00:00Z", now, 72, None) is True
    assert roundup.within_lookback("2026-05-25T00:00:00Z", now, 72, None) is False


def test_boundary_inclusive():
    now = "2026-05-29T00:00:00Z"
    # exactly 72h ago
    assert roundup.within_lookback("2026-05-26T00:00:00Z", now, 72, None) is True


def test_since_iso():
    now = "2026-05-29T00:00:00Z"
    assert roundup.within_lookback("2026-05-20T00:00:00Z", now, None, "2026-05-19T00:00:00Z") is True
    assert roundup.within_lookback("2026-05-18T00:00:00Z", now, None, "2026-05-19T00:00:00Z") is False


def test_mutually_exclusive_raises():
    with pytest.raises(Exception):
        roundup.within_lookback("2026-05-28T00:00:00Z", "2026-05-29T00:00:00Z", 72, "2026-05-01T00:00:00Z")
