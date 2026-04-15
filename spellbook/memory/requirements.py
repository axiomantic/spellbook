"""Memory system prerequisites check."""
import shutil


class MemorySystemNotAvailable(Exception):
    """Raised when memory system dependencies (QMD, Serena) are missing."""


def ensure_memory_system_available() -> None:
    """Raise MemorySystemNotAvailable if QMD or Serena is missing."""
    missing = []
    if not shutil.which("qmd"):
        missing.append("qmd (install with: npm install -g @tobilu/qmd)")
    if not shutil.which("serena"):
        missing.append(
            "serena (install with: uv tool install -p 3.13 serena-agent@latest --prerelease=allow)"
        )
    if missing:
        raise MemorySystemNotAvailable(
            "Memory system requires: " + ", ".join(missing)
            + ". Run `spellbook install memory` or re-run the installer wizard."
        )
