"""Device auto-detection for TTS inference.

Detects the best available compute device without importing torch
(which is heavy and lives in the TTS venv, not the daemon venv).
"""

import platform as plat
import shutil
import subprocess

from spellbook.core.config import config_get


def detect_device() -> str:
    """Detect best available compute device for TTS.

    Priority:
    1. User override via tts_device config (if not "auto" or None)
    2. macOS Apple Silicon -> "mps"
    3. NVIDIA GPU detected via nvidia-smi -> "cuda"
    4. Fallback -> "cpu"

    Returns:
        One of "mps", "cuda", or "cpu".
    """
    override = config_get("tts_device")
    if override and override != "auto":
        return override

    # macOS Apple Silicon
    if plat.system() == "Darwin" and plat.machine() == "arm64":
        return "mps"

    # NVIDIA CUDA (probe without importing torch)
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return "cuda"
        except (subprocess.TimeoutExpired, OSError):
            pass

    return "cpu"
