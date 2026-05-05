"""Regression: hooks.py settings writes go through atomic_replace and tolerate
Windows transient-error PermissionError on os.replace.

Drive-by part of WI-0. Without this, install_hooks/uninstall_hooks would lose
data on Windows when an antivirus / Claude Code / another process holds an
open handle on settings.json at the moment of write.
"""

import json
from pathlib import Path
from unittest.mock import patch



def _write_baseline(settings_path: Path) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"existing": "value"}), encoding="utf-8")


def test_install_hooks_retries_os_replace_permission_error_once(tmp_path):
    """install_hooks must retry os.replace once when it raises PermissionError.

    Simulates the Windows behaviour where os.replace fails with WinError 5
    (PermissionError) the first time because settings.json has an open
    handle, then succeeds on retry. atomic_replace's retry budget covers
    this; if hooks.py wrote via Path.write_text instead, the test would
    show no retry happened and the write would have lost data.
    """
    from installer.components import hooks
    from spellbook.core import command_utils

    config_dir = tmp_path / ".claude"
    settings_path = config_dir / "settings.json"
    _write_baseline(settings_path)

    real_replace = command_utils.os.replace
    call_count = {"n": 0}

    def flaky_replace(src, dst):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise PermissionError("simulated WinError 5: file in use")
        real_replace(src, dst)

    # Force the Windows code path inside atomic_replace, then patch os.replace
    # to simulate a transient PermissionError on the first attempt.
    with patch.object(command_utils.platform, "system", return_value="Windows"), \
         patch.object(command_utils.os, "replace", side_effect=flaky_replace), \
         patch.object(command_utils.time, "sleep", return_value=None):
        result = hooks.install_hooks(
            settings_path=settings_path,
            spellbook_dir=tmp_path / "spellbook_dir",
            dry_run=False,
        )

    assert result.success is True
    assert result.component == "hooks"
    # Two calls: first fails, second succeeds.
    assert call_count["n"] == 2
    # The hooks section ended up registered; the prior "existing" key survived.
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written["existing"] == "value"
    assert "hooks" in written
    assert "PreToolUse" in written["hooks"]


def test_uninstall_hooks_retries_os_replace_permission_error_once(tmp_path):
    """uninstall_hooks must also use the atomic-write retry path."""
    from installer.components import hooks
    from spellbook.core import command_utils

    config_dir = tmp_path / ".claude"
    settings_path = config_dir / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    # Pre-populate with a spellbook-managed hook so uninstall has work to do.
    settings_path.write_text(
        json.dumps(
            {
                "existing": "value",
                "hooks": {
                    "PreToolUse": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$SPELLBOOK_DIR/hooks/spellbook_hook.py",
                                    "spellbook_managed": True,
                                }
                            ]
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    real_replace = command_utils.os.replace
    call_count = {"n": 0}

    def flaky_replace(src, dst):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise PermissionError("simulated WinError 5: file in use")
        real_replace(src, dst)

    with patch.object(command_utils.platform, "system", return_value="Windows"), \
         patch.object(command_utils.os, "replace", side_effect=flaky_replace), \
         patch.object(command_utils.time, "sleep", return_value=None):
        result = hooks.uninstall_hooks(
            settings_path=settings_path,
            spellbook_dir=tmp_path / "spellbook_dir",
            dry_run=False,
        )

    assert result.success is True
    assert call_count["n"] == 2
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written.get("existing") == "value"
