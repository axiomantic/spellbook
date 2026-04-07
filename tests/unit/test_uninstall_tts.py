"""Tests for Uninstaller TTS service cleanup."""

from pathlib import Path

import bigfoot

from installer.core import Uninstaller


class _FakeServiceManager:
    """Minimal ServiceManager stand-in for testing."""

    def __init__(self):
        self._installed = True
        self._stop_result = (True, "stopped")
        self._uninstall_result = (True, "uninstalled")

    def is_installed(self):
        return self._installed

    def stop(self):
        return self._stop_result

    def uninstall(self):
        return self._uninstall_result


class TestUninstallTtsServiceInstalled:
    """TTS service is installed and running -- full cleanup."""

    def test_stops_uninstalls_removes_venv_resets_config(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")

        tts_venv_dir = tmp_path / "tts-venv"
        tts_venv_dir.mkdir()
        (tts_venv_dir / "bin").mkdir(parents=True)

        tts_data_dir = tmp_path / "tts-data"
        tts_data_dir.mkdir()

        fake_config = object()
        fake_mgr = _FakeServiceManager()

        mock_venv_dir = bigfoot.mock("spellbook.tts.venv:get_tts_venv_dir")
        mock_venv_dir.returns(tts_venv_dir)

        mock_data_dir = bigfoot.mock("spellbook.tts.venv:get_tts_data_dir")
        mock_data_dir.returns(tts_data_dir)

        mock_tts_cfg = bigfoot.mock("installer.compat:tts_service_config")
        mock_tts_cfg.returns(fake_config)

        mock_svc_cls = bigfoot.mock("installer.compat:ServiceManager")
        mock_svc_cls.returns(fake_mgr)

        mock_rmtree = bigfoot.mock("installer.core:shutil.rmtree")
        mock_rmtree.returns(None)

        mock_config_set = bigfoot.mock("spellbook.core.config:config_set")
        mock_config_set.returns({})  # tts_enabled
        mock_config_set.returns({})  # tts_deps_installed
        mock_config_set.returns({})  # tts_service_installed

        with bigfoot:
            uninstaller = Uninstaller(spellbook_dir)
            result = uninstaller._uninstall_tts_service(dry_run=False)

        assert result is not None
        assert result.component == "tts_service"
        assert result.platform == "system"
        assert result.success is True
        assert result.action == "removed"
        assert result.message == "TTS service: uninstalled"

        # Assertions in timeline order
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_data_dir.assert_call(args=(), kwargs={})
        mock_tts_cfg.assert_call(args=(), kwargs={"tts_venv_dir": tts_venv_dir})
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})
        mock_rmtree.assert_call(args=(str(tts_venv_dir),), kwargs={})
        mock_config_set.assert_call(args=("tts_enabled", False), kwargs={})
        mock_config_set.assert_call(args=("tts_deps_installed", False), kwargs={})
        mock_config_set.assert_call(args=("tts_service_installed", False), kwargs={})


class TestUninstallTtsServiceNotInstalled:
    """TTS service is not installed and venv doesn't exist -- returns None."""

    def test_returns_none_when_not_installed(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")

        tts_venv_dir = tmp_path / "tts-venv"
        # venv does not exist on disk

        fake_config = object()
        fake_mgr = _FakeServiceManager()
        fake_mgr._installed = False

        mock_venv_dir = bigfoot.mock("spellbook.tts.venv:get_tts_venv_dir")
        mock_venv_dir.returns(tts_venv_dir)

        mock_data_dir = bigfoot.mock("spellbook.tts.venv:get_tts_data_dir")
        mock_data_dir.returns(tmp_path / "tts-data")

        mock_tts_cfg = bigfoot.mock("installer.compat:tts_service_config")
        mock_tts_cfg.returns(fake_config)

        mock_svc_cls = bigfoot.mock("installer.compat:ServiceManager")
        mock_svc_cls.returns(fake_mgr)

        with bigfoot:
            uninstaller = Uninstaller(spellbook_dir)
            result = uninstaller._uninstall_tts_service(dry_run=False)

        assert result is None

        # Still called before early return (timeline order)
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_data_dir.assert_call(args=(), kwargs={})
        mock_tts_cfg.assert_call(args=(), kwargs={"tts_venv_dir": tts_venv_dir})
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})


