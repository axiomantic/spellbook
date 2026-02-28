"""Kokoro TTS integration - lazy-loaded model with async-safe wrappers.

All public functions are designed to be called from async context.
Synchronous Kokoro operations are wrapped in asyncio.to_thread().
"""

import asyncio
import logging
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from spellbook_mcp import config_tools
from spellbook_mcp.config_tools import TTS_DEFAULT_ENABLED, TTS_DEFAULT_VOICE, TTS_DEFAULT_VOLUME

logger = logging.getLogger(__name__)

# Module-level state
_kokoro_available: Optional[bool] = None  # None = not checked yet
_kokoro_pipeline = None  # KPipeline instance, cached after first load
_load_lock = threading.Lock()  # Prevents concurrent model loads
_import_error: Optional[str] = None  # Stored error message if import fails

# WAV file prefix for targeted cleanup
_WAV_PREFIX = "spellbook-tts-"


def _check_availability() -> bool:
    """Check if kokoro and soundfile are importable. Caches result.

    Returns:
        True if TTS dependencies are available, False otherwise.
    """
    global _kokoro_available, _import_error
    if _kokoro_available is not None:
        return _kokoro_available
    try:
        import kokoro  # noqa: F401
        import soundfile  # noqa: F401
        _kokoro_available = True
        _import_error = None
        # Clean up stale WAV files from previous server runs
        _cleanup_stale_wav_files()
    except ImportError as e:
        _kokoro_available = False
        _import_error = f"Missing dependency: {e}. Install with: pip install .[tts]"
    return _kokoro_available


def _cleanup_stale_wav_files() -> None:
    """Remove stale spellbook TTS WAV files from temp directory."""
    for path in Path(tempfile.gettempdir()).glob(f"{_WAV_PREFIX}*.wav"):
        try:
            path.unlink()
        except OSError:
            pass


def _load_model() -> None:
    """Load Kokoro model with thread-safe double-checked locking.

    If _kokoro_pipeline is already set, returns immediately (fast path,
    no lock acquired). If another thread is currently loading, blocks on
    _load_lock until that thread finishes. On failure, stores error in
    _import_error and leaves _kokoro_pipeline as None so next call retries.
    """
    global _kokoro_pipeline, _import_error
    # Fast path: model already loaded (no lock needed)
    if _kokoro_pipeline is not None:
        return
    with _load_lock:
        # Re-check after acquiring lock (another thread may have loaded it)
        if _kokoro_pipeline is not None:
            return
        try:
            from kokoro import KPipeline
            _kokoro_pipeline = KPipeline(lang_code="a")
            _import_error = None
            logger.info("Kokoro model loaded successfully")
        except Exception as e:
            _import_error = f"Model load failed: {e}"
            logger.error(_import_error)
            # _kokoro_pipeline stays None so next call retries


def _generate_audio(text: str, voice: str) -> str:
    """Generate WAV audio from text using the loaded Kokoro pipeline.

    Args:
        text: Text to synthesize.
        voice: Kokoro voice ID.

    Returns:
        Path to the generated WAV file.

    Raises:
        ValueError: If no audio generated for the given text.
        RuntimeError: If _kokoro_pipeline is None.
    """
    if _kokoro_pipeline is None:
        raise RuntimeError("Kokoro pipeline not loaded")

    import soundfile as sf

    # Generate audio
    audio_chunks = []
    for _graphemes, _phonemes, audio_tensor in _kokoro_pipeline(text, voice=voice):
        audio_chunks.append(audio_tensor.numpy())

    if not audio_chunks:
        raise ValueError(f"No audio generated for text: {text!r}")

    import numpy as np
    audio_data = np.concatenate(audio_chunks)

    # Write to temp file
    wav_filename = f"{_WAV_PREFIX}{uuid.uuid4()}.wav"
    wav_path = str(Path(tempfile.gettempdir()) / wav_filename)
    sf.write(wav_path, audio_data, 24000)

    return wav_path


