"""Tests for spellbook_mcp/tts.py - Core TTS module.

Tests the lazy-loaded Kokoro TTS integration in isolation.
All kokoro/soundfile/sounddevice imports are mocked.
"""

import os
import tempfile
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
        # Patch __import__ to raise, proving cache bypasses imports entirely
        original_import = __import__
        def fail_import(name, *args, **kwargs):
            if name in ("kokoro", "soundfile"):
                raise ImportError(f"Should not be importing {name} when cached")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=fail_import):
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


class TestGenerateAudio:
    """_generate_audio() runs KPipeline and writes WAV to temp file."""

    def test_generates_wav_file(self, tmp_path):
        import spellbook_mcp.tts as tts_mod

        # Set up mock pipeline
        mock_pipeline = MagicMock()
        mock_generator = MagicMock()
        # KPipeline returns a generator of (graphemes, phonemes, audio_tensor) tuples
        mock_audio = MagicMock()
        mock_audio.numpy.return_value = [0.1, 0.2, 0.3]
        mock_generator.__iter__ = MagicMock(return_value=iter([
            ("hello", "h@loU", mock_audio),
        ]))
        mock_pipeline.return_value = mock_generator
        tts_mod._kokoro_pipeline = mock_pipeline

        mock_sf = MagicMock()
        mock_np = MagicMock()
        mock_np.concatenate.return_value = [0.1, 0.2, 0.3]
        with patch.dict("sys.modules", {"soundfile": mock_sf, "numpy": mock_np}):
            with patch("spellbook_mcp.tts.tempfile") as mock_tempfile:
                mock_tempfile.gettempdir.return_value = str(tmp_path)
                with patch("spellbook_mcp.tts.uuid") as mock_uuid:
                    mock_uuid.uuid4.return_value = "fixed-uuid"
                    wav_path = tts_mod._generate_audio("hello", "af_heart")

        expected = os.path.join(str(tmp_path), f"{tts_mod._WAV_PREFIX}fixed-uuid.wav")
        assert wav_path == expected
        mock_sf.write.assert_called_once_with(
            wav_path, mock_np.concatenate.return_value, 24000
        )

    def test_raises_when_pipeline_not_loaded(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_pipeline = None
        with pytest.raises(RuntimeError, match="Kokoro pipeline not loaded"):
            tts_mod._generate_audio("hello", "af_heart")

    def test_raises_on_empty_audio_chunks(self):
        import spellbook_mcp.tts as tts_mod

        mock_pipeline = MagicMock()
        mock_generator = MagicMock()
        mock_generator.__iter__ = MagicMock(return_value=iter([]))
        mock_pipeline.return_value = mock_generator
        tts_mod._kokoro_pipeline = mock_pipeline

        mock_sf = MagicMock()
        with patch.dict("sys.modules", {"soundfile": mock_sf}):
            with pytest.raises(ValueError, match="No audio generated"):
                tts_mod._generate_audio("hello", "af_heart")

    def test_raises_on_pipeline_error(self):
        import spellbook_mcp.tts as tts_mod

        mock_pipeline = MagicMock()
        mock_pipeline.side_effect = ValueError("Invalid voice 'xyz'")
        tts_mod._kokoro_pipeline = mock_pipeline

        mock_sf = MagicMock()
        with patch.dict("sys.modules", {"soundfile": mock_sf}):
            with pytest.raises(ValueError, match="Invalid voice"):
                tts_mod._generate_audio("hello", "xyz")


class TestPlayAudio:
    """_play_audio() uses sounddevice to play WAV and cleans up the file."""

    def test_plays_and_deletes_wav(self, tmp_path):
        import spellbook_mcp.tts as tts_mod

        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav data")

        mock_data = MagicMock()  # MagicMock supports * operator
        mock_sf = MagicMock()
        mock_sf.read.return_value = (mock_data, 24000)
        mock_sd = MagicMock()

        with patch.dict("sys.modules", {"soundfile": mock_sf, "sounddevice": mock_sd}):
            tts_mod._play_audio(str(wav_file), 0.5)

        mock_sd.play.assert_called_once_with(mock_data * 0.5, 24000)
        mock_sd.wait.assert_called_once()
        assert not wav_file.exists()  # File deleted after playback

    def test_preserves_file_on_playback_error(self, tmp_path):
        import spellbook_mcp.tts as tts_mod

        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav data")

        mock_data = MagicMock()
        mock_sf = MagicMock()
        mock_sf.read.return_value = (mock_data, 24000)
        mock_sd = MagicMock()
        mock_sd.play.side_effect = RuntimeError("No output device")

        with patch.dict("sys.modules", {"soundfile": mock_sf, "sounddevice": mock_sd}):
            with pytest.raises(RuntimeError, match="No output device"):
                tts_mod._play_audio(str(wav_file), 0.5)

        assert wav_file.exists()  # File preserved for manual playback

    def test_sounddevice_import_failure_raises(self):
        import spellbook_mcp.tts as tts_mod

        original_import = __import__
        def mock_import(name, *args, **kwargs):
            if name == "sounddevice":
                raise ImportError("No module named 'sounddevice'")
            return original_import(name, *args, **kwargs)

        mock_sf = MagicMock()
        with patch.dict("sys.modules", {"soundfile": mock_sf}):
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ImportError, match="sounddevice"):
                    tts_mod._play_audio("/fake/path.wav", 0.5)