class TestUninstallTtsServiceDryRun:
    """Dry-run mode returns a result without side effects."""

    def test_dry_run_returns_would_uninstall(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")

        tts_venv_dir = tmp_path / "tts-venv"
        tts_venv_dir.mkdir()

        fake_config = object()
        fake_mgr = _FakeServiceManager()

        mock_venv_dir = bigfoot.mock("spellbook.tts.venv:get_tts_venv_dir")
        mock_venv_dir.returns(tts_venv_dir)

        mock_data_dir = bigfoot.mock("spellbook.tts.venv:get_tts_data_dir")
        mock_data_dir.returns(tmp_path / "tts-data")

        mock_tts_cfg = bigfoot.mock("installer.compat:tts_service_config")
        mock_tts_cfg.returns(fake_config)

        mock_svc_cls = bigfoot.mock("installer.compat:ServiceManager")
        mock_svc_cls.returns(fake_mgr)

        with bigfoot:
            uninstaller = Uninstaller(spellbook_dir)
            result = uninstaller._uninstall_tts_service(dry_run=True)

        assert result is not None
        assert result.component == "tts_service"
        assert result.platform == "system"
        assert result.success is True
        assert result.action == "removed"
        assert result.message == "TTS service: would uninstall service, remove venv, and reset config"

        # Setup calls still happen in dry-run
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_data_dir.assert_call(args=(), kwargs={})
        mock_tts_cfg.assert_call(args=(), kwargs={"tts_venv_dir": tts_venv_dir})
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})


class TestUninstallTtsServiceNoVenv:
    """TTS service is installed but venv is already gone."""

    def test_still_uninstalls_service_and_resets_config(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")

        tts_venv_dir = tmp_path / "tts-venv"
        # venv does NOT exist on disk

        fake_config = object()
        fake_mgr = _FakeServiceManager()

        mock_venv_dir = bigfoot.mock("spellbook.tts.venv:get_tts_venv_dir")
        mock_venv_dir.returns(tts_venv_dir)

        mock_data_dir = bigfoot.mock("spellbook.tts.venv:get_tts_data_dir")
        mock_data_dir.returns(tmp_path / "tts-data")

        mock_tts_cfg = bigfoot.mock("installer.compat:tts_service_config")
        mock_tts_cfg.returns(fake_config)

        mock_svc_cls = bigfoot.mock("installer.compat:ServiceManager")
        mock_svc_cls.returns(fake_mgr)

        # No rmtree mock -- venv doesn't exist so rmtree shouldn't be called

        mock_config_set = bigfoot.mock("spellbook.core.config:config_set")
        mock_config_set.returns({})  # tts_enabled
        mock_config_set.returns({})  # tts_deps_installed
        mock_config_set.returns({})  # tts_service_installed

        with bigfoot:
            uninstaller = Uninstaller(spellbook_dir)
            result = uninstaller._uninstall_tts_service(dry_run=False)

        assert result is not None
        assert result.success is True
        assert result.action == "removed"
        assert result.message == "TTS service: uninstalled"

        # Timeline order
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_data_dir.assert_call(args=(), kwargs={})
        mock_tts_cfg.assert_call(args=(), kwargs={"tts_venv_dir": tts_venv_dir})
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})
        mock_config_set.assert_call(args=("tts_enabled", False), kwargs={})
        mock_config_set.assert_call(args=("tts_deps_installed", False), kwargs={})
        mock_config_set.assert_call(args=("tts_service_installed", False), kwargs={})


class TestUninstallTtsServiceModelDataPreserved:
    """Model data directory is never removed during uninstall."""

    def test_data_dir_not_removed_when_exists(self, tmp_path):
        """Venv is removed but data dir is left intact."""
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")

        tts_venv_dir = tmp_path / "tts-venv"
        tts_venv_dir.mkdir()

        tts_data_dir = tmp_path / "tts-data"
        tts_data_dir.mkdir()
        (tts_data_dir / "model.bin").write_text("data")

        fake_config = object()
        fake_mgr = _FakeServiceManager()

        mock_venv_dir = bigfoot.mock("spellbook.tts.venv:get_tts_venv_dir")
        mock_venv_dir.returns(tts_venv_dir)

        mock_data_dir = bigfoot.mock("spellbook.tts.venv:get_tts_data_dir")
        mock_data_dir.returns(tts_data_dir)

        mock_tts_cfg = bigfoot.mock("installer.compat:tts_service_config")
        mock_tts_cfg.returns(fake_config)

        mock_svc_cls = bigfoot.mock("installer.compat:ServiceManager")
        mock_svc_cls.returns(fake_mgr)

        mock_rmtree = bigfoot.mock("installer.core:shutil.rmtree")
        mock_rmtree.returns(None)

        mock_config_set = bigfoot.mock("spellbook.core.config:config_set")
        mock_config_set.returns({})
        mock_config_set.returns({})
        mock_config_set.returns({})

        with bigfoot:
            uninstaller = Uninstaller(spellbook_dir)
            result = uninstaller._uninstall_tts_service(dry_run=False)

        assert result is not None
        assert result.success is True
        assert result.message == "TTS service: uninstalled"

        # rmtree called only for venv, NOT for data dir
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_data_dir.assert_call(args=(), kwargs={})
        mock_tts_cfg.assert_call(args=(), kwargs={"tts_venv_dir": tts_venv_dir})
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})
        mock_rmtree.assert_call(args=(str(tts_venv_dir),), kwargs={})
        mock_config_set.assert_call(args=("tts_enabled", False), kwargs={})
        mock_config_set.assert_call(args=("tts_deps_installed", False), kwargs={})
        mock_config_set.assert_call(args=("tts_service_installed", False), kwargs={})
        # Data dir still exists on disk (rmtree was NOT called on it)
        assert tts_data_dir.exists()
        assert (tts_data_dir / "model.bin").read_text() == "data"


