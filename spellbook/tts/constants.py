"""Named constants for TTS service integration."""

# Disk space check before venv creation (3 GB)
TTS_MIN_DISK_SPACE_BYTES = 3_221_225_472

# Default Wyoming server port
TTS_DEFAULT_PORT = 10200

# Progressive health check backoff schedule (seconds)
TTS_HEALTH_PROBE_DELAYS_S = (2, 5, 10, 20, 40)

# systemd RestartSec value
TTS_SYSTEMD_RESTART_SEC = 5

# Default voice
TTS_DEFAULT_VOICE = "af_heart"

# Default data directory name (under ~/.local/spellbook/)
TTS_DATA_DIR_NAME = "tts-data"

# Default venv directory name (under ~/.local/spellbook/)
TTS_VENV_DIR_NAME = "tts-venv"
