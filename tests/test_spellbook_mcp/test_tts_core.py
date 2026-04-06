"""Tests for spellbook/notifications/tts.py - Wyoming TTS client.

Tests the Wyoming protocol-based TTS integration in isolation.
All Wyoming/sounddevice/numpy operations are mocked via bigfoot or monkeypatch.
"""

import asyncio
import socket
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import bigfoot
import pytest


@pytest.fixture(autouse=True)
def reset_tts_state():
    """Reset module-level TTS state between tests."""
    import spellbook.notifications.tts as tts_mod
    tts_mod._server_reachable = False
    yield
    tts_mod._server_reachable = False


class TestWyomingSynthesize:
    """_wyoming_synthesize() sends Synthesize event and collects AudioChunks."""

    @pytest.mark.asyncio
    async def test_successful_synthesis(self, monkeypatch):
        """Sends Synthesize, receives AudioChunks + AudioStop, returns PCM."""
        import spellbook.notifications.tts as tts_mod

        pcm_data = b"\x00\x01" * 100

        from wyoming.audio import AudioChunk, AudioStop

        chunk_event = AudioChunk(
            rate=22050, width=2, channels=1, audio=pcm_data
        ).event()
        stop_event = AudioStop().event()
        events_to_return = [chunk_event, stop_event]

        event_index = 0

        async def mock_async_read_event(reader):
            nonlocal event_index
            if event_index < len(events_to_return):
                evt = events_to_return[event_index]
                event_index += 1
                return evt
            return None

        write_calls = []

        async def mock_async_write_event(event, writer):
            write_calls.append(event)

        monkeypatch.setattr(tts_mod, "async_read_event", mock_async_read_event)
        monkeypatch.setattr(tts_mod, "async_write_event", mock_async_write_event)

        mock_writer = SimpleNamespace(
            close=lambda: None,
            wait_closed=lambda: asyncio.sleep(0),
        )

        open_calls = []

        async def mock_open_conn(host, port):
            open_calls.append((host, port))
            return SimpleNamespace(), mock_writer

        monkeypatch.setattr(asyncio, "open_connection", mock_open_conn)

        pcm, rate, width = await tts_mod._wyoming_synthesize(
            "hello", "test-voice", "localhost", 10200
        )

        assert pcm == pcm_data
        assert rate == 22050
        assert width == 2
        assert open_calls == [("localhost", 10200)]
        assert len(write_calls) == 1
        assert write_calls[0].type == "synthesize"

    @pytest.mark.asyncio
    async def test_connection_refused_raises(self, monkeypatch):
        """ConnectionError when server is unreachable."""
        import spellbook.notifications.tts as tts_mod

        async def mock_open_conn(host, port):
            raise OSError("Connection refused")

        monkeypatch.setattr(asyncio, "open_connection", mock_open_conn)

        with pytest.raises(ConnectionError, match="Cannot reach"):
            await tts_mod._wyoming_synthesize("hello", "", "localhost", 10200)

    @pytest.mark.asyncio
    async def test_empty_audio_raises(self, monkeypatch):
        """RuntimeError when no AudioChunks received."""
        import spellbook.notifications.tts as tts_mod
        from wyoming.audio import AudioStop

        stop_event = AudioStop().event()

        async def mock_async_read_event(reader):
            return stop_event

        async def mock_async_write_event(event, writer):
            pass

        monkeypatch.setattr(tts_mod, "async_read_event", mock_async_read_event)
        monkeypatch.setattr(tts_mod, "async_write_event", mock_async_write_event)

        mock_writer = SimpleNamespace(
            close=lambda: None,
            wait_closed=lambda: asyncio.sleep(0),
        )

        async def mock_open_conn(host, port):
            return SimpleNamespace(), mock_writer

        monkeypatch.setattr(asyncio, "open_connection", mock_open_conn)

        with pytest.raises(RuntimeError, match="no audio data"):
            await tts_mod._wyoming_synthesize("hello", "", "localhost", 10200)

    @pytest.mark.asyncio
    async def test_default_sample_rate_when_missing(self, monkeypatch):
        """Defaults to 22050 Hz when AudioChunk does not provide rate."""
        import spellbook.notifications.tts as tts_mod
        from wyoming.audio import AudioChunk, AudioStop

        chunk_event = AudioChunk(
            rate=0, width=2, channels=1, audio=b"\x00\x01"
        ).event()
        stop_event = AudioStop().event()
        events = [chunk_event, stop_event]
        idx = 0

        async def mock_read(reader):
            nonlocal idx
            if idx < len(events):
                e = events[idx]
                idx += 1
                return e
            return None

        async def mock_write(event, writer):
            pass

        monkeypatch.setattr(tts_mod, "async_read_event", mock_read)
        monkeypatch.setattr(tts_mod, "async_write_event", mock_write)

        mock_writer = SimpleNamespace(
            close=lambda: None,
            wait_closed=lambda: asyncio.sleep(0),
        )

        async def mock_open_conn(h, p):
            return SimpleNamespace(), mock_writer

        monkeypatch.setattr(asyncio, "open_connection", mock_open_conn)

        _pcm, rate, _width = await tts_mod._wyoming_synthesize(
            "hi", "", "localhost", 10200
        )

        assert rate == 22050


