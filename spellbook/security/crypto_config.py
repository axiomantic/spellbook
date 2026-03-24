"""Configuration defaults for the cryptographic content provenance system.

All keys use the security.crypto.* namespace. Values here serve as
documentation of available settings and their defaults. The actual
config store uses flat string keys (no nested dict traversal).
"""

from __future__ import annotations

from pathlib import Path

CRYPTO_CONFIG_DEFAULTS: dict[str, object] = {
    # Master switch for crypto provenance checking
    "security.crypto.enabled": False,  # Opt-in: enabled by installer after key generation
    # Directory for Ed25519 keypair storage
    "security.crypto.keys_dir": str(Path.home() / ".local" / "spellbook" / "keys"),
    # Per-operation gate switches
    "security.crypto.gate_spawn_session": True,
    "security.crypto.gate_workflow_save": True,
}
