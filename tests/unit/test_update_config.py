"""Tests for thread-safe config access and update notification integration."""

import json
import os
import threading
import tripwire
import pytest
from dirty_equals import IsBytes, IsInstance, IsStr

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows


class TestConfigFileLocking:
    """Tests for file-level locking in config_get/config_set."""

    def test_config_set_creates_lock_file(self, tmp_path):
        """config_set should use CrossPlatformLock during writes."""
        from spellbook.core.config import config_set

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        path_mock = tripwire.mock("spellbook.core.config:get_config_path")
        path_mock.returns(config_path)
        lock_mock = tripwire.mock("spellbook.core.config:_config_lock_path")
        lock_mock.returns(lock_path)

        # Spy on CrossPlatformLock.__enter__ to verify it's used as a context manager
        from spellbook.core.compat import CrossPlatformLock

        enter_spy = tripwire.spy.object(CrossPlatformLock, "__enter__")

        with tripwire:
            config_set("test_key", "test_value")

        path_mock.assert_call(args=(), kwargs={})
        lock_mock.assert_call(args=(), kwargs={})
        enter_spy.assert_call(
            args=(IsInstance(CrossPlatformLock),),
            kwargs={},
            returned=IsInstance(CrossPlatformLock),
        )

        # Config file should exist with the value
        config = json.loads(config_path.read_text())
        assert config["test_key"] == "test_value"

    def test_concurrent_config_writes_no_data_loss(self, tmp_path):
        """Concurrent writes should not lose data due to locking."""
        from spellbook.core.config import config_set

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        path_mock = tripwire.mock("spellbook.core.config:get_config_path")
        path_mock.always_returns(config_path)
        lock_mock = tripwire.mock("spellbook.core.config:_config_lock_path")
        lock_mock.always_returns(lock_path)

        # Write initial config
        config_path.write_text(json.dumps({"initial": True}) + "\n")

        writer_count = 10
        errors = []

        def write_key(key, value):
            try:
                config_set(key, value)
            except Exception as e:
                errors.append(e)

        # Concurrent writes
        threads = []
        for i in range(writer_count):
            t = threading.Thread(target=write_key, args=(f"key_{i}", f"value_{i}"))
            threads.append(t)

        with tripwire:
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(errors) == 0

        # Every writer resolved the config path and the lock path exactly once.
        # Thread interleaving makes the recorded order arbitrary, so the
        # per-writer counts are what carries the meaning here.
        with tripwire.in_any_order():
            for _ in range(writer_count):
                path_mock.assert_call(args=(), kwargs={})
                lock_mock.assert_call(args=(), kwargs={})

        # All keys should be present (no lost updates)
        final_config = json.loads(config_path.read_text())
        assert final_config["initial"] is True
        for i in range(writer_count):
            assert final_config[f"key_{i}"] == f"value_{i}"

    def test_config_get_reads_with_shared_lock(self, tmp_path):
        """config_get should work correctly with locking."""
        from spellbook.core.config import config_get, config_set

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        path_mock = tripwire.mock("spellbook.core.config:get_config_path")
        path_mock.always_returns(config_path)
        lock_mock = tripwire.mock("spellbook.core.config:_config_lock_path")
        lock_mock.always_returns(lock_path)

        with tripwire:
            config_set("locked_key", 42)
            result = config_get("locked_key")

        assert result == 42

        # Write then read: each resolves the config path and takes the lock once.
        path_mock.assert_call(args=(), kwargs={})
        lock_mock.assert_call(args=(), kwargs={})
        path_mock.assert_call(args=(), kwargs={})
        lock_mock.assert_call(args=(), kwargs={})

    def test_config_write_is_atomic(self, tmp_path):
        """Config write uses atomic replace pattern.

        Verifies that config_set writes to a temp file then replaces,
        so a Ctrl+C mid-write cannot corrupt the original config file.
        """
        from spellbook.core.config import config_set

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        path_mock = tripwire.mock("spellbook.core.config:get_config_path")
        path_mock.returns(config_path)
        lock_mock = tripwire.mock("spellbook.core.config:_config_lock_path")
        lock_mock.returns(lock_path)

        # Write initial valid config
        config_path.write_text(json.dumps({"existing": "data"}) + "\n")

        # Spy rather than mock: the real rename must happen for the
        # post-conditions on the config file below to mean anything.
        replace_spy = tripwire.spy("os:replace")

        with tripwire:
            config_set("new_key", "new_value")

        path_mock.assert_call(args=(), kwargs={})
        lock_mock.assert_call(args=(), kwargs={})
        # Exactly one rename, from a .tmp sibling onto the config path.
        # Tripwire fails the test on any unasserted interaction, so this
        # single assertion also pins the call count. mkstemp picks the
        # basename, so only its .tmp suffix is knowable here.
        replace_spy.assert_call(
            args=(IsStr(regex=r".*\.tmp"), str(config_path)),
            kwargs={},
            returned=None,
        )

        # Verify final config is valid and contains both keys
        config = json.loads(config_path.read_text())
        assert config["existing"] == "data"
        assert config["new_key"] == "new_value"

    def test_config_write_atomic_cleanup_on_failure(self, tmp_path):
        """If write fails before os.replace, original config is untouched."""
        from spellbook.core.config import config_set

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        path_mock = tripwire.mock("spellbook.core.config:get_config_path")
        path_mock.returns(config_path)
        lock_mock = tripwire.mock("spellbook.core.config:_config_lock_path")
        lock_mock.returns(lock_path)

        # Write initial valid config
        original_content = json.dumps({"precious": "data"}) + "\n"
        config_path.write_text(original_content)

        # CrossPlatformLock writes its own metadata through os.write before
        # config_set writes the payload, so the first call is delegated to the
        # real syscall and only the second one fails.
        real_write = os.write
        failure = OSError("simulated write failure")
        write_mock = tripwire.mock("os:write")
        write_mock.calls(real_write).raises(failure)

        with tripwire:
            with pytest.raises(OSError, match="simulated write failure"):
                config_set("bad_key", "bad_value")

        path_mock.assert_call(args=(), kwargs={})
        lock_mock.assert_call(args=(), kwargs={})
        # Lock metadata: the pid is knowable, the wall-clock timestamp is not.
        write_mock.assert_call(
            args=(
                IsInstance(int),
                IsBytes(regex=rb'\{"pid": %d, "timestamp": [0-9.]+\}' % os.getpid()),
            ),
            kwargs={},
        )
        # The merged config is written in one os.write of the full payload.
        # The descriptor comes from mkstemp, so only its type is knowable.
        expected_payload = (
            json.dumps({"precious": "data", "bad_key": "bad_value"}, indent=2) + "\n"
        ).encode("utf-8")
        write_mock.assert_call(
            args=(IsInstance(int), expected_payload),
            kwargs={},
            raised=failure,
        )

        # Original config must be untouched
        assert config_path.read_text() == original_content

        # No leftover temp files
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Temp files should be cleaned up: {tmp_files}"