def _play_audio(wav_path: str, volume: float) -> None:
    """Play a WAV file through the default audio device, then delete it.

    Args:
        wav_path: Path to WAV file.
        volume: Volume multiplier 0.0-1.0.

    Raises:
        ImportError: If sounddevice is not available.
        Exception: If playback fails (sounddevice.PortAudioError or similar).
            File is preserved on failure for manual playback.
    """
    import soundfile as sf
    import sounddevice as sd

    data, samplerate = sf.read(wav_path)
    sd.play(data * volume, samplerate)
    sd.wait()  # Block until playback finishes

    # Clean up WAV file after successful playback
    try:
        Path(wav_path).unlink()
    except OSError:
        pass  # Best-effort cleanup


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
    defaults = {"enabled": TTS_DEFAULT_ENABLED, "voice": TTS_DEFAULT_VOICE, "volume": TTS_DEFAULT_VOLUME}
    return defaults.get(key)


def get_status(session_id: str = None) -> dict:
    """Get TTS availability and current settings.

    Triggers an availability check (import test) on first call but does
    NOT trigger model loading. Safe to call at any time.

    Args:
        session_id: Session ID for settings resolution.

    Returns:
        Dict with available, enabled, model_loaded, voice, volume, error keys.
    """
    available = _check_availability()
    return {
        "available": available,
        "enabled": _resolve_setting("enabled", session_id=session_id),
        "model_loaded": _kokoro_pipeline is not None,
        "voice": _resolve_setting("voice", session_id=session_id),
        "volume": _resolve_setting("volume", session_id=session_id),
        "error": _import_error if not available else None,
    }


def preload() -> None:
    """Preload Kokoro model if TTS is enabled and available.

    Intended to be called from a background thread at daemon startup.
    Safe to call multiple times (idempotent via _load_model's double-checked locking).
    """
    enabled = config_tools.config_get("tts_enabled")
    if enabled is False:
        logger.info("TTS preload skipped: disabled in config")
        return
    if not _check_availability():
        logger.info("TTS preload skipped: dependencies not available")
        return
    logger.info("TTS preload: loading Kokoro model...")
    _load_model()


async def ensure_loaded() -> tuple[bool, str | None]:
    """Async wrapper for model loading.

    Returns:
        (True, None) on success, (False, error_message) on failure.
    """
    await asyncio.to_thread(_load_model)
    if _kokoro_pipeline is not None:
        return True, None
    return False, _import_error


async def speak(
    text: str,
    voice: str = None,
    volume: float = None,
    session_id: str = None,
) -> dict:
    """Generate and play speech from text.

    Main async entry point for TTS. Lazy-loads model on first call.

    Args:
        text: Text to speak.
        voice: Voice ID override.
        volume: Volume override (0.0-1.0).
        session_id: Session ID for settings resolution.

    Returns:
        {"ok": True, "elapsed": float, "wav_path": str} on success.
        wav_path is deleted after successful playback; only preserved on
        playback failure (with a warning).
        {"error": str} on failure.
    """
    # Check availability
    if not _check_availability():
        return {"error": f"TTS not available. {_import_error}"}

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

    start_time = time.monotonic()

    # Ensure model is loaded
    success, error = await ensure_loaded()
    if not success:
        return {"error": f"TTS model failed to load: {error}"}

    # Generate audio
    try:
        wav_path = await asyncio.to_thread(_generate_audio, text, effective_voice)
    except Exception as e:
        return {"error": f"Audio generation failed: {e}"}

    # Play audio
    elapsed = time.monotonic() - start_time
    result = {"ok": True, "elapsed": round(elapsed, 2), "wav_path": wav_path}

    try:
        await asyncio.to_thread(_play_audio, wav_path, effective_volume)
    except Exception as e:
        # Playback failed but WAV was generated - return path for manual use
        warnings.append(f"Audio playback failed: {e}. WAV file saved to {wav_path}")
        logger.warning(warnings[-1])

    if warnings:
        result["warning"] = "; ".join(warnings)

    return result
