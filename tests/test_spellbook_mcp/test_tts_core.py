"""Tests for spellbook_mcp/tts.py - Core TTS module.

Tests the lazy-loaded Kokoro TTS integration in isolation.
All kokoro/soundfile/sounddevice imports are mocked.
"""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


@pytest.fixture(autouse=True)
def reset_tts_state():
    """Reset module-level TTS state between tests."""
    import spellbook_mcp.tts as tts_mod
    tts_mod._kokoro_available = None
    tts_mod._kokoro_pipeline = None
    tts_mod._import_error = None
    yield
    tts_mod._kokoro_available = None
    tts_mod._kokoro_pipeline = None
    tts_mod._import_error = None


class TestCheckAvailability:
    """_check_availability() probes for kokoro and soundfile imports."""

    def test_returns_true_when_kokoro_importable(self):
        import spellbook_mcp.tts as tts_mod
        mock_kokoro = MagicMock()
        mock_soundfile = MagicMock()
        with patch.dict("sys.modules", {"kokoro": mock_kokoro, "soundfile": mock_soundfile}):
            result = tts_mod._check_availability()
        assert result is True
        assert tts_mod._kokoro_available is True
        assert tts_mod._import_error is None

    def test_returns_false_when_kokoro_missing(self):
        import spellbook_mcp.tts as tts_mod
        with patch.dict("sys.modules", {"kokoro": None}):
            # Force ImportError by removing from sys.modules and patching __import__
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
            def mock_import(name, *args, **kwargs):
                if name == "kokoro":
                    raise ImportError("No module named 'kokoro'")
                return original_import(name, *args, **kwargs)
            with patch("builtins.__import__", side_effect=mock_import):
                result = tts_mod._check_availability()
        assert result is False
        assert tts_mod._kokoro_available is False
        assert "kokoro" in tts_mod._import_error

    def test_caches_result_on_second_call(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = True  # Pre-set cached value
        # Should return cached value without attempting imports
        result = tts_mod._check_availability()
        assert result is True


class TestLoadModel:
    """_load_model() thread-safe model loading with double-checked locking."""

    def test_loads_model_successfully(self):
        import spellbook_mcp.tts as tts_mod
        mock_pipeline = MagicMock()
        mock_kpipeline_cls = MagicMock(return_value=mock_pipeline)
        mock_kokoro = MagicMock()
        mock_kokoro.KPipeline = mock_kpipeline_cls
        with patch.dict("sys.modules", {"kokoro": mock_kokoro}):
            tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is mock_pipeline
        mock_kpipeline_cls.assert_called_once_with(lang_code="a")

    def test_failure_not_cached_allows_retry(self):
        import spellbook_mcp.tts as tts_mod
        mock_kokoro = MagicMock()
        mock_kokoro.KPipeline.side_effect = RuntimeError("CUDA OOM")
        with patch.dict("sys.modules", {"kokoro": mock_kokoro}):
            tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is None
        assert "CUDA OOM" in tts_mod._import_error

        # Second call should retry (not cached on failure)
        mock_pipeline = MagicMock()
        mock_kokoro.KPipeline.side_effect = None
        mock_kokoro.KPipeline.return_value = mock_pipeline
        with patch.dict("sys.modules", {"kokoro": mock_kokoro}):
            tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is mock_pipeline

    def test_concurrent_loads_only_create_one_pipeline(self):
        import spellbook_mcp.tts as tts_mod
        call_count = 0
        mock_pipeline = MagicMock()

        def slow_init(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)  # Simulate slow model load
            return mock_pipeline

        mock_kokoro = MagicMock()
        mock_kokoro.KPipeline.side_effect = slow_init

        with patch.dict("sys.modules", {"kokoro": mock_kokoro}):
            threads = [threading.Thread(target=tts_mod._load_model) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        assert call_count == 1
        assert tts_mod._kokoro_pipeline is mock_pipeline

    def test_skips_if_already_loaded(self):
        import spellbook_mcp.tts as tts_mod
        existing = MagicMock()
        tts_mod._kokoro_pipeline = existing
        tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is existing  # Unchanged
