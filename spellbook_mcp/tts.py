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