class TestEnsureConnected:
    """ensure_connected() verifies Wyoming server is reachable."""

    @pytest.mark.asyncio
    async def test_returns_true_when_reachable(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        mock_writer = SimpleNamespace(
            close=lambda: None,
            wait_closed=lambda: asyncio.sleep(0),
        )

        async def mock_open_conn(host, port):
            return SimpleNamespace(), mock_writer

        monkeypatch.setattr(asyncio, "open_connection", mock_open_conn)

        success, error = await tts_mod.ensure_connected()

        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_returns_false_when_unreachable(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        async def mock_open_conn(host, port):
            raise OSError("Connection refused")

        monkeypatch.setattr(asyncio, "open_connection", mock_open_conn)

        success, error = await tts_mod.ensure_connected()

        assert success is False
        assert error == "Cannot reach Wyoming TTS server at localhost:10200: Connection refused"


class TestResolveSetting:
    """_resolve_setting() follows explicit > session > config > default priority."""

    def test_explicit_value_wins(self):
        import spellbook.notifications.tts as tts_mod
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

    def test_falls_back_to_default_empty_string(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})

        mock_cg = bigfoot.mock("spellbook.core.config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            result = tts_mod._resolve_setting("voice")

        assert result == ""
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
    """get_status() returns TTS availability and settings."""

    def test_status_when_server_reachable(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._server_reachable = True

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        status = tts_mod.get_status()

        assert status["available"] is True
        assert status["server_reachable"] is True
        assert status["enabled"] is True
        assert status["voice"] == ""
        assert status["volume"] == 0.3
        assert status["error"] is None
        assert status["tts_wyoming_host"] == "localhost"
        assert status["tts_wyoming_port"] == 10200

    def test_status_when_server_unreachable(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod
        tts_mod._server_reachable = False

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        status = tts_mod.get_status()

        assert status["available"] is True
        assert status["server_reachable"] is False


class TestPreload:
    """preload() probes Wyoming server connectivity at startup."""

    def test_preload_sets_server_reachable_true(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        cleanup_called = []
        monkeypatch.setattr(tts_mod, "_cleanup_stale_wav_files", lambda: cleanup_called.append(True))

        check_calls = []
        def fake_check_server(host, port):
            check_calls.append((host, port))
            return True
        monkeypatch.setattr(tts_mod, "_check_server", fake_check_server)

        tts_mod.preload()

        assert tts_mod._server_reachable is True
        assert cleanup_called == [True]
        assert check_calls == [("localhost", 10200)]

    def test_preload_sets_server_reachable_false_on_failure(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        cleanup_called = []
        monkeypatch.setattr(tts_mod, "_cleanup_stale_wav_files", lambda: cleanup_called.append(True))

        check_calls = []
        def fake_check_server(host, port):
            check_calls.append((host, port))
            return False
        monkeypatch.setattr(tts_mod, "_check_server", fake_check_server)

        tts_mod.preload()

        assert tts_mod._server_reachable is False
        assert cleanup_called == [True]
        assert check_calls == [("localhost", 10200)]

    def test_preload_skipped_when_disabled(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "config_get", lambda key: False if key == "tts_enabled" else None)

        cleanup_called = []
        monkeypatch.setattr(tts_mod, "_cleanup_stale_wav_files", lambda: cleanup_called.append(True))

        check_calls = []
        monkeypatch.setattr(tts_mod, "_check_server", lambda h, p: check_calls.append(True) or True)

        tts_mod.preload()

        assert cleanup_called == [True]
        assert check_calls == []  # Should not check server when disabled

    def test_preload_calls_cleanup(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "config_get", lambda key: False if key == "tts_enabled" else None)

        cleanup_called = []
        monkeypatch.setattr(tts_mod, "_cleanup_stale_wav_files", lambda: cleanup_called.append(True))

        tts_mod.preload()

        assert cleanup_called == [True]


class TestSpeak:
    """speak() is the main async entry point for TTS."""

    @pytest.mark.asyncio
    async def test_speak_success(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

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
        pcm_data = b"\x00\x01" * 100

        async def fake_synth(text, voice, host, port):
            return (pcm_data, 22050, 2)

        monkeypatch.setattr(tts_mod, "_wyoming_synthesize", fake_synth)

        # Mock sounddevice (has private methods that bigfoot can't intercept)
        play_calls = []
        mock_sd = SimpleNamespace(
            play=lambda data, rate: play_calls.append((data, rate)),
            wait=lambda: None,
            _terminate=lambda: None,
            _initialize=lambda: None,
        )
        monkeypatch.setattr(tts_mod, "sd", mock_sd)

        # Mock wave module
        mock_wave_file = SimpleNamespace(
            setnchannels=lambda n: None,
            setsampwidth=lambda w: None,
            setframerate=lambda r: None,
            writeframes=lambda d: None,
            close=lambda: None,
        )
        monkeypatch.setattr(tts_mod, "wave", SimpleNamespace(open=lambda path, mode: mock_wave_file))
        monkeypatch.setattr(tts_mod, "uuid", SimpleNamespace(uuid4=lambda: "test-uuid"))
        monkeypatch.setattr(tts_mod, "tempfile", SimpleNamespace(gettempdir=lambda: "/tmp"))

        result = await tts_mod.speak("hello", voice="test-voice", volume=0.3)

        assert result["ok"] is True
        assert isinstance(result["elapsed"], float)
        assert result["wav_path"] == "/tmp/spellbook-tts-test-uuid.wav"
        assert len(play_calls) == 1

    @pytest.mark.asyncio
    async def test_speak_when_disabled(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {"enabled": False}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        result = await tts_mod.speak("hello")

        assert result == {
            "error": "TTS disabled. Enable with tts_config_set(enabled=true) "
            "or tts_session_set(enabled=true)"
        }

    @pytest.mark.asyncio
    async def test_speak_connection_error(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        async def fake_synth(text, voice, host, port):
            raise ConnectionError("Cannot reach server")

        monkeypatch.setattr(tts_mod, "_wyoming_synthesize", fake_synth)

        result = await tts_mod.speak("hello")

        assert result == {"error": "Cannot reach server"}

    @pytest.mark.asyncio
    async def test_speak_clamps_volume(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        pcm_data = b"\x00\x01" * 100

        async def fake_synth(text, voice, host, port):
            return (pcm_data, 22050, 2)

        monkeypatch.setattr(tts_mod, "_wyoming_synthesize", fake_synth)

        mock_sd = SimpleNamespace(
            play=lambda data, rate: None,
            wait=lambda: None,
            _terminate=lambda: None,
            _initialize=lambda: None,
        )
        monkeypatch.setattr(tts_mod, "sd", mock_sd)

        mock_wave_file = SimpleNamespace(
            setnchannels=lambda n: None,
            setsampwidth=lambda w: None,
            setframerate=lambda r: None,
            writeframes=lambda d: None,
            close=lambda: None,
        )
        monkeypatch.setattr(tts_mod, "wave", SimpleNamespace(open=lambda path, mode: mock_wave_file))
        monkeypatch.setattr(tts_mod, "uuid", SimpleNamespace(uuid4=lambda: "test-uuid"))
        monkeypatch.setattr(tts_mod, "tempfile", SimpleNamespace(gettempdir=lambda: "/tmp"))

        result = await tts_mod.speak("hello", volume=1.5)

        assert result["ok"] is True
        assert result["warning"] == "Volume clamped from 1.5 to 1.0"

    @pytest.mark.asyncio
    async def test_speak_playback_failure_returns_wav_path(self, monkeypatch):
        import spellbook.notifications.tts as tts_mod
        import spellbook.core.config as config_mod

        monkeypatch.setattr(config_mod, "_get_session_state", lambda sid=None: {"tts": {}})
        monkeypatch.setattr(config_mod, "config_get", lambda key: None)

        pcm_data = b"\x00\x01" * 100

        async def fake_synth(text, voice, host, port):
            return (pcm_data, 22050, 2)

        monkeypatch.setattr(tts_mod, "_wyoming_synthesize", fake_synth)

        def play_raises(data, rate):
            raise ImportError("No sounddevice")

        mock_sd = SimpleNamespace(
            play=play_raises,
            wait=lambda: None,
            _terminate=lambda: None,
            _initialize=lambda: None,
        )
        monkeypatch.setattr(tts_mod, "sd", mock_sd)

        mock_wave_file = SimpleNamespace(
            setnchannels=lambda n: None,
            setsampwidth=lambda w: None,
            setframerate=lambda r: None,
            writeframes=lambda d: None,
            close=lambda: None,
        )
        monkeypatch.setattr(tts_mod, "wave", SimpleNamespace(open=lambda path, mode: mock_wave_file))
        monkeypatch.setattr(tts_mod, "uuid", SimpleNamespace(uuid4=lambda: "test-uuid"))
        monkeypatch.setattr(tts_mod, "tempfile", SimpleNamespace(gettempdir=lambda: "/tmp"))

        result = await tts_mod.speak("hello")

        assert result["ok"] is True
        assert result["wav_path"] == "/tmp/spellbook-tts-test-uuid.wav"
        assert result["warning"] == "Audio playback failed: No sounddevice. WAV file saved to /tmp/spellbook-tts-test-uuid.wav"
