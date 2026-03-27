"""Tests for spellbook/tts.py - Core TTS module.

Tests the lazy-loaded Kokoro TTS integration in isolation.
All kokoro/soundfile/sounddevice imports are mocked.
"""

import os
import sys
import threading
import time
from types import SimpleNamespace

import bigfoot
import pytest


@pytest.fixture(autouse=True)
def reset_tts_state():
    """Reset module-level TTS state between tests."""
    import spellbook.notifications.tts as tts_mod
    tts_mod._kokoro_available = None
    tts_mod._kokoro_pipeline = None
    tts_mod._import_error = None
    yield
    tts_mod._kokoro_available = None
    tts_mod._kokoro_pipeline = None
    tts_mod._import_error = None


class TestCheckAvailability:
    """_check_availability() probes for kokoro and soundfile imports."""

    def test_returns_true_when_kokoro_importable(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        mock_kokoro = SimpleNamespace()
        mock_soundfile = SimpleNamespace()
        monkeypatch.setitem(sys.modules, "kokoro", mock_kokoro)
        monkeypatch.setitem(sys.modules, "soundfile", mock_soundfile)
        result = tts_mod._check_availability()
        assert result is True
        assert tts_mod._kokoro_available is True
        assert tts_mod._import_error is None

    def test_returns_false_when_kokoro_missing(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        # Setting sys.modules entry to None forces ImportError on import
        monkeypatch.setitem(sys.modules, "kokoro", None)
        result = tts_mod._check_availability()
        assert result is False
        assert tts_mod._kokoro_available is False
        assert "kokoro" in tts_mod._import_error

    def test_caches_result_on_second_call(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        tts_mod._kokoro_available = True  # Pre-set cached value
        # Setting sys.modules to None proves cache bypasses imports entirely
        monkeypatch.setitem(sys.modules, "kokoro", None)
        monkeypatch.setitem(sys.modules, "soundfile", None)
        result = tts_mod._check_availability()
        assert result is True


class TestLoadModel:
    """_load_model() thread-safe model loading with double-checked locking."""

    def test_loads_model_successfully(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        mock_pipeline = SimpleNamespace()
        mock_kokoro = SimpleNamespace(KPipeline=lambda lang_code="a": mock_pipeline)
        monkeypatch.setitem(sys.modules, "kokoro", mock_kokoro)
        tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is mock_pipeline

    def test_failure_not_cached_allows_retry(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        def raise_oom(lang_code="a"):
            raise RuntimeError("CUDA OOM")

        mock_kokoro = SimpleNamespace(KPipeline=raise_oom)
        monkeypatch.setitem(sys.modules, "kokoro", mock_kokoro)
        tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is None
        assert "CUDA OOM" in tts_mod._import_error

        # Second call should retry (not cached on failure)
        mock_pipeline = SimpleNamespace()
        mock_kokoro.KPipeline = lambda lang_code="a": mock_pipeline
        tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is mock_pipeline

    def test_concurrent_loads_only_create_one_pipeline(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        call_count = 0
        mock_pipeline = SimpleNamespace()

        def slow_init(lang_code="a"):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)  # Simulate slow model load
            return mock_pipeline

        mock_kokoro = SimpleNamespace(KPipeline=slow_init)
        monkeypatch.setitem(sys.modules, "kokoro", mock_kokoro)

        threads = [threading.Thread(target=tts_mod._load_model) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert call_count == 1
        assert tts_mod._kokoro_pipeline is mock_pipeline

    def test_skips_if_already_loaded(self):
        import spellbook.notifications.tts as tts_mod
        existing = SimpleNamespace()
        tts_mod._kokoro_pipeline = existing
        tts_mod._load_model()
        assert tts_mod._kokoro_pipeline is existing  # Unchanged


class TestGenerateAudio:
    """_generate_audio() runs KPipeline and writes WAV to temp file."""

    def test_generates_wav_file(self, tmp_path, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        # Set up mock pipeline as a callable that returns an iterable
        mock_audio = SimpleNamespace(numpy=lambda: [0.1, 0.2, 0.3])
        pipeline_results = [("hello", "h@loU", mock_audio)]

        def mock_pipeline_call(text, voice=None):
            return iter(pipeline_results)

        tts_mod._kokoro_pipeline = mock_pipeline_call

        # Mock soundfile and numpy in sys.modules
        sf_writes = []
        mock_sf = SimpleNamespace(write=lambda path, data, rate: sf_writes.append((path, data, rate)))
        mock_np = SimpleNamespace(concatenate=lambda chunks: [0.1, 0.2, 0.3])
        monkeypatch.setitem(sys.modules, "soundfile", mock_sf)
        monkeypatch.setitem(sys.modules, "numpy", mock_np)

        mock_tempfile = bigfoot.mock("spellbook.notifications.tts:tempfile")
        mock_tempfile.gettempdir.returns(str(tmp_path))

        mock_uuid = bigfoot.mock("spellbook.notifications.tts:uuid")
        mock_uuid.uuid4.returns("fixed-uuid")

        with bigfoot:
            wav_path = tts_mod._generate_audio("hello", "af_heart")

        expected = os.path.join(str(tmp_path), f"{tts_mod._WAV_PREFIX}fixed-uuid.wav")
        assert wav_path == expected
        assert len(sf_writes) == 1
        assert sf_writes[0][0] == wav_path
        assert sf_writes[0][1] == [0.1, 0.2, 0.3]
        assert sf_writes[0][2] == 24000
        mock_uuid.uuid4.assert_call(args=(), kwargs={})
        mock_tempfile.gettempdir.assert_call(args=(), kwargs={})

    def test_raises_when_pipeline_not_loaded(self):
        import spellbook.notifications.tts as tts_mod
        tts_mod._kokoro_pipeline = None
        with pytest.raises(RuntimeError, match="Kokoro pipeline not loaded"):
            tts_mod._generate_audio("hello", "af_heart")

    def test_raises_on_empty_audio_chunks(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        def mock_pipeline_call(text, voice=None):
            return iter([])

        tts_mod._kokoro_pipeline = mock_pipeline_call

        mock_sf = SimpleNamespace()
        monkeypatch.setitem(sys.modules, "soundfile", mock_sf)

        with pytest.raises(ValueError, match="No audio generated"):
            tts_mod._generate_audio("hello", "af_heart")

    def test_raises_on_pipeline_error(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        def mock_pipeline_call(text, voice=None):
            raise ValueError("Invalid voice 'xyz'")

        tts_mod._kokoro_pipeline = mock_pipeline_call

        mock_sf = SimpleNamespace()
        monkeypatch.setitem(sys.modules, "soundfile", mock_sf)

        with pytest.raises(ValueError, match="Invalid voice"):
            tts_mod._generate_audio("hello", "xyz")


class TestPlayAudio:
    """_play_audio() uses sounddevice to play WAV and cleans up the file."""

    def test_plays_and_deletes_wav(self, tmp_path, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav data")

        class MockAudioData:
            def __mul__(self, other):
                return f"scaled_{other}"

        mock_data = MockAudioData()
        mock_sf = SimpleNamespace(read=lambda path: (mock_data, 24000))

        play_calls = []
        wait_calls = []
        mock_sd = SimpleNamespace(
            play=lambda data, rate: play_calls.append((data, rate)),
            wait=lambda: wait_calls.append(True),
            _terminate=lambda: None,
            _initialize=lambda: None,
        )
        monkeypatch.setitem(sys.modules, "soundfile", mock_sf)
        monkeypatch.setitem(sys.modules, "sounddevice", mock_sd)

        tts_mod._play_audio(str(wav_file), 0.5)

        assert len(play_calls) == 1
        assert play_calls[0] == ("scaled_0.5", 24000)
        assert len(wait_calls) == 1
        assert not wav_file.exists()  # File deleted after playback

    def test_preserves_file_on_playback_error(self, tmp_path, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav data")

        class MockAudioData:
            def __mul__(self, other):
                return f"scaled_{other}"

        mock_data = MockAudioData()
        mock_sf = SimpleNamespace(read=lambda path: (mock_data, 24000))

        def play_raises(data, rate):
            raise RuntimeError("No output device")

        mock_sd = SimpleNamespace(
            play=play_raises,
            wait=lambda: None,
            _terminate=lambda: None,
            _initialize=lambda: None,
        )
        monkeypatch.setitem(sys.modules, "soundfile", mock_sf)
        monkeypatch.setitem(sys.modules, "sounddevice", mock_sd)

        with pytest.raises(RuntimeError, match="No output device"):
            tts_mod._play_audio(str(wav_file), 0.5)

        assert wav_file.exists()  # File preserved for manual playback

    def test_sounddevice_import_failure_raises(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        mock_sf = SimpleNamespace()
        monkeypatch.setitem(sys.modules, "soundfile", mock_sf)
        # Setting sys.modules entry to None forces ImportError on import
        monkeypatch.setitem(sys.modules, "sounddevice", None)

        with pytest.raises(ImportError, match="sounddevice"):
            tts_mod._play_audio("/fake/path.wav", 0.5)


class TestResolveSetting:
    """_resolve_setting() follows explicit > session > config > default priority."""

    def test_explicit_value_wins(self):
        import spellbook.notifications.tts as tts_mod
        # Explicit value short-circuits before any config lookup
        result = tts_mod._resolve_setting("voice", explicit_value="explicit_voice")
        assert result == "explicit_voice"

    def test_session_override_wins_over_config(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {"voice": "session_voice"}})
        # Session value found, so config_get is never called
        result = tts_mod._resolve_setting("voice")
        assert result == "session_voice"

    def test_config_wins_over_default(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})

        mock_cg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cg.returns("config_voice")

        with bigfoot:
            result = tts_mod._resolve_setting("voice")

        assert result == "config_voice"
        mock_cg.assert_call(args=("tts_voice",), kwargs={})

    def test_falls_back_to_default(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})

        mock_cg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            result = tts_mod._resolve_setting("voice")

        assert result == "af_heart"
        mock_cg.assert_call(args=("tts_voice",), kwargs={})

    def test_default_volume_is_0_3(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})

        mock_cg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            result = tts_mod._resolve_setting("volume")

        assert result == 0.3
        mock_cg.assert_call(args=("tts_volume",), kwargs={})

    def test_default_enabled_is_true(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})

        mock_cg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            result = tts_mod._resolve_setting("enabled")

        assert result is True
        mock_cg.assert_call(args=("tts_enabled",), kwargs={})


class TestGetStatus:
    """get_status() returns TTS availability and settings without side effects."""

    def test_status_when_available_and_loaded(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._kokoro_available = True
        tts_mod._kokoro_pipeline = SimpleNamespace()  # Model loaded

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        status = tts_mod.get_status()

        assert status["available"] is True
        assert status["model_loaded"] is True
        assert status["enabled"] is True
        assert status["voice"] == "af_heart"
        assert status["volume"] == 0.3
        assert status["error"] is None

    def test_status_when_not_available(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._kokoro_available = False
        tts_mod._import_error = "Missing dependency: kokoro"

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        status = tts_mod.get_status()

        assert status["available"] is False
        assert status["model_loaded"] is False
        assert "kokoro" in status["error"]

    def test_status_does_not_trigger_model_load(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._kokoro_available = True
        tts_mod._kokoro_pipeline = None  # Not loaded

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        status = tts_mod.get_status()

        assert status["model_loaded"] is False
        assert tts_mod._kokoro_pipeline is None  # Still not loaded


class TestEnsureLoaded:
    """ensure_loaded() is the async wrapper around _load_model()."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        mock_pipeline = SimpleNamespace()
        mock_kokoro = SimpleNamespace(KPipeline=lambda lang_code="a": mock_pipeline)
        monkeypatch.setitem(sys.modules, "kokoro", mock_kokoro)
        success, error = await tts_mod.ensure_loaded()
        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod

        def raise_oom(lang_code="a"):
            raise RuntimeError("OOM")

        mock_kokoro = SimpleNamespace(KPipeline=raise_oom)
        monkeypatch.setitem(sys.modules, "kokoro", mock_kokoro)
        success, error = await tts_mod.ensure_loaded()
        assert success is False
        assert "OOM" in error


class TestSpeak:
    """speak() is the main async entry point for TTS."""

    @pytest.mark.asyncio
    async def test_speak_success(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._kokoro_available = True

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        async def fake_ensure_loaded():
            return (True, None)

        monkeypatch.setattr(tts_mod, "ensure_loaded", fake_ensure_loaded)

        gen_calls = []

        def fake_generate_audio(text, voice):
            gen_calls.append((text, voice))
            return "/tmp/test.wav"

        monkeypatch.setattr(tts_mod, "_generate_audio", fake_generate_audio)

        play_calls = []

        def fake_play_audio(wav_path, volume):
            play_calls.append((wav_path, volume))

        monkeypatch.setattr(tts_mod, "_play_audio", fake_play_audio)

        result = await tts_mod.speak("hello", voice="af_heart", volume=0.3)

        assert result["ok"] is True
        assert "elapsed" in result
        assert result["wav_path"] == "/tmp/test.wav"
        assert gen_calls == [("hello", "af_heart")]
        assert play_calls == [("/tmp/test.wav", 0.3)]

    @pytest.mark.asyncio
    async def test_speak_when_disabled(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._kokoro_available = True

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {"enabled": False}})
        # config_get may or may not be called depending on session state
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        result = await tts_mod.speak("hello")

        assert "error" in result
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_speak_when_not_available(self):
        import spellbook.notifications.tts as tts_mod
        tts_mod._kokoro_available = False
        tts_mod._import_error = "Missing dependency: kokoro"
        result = await tts_mod.speak("hello")
        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_speak_clamps_volume(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._kokoro_available = True

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        async def fake_ensure_loaded():
            return (True, None)

        monkeypatch.setattr(tts_mod, "ensure_loaded", fake_ensure_loaded)
        monkeypatch.setattr(tts_mod, "_generate_audio", lambda text, voice: "/tmp/test.wav")

        play_calls = []

        def fake_play_audio(wav_path, volume):
            play_calls.append((wav_path, volume))

        monkeypatch.setattr(tts_mod, "_play_audio", fake_play_audio)

        result = await tts_mod.speak("hello", volume=1.5)

        assert result["ok"] is True
        assert "warning" in result
        # Volume should have been clamped to 1.0
        assert play_calls == [("/tmp/test.wav", 1.0)]

    @pytest.mark.asyncio
    async def test_speak_playback_failure_returns_wav_path(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._kokoro_available = True

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        async def fake_ensure_loaded():
            return (True, None)

        monkeypatch.setattr(tts_mod, "ensure_loaded", fake_ensure_loaded)
        monkeypatch.setattr(tts_mod, "_generate_audio", lambda text, voice: "/tmp/test.wav")

        def fake_play_audio(wav_path, volume):
            raise ImportError("No sounddevice")

        monkeypatch.setattr(tts_mod, "_play_audio", fake_play_audio)

        result = await tts_mod.speak("hello")

        assert result["ok"] is True
        assert result["wav_path"] == "/tmp/test.wav"
        assert "Audio playback failed" in result.get("warning", "")