class _IsInstance:
    """Matcher that compares equal to any instance of the given type."""

    def __init__(self, cls):
        self._cls = cls

    def __eq__(self, other):
        return isinstance(other, self._cls)

    def __repr__(self):
        return f"_IsInstance({self._cls.__name__})"


class TestUninstallTtsCalledFromRun:
    """Uninstaller.run() calls _uninstall_tts_service."""

    def test_run_includes_tts_cleanup_result(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")

        # Mock the platform detection to return empty (no platforms to uninstall)
        mock_detect = bigfoot.mock(
            "installer.core:Uninstaller.detect_installed_platforms"
        )
        mock_detect.returns([])

        # Mock resolve_config_dirs (called before mcp/tts)
        mock_resolve = bigfoot.mock("installer.core:resolve_config_dirs")
        mock_resolve.returns([])

        # Mock MCP uninstall to return None (not installed)
        mock_mcp = bigfoot.mock(
            "installer.core:Uninstaller._uninstall_mcp_service"
        )
        mock_mcp.returns(None)

        # Mock TTS uninstall to return a result
        from installer.core import InstallResult

        tts_result = InstallResult(
            component="tts_service",
            platform="system",
            success=True,
            action="removed",
            message="TTS service: uninstalled",
        )
        mock_tts = bigfoot.mock(
            "installer.core:Uninstaller._uninstall_tts_service"
        )
        mock_tts.returns(tts_result)

        with bigfoot:
            uninstaller = Uninstaller(spellbook_dir)
            session = uninstaller.run()

        # TTS result should be in session results
        tts_results = [r for r in session.results if r.component == "tts_service"]
        assert len(tts_results) == 1
        assert tts_results[0] == tts_result

        # Timeline assertions (instance methods receive self as first arg)
        _uninstaller = _IsInstance(Uninstaller)
        mock_detect.assert_call(args=(_uninstaller,), kwargs={})
        mock_resolve.assert_call(
            args=("claude_code",),
            kwargs={"cli_dirs": None},
        )
        mock_mcp.assert_call(args=(_uninstaller, False), kwargs={})
        mock_tts.assert_call(args=(_uninstaller, False), kwargs={})


class TestUninstallTtsServiceUninstallFails:
    """Service uninstall fails -- result reflects failure."""

    def test_returns_failure_when_uninstall_fails(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")

        tts_venv_dir = tmp_path / "tts-venv"
        tts_venv_dir.mkdir()

        fake_config = object()
        fake_mgr = _FakeServiceManager()
        fake_mgr._uninstall_result = (False, "permission denied")

        mock_venv_dir = bigfoot.mock("spellbook.tts.venv:get_tts_venv_dir")
        mock_venv_dir.returns(tts_venv_dir)

        mock_data_dir = bigfoot.mock("spellbook.tts.venv:get_tts_data_dir")
        mock_data_dir.returns(tmp_path / "tts-data")

        mock_tts_cfg = bigfoot.mock("installer.compat:tts_service_config")
        mock_tts_cfg.returns(fake_config)

        mock_svc_cls = bigfoot.mock("installer.compat:ServiceManager")
        mock_svc_cls.returns(fake_mgr)

        mock_rmtree = bigfoot.mock("installer.core:shutil.rmtree")
        mock_rmtree.returns(None)

        mock_config_set = bigfoot.mock("spellbook.core.config:config_set")
        mock_config_set.returns({})
        mock_config_set.returns({})
        mock_config_set.returns({})

        with bigfoot:
            uninstaller = Uninstaller(spellbook_dir)
            result = uninstaller._uninstall_tts_service(dry_run=False)

        # Even if uninstall fails, we still clean up venv and config
        assert result is not None
        assert result.success is False
        assert result.action == "failed"
        assert result.message == "TTS service: permission denied"

        # Timeline assertions
        mock_venv_dir.assert_call(args=(), kwargs={})
        mock_data_dir.assert_call(args=(), kwargs={})
        mock_tts_cfg.assert_call(args=(), kwargs={"tts_venv_dir": tts_venv_dir})
        mock_svc_cls.assert_call(args=(fake_config,), kwargs={})
        mock_rmtree.assert_call(args=(str(tts_venv_dir),), kwargs={})
        mock_config_set.assert_call(args=("tts_enabled", False), kwargs={})
        mock_config_set.assert_call(args=("tts_deps_installed", False), kwargs={})
        mock_config_set.assert_call(args=("tts_service_installed", False), kwargs={})
