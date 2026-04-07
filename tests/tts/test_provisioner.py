"""Tests for TTS provisioner state machine."""

from pathlib import Path

import bigfoot
import pytest

from spellbook.tts.provisioner import ensure_provisioned, provision_sync


def _async_return(value):
    """Create an async callable that returns value."""
    async def _fn(*args, **kwargs):
        return value
    return _fn


class _FakeLockCm:
    """Fake context manager returned by _acquire_provisioning_lock."""
    pass


class _FakeManager:
    def __init__(self):
        self.install_called = False
        self.start_called = False

    def install(self):
        self.install_called = True
        return (True, "ok")

    def start(self):
        self.start_called = True
        return (True, "ok")

    def is_running(self):
        return True


class _FailingInstallManager:
    def __init__(self):
        self.install_called = False
        self.start_called = False

    def install(self):
        self.install_called = True
        return (False, "permission denied")

    def start(self):
        self.start_called = True
        return (True, "ok")

    def is_running(self):
        return False


class TestEnsureProvisioned:
    @pytest.mark.asyncio
    async def test_full_provision_from_scratch(self):
        _fake_lock = _FakeLockCm()
        mock_acquire = bigfoot.mock("spellbook.tts.provisioner:_acquire_provisioning_lock")
        mock_acquire.calls(_async_return(_fake_lock))
        mock_release = bigfoot.mock("spellbook.tts.provisioner:_release_provisioning_lock")
        mock_release.calls(_async_return(None))

        mock_venv_dir = bigfoot.mock("spellbook.tts.provisioner:get_tts_venv_dir")
        mock_venv_dir.returns(Path("/fake/tts-venv"))

        mock_tts_python = bigfoot.mock("spellbook.tts.provisioner:get_tts_python")
        mock_tts_python.returns(Path("/fake/tts-venv/bin/python"))

        mock_get = bigfoot.mock("spellbook.tts.provisioner:config_get")
        mock_get.returns(False)       # tts_deps_installed
        mock_get.returns(False)       # tts_service_installed
        mock_get.returns(None)        # tts_service_config_hash (no stored hash)
        mock_get.returns(10200)       # tts_wyoming_port
        mock_get.returns("af_heart")  # tts_voice

        mock_venv = bigfoot.mock("spellbook.tts.provisioner:create_tts_venv")
        mock_venv.calls(_async_return((True, "ok")))

        mock_hash = bigfoot.mock("spellbook.tts.provisioner:_tts_config_hash")
        mock_hash.returns("new_hash")

        mock_set = bigfoot.mock("spellbook.tts.provisioner:config_set")
        mock_set.returns(None)  # tts_deps_installed = True
        mock_set.returns(None)  # tts_service_installed = True
        mock_set.returns(None)  # tts_service_config_hash
        mock_set.returns(None)  # tts_device = cpu

        mock_detect = bigfoot.mock("spellbook.tts.provisioner:detect_device")
        mock_detect.returns("cpu")

        mock_port = bigfoot.mock("spellbook.tts.provisioner:_check_port_available")
        mock_port.calls(_async_return(True))

        mock_tts_cfg = bigfoot.mock("spellbook.tts.provisioner:tts_service_config")
        fake_config = object()
        mock_tts_cfg.returns(fake_config)

        fake_manager = _FakeManager()
        mock_svc_cls = bigfoot.mock("spellbook.tts.provisioner:ServiceManager")
        mock_svc_cls.returns(fake_manager)

        mock_health = bigfoot.mock("spellbook.tts.provisioner:_progressive_health_check")
        mock_health.calls(_async_return(True))

        async with bigfoot:
            result = await ensure_provisioned()

        assert result == {
            "status": "ok",
            "detail": "TTS fully provisioned",
            "steps_completed": ["deps", "service"],
        }

        # Verify install() was actually invoked on the manager
        assert fake_manager.install_called, "ServiceManager.install() was never called"

        # Assertions in timeline order
        mock_acquire.assert_call(args=(), kwargs={})
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_tts_python.assert_call(args=(Path("/fake/tts-venv"),), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_venv.assert_call(
            args=(Path("/fake/tts-venv"),),
            kwargs={"progress_callback": None},
        )
        mock_set.assert_call(args=("tts_deps_installed", True), kwargs={})
        mock_hash.assert_call(args=(), kwargs={})
        mock_get.assert_call(args=("tts_service_config_hash",), kwargs={})
        mock_detect.assert_call(args=(), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_get.assert_call(args=("tts_voice",), kwargs={})
        mock_port.assert_call(args=(10200,), kwargs={})
        mock_tts_cfg.assert_call(
            args=(),
            kwargs={"tts_venv_dir": Path("/fake/tts-venv"), "port": 10200, "device": "cpu", "voice": "af_heart"},
        )
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})
        mock_set.assert_call(args=("tts_service_installed", True), kwargs={})
        mock_set.assert_call(args=("tts_service_config_hash", "new_hash"), kwargs={})
        mock_set.assert_call(args=("tts_device", "cpu"), kwargs={})
        mock_health.assert_call(args=("127.0.0.1", 10200), kwargs={})
        mock_release.assert_call(args=(_fake_lock,), kwargs={})

    @pytest.mark.asyncio
    async def test_already_provisioned_service_running(self):
        _fake_lock = _FakeLockCm()
        mock_acquire = bigfoot.mock("spellbook.tts.provisioner:_acquire_provisioning_lock")
        mock_acquire.calls(_async_return(_fake_lock))
        mock_release = bigfoot.mock("spellbook.tts.provisioner:_release_provisioning_lock")
        mock_release.calls(_async_return(None))

        mock_venv_dir = bigfoot.mock("spellbook.tts.provisioner:get_tts_venv_dir")
        mock_venv_dir.returns(Path("/fake/tts-venv"))

        mock_tts_python = bigfoot.mock("spellbook.tts.provisioner:get_tts_python")
        mock_tts_python.returns(Path("/fake/tts-venv/bin/python"))

        mock_get = bigfoot.mock("spellbook.tts.provisioner:config_get")
        mock_get.returns(True)    # tts_deps_installed
        mock_get.returns(True)    # tts_service_installed
        mock_get.returns("same_hash")  # tts_service_config_hash
        mock_get.returns(10200)   # tts_wyoming_port (for service check)

        # Mock Path.exists to return True for the python check
        mock_exists = bigfoot.mock.object(Path, "exists")
        mock_exists.returns(True)

        mock_hash = bigfoot.mock("spellbook.tts.provisioner:_tts_config_hash")
        mock_hash.returns("same_hash")

        mock_health = bigfoot.mock("spellbook.tts.provisioner:_health_probe")
        mock_health.calls(_async_return(True))  # Service is running

        async with bigfoot:
            result = await ensure_provisioned()

        assert result == {
            "status": "ok",
            "detail": "TTS fully provisioned",
            "steps_completed": [],
        }

        mock_acquire.assert_call(args=(), kwargs={})
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_tts_python.assert_call(args=(Path("/fake/tts-venv"),), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_exists.assert_call(args=(Path("/fake/tts-venv/bin/python"),), kwargs={})
        mock_hash.assert_call(args=(), kwargs={})
        mock_get.assert_call(args=("tts_service_config_hash",), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_health.assert_call(args=("127.0.0.1", 10200), kwargs={})
        mock_release.assert_call(args=(_fake_lock,), kwargs={})

    @pytest.mark.asyncio
    async def test_venv_creation_failure(self):
        _fake_lock = _FakeLockCm()
        mock_acquire = bigfoot.mock("spellbook.tts.provisioner:_acquire_provisioning_lock")
        mock_acquire.calls(_async_return(_fake_lock))
        mock_release = bigfoot.mock("spellbook.tts.provisioner:_release_provisioning_lock")
        mock_release.calls(_async_return(None))

        mock_venv_dir = bigfoot.mock("spellbook.tts.provisioner:get_tts_venv_dir")
        mock_venv_dir.returns(Path("/fake/tts-venv"))

        mock_tts_python = bigfoot.mock("spellbook.tts.provisioner:get_tts_python")
        mock_tts_python.returns(Path("/fake/tts-venv/bin/python"))

        mock_get = bigfoot.mock("spellbook.tts.provisioner:config_get")
        mock_get.returns(False)  # tts_deps_installed
        mock_get.returns(False)  # tts_service_installed

        mock_venv = bigfoot.mock("spellbook.tts.provisioner:create_tts_venv")
        mock_venv.calls(_async_return((False, "disk full")))

        async with bigfoot:
            result = await ensure_provisioned()

        assert result == {
            "status": "error",
            "detail": "disk full",
            "steps_completed": [],
        }

        mock_acquire.assert_call(args=(), kwargs={})
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_tts_python.assert_call(args=(Path("/fake/tts-venv"),), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_venv.assert_call(
            args=(Path("/fake/tts-venv"),),
            kwargs={"progress_callback": None},
        )
        mock_release.assert_call(args=(_fake_lock,), kwargs={})

    @pytest.mark.asyncio
    async def test_lock_contention_returns_already_provisioning(self):
        from spellbook.tts.lock import ProvisioningLocked

        async def _raise_locked(*args, **kwargs):
            raise ProvisioningLocked("TTS provisioning already in progress")

        mock_acquire = bigfoot.mock("spellbook.tts.provisioner:_acquire_provisioning_lock")
        mock_acquire.calls(_raise_locked)

        async with bigfoot:
            result = await ensure_provisioned()

        assert result == {
            "status": "already_provisioning",
            "detail": "Another process is provisioning TTS",
            "steps_completed": [],
        }
        mock_acquire.assert_call(args=(), kwargs={})

    @pytest.mark.asyncio
    async def test_port_in_use_returns_error(self):
        _fake_lock = _FakeLockCm()
        mock_acquire = bigfoot.mock("spellbook.tts.provisioner:_acquire_provisioning_lock")
        mock_acquire.calls(_async_return(_fake_lock))
        mock_release = bigfoot.mock("spellbook.tts.provisioner:_release_provisioning_lock")
        mock_release.calls(_async_return(None))

        mock_venv_dir = bigfoot.mock("spellbook.tts.provisioner:get_tts_venv_dir")
        mock_venv_dir.returns(Path("/fake/tts-venv"))

        mock_tts_python = bigfoot.mock("spellbook.tts.provisioner:get_tts_python")
        mock_tts_python.returns(Path("/fake/tts-venv/bin/python"))

        mock_get = bigfoot.mock("spellbook.tts.provisioner:config_get")
        mock_get.returns(True)    # tts_deps_installed
        mock_get.returns(False)   # tts_service_installed
        mock_get.returns(None)    # tts_service_config_hash
        mock_get.returns(10200)   # tts_wyoming_port
        mock_get.returns("af_heart")  # tts_voice

        mock_exists = bigfoot.mock.object(Path, "exists")
        mock_exists.returns(True)

        mock_hash = bigfoot.mock("spellbook.tts.provisioner:_tts_config_hash")
        mock_hash.returns("some_hash")

        mock_detect = bigfoot.mock("spellbook.tts.provisioner:detect_device")
        mock_detect.returns("cpu")

        mock_port = bigfoot.mock("spellbook.tts.provisioner:_check_port_available")
        mock_port.calls(_async_return(False))  # Port in use

        async with bigfoot:
            result = await ensure_provisioned()

        assert result == {
            "status": "error",
            "detail": "Port 10200 is already in use. Change tts_wyoming_port in config.",
            "steps_completed": [],
        }

        mock_acquire.assert_call(args=(), kwargs={})
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_tts_python.assert_call(args=(Path("/fake/tts-venv"),), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_exists.assert_call(args=(Path("/fake/tts-venv/bin/python"),), kwargs={})
        mock_hash.assert_call(args=(), kwargs={})
        mock_get.assert_call(args=("tts_service_config_hash",), kwargs={})
        mock_detect.assert_call(args=(), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_get.assert_call(args=("tts_voice",), kwargs={})
        mock_port.assert_call(args=(10200,), kwargs={})
        mock_release.assert_call(args=(_fake_lock,), kwargs={})

    @pytest.mark.asyncio
    async def test_install_failure_returns_error_and_skips_start(self):
        _fake_lock = _FakeLockCm()
        mock_acquire = bigfoot.mock("spellbook.tts.provisioner:_acquire_provisioning_lock")
        mock_acquire.calls(_async_return(_fake_lock))
        mock_release = bigfoot.mock("spellbook.tts.provisioner:_release_provisioning_lock")
        mock_release.calls(_async_return(None))

        mock_venv_dir = bigfoot.mock("spellbook.tts.provisioner:get_tts_venv_dir")
        mock_venv_dir.returns(Path("/fake/tts-venv"))

        mock_tts_python = bigfoot.mock("spellbook.tts.provisioner:get_tts_python")
        mock_tts_python.returns(Path("/fake/tts-venv/bin/python"))

        mock_get = bigfoot.mock("spellbook.tts.provisioner:config_get")
        mock_get.returns(False)       # tts_deps_installed
        mock_get.returns(False)       # tts_service_installed
        mock_get.returns(None)        # tts_service_config_hash
        mock_get.returns(10200)       # tts_wyoming_port
        mock_get.returns("af_heart")  # tts_voice

        mock_venv = bigfoot.mock("spellbook.tts.provisioner:create_tts_venv")
        mock_venv.calls(_async_return((True, "ok")))

        mock_set = bigfoot.mock("spellbook.tts.provisioner:config_set")
        mock_set.returns(None)  # tts_deps_installed = True

        mock_hash = bigfoot.mock("spellbook.tts.provisioner:_tts_config_hash")
        mock_hash.returns("some_hash")

        mock_detect = bigfoot.mock("spellbook.tts.provisioner:detect_device")
        mock_detect.returns("cpu")

        mock_port = bigfoot.mock("spellbook.tts.provisioner:_check_port_available")
        mock_port.calls(_async_return(True))

        mock_tts_cfg = bigfoot.mock("spellbook.tts.provisioner:tts_service_config")
        fake_config = object()
        mock_tts_cfg.returns(fake_config)

        failing_manager = _FailingInstallManager()
        mock_svc_cls = bigfoot.mock("spellbook.tts.provisioner:ServiceManager")
        mock_svc_cls.returns(failing_manager)

        async with bigfoot:
            result = await ensure_provisioned()

        assert result == {
            "status": "error",
            "detail": "Service install failed: permission denied",
            "steps_completed": ["deps"],
        }

        # Verify install() was called but start() was NOT
        assert failing_manager.install_called, "ServiceManager.install() was never called"
        assert not failing_manager.start_called, (
            "ServiceManager.start() should not be called after install failure"
        )

        mock_acquire.assert_call(args=(), kwargs={})
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_tts_python.assert_call(args=(Path("/fake/tts-venv"),), kwargs={})
        mock_get.assert_call(args=("tts_deps_installed",), kwargs={})
        mock_get.assert_call(args=("tts_service_installed",), kwargs={})
        mock_venv.assert_call(
            args=(Path("/fake/tts-venv"),),
            kwargs={"progress_callback": None},
        )
        mock_set.assert_call(args=("tts_deps_installed", True), kwargs={})
        mock_hash.assert_call(args=(), kwargs={})
        mock_get.assert_call(args=("tts_service_config_hash",), kwargs={})
        mock_detect.assert_call(args=(), kwargs={})
        mock_get.assert_call(args=("tts_wyoming_port",), kwargs={})
        mock_get.assert_call(args=("tts_voice",), kwargs={})
        mock_port.assert_call(args=(10200,), kwargs={})
        mock_tts_cfg.assert_call(
            args=(),
            kwargs={"tts_venv_dir": Path("/fake/tts-venv"), "port": 10200, "device": "cpu", "voice": "af_heart"},
        )
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})
        mock_release.assert_call(args=(_fake_lock,), kwargs={})


class _CoroutineOf:
    """Matcher for coroutine objects from a specific function."""
    def __init__(self, fn_name):
        self._fn_name = fn_name

    def __eq__(self, other):
        import asyncio
        if asyncio.iscoroutine(other):
            return other.cr_code.co_qualname == self._fn_name
        return False

    def __repr__(self):
        return f"_CoroutineOf({self._fn_name!r})"


class TestProvisionSync:
    def test_wraps_async(self):
        expected = {"status": "ok", "detail": "", "steps_completed": []}
        mock_run = bigfoot.mock("spellbook.tts.provisioner:asyncio.run")
        mock_run.returns(expected)

        with bigfoot:
            result = provision_sync()

        assert result == {"status": "ok", "detail": "", "steps_completed": []}
        # coroutine arg is dynamically created; match by function name
        mock_run.assert_call(
            args=(_CoroutineOf("ensure_provisioned"),),
            kwargs={},
        )
