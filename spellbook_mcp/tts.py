"""Kokoro TTS integration - lazy-loaded model with async-safe wrappers.

All public functions are designed to be called from async context.
Synchronous Kokoro operations are wrapped in asyncio.to_thread().
"""

import asyncio
import glob
import logging
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level state
_kokoro_available: Optional[bool] = None  # None = not checked yet
_kokoro_pipeline = None  # KPipeline instance, cached after first load
_load_lock = threading.Lock()  # Prevents concurrent model loads
_import_error: Optional[str] = None  # Stored error message if import fails

# Defaults
DEFAULT_VOICE = "af_heart"
DEFAULT_VOLUME = 0.3

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
    pattern = os.path.join(tempfile.gettempdir(), f"{_WAV_PREFIX}*.wav")
    for path in glob.glob(pattern):
        try:
            os.unlink(path)
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
        ValueError: If voice is invalid or pipeline fails.
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
    wav_path = os.path.join(tempfile.gettempdir(), wav_filename)
    sf.write(wav_path, audio_data, 24000)

    return wav_path


def _play_audio(wav_path: str, volume: float) -> None:
    """Play a WAV file through the default audio device, then delete it.

    Args:
        wav_path: Path to WAV file.
        volume: Volume multiplier 0.0-1.0.

    Raises:
        ImportError: If sounddevice is not available.
        RuntimeError: If playback fails (file is preserved).
    """
    import soundfile as sf
    import sounddevice as sd

    data, samplerate = sf.read(wav_path)
    sd.play(data * volume, samplerate)
    sd.wait()  # Block until playback finishes

    # Clean up WAV file after successful playback
    try:
        os.unlink(wav_path)
    except OSError:
        pass  # Best-effort cleanup