class TestResolveSetting:
    """_resolve_setting() follows explicit > session > config > default priority."""

    def test_explicit_value_wins(self):
        import spellbook_mcp.tts as tts_mod
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {"voice": "session_voice"}}
            mock_ct.config_get.return_value = "config_voice"
            result = tts_mod._resolve_setting("voice", explicit_value="explicit_voice")
        assert result == "explicit_voice"

    def test_session_override_wins_over_config(self):
        import spellbook_mcp.tts as tts_mod
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {"voice": "session_voice"}}
            mock_ct.config_get.return_value = "config_voice"
            result = tts_mod._resolve_setting("voice")
        assert result == "session_voice"

    def test_config_wins_over_default(self):
        import spellbook_mcp.tts as tts_mod
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {}}
            mock_ct.config_get.return_value = "config_voice"
            result = tts_mod._resolve_setting("voice")
        assert result == "config_voice"

    def test_falls_back_to_default(self):
        import spellbook_mcp.tts as tts_mod
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {}}
            mock_ct.config_get.return_value = None
            result = tts_mod._resolve_setting("voice")
        assert result == "af_heart"

    def test_default_volume_is_0_3(self):
        import spellbook_mcp.tts as tts_mod
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {}}
            mock_ct.config_get.return_value = None
            result = tts_mod._resolve_setting("volume")
        assert result == 0.3

    def test_default_enabled_is_true(self):
        import spellbook_mcp.tts as tts_mod
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {}}
            mock_ct.config_get.return_value = None
            result = tts_mod._resolve_setting("enabled")
        assert result is True


class TestGetStatus:
    """get_status() returns TTS availability and settings without side effects."""

    def test_status_when_available_and_loaded(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = True
        tts_mod._kokoro_pipeline = MagicMock()  # Model loaded
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {}}
            mock_ct.config_get.return_value = None
            status = tts_mod.get_status()
        assert status["available"] is True
        assert status["model_loaded"] is True
        assert status["enabled"] is True
        assert status["voice"] == "af_heart"
        assert status["volume"] == 0.3
        assert status["error"] is None

    def test_status_when_not_available(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = False
        tts_mod._import_error = "Missing dependency: kokoro"
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {}}
            mock_ct.config_get.return_value = None
            status = tts_mod.get_status()
        assert status["available"] is False
        assert status["model_loaded"] is False
        assert "kokoro" in status["error"]

    def test_status_does_not_trigger_model_load(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = True
        tts_mod._kokoro_pipeline = None  # Not loaded
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {}}
            mock_ct.config_get.return_value = None
            status = tts_mod.get_status()
        assert status["model_loaded"] is False
        assert tts_mod._kokoro_pipeline is None  # Still not loaded


