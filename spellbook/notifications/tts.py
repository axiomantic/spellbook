"""Wyoming protocol TTS client - connects to any Wyoming-compatible TTS server.

Spellbook acts as a pure TTS client, sending Synthesize events over TCP and
receiving AudioChunk/AudioStop responses. Audio playback uses numpy for PCM
decoding and sounddevice for output, with WAV writing via stdlib wave.
"""

import asyncio
import logging
import socket
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path
from typing import Any, Optional

import numpy
import sounddevice as sd

from wyoming.audio import AudioChunk, AudioStop
from wyoming.event import async_read_event, async_write_event
from wyoming.tts import Synthesize, SynthesizeVoice

from spellbook.core import config as config_tools
from spellbook.core.config import (
    TTS_DEFAULT_ENABLED,
    TTS_DEFAULT_VOICE,
    TTS_DEFAULT_VOLUME,
    WYOMING_DEFAULT_HOST,
    WYOMING_DEFAULT_PORT,
)
from spellbook.tts.venv import get_tts_data_dir, get_tts_venv_dir

logger = logging.getLogger(__name__)

# WAV file prefix for targeted cleanup
_WAV_PREFIX = "spellbook-tts-"

# Protocol constants
_CONNECT_TIMEOUT = 5.0  # TCP connect timeout in seconds
_READ_TIMEOUT = 30.0  # Max time waiting for audio events
_MAX_TEXT_LENGTH = 5000  # Character limit for synthesis requests

# Module-level state
_server_reachable = False

# Lock protecting sounddevice re-initialization and playback.
# PortAudio is not thread-safe, so concurrent _terminate/_initialize/play/wait
# sequences must be serialized.
_playback_lock = threading.Lock()


def _cleanup_stale_wav_files() -> None:
    """Remove stale spellbook TTS WAV files from temp directory."""
    for path in Path(tempfile.gettempdir()).glob(f"{_WAV_PREFIX}*.wav"):
        try:
            path.unlink()
        except OSError:
            pass


