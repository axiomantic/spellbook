"""Tests for security integration in installer core flow."""
import bigfoot
from pathlib import Path


def test_install_session_has_security_config_field():
    """InstallSession must have a security_config attribute."""
    from installer.core import InstallSession
    session = InstallSession(
        spellbook_dir=Path("/tmp/test"),
        version="1.0.0",
        previous_version=None,
    )
    assert hasattr(session, "security_config")
    # Default should be None or empty dict
    assert session.security_config is None or isinstance(session.security_config, dict)


def test_installer_accepts_security_selections():
    """Installer.run must accept security_selections parameter."""
    import inspect
    from installer.core import Installer
    sig = inspect.signature(Installer.run)
    assert "security_selections" in sig.parameters
