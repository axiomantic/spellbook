"""
Abstract base class for platform installers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..core import InstallResult


@dataclass
class PlatformStatus:
    """Status of a platform installation."""

    platform: str
    available: bool  # Config directory exists or can be created
    installed: bool  # Spellbook components are installed
    version: Optional[str]  # Installed version if any
    details: Dict[str, Any] = field(default_factory=dict)


class PlatformInstaller(ABC):
    """Abstract base class for platform-specific installers."""

    def __init__(
        self, spellbook_dir: Path, config_dir: Path, version: str, dry_run: bool = False
    ):
        self.spellbook_dir = spellbook_dir
        self.config_dir = config_dir
        self.version = version
        self.dry_run = dry_run

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name."""
        pass

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Platform identifier (e.g., 'claude_code')."""
        pass

    @abstractmethod
    def detect(self) -> PlatformStatus:
        """
        Detect platform status.

        Returns PlatformStatus with:
        - available: True if platform can be installed to
        - installed: True if spellbook is already installed
        - version: Installed version if any
        """
        pass

    @abstractmethod
    def install(self, force: bool = False) -> List["InstallResult"]:
        """
        Install spellbook components for this platform.

        Args:
            force: Reinstall even if already installed

        Returns list of InstallResult for each component.
        """
        pass

    @abstractmethod
    def uninstall(self) -> List["InstallResult"]:
        """
        Uninstall spellbook components from this platform.

        Returns list of InstallResult for each component.
        """
        pass

    @abstractmethod
    def get_context_files(self) -> List[Path]:
        """Get paths to context files managed by this platform."""
        pass

    @abstractmethod
    def get_symlinks(self) -> List[Path]:
        """Get paths to symlinks created by this platform."""
        pass

    def ensure_config_dir(self) -> bool:
        """Ensure the config directory exists."""
        if self.dry_run:
            return True
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False