class TestEnsureLoaded:
    """ensure_loaded() is the async wrapper around _load_model()."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        import spellbook_mcp.tts as tts_mod
        mock_pipeline = MagicMock()
        mock_kokoro = MagicMock()
        mock_kokoro.KPipeline.return_value = mock_pipeline
        with patch.dict("sys.modules", {"kokoro": mock_kokoro}):
            success, error = await tts_mod.ensure_loaded()
        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self):
        import spellbook_mcp.tts as tts_mod
        mock_kokoro = MagicMock()
        mock_kokoro.KPipeline.side_effect = RuntimeError("OOM")
        with patch.dict("sys.modules", {"kokoro": mock_kokoro}):
            success, error = await tts_mod.ensure_loaded()
        assert success is False
        assert "OOM" in error


class TestSpeak:
    """speak() is the main async entry point for TTS."""

    @pytest.mark.asyncio
    async def test_speak_success(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = True

        with patch.object(tts_mod, "ensure_loaded", return_value=(True, None)):
            with patch.object(tts_mod, "_generate_audio", return_value="/tmp/test.wav") as mock_gen:
                with patch.object(tts_mod, "_play_audio") as mock_play:
                    with patch("spellbook_mcp.tts.config_tools") as mock_ct:
                        mock_ct._get_session_state.return_value = {"tts": {}}
                        mock_ct.config_get.return_value = None
                        result = await tts_mod.speak("hello", voice="af_heart", volume=0.3)

        assert result["ok"] is True
        assert "elapsed" in result
        assert result["wav_path"] == "/tmp/test.wav"
        mock_gen.assert_called_once_with("hello", "af_heart")
        mock_play.assert_called_once_with("/tmp/test.wav", 0.3)

    @pytest.mark.asyncio
    async def test_speak_when_disabled(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = True
        with patch("spellbook_mcp.tts.config_tools") as mock_ct:
            mock_ct._get_session_state.return_value = {"tts": {"enabled": False}}
            mock_ct.config_get.return_value = None
            result = await tts_mod.speak("hello")
        assert "error" in result
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_speak_when_not_available(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = False
        tts_mod._import_error = "Missing dependency: kokoro"
        result = await tts_mod.speak("hello")
        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_speak_clamps_volume(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = True

        with patch.object(tts_mod, "ensure_loaded", return_value=(True, None)):
            with patch.object(tts_mod, "_generate_audio", return_value="/tmp/test.wav"):
                with patch.object(tts_mod, "_play_audio") as mock_play:
                    with patch("spellbook_mcp.tts.config_tools") as mock_ct:
                        mock_ct._get_session_state.return_value = {"tts": {}}
                        mock_ct.config_get.return_value = None
                        result = await tts_mod.speak("hello", volume=1.5)

        assert result["ok"] is True
        assert "warning" in result
        # Volume should have been clamped to 1.0
        mock_play.assert_called_once()
        actual_volume = mock_play.call_args[0][1]
        assert actual_volume == 1.0

    @pytest.mark.asyncio
    async def test_speak_playback_failure_returns_wav_path(self):
        import spellbook_mcp.tts as tts_mod
        tts_mod._kokoro_available = True

        with patch.object(tts_mod, "ensure_loaded", return_value=(True, None)):
            with patch.object(tts_mod, "_generate_audio", return_value="/tmp/test.wav"):
                with patch.object(tts_mod, "_play_audio", side_effect=ImportError("No sounddevice")):
                    with patch("spellbook_mcp.tts.config_tools") as mock_ct:
                        mock_ct._get_session_state.return_value = {"tts": {}}
                        mock_ct.config_get.return_value = None
                        result = await tts_mod.speak("hello")

        assert result["ok"] is True
        assert result["wav_path"] == "/tmp/test.wav"
        assert "Audio playback failed" in result.get("warning", "")