async def _wyoming_synthesize(
    text: str, voice: str, host: str, port: int
) -> tuple[bytes, int, int]:
    """Send a Synthesize event to a Wyoming TTS server and collect audio.

    Opens a TCP connection, sends the Synthesize event with the requested
    voice, then reads AudioChunk events until AudioStop is received.

    Args:
        text: Text to synthesize.
        voice: Voice name (empty string for server default).
        host: Wyoming server hostname.
        port: Wyoming server port.

    Returns:
        Tuple of (pcm_bytes, sample_rate, sample_width).

    Raises:
        ConnectionError: If the server is unreachable.
        RuntimeError: If no audio data is received.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=_CONNECT_TIMEOUT,
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise ConnectionError(
            f"Cannot reach Wyoming TTS server at {host}:{port}: {exc}"
        ) from exc

    try:
        # Send Synthesize event
        synth_event = Synthesize(
            text=text,
            voice=SynthesizeVoice(name=voice) if voice else None,
        ).event()
        await async_write_event(synth_event, writer)

        # Collect audio chunks
        pcm_parts: list[bytes] = []
        sample_rate = 0
        sample_width = 2  # default 16-bit

        while True:
            event = await asyncio.wait_for(
                async_read_event(reader), timeout=_READ_TIMEOUT
            )
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                pcm_parts.append(chunk.audio)
                if chunk.rate:
                    sample_rate = chunk.rate
                if chunk.width:
                    sample_width = chunk.width
            elif AudioStop.is_type(event.type):
                break

        if not pcm_parts:
            raise RuntimeError("Wyoming server returned no audio data")

        # Default sample rate if server didn't provide one
        if sample_rate == 0:
            sample_rate = 22050

        return b"".join(pcm_parts), sample_rate, sample_width
    finally:
        writer.close()
        await writer.wait_closed()


def _check_server(host: str, port: int) -> bool:
    """Probe Wyoming server connectivity via TCP.

    Args:
        host: Server hostname.
        port: Server port.

    Returns:
        True if the server accepted a TCP connection.
    """
    try:
        s = socket.create_connection((host, port), timeout=2.0)
        s.close()
        return True
    except OSError:
        return False


def _resolve_setting(
    key: str,
    explicit_value: Any = None,
    session_id: Optional[str] = None,
):
    """Resolve a TTS setting using the priority chain.

    Priority: explicit parameter > session override > config > default.

    Args:
        key: Setting key ("enabled", "voice", "volume").
        explicit_value: Value passed directly to a tool call.
        session_id: Session ID for session override lookup.

    Returns:
        The resolved setting value.
    """
    if explicit_value is not None:
        return explicit_value

    # Check session override
    session = config_tools._get_session_state(session_id)
    session_value = session.get("tts", {}).get(key)
    if session_value is not None:
        return session_value

    # Check config
    config_value = config_tools.config_get(f"tts_{key}")
    if config_value is not None:
        return config_value

    # Default
    defaults = {
        "enabled": TTS_DEFAULT_ENABLED,
        "voice": TTS_DEFAULT_VOICE,
        "volume": TTS_DEFAULT_VOLUME,
    }
    return defaults.get(key)


def get_status(session_id: str = None) -> dict:
    """Get TTS availability and current settings.

    Reports whether the Wyoming TTS server was reachable at last probe.
    Does NOT attempt a new connection. Safe to call at any time.

    When the TTS service is managed by spellbook (deps or service installed),
    includes a ``service`` sub-dict with provisioning state, device info,
    and filesystem paths.

    Args:
        session_id: Session ID for settings resolution.

    Returns:
        Dict with available, enabled, server_reachable, voice, volume,
        tts_wyoming_host, tts_wyoming_port, error keys, and optionally
        a service sub-dict when TTS service management is active.
    """
    host = config_tools.config_get("tts_wyoming_host") or WYOMING_DEFAULT_HOST
    port = config_tools.config_get("tts_wyoming_port") or WYOMING_DEFAULT_PORT
    result = {
        "available": True,
        "enabled": _resolve_setting("enabled", session_id=session_id),
        "server_reachable": _server_reachable,
        "voice": _resolve_setting("voice", session_id=session_id),
        "volume": _resolve_setting("volume", session_id=session_id),
        "tts_wyoming_host": host,
        "tts_wyoming_port": port,
        "error": None,
    }

    # Add service health info if TTS service management is active
    deps_installed = config_tools.config_get("tts_deps_installed")
    service_installed = config_tools.config_get("tts_service_installed")
    if deps_installed or service_installed:
        result["service"] = {
            "deps_installed": bool(deps_installed),
            "service_installed": bool(service_installed),
            "device": config_tools.config_get("tts_device") or "unknown",
            "provisioning": False,
            "data_dir": str(get_tts_data_dir()),
            "venv_dir": str(get_tts_venv_dir()),
            "log_file": str(Path.home() / ".local" / "spellbook" / "logs" / "tts.log"),
        }

    return result


def preload() -> None:
    """Probe Wyoming server connectivity at daemon startup.

    Sets _server_reachable based on whether the configured host:port
    accepts TCP connections. Always cleans up stale WAV files.
    """
    global _server_reachable

    _cleanup_stale_wav_files()

    enabled = config_tools.config_get("tts_enabled")
    if enabled is False:
        logger.info("TTS preload skipped: disabled in config")
        return

    host = config_tools.config_get("tts_wyoming_host") or WYOMING_DEFAULT_HOST
    port = config_tools.config_get("tts_wyoming_port") or WYOMING_DEFAULT_PORT

    reachable = _check_server(host, port)
    _server_reachable = reachable

    if reachable:
        logger.info("Wyoming TTS server reachable at %s:%s", host, port)
    else:
        logger.warning("Wyoming TTS server not reachable at %s:%s", host, port)


async def ensure_connected() -> tuple[bool, Optional[str]]:
    """Verify Wyoming TTS server connectivity.

    Returns:
        (True, None) if server is reachable, (False, error_message) otherwise.
    """
    global _server_reachable

    host = config_tools.config_get("tts_wyoming_host") or WYOMING_DEFAULT_HOST
    port = config_tools.config_get("tts_wyoming_port") or WYOMING_DEFAULT_PORT

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=_CONNECT_TIMEOUT,
        )
        writer.close()
        await writer.wait_closed()
        _server_reachable = True
        return True, None
    except (OSError, asyncio.TimeoutError) as exc:
        _server_reachable = False
        return False, f"Cannot reach Wyoming TTS server at {host}:{port}: {exc}"


async def speak(
    text: str,
    voice: str = None,
    volume: float = None,
    session_id: str = None,
) -> dict:
    """Synthesize and play speech from text via Wyoming TTS server.

    Main async entry point for TTS. Connects to the configured Wyoming
    server, synthesizes audio, converts to WAV, and plays through the
    default audio device.

    Args:
        text: Text to speak (max 5000 characters).
        voice: Voice name override.
        volume: Volume override (0.0-1.0).
        session_id: Session ID for settings resolution.

    Returns:
        {"ok": True, "elapsed": float, "wav_path": str} on success.
        {"error": str} on failure.
    """
    # Resolve settings
    effective_enabled = _resolve_setting("enabled", session_id=session_id)
    if not effective_enabled:
        return {
            "error": "TTS disabled. Enable with tts_config_set(enabled=true) "
            "or tts_session_set(enabled=true)"
        }

    effective_voice = _resolve_setting("voice", explicit_value=voice, session_id=session_id)
    effective_volume = _resolve_setting("volume", explicit_value=volume, session_id=session_id)

    # Clamp volume
    warnings = []
    if effective_volume is not None:
        if effective_volume < 0.0:
            warnings.append(f"Volume clamped from {effective_volume} to 0.0")
            effective_volume = 0.0
        elif effective_volume > 1.0:
            warnings.append(f"Volume clamped from {effective_volume} to 1.0")
            effective_volume = 1.0
    if effective_volume == 0.0:
        warnings.append("Volume is 0.0 (muted)")

    # Truncate text
    if len(text) > _MAX_TEXT_LENGTH:
        text = text[:_MAX_TEXT_LENGTH]
        warnings.append(f"Text truncated to {_MAX_TEXT_LENGTH} characters")

    host = config_tools.config_get("tts_wyoming_host") or WYOMING_DEFAULT_HOST
    port = config_tools.config_get("tts_wyoming_port") or WYOMING_DEFAULT_PORT

    start_time = time.monotonic()

    # Synthesize via Wyoming
    try:
        pcm_bytes, sample_rate, sample_width = await _wyoming_synthesize(
            text, effective_voice, host, port
        )
    except (ConnectionError, RuntimeError) as e:
        return {"error": str(e)}

    # Convert PCM to numpy float32 array
    if sample_width == 2:
        dtype = numpy.int16
    elif sample_width == 4:
        dtype = numpy.int32
    else:
        dtype = numpy.int16

    audio_array = numpy.frombuffer(pcm_bytes, dtype=dtype).astype(numpy.float32)
    # Normalize to [-1.0, 1.0]
    max_val = float(numpy.iinfo(dtype).max)
    audio_array = audio_array / max_val

    # Apply volume
    if effective_volume is not None:
        audio_array = audio_array * effective_volume

    # Write WAV via stdlib wave module
    wav_filename = f"{_WAV_PREFIX}{uuid.uuid4()}.wav"
    wav_path = str(Path(tempfile.gettempdir()) / wav_filename)

    wf = wave.open(wav_path, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(sample_width)
    wf.setframerate(sample_rate)
    wf.writeframes(pcm_bytes)
    wf.close()

    elapsed = time.monotonic() - start_time
    result = {"ok": True, "elapsed": round(elapsed, 2), "wav_path": wav_path}

    # Play audio
    try:
        # Re-initialize PortAudio so it picks up the current system default
        # output device. Without this, playback always targets whatever device
        # was default when the daemon (and thus PortAudio) first started.
        # These are private methods but necessary for PortAudio re-init in
        # long-running daemons; the lock serializes access to avoid races.
        def _play_sync() -> None:
            with _playback_lock:
                sd._terminate()
                sd._initialize()
                sd.play(audio_array, sample_rate)
                sd.wait()

        await asyncio.to_thread(_play_sync)

        # Clean up WAV file after successful playback
        try:
            Path(wav_path).unlink()
        except OSError:
            pass
    except Exception as e:
        warnings.append(f"Audio playback failed: {e}. WAV file saved to {wav_path}")
        logger.warning(warnings[-1])

    if warnings:
        result["warning"] = "; ".join(warnings)
        result["warnings"] = warnings

    return result
